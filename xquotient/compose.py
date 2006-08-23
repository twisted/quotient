# -*- test-case-name: xquotient.test.test_compose -*- 
import datetime

from zope.interface import implements

from twisted.python.components import registerAdapter
from twisted.python import log
from twisted.mail import smtp, relaymanager
from twisted.names import client
from twisted.internet import error, defer

from nevow import inevow, rend, json
from nevow.athena import expose

from epsilon import extime

from axiom import iaxiom, attributes, item, scheduler, userbase
from axiom.upgrade import registerUpgrader, registerAttributeCopyingUpgrader

from xmantissa.fragmentutils import dictFillSlots
from xmantissa import webnav, ixmantissa, people, liveform, prefs
from xmantissa.scrolltable import ScrollingFragment
from xmantissa.webtheme import getLoader

from xquotient import iquotient, equotient, renderers, mimeutil
from xquotient.exmess import Message
from xquotient.mimestorage import Header, Part



def _esmtpSendmail(username, password, smtphost, port, from_addr, to_addrs, 
                   msg, reactor=None):
    """
    This should be the only function in this module that uses the reactor.
    """
    d = defer.Deferred()
    f = smtp.ESMTPSenderFactory(username, password, from_addr, to_addrs, msg,
                                d, requireTransportSecurity=False)
    if reactor is None:
        from twisted.internet import reactor
    reactor.connectTCP(smtphost, port, f)
    return d



class _TransientError(Exception):
    pass



class _NeedsDelivery(item.Item):
    composer = attributes.reference()
    message = attributes.reference()
    toAddress = attributes.text()
    tries = attributes.integer(default=0)

    running = attributes.inmemory()

    # Retry for about five days, backing off to trying once every 6 hours gradually.
    RETRANS_TIMES = ([60] * 5 +          #     5 minutes
                     [60 * 5] * 5 +      #    25 minutes
                     [60 * 30] * 3 +     #    90 minutes
                     [60 * 60 * 2] * 2 + #   240 minutes
                     [60 * 60 * 6] * 19) # + 114 hours   = 5 days


    def activate(self):
        self.running = False


    def getMailExchange(self, recipientDomain):
        resolver = client.Resolver(resolv='/etc/resolv.conf')
        mxc = relaymanager.MXCalculator(resolver)
        d = mxc.getMX(recipientDomain)

        def gotMX(mx):
            resolver.protocol.transport.stopListening()
            return mx
        d.addCallback(gotMX)
        return d

    def sendmail(self):
        """
        Send this queued message.

        @param fromAddress: An optional address to use in the SMTP
            conversation.
        """
        # XXX
        # Why aren't these self.compose.foo?  They probably should be.
        prefCollection = self.store.findUnique(ComposePreferenceCollection)
        if prefCollection.preferredSmarthost is not None:
            fromAddress = prefCollection.smarthostAddress
            if fromAddress is None:
                fromAddress = self.composer.fromAddress
            return _esmtpSendmail(
                prefCollection.smarthostUsername,
                prefCollection.smarthostPassword,
                prefCollection.preferredSmarthost,
                prefCollection.smarthostPort,
                fromAddress,
                [self.toAddress],
                self.message.impl.source.open())
        else:
            d = self.getMailExchange(mimeutil.EmailAddress(
                    self.toAddress, mimeEncoded=False).domain)
            def sendMail(mx):
                host = str(mx.name)
                log.msg(interface=iaxiom.IStatEvent, stat_messagesSent=1,
                        userstore=self.store)
                return smtp.sendmail(
                    host,
                    self.composer.fromAddress,
                    [self.toAddress],
                    # XXX
                    self.message.impl.source.open())
            d.addCallback(sendMail)
            return d


    def run(self):
        """
        Try to reliably deliver this message. If errors are
        encountered, try harder.
        """
        sch = iaxiom.IScheduler(self.store)
        if self.tries < len(self.RETRANS_TIMES):
            # Set things up to try again, if this attempt fails
            nextTry = datetime.timedelta(seconds=self.RETRANS_TIMES[self.tries])
            sch.schedule(self, extime.Time() + nextTry)

        if not self.running:
            self.running = True
            self.tries += 1

            d = self.sendmail()

            def mailSent(result):
                # Success!  Don't bother to try again.
                sch.unscheduleAll(self)
                self.composer.messageSent(self.toAddress, self.message)
                self.deleteFromStore()
            d.addCallback(mailSent)

            def failureSending(err):
                t = err.trap(smtp.SMTPDeliveryError, error.DNSLookupError)
                if t is smtp.SMTPDeliveryError:
                    code = err.value.code
                    log = err.value.log
                    if 500 <= code < 600 or self.tries >= len(self.RETRANS_TIMES):
                        # Fatal
                        self.composer.messageBounced(log, self.toAddress, self.message)
                        # Don't bother to try again.
                        sch.unscheduleAll(self)
                elif t is error.DNSLookupError:
                    # Lalala
                    pass
                else:
                    assert False, "Cannot arrive at this branch."
            d.addErrback(failureSending)

            d.addErrback(log.err)



class Composer(item.Item, item.InstallableMixin):
    implements(ixmantissa.INavigableElement, iquotient.IMessageSender)

    typeName = 'quotient_composer'
    schemaVersion = 2

    installedOn = attributes.reference()

    fromAddress = attributes.inmemory()

    def activate(self):
        for (localpart, domain) in userbase.getAccountNames(self.store):
            self.fromAddress = localpart + '@' + domain
            return

    def installOn(self, other):
        super(Composer, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)
        other.powerUp(self, iquotient.IMessageSender)


    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Compose', self.storeID, 0.1)],
                authoritative=False)]


    def sendMessage(self, toAddresses, msg):
        """
        Send a message from this composer. 

        @param toAddresses: List of email addresses (Which can be
            coerced to L{smtp.Address}es).
        @param msg: The L{exmess.Message} to send.
        """
        msg.outgoing = True
        for toAddress in toAddresses:
            _NeedsDelivery(
                store=self.store,
                composer=self,
                message=msg,
                toAddress=toAddress).run()


    def messageBounced(self, log, toAddress, msg):
        from email import Parser as P, Generator as G, MIMEMultipart as MMP, MIMEText as MT, MIMEMessage as MM
        import StringIO as S

        bounceText = (
            'Your message to %(recipient)s, subject "%(subject)s", '
            'could not be delivered.')
        bounceText %= {
            'recipient': toAddress,
            'subject': msg.impl.getHeader(u'subject')}

        s = S.StringIO()
        original = P.Parser().parse(msg.impl.source.open())

        m = MMP.MIMEMultipart(
            'mixed',
            None,
            [MT.MIMEText(bounceText, 'plain'),
             MT.MIMEText(log, 'plain'),
             MM.MIMEMessage(original)])

        m['Subject'] = 'Unable to deliver message to ' + toAddress
        m['From'] = '<>'
        m['To'] = ''

        G.Generator(s).flatten(m)
        s.seek(0)

        def createMessage():
            # this doesn't seem to get called (yet?)
            mr = iquotient.IMIMEDelivery(
                    self.store).createMIMEReceiver(
                                'sent://' + self.fromAddress)
            for L in s:
                mr.lineReceived(L.rstrip('\n'))
            mr.messageDone()
        self.store.transact(createMessage)


    def messageSent(self, toAddress, msg):
        print 'Z' * 50
        print 'DELIVERY PROBABLY!!!!!!!!!!!!!!!!!!'
        print 'Z' * 50



def upgradeCompose1to2(oldComposer):
    """
    Version 2 of the Composer powers up IMessageSender, which version 1 did
    not.  Correct that here.
    """
    newComposer = oldComposer.upgradeVersion(
        'quotient_composer', 1, 2,
        installedOn=oldComposer.installedOn)
    newComposer.installedOn.powerUp(
        newComposer, iquotient.IMessageSender)
    return newComposer

registerUpgrader(upgradeCompose1to2, 'quotient_composer', 1, 2)
class File(item.Item):
    typeName = 'quotient_file'
    schemaVersion = 1

    type = attributes.text(allowNone=False)
    body = attributes.path(allowNone=False)
    name = attributes.text(allowNone=False)

    message = attributes.reference()
    cabinet = attributes.reference(allowNone=False)

class FileCabinet(item.Item):
    typeName = 'quotient_file_cabinet'
    schemaVersion = 1

    name = attributes.text()
    filesCount = attributes.integer(default=0)

    def createFileItem(self, name, type, data):
        """
        @param name: file name
        @param type: content-type
        @param data: file contents

        @return: C{File} item
        """
        outf = self.store.newFile('cabinet-'+str(self.storeID),
                                  str(self.filesCount))
        outf.write(data)
        outf.close()

        f = File(store=self.store,
                 body=outf.finalpath,
                 name=name,
                 type=type,
                 cabinet=self)

        self.filesCount += 1
        return f

class FileCabinetPage(rend.Page):
    lastFile = None

    def __init__(self, original):
        rend.Page.__init__(self, original, docFactory=getLoader('file-upload'))

    def renderHTTP(self, ctx):
        req = inevow.IRequest(ctx)
        if req.method == 'POST':
            uploadedFileArg = req.fields['uploaddata']
            def txn():
                self.lastFile = self.original.createFileItem(
                                        name=unicode(uploadedFileArg.filename),
                                        type=unicode(uploadedFileArg.type),
                                        data=uploadedFileArg.file.read())
            self.original.store.transact(txn)

        return rend.Page.renderHTTP(self, ctx)

    def render_lastFileData(self, ctx, data):
        if self.lastFile is None:
            return ''
        return json.serialize({u'id': self.lastFile.storeID,
                               u'name': self.lastFile.name})

registerAdapter(FileCabinetPage, FileCabinet, inevow.IResource)

class ComposeFragment(liveform.LiveFormFragment, renderers.ButtonRenderingMixin):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'compose'
    live = 'athena'
    jsClass = 'Quotient.Compose.Controller'
    title = ''

    _savedDraft = None

    def __init__(self, original, toAddress='', subject='', messageBody='',
                 attachments=(), inline=False):
        self.original = original
        super(ComposeFragment, self).__init__(
            callable=self._sendOrSave,
            parameters=[liveform.Parameter(name='toAddress',
                                           type=liveform.TEXT_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='subject',
                                           type=liveform.TEXT_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='messageBody',
                                           type=liveform.TEXTAREA_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='cc',
                                           type=liveform.TEXT_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='bcc',
                                           type=liveform.TEXT_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='draft',
                                           type=liveform.CHECKBOX_INPUT,
                                           coercer=bool)])
        self.toAddress = toAddress
        self.subject = subject
        self.messageBody = messageBody
        self.attachments = attachments
        self.fileAttachments = []
        self.inline = inline

        self.docFactory = None
        self.translator = ixmantissa.IWebTranslator(original.store)
        self.cabinet = self.original.store.findOrCreate(FileCabinet)

    def invoke(self, formPostEmulator):
        coerced = self._coerced(formPostEmulator)
        # we want to allow the javascript to submit an
        # list of filenames of arbitrary length with the form
        coerced['files'] = formPostEmulator.get('files', ())
        self.callable(**coerced)
    expose(invoke)


    def getPeople(self):
        """
        @return: a sequence of pairs (name, email) for each Person in the store of
                 my L{Composer}, where name is the person's display name, and email
                 is their email address.  omits people without a display name or
                 email address
        """
        peeps = []
        for person in self.original.store.query(people.Person):
            email = person.getEmailAddress()
            if email is None:
                email = u''
            name = person.getDisplayName()
            if name or email:
                peeps.append((name, email))
        return peeps
    expose(getPeople)


    def getInitialArguments(self):
        return (self.inline, self.getPeople())

    def render_inboxLink(self, ctx, data):
        from xquotient.inbox import Inbox
        return self.translator.linkTo(self.original.store.findUnique(Inbox).storeID)

    def render_compose(self, ctx, data):
        req = inevow.IRequest(ctx)
        draftWebID = req.args.get('draft', [None])[0]

        attachmentPattern = inevow.IQ(self.docFactory).patternGenerator('attachment')
        attachments = []

        if draftWebID is not None:
            draft = self.translator.fromWebID(draftWebID)
            # i think this will suffice until we have a rich text compose
            (alt,) = list(draft.message.impl.getTypedParts('multipart/alternative'))
            (txt,) = list(alt.getTypedParts('text/plain'))
            try:
                cc = draft.message.impl.getHeader(u'cc')
            except equotient.NoSuchHeader:
                cc = ''

            for f in draft.store.query(File, File.message == draft.message):
                attachments.append(attachmentPattern.fillSlots(
                                    'id', f.storeID).fillSlots(
                                    'name', f.name))

            slotData = dict(to=draft.message.recipient,
                            subject=draft.message.subject,
                            body=txt.getBody(decode=True),
                            cc=cc,
                            attachments=attachments)

            # make subsequent edits overwrite the draft we're editing
            self._savedDraft = draft
        else:
            for a in self.attachments:
                attachments.append(attachmentPattern.fillSlots(
                                    'id', a.part.storeID).fillSlots(
                                    'name', a.filename or 'No Name'))

            slotData = dict(to=self.toAddress,
                            subject=self.subject,
                            body=self.messageBody,
                            cc='',
                            attachments=attachments)

        return dictFillSlots(ctx.tag, slotData)

    def render_fileCabinet(self, ctx, data):
        return inevow.IQ(self.docFactory).onePattern('cabinet-iframe').fillSlots(
                    'src', ixmantissa.IWebTranslator(self.cabinet.store).linkTo(self.cabinet.storeID))

    def head(self):
        return None

    def createMessage(self, toAddress, subject, messageBody, cc, bcc, files):
        from email import (Generator as G, MIMEBase as MB,
                           MIMEMultipart as MMP, MIMEText as MT,
                           Header as MH, Charset as MC, Utils as EU)
        import StringIO as S

        MC.add_charset('utf-8', None, MC.QP, 'utf-8')

        encode = lambda s: MH.Header(s).encode()

        s = S.StringIO()
        m = MMP.MIMEMultipart(
            'alternative',
            None,
            [MT.MIMEText(messageBody, 'plain', 'utf-8'),
             MT.MIMEText(renderers.textToRudimentaryHTML(messageBody), 'html', 'utf-8')])

        fileItems = []
        if files:
            attachmentParts = []
            for storeID in files:
                a = self.original.store.getItemByID(long(storeID))
                if isinstance(a, Part):
                    a = self.cabinet.createFileItem(
                            a.getParam('filename',
                                       default=u'',
                                       header=u'content-disposition'),
                            unicode(a.getContentType()),
                            a.getBody(decode=True))
                fileItems.append(a)
                part = MB.MIMEBase(*a.type.split('/'))
                part.set_payload(a.body.getContent())
                part.add_header('content-disposition', 'attachment', filename=a.name)
                attachmentParts.append(part)

            m = MMP.MIMEMultipart('mixed', None, [m] + attachmentParts)

        # XXX XXX XXX
        prefCollection = self.original.store.findUnique(
            ComposePreferenceCollection)
        if prefCollection.preferredSmarthost is not None:
            fromAddress = prefCollection.smarthostAddress
        else:
            if self.original.fromAddress.endswith('.divmod.com'):
                (localpart, domain) = self.original.fromAddress.split('@')
                fromAddress = localpart + '@divmod.com'
            else:
                fromAddress = self.original.fromAddress

        m['From'] = encode(fromAddress)
        m['To'] = encode(toAddress)
        m['Subject'] = encode(subject)
        m['Date'] = EU.formatdate()
        m['Message-ID'] = smtp.messageid('divmod.xquotient')

        if cc:
            m['Cc'] = encode(cc)

        G.Generator(s).flatten(m)
        s.seek(0)

        def createMessageAndQueueIt():
            mr = iquotient.IMIMEDelivery(
                        self.original.store).createMIMEReceiver(
                                'sent://' + self.original.fromAddress)
            for L in s:
                mr.lineReceived(L.rstrip('\n'))
            mr.messageDone()
            return mr.message

        msg = self.original.store.transact(createMessageAndQueueIt)
        # there is probably a better way than this, but there
        # isn't a way to associate the same file item with multiple
        # messages anyway, so there isn't a need to reflect that here
        for fileItem in fileItems:
            fileItem.message = msg
        return msg

    _mxCalc = None
    def _sendMail(self, toAddress, subject, messageBody, cc, bcc, files):
        # overwrite the previous draft of this message with another draft
        self._saveDraft(toAddress, subject, messageBody, cc, bcc, files)

        addresses = [toAddress]
        if cc:
            addresses.append(cc)

        # except we are going to send this draft
        self.original.sendMessage(addresses, self._savedDraft.message)
        # and then make it not a draft anymore
        self._savedDraft.message.draft = False

        # once the user has sent a message, we'll consider all subsequent
        # drafts in the lifetime of this fragment as being drafts of a
        # different message
        self._savedDraft.deleteFromStore()
        self._savedDraft = None

    def _saveDraft(self, toAddress, subject, messageBody, cc, bcc, files):
        msg = self.createMessage(toAddress, subject, messageBody, cc, bcc, files)
        msg.draft = True

        if self._savedDraft is not None:
            oldmsg = self._savedDraft.message
            for p in oldmsg.store.query(Part, Part.message == oldmsg):
                p.deleteFromStore()
            for h in oldmsg.store.query(Header, Header.message == oldmsg):
                h.deleteFromStore()
            oldmsg.deleteFromStore()
            self._savedDraft.message = msg
        else:
            self._savedDraft = Draft(store=self.original.store, message=msg)


    def _sendOrSave(self, toAddress, subject, messageBody, cc, bcc, files, draft):
        if draft:
            f = self._saveDraft
        else:
            f = self._sendMail
        return f(toAddress, subject, messageBody, cc, bcc, files)


registerAdapter(ComposeFragment, Composer, ixmantissa.INavigableFragment)



class ComposeBenefactor(item.Item, item.InstallableMixin):
    endowed = attributes.integer(default=0)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(scheduler.SubScheduler).installOn(avatar)
        from xquotient.mail import MailDeliveryAgent
        avatar.findOrCreate(MailDeliveryAgent).installOn(avatar)
        avatar.findOrCreate(ComposePreferenceCollection).installOn(avatar)
        avatar.findOrCreate(Composer).installOn(avatar)
        avatar.findOrCreate(Drafts).installOn(avatar)


    def revoke(self, ticket, avatar):
        avatar.findUnique(Composer).deleteFromStore()
        avatar.findUnique(Drafts).deleteFromStore()



class _SmarthostPreference(prefs.Preference):
    def __init__(self, value, collection):
        prefs.Preference.__init__(
            self,
            'smarthost-host', value,
            'Smart Host', collection,
            'Hostname of an SMTP server to which all outgoing mail will be sent.')


    def choices(self):
        return None


    def displayToValue(self, display):
        if display:
            return display
        return None


    def valueToDisplay(self, value):
        if value:
            return value
        return ''


    def settable(self):
        return True



class _SmarthostUsernamePreference(prefs.Preference):
    def __init__(self, value, collection):
        prefs.Preference.__init__(
            self,
            'smarthost-username', value,
            'Smarthost Username', collection,
            'Username to use to log in to the smarthost.')


    def choices(self):
        return None


    def displayToValue(self, display):
        if display:
            return display
        return None


    def valueToDisplay(self, value):
        if value:
            return value
        return ''


    def settable(self):
        return True



class _SmarthostPasswordPreference(prefs.Preference):
    def __init__(self, value, collection):
        prefs.Preference.__init__(
            self,
            'smarthost-password', value,
            'Smarthost password', collection,
            'Password to use to log in to the smarthost.')


    def choices(self):
        return None


    def displayToValue(self, display):
        if display:
            return display
        return None


    def valueToDisplay(self, value):
        if value:
            return value
        return ''


    def settable(self):
        return True



class _SmarthostPortPreference(prefs.Preference):
    """
    Represent the port number preference in the preferences page.

    This class is full of meaningless boilerplate.
    """

    def __init__(self, value, collection):
        """
        Initialize this preference object with a default value and the
        preference collection.
        """
        prefs.Preference.__init__(
            self,
            'smarthost-port', value,
            'Smarthost port', collection,
            'Port number to connect to the smarthost for SMTP sending.')


    def choices(self):
        """
        Meaningless boilerplate.
        """
        return None


    def displayToValue(self, display):
        """
        Meaningless boilerplate.
        """
        if display:
            return display
        return None


    def valueToDisplay(self, value):
        """
        The default value is 25.
        """
        if value:
            return value
        return 25


    def settable(self):
        """
        Meaningless boilerplate.
        """
        return True



class _SmarthostAddressPreference(prefs.Preference):
    """
    Represent the from address preference in the preferences page.

    This class is full of meaningless boilerplate.
    """

    def __init__(self, value, collection):
        """
        Initialize this preference object with a default value and the
        preference collection.
        """
        prefs.Preference.__init__(
            self,
            'smarthost-address', value,
            'Smarthost address', collection,
            'The email address to send email as.')


    def choices(self):
        """
        Meaningless boilerplate.
        """
        return None


    def displayToValue(self, display):
        """
        Meaningless boilerplate.
        """
        if display:
            return display
        return None


    def valueToDisplay(self, value):
        """
        Meaningless boilerplate.
        """
        if value:
            return value
        return ''


    def settable(self):
        """
        Meaningless boilerplate.
        """
        return True






class ComposePreferenceCollection(item.Item, item.InstallableMixin):

    implements(ixmantissa.IPreferenceCollection)

    schemaVersion = 2

    installedOn = attributes.reference()

    preferredSmarthost = attributes.text(doc="""
    Hostname to which all outgoing mail will be delivered.
    """)
    smarthostUsername = attributes.text(doc="""
    Username with which to authenticate to the smart host.
    """)
    smarthostPassword = attributes.text(doc="""
    Password with which to authenticate to the smart host.
    """)
    smarthostPort = attributes.integer(doc="""
    The port number which outbound messages will be delivered to.
    """, default=25)
    smarthostAddress = attributes.text(doc="""
    The address which messages will be sent from.
    """)

    _cachedPrefs = attributes.inmemory()

    applicationName = 'Compose'

    def installOn(self, other):
        super(ComposePreferenceCollection, self).installOn(other)
        other.powerUp(self, ixmantissa.IPreferenceCollection)


    def getPreferences(self):
        try:
            return self._cachedPrefs
        except AttributeError:
            self._cachedPrefs = {
                'smarthost-address': _SmarthostAddressPreference(self.smarthostAddress, self),
                'smarthost-host': _SmarthostPreference(self.preferredSmarthost, self),
                'smarthost-port': _SmarthostPortPreference(self.smarthostPort, self),
                'smarthost-username': _SmarthostUsernamePreference(self.smarthostUsername, self),
                'smarthost-password': _SmarthostPasswordPreference(self.smarthostPassword, self)
                }
            return self._cachedPrefs


    def setPreferenceValue(self, pref, value):
        if pref.key == 'smarthost-host':
            self.preferredSmarthost = value
        elif pref.key == 'smarthost-username':
            self.smarthostUsername = value
        elif pref.key == 'smarthost-password':
            self.smarthostPassword = value
        elif pref.key == 'smarthost-port':
            # Does the coercion belong *here*? -radix
            self.smarthostPort = int(value) 
        elif pref.key == 'smarthost-address':
            self.smarthostAddress = value
        else:
            assert False, "Bogus preference input: %r %r" % (pref, value)
        setattr(pref, 'value', value)


    def getSections(self):
        return None


registerAttributeCopyingUpgrader(ComposePreferenceCollection, 1, 2)



class Draft(item.Item):
    """
    i only exist so my storeID can be exposed, instead of exposing
    the storeID of the underlying Message (which gets overwritten
    with each draft save).  this stops draft-editing URLs from being
    invalidated every 30 seconds
    """

    typeName = 'quotient_draft'
    schemaVersion = 1

    message = attributes.reference(allowNone=False)

class Drafts(item.Item, item.InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_drafts'
    schemaVersion = 1

    installedOn = attributes.reference()

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Drafts', self.storeID, 0.0)],
                authoritative=False)]

    def installOn(self, other):
        super(Drafts, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

class DraftsScreen(ScrollingFragment):
    jsClass = 'Quotient.Compose.DraftListScrollingWidget'

    def __init__(self, original):
        ScrollingFragment.__init__(
            self,
            original.store,
            Message,
            Message.draft == True,
            (Message.recipient, Message.subject, Message.sentWhen),
            defaultSortColumn=Message.sentWhen,
            defaultSortAscending=False)

        self.composerURL = self.wt.linkTo(self.wt.store.findUnique(Composer).storeID)
        self.docFactory = getLoader(self.fragmentName)

    def constructRows(self, items):
        rows = ScrollingFragment.constructRows(self, items)
        for (item, row) in zip(items, rows):
            draft = self.wt.store.findUnique(Draft, Draft.message==item)
            row['__id__'] = self.composerURL + u'?draft=' + self.wt.toWebID(draft)
        return rows

    def head(self):
        return None

registerAdapter(DraftsScreen, Drafts, ixmantissa.INavigableFragment)
