# -*- test-case-name: xquotient.test.test_compose -*-
import datetime

from email import (Parser as P, Generator as G, MIMEMultipart as MMP,
                   MIMEText as MT, MIMEMessage as MM, MIMEBase as MB,
                   Header as MH, Charset as MC, Utils as EU, Encoders as EE)

import StringIO as S

from zope.interface import implements

from twisted.python.components import registerAdapter
from twisted.python import log
from twisted.mail import smtp, relaymanager
from twisted.names import client
from twisted.internet import error, defer

from nevow import inevow, rend, json
from nevow.athena import expose, LiveElement
from nevow.page import renderer

from epsilon import extime, descriptor

from axiom import iaxiom, attributes, item, scheduler, userbase
from axiom.upgrade import registerUpgrader, registerAttributeCopyingUpgrader

from xmantissa.fragmentutils import dictFillSlots
from xmantissa import webnav, ixmantissa, people, liveform, prefs
from xmantissa.scrolltable import ScrollingFragment
from xmantissa.webtheme import getLoader

from xquotient import iquotient, equotient, renderers, mimeutil
from xquotient.exmess import Message, MessageDetail
from xquotient.mimestorage import Part



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


def _getFromAddressFromStore(store):
    """
    Find a suitable outgoing email address by looking at the
    L{userbase.LoginMethod} items in C{store}.  Throws L{RuntimeError} if it
    can't find anything
    """
    for meth in userbase.getLoginMethods(store, protocol=u'email'):
        if meth.internal or meth.verified:
            return meth.localpart + '@' + meth.domain
    raise RuntimeError("cannot find a suitable LoginMethod")

class _TransientError(Exception):
    pass


class FromAddress(item.Item):
    """
    I hold information about an email addresses that a user can send mail from
    """
    schemaVersion = 2

    _address = attributes.text(doc="""
                The email address.  Don't set this directly; use
                C{self.address}.
                """)

    class address(descriptor.attribute):
        def get(self):
            """
            Substitute the result of C{_getFromAddressFromStore} on our store if
            C{self._address} is None, so we can avoid storing the system address
            in the database, as it will change if this store is migrated
            """
            if self._address is None:
                return _getFromAddressFromStore(self.store)
            return self._address

        def set(self, value):
            self._address = value

    _default = attributes.boolean(default=False, doc="""
                Is this the default from address?  Don't mutate this value
                directly, use L{setAsDefault}
                """)

    # if any of these are set, they should all be set
    smtpHost = attributes.text()
    smtpPort = attributes.integer(default=25)
    smtpUsername = attributes.text()
    smtpPassword = attributes.text()

    def setAsDefault(self):
        """
        Make this the default from address, revoking the defaultness of the
        previous default.
        """
        default = self.store.findUnique(
                    FromAddress, FromAddress._default == True,
                    default=None)
        if default is not None:
            default._default = False
        self._default = True

    def findDefault(cls, store):
        """
        Find the L{FromAddress} item which is the current default address
        """
        return store.findUnique(cls, cls._default == True)
    findDefault = classmethod(findDefault)

    def findSystemAddress(cls, store):
        """
        Find the L{FromAddress} item which represents the "system address" -
        i.e. the L{FromAddress} item we created out of the user's login
        credentials
        """
        return cls.findByAddress(store, None)
    findSystemAddress = classmethod(findSystemAddress)

    def findByAddress(cls, store, address):
        """
        Find the L{FromAddress} item with address C{address}
        """
        return store.findUnique(cls, cls._address == address)
    findByAddress = classmethod(findByAddress)



def fromAddress1to2(old):
    new = old.upgradeVersion(old.typeName, 1, 2,
                             _address=old.address,
                             _default=old._default,
                             smtpHost=old.smtpHost,
                             smtpPort=old.smtpPort,
                             smtpUsername=old.smtpUsername,
                             smtpPassword=old.smtpPassword)

    if new._address == _getFromAddressFromStore(new.store):
        new._address = None
    return new



registerUpgrader(fromAddress1to2, FromAddress.typeName, 1, 2)



class _NeedsDelivery(item.Item):
    schemaVersion = 2

    composer = attributes.reference()
    message = attributes.reference()
    fromAddress = attributes.reference()
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
        fromAddress = self.fromAddress
        if fromAddress is None:
            fromAddress = FromAddress.findDefault(self.store)

        if fromAddress.smtpHost:
            return _esmtpSendmail(
                fromAddress.smtpUsername,
                fromAddress.smtpPassword,
                fromAddress.smtpHost,
                fromAddress.smtpPort,
                fromAddress.address,
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
                    fromAddress.address,
                    [self.toAddress],
                    # XXX
                    self.message.impl.source.open())
            d.addCallback(sendMail)
            return d


    def run(self):
        """
        Try to reliably deliver this message. If errors are encountered, try
        harder.
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


registerAttributeCopyingUpgrader(_NeedsDelivery, 1, 2)


class Composer(item.Item, item.InstallableMixin):
    implements(ixmantissa.INavigableElement, iquotient.IMessageSender)

    typeName = 'quotient_composer'
    schemaVersion = 3

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Composer, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)
        other.powerUp(self, iquotient.IMessageSender)


    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Compose', self.storeID, 0.1)],
                authoritative=False)]


    def sendMessage(self, fromAddress, toAddresses, msg):
        """
        Send a message from this composer.

        @param toAddresses: List of email addresses (Which can be
            coerced to L{smtp.Address}es).
        @param msg: The L{exmess.Message} to send.
        """
        msg.startedSending()
        for toAddress in toAddresses:
            _NeedsDelivery(
                store=self.store,
                composer=self,
                message=msg,
                fromAddress=fromAddress,
                toAddress=toAddress).run()


    def messageBounced(self, log, toAddress, msg):
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

        self.createMessageAndQueueIt(FromAddress.findDefault(self.store).address, s, False)


    def messageSent(self, toAddress, msg):
        print 'Z' * 50
        print 'DELIVERY PROBABLY!!!!!!!!!!!!!!!!!!'
        print 'Z' * 50


    def createMessageAndQueueIt(self, fromAddress, s, draft):
        """
        Create a message out of C{s}, from C{fromAddress}

        @param fromAddress: address from which to send the email
        @type fromAddress: C{unicode}
        @param s: message to send
        @type s: line iterable
        @type draft: C{bool}
        @param draft: Flag indicating whether this is a draft message or not
        (eg, a bounce message).

        @rtype: L{xquotient.exmess.Message}
        """
        def deliverMIMEMessage():
            # this doesn't seem to get called (yet?)
            md = iquotient.IMIMEDelivery(self.store)
            if draft:
                mr = md._createMIMEDraftReceiver('sent://' + fromAddress)
            else:
                mr = md.createMIMEReceiver('sent://' + fromAddress)
            for L in s:
                mr.lineReceived(L.rstrip('\n'))
            mr.messageDone()
            return mr.message
        return self.store.transact(deliverMIMEMessage)


    def createRedirectedMessage(self, fromAddress, toAddresses, message):
        """
        Create a L{Message} item based on C{message}, with the C{Resent-From}
        and C{Resent-To} headers set

        @type fromAddress: L{FromAddress}

        @type toAddresses: sequence of L{mimeutil.EmailAddress}

        @type message: L{Message}

        @rtype: L{Message}
        """
        m = P.Parser().parse(message.impl.source.open())
        m['Resent-From'] = MH.Header(fromAddress.address).encode()
        m['Resent-To']  = MH.Header(mimeutil.flattenEmailAddresses(toAddresses)).encode()

        s = S.StringIO()
        G.Generator(s).flatten(m)
        s.seek(0)

        return self.createMessageAndQueueIt(fromAddress.address, s, True)


    def redirect(self, fromAddress, toAddresses, message):
        """
        Redirect C{message} from C{fromAddress} to C{toAddresses}.
        Parameters the same as for L{createRedirectedMessage}

        @rtype: C{None}
        """
        msg = self.createRedirectedMessage(fromAddress, toAddresses, message)
        addresses = [addr.email for addr in toAddresses]
        self.sendMessage(fromAddress, addresses, msg)


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

item.declareLegacyItem(Composer.typeName, 2,
                       dict(installedOn=attributes.reference()))

def composer2to3(old):
    """
    Remove the L{Composer.fromAddress} attribute
    """
    return old.upgradeVersion(old.typeName, 2, 3,
                              installedOn=old.installedOn)

registerUpgrader(composer2to3, Composer.typeName, 2, 3)

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

class _ComposeFragmentMixin:
    """
    Mixin which provides some stuff that might be useful to fragments which do
    composey things.

    Assumes it is mixed-in to something where C{self.composer} is a
    L{Composer}
    """

    def _coerceEmailAddressString(self, s):
        """
        Turn a string representation of one or more email addresses into a
        list of L{mimetuil.EmailAddress} instances

        @param s: non mime-encoded string
        @type s: C{str}

        @return: L{mimeutil.EmailAddress} instances
        @rtype: sequence
        """
        return mimeutil.parseEmailAddresses(s, mimeEncoded=False)

    def _getFromAddressStan(self):
        """
        Turn the L{FromAddress} items in the L{Composer}'s store into some
        stan, using the C{from-select} and C{from-select-option} patterns from
        the template
        """
        fromAddrs = []
        for fromAddress in self.composer.store.query(FromAddress):
            if fromAddress._default:
                fromAddrs.insert(0, fromAddress)
            else:
                fromAddrs.append(fromAddress)

        iq = inevow.IQ(self.docFactory)
        return iq.onePattern('from-select').fillSlots(
                        'options', [iq.onePattern(
                                    'from-select-option').fillSlots(
                                        'address', addr.address).fillSlots(
                                        'value', self.translator.toWebID(addr))
                                        for addr in fromAddrs])



    def getPeople(self):
        """
        @return: a sequence of pairs (name, email) for each Person in the
        store of my L{Composer}, where name is the person's display name, and
        email is their email address.  omits people without a display name or
        email address
        """
        peeps = []
        for person in self.composer.store.query(people.Person):
            email = person.getEmailAddress()
            if email is None:
                email = u''
            name = person.getDisplayName()
            if name or email:
                peeps.append((name, email))
        return peeps
    expose(getPeople)



class ComposeFragment(liveform.LiveFormFragment, renderers.ButtonRenderingMixin, _ComposeFragmentMixin):
    implements(ixmantissa.INavigableFragment)

    jsClass = u'Quotient.Compose.Controller'
    fragmentName = 'compose'

    _savedDraft = None

    def __init__(self, composer, toAddresses=(), subject=u'', messageBody=u'',
                 attachments=(), inline=False):
        """
        @type composer: L{Composer}

        @param toAddresses: email addresses of the recipients of this message
        @type toAddresses: sequence of L{xquotient.mimeutil.EmailAddress}
        instances

        @param subject: the subject of this message
        @type subject: C{unicode}

        @param messageBody: the body of this message
        @type messageBody: C{unicode}

        @param attachments: the attachments of this message
        @type attachments: sequence of L{xquotient.mimepart.AttachmentPart}
        instances

        @param inline: whether the compose widget is being displayed inline,
        e.g. as a child of another widget
        @type inline: boolean

        C{toAddresses}, C{subject}, C{messageBody} and C{attachments} should
        be considered as presets - their values can be manipulated via the
        user interface
        """
        self.composer = composer
        self.translator = ixmantissa.IWebTranslator(composer.store)

        super(ComposeFragment, self).__init__(
            callable=self._sendOrSave,
            parameters=[liveform.Parameter(name='fromAddress',
                                           type=liveform.TEXT_INPUT,
                                           coercer=self.translator.fromWebID),
                        liveform.Parameter(name='toAddresses',
                                           type=liveform.TEXT_INPUT,
                                           coercer=self._coerceEmailAddressString),
                        liveform.Parameter(name='subject',
                                           type=liveform.TEXT_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='messageBody',
                                           type=liveform.TEXTAREA_INPUT,
                                           coercer=unicode),
                        liveform.Parameter(name='cc',
                                           type=liveform.TEXT_INPUT,
                                           coercer=self._coerceEmailAddressString),
                        liveform.Parameter(name='bcc',
                                           type=liveform.TEXT_INPUT,
                                           coercer=self._coerceEmailAddressString),
                        liveform.Parameter(name='draft',
                                           type=liveform.CHECKBOX_INPUT,
                                           coercer=bool)])
        self.toAddresses = toAddresses
        self.subject = subject
        self.messageBody = messageBody
        self.attachments = attachments
        self.fileAttachments = []
        self.inline = inline

        self.docFactory = None
        self.cabinet = self.composer.store.findOrCreate(FileCabinet)

    def invoke(self, formPostEmulator):
        coerced = self._coerced(formPostEmulator)
        # we want to allow the javascript to submit an
        # list of filenames of arbitrary length with the form
        coerced['files'] = formPostEmulator.get('files', ())
        return self.callable(**coerced)
    expose(invoke)


    def getInitialArguments(self):
        return (self.inline, self.getPeople())

    def render_attachButton(self, ctx, data):
        return inevow.IQ(self.docFactory).onePattern('attach-button')

    def render_inboxLink(self, ctx, data):
        from xquotient.inbox import Inbox
        return self.translator.linkTo(self.composer.store.findUnique(Inbox).storeID)

    def render_compose(self, ctx, data):
        req = inevow.IRequest(ctx)
        draftWebID = req.args.get('draft', [None])[0]

        iq = inevow.IQ(self.docFactory)
        attachmentPattern = iq.patternGenerator('attachment')
        attachments = []

        bodyPattern = iq.onePattern('message-body')
        subjectPattern = iq.onePattern('subject')

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

            slotData = {'to': draft.message.recipient,
                        'from': self._getFromAddressStan(),
                        'subject': subjectPattern.fillSlots(
                                        'subject', draft.message.subject),
                        'message-body': bodyPattern.fillSlots(
                                            'body', txt.getBody(decode=True)),
                        'cc': cc,
                        'attachments': attachments}

            # make subsequent edits overwrite the draft we're editing
            self._savedDraft = draft
        else:
            for a in self.attachments:
                attachments.append(attachmentPattern.fillSlots(
                                    'id', a.part.storeID).fillSlots(
                                    'name', a.filename or 'No Name'))

            slotData = {'to': mimeutil.flattenEmailAddresses(self.toAddresses),
                        'from': self._getFromAddressStan(),
                        'subject': subjectPattern.fillSlots(
                                    'subject', self.subject),
                        'message-body': bodyPattern.fillSlots(
                                            'body', self.messageBody),
                        'cc': '',
                        'attachments': attachments}

        return dictFillSlots(ctx.tag, slotData)


    def render_fileCabinet(self, ctx, data):
        return inevow.IQ(self.docFactory).onePattern('cabinet-iframe').fillSlots(
                    'src', ixmantissa.IWebTranslator(self.cabinet.store).linkTo(self.cabinet.storeID))

    def head(self):
        return None

    def _fileItemToEmailPart(self, fileItem):
        """
        Convert a L{File} item into an appropriate MIME part object
        understandable by the stdlib's C{email} package
        """
        (majorType, minorType) = fileItem.type.split('/')
        if majorType == 'multipart':
            part = P.Parser().parse(fileItem.body.open())
        else:
            part = MB.MIMEBase(majorType, minorType)
            if majorType == 'message':
                part.set_payload([P.Parser().parse(fileItem.body.open())])
            else:
                part.set_payload(fileItem.body.getContent())
                if majorType == 'text':
                    EE.encode_quopri(part)
                else:
                    EE.encode_base64(part)
        part.add_header('content-disposition', 'attachment', filename=fileItem.name)
        return part


    def createMessage(self, fromAddress, toAddresses, subject, messageBody,
                      cc, bcc, files):
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
                a = self.composer.store.getItemByID(long(storeID))
                if isinstance(a, Part):
                    a = self.cabinet.createFileItem(
                            a.getParam('filename',
                                       default=u'',
                                       header=u'content-disposition'),
                            unicode(a.getContentType()),
                            a.getBody(decode=True))
                fileItems.append(a)
                attachmentParts.append(
                    self._fileItemToEmailPart(a))

            m = MMP.MIMEMultipart('mixed', None, [m] + attachmentParts)

        m['From'] = encode(fromAddress.address)
        m['To'] = encode(mimeutil.flattenEmailAddresses(toAddresses))
        m['Subject'] = encode(subject)
        m['Date'] = EU.formatdate()
        m['Message-ID'] = smtp.messageid('divmod.xquotient')

        if cc:
            m['Cc'] = encode(mimeutil.flattenEmailAddresses(cc))

        G.Generator(s).flatten(m)
        s.seek(0)

        msg = self.composer.createMessageAndQueueIt(fromAddress.address, s, True)
        # there is probably a better way than this, but there
        # isn't a way to associate the same file item with multiple
        # messages anyway, so there isn't a need to reflect that here
        for fileItem in fileItems:
            fileItem.message = msg
        return msg

    _mxCalc = None
    def _sendMail(self, fromAddress, toAddresses, subject, messageBody,
                  cc, bcc, files):
        # overwrite the previous draft of this message with another draft
        self._saveDraft(fromAddress, toAddresses, subject, messageBody, cc, bcc, files)

        addresses = [addr.pseudoFormat() for addr in toAddresses + cc + bcc]

        # except we are going to send this draft
        self.composer.sendMessage(fromAddress, addresses, self._savedDraft.message)

        # once the user has sent a message, we'll consider all subsequent
        # drafts in the lifetime of this fragment as being drafts of a
        # different message
        self._savedDraft.deleteFromStore()
        self._savedDraft = None

    def _saveDraft(self, fromAddress, toAddresses, subject, messageBody,
                   cc, bcc, files):
        msg = self.createMessage(fromAddress, toAddresses, subject,
                                 messageBody, cc, bcc, files)
        if self._savedDraft is not None:
            oldmsg = self._savedDraft.message
            oldmsg.deleteFromStore()
            self._savedDraft.message = msg
        else:
            self._savedDraft = Draft(store=self.composer.store, message=msg)


    def _sendOrSave(self, fromAddress, toAddresses, subject, messageBody,
                    cc, bcc, files, draft):
        """
        This method is called interactively from the browser via a liveform in
        response to clicking 'send' or 'save draft'.

        @param fromAddress: a L{FromAddress} item.

        @param toAddresses: a list of L{mimeutil.EmailAddress} objects,
        representing the people to send this to.

        @param subject: freeform string
        @type subject: L{unicode}

        @param messageBody: the message's body, a freeform string.
        @type messageBody: L{unicode}

        @param cc: a string, likely an rfc2822-formatted list of addresses
        (not validated between the client and here, XXX FIXME)
        @type cc: L{unicode}

        @param bcc: a string, likely an rfc2822-formatted list of addresses
        (not validated between the client and here, XXX FIXME)
        @type bcc: L{unicode}

        @param files: a sequence of stringified storeIDs which should point at
        L{File} items.

        @param draft: a boolean, indicating whether the message represented by
        the other arguments to this function should be saved as a draft or sent
        as an outgoing message.  True for save, False for send.
        """

        if draft:
            f = self._saveDraft
        else:
            f = self._sendMail
        return f(fromAddress, toAddresses, subject, messageBody, cc, bcc, files)


registerAdapter(ComposeFragment, Composer, ixmantissa.INavigableFragment)



class RedirectingComposeFragment(liveform.LiveFormFragment, renderers.ButtonRenderingMixin, _ComposeFragmentMixin):
    """
    A fragment which provides UI for redirecting email messages
    """
    implements(ixmantissa.INavigableFragment)

    jsClass = u'Quotient.Compose.RedirectingController'
    fragmentName = 'compose'

    def __init__(self, composer, message):
        """
        @type composer: L{Composer}

        @param message: the message being redirected
        @type message: L{Message}
        """
        self.composer = composer
        self.message = message

        self.translator = ixmantissa.IWebTranslator(composer.store)

        super(RedirectingComposeFragment, self).__init__(
            callable=self.redirect,
            parameters=(liveform.Parameter(name='fromAddress',
                                           type=liveform.TEXT_INPUT,
                                           coercer=self.translator.fromWebID),
                        liveform.Parameter(name='toAddresses',
                                           type=liveform.TEXT_INPUT,
                                           coercer=self._coerceEmailAddressString)))


    def render_attachButton(self, ctx, data):
        """
        The template contains an "attachButton" render directive.  Return the
        empty string, as we don't want an attach button for redirected
        messages
        """
        return ''


    def _getMessageBody(self):
        f = MessageDetail(self.message)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f


    def render_compose(self, ctx, data):
        """
        Only fill in the C{from} and C{message-body} slots with anything
        useful - the stuff that L{ComposeFragment} puts in the rest of slots
        will be apparent from the L{MessageDetail} fragment we put in
        C{message-body}
        """
        return dictFillSlots(ctx.tag,
                {'to': '',
                 'from': self._getFromAddressStan(),
                 'subject': '',
                 'message-body': self._getMessageBody(),
                 'cc': '',
                 'attachments': ''})


    def getInitialArguments(self):
        return (self.getPeople(),)


    def redirect(self, fromAddress, toAddresses):
        """
        Ask L{Composer} to redirect C{self.message}

        @param fromAddress: the address to send from
        @type fromAddress: L{FromAddress}

        @param toAddresses: L{mimeutil.EmailAddress} instances
        @type toAddresses: sequence
        """
        self.composer.redirect(fromAddress, toAddresses, self.message)



class ComposeBenefactor(item.Item, item.InstallableMixin):
    endowed = attributes.integer(default=0)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(scheduler.SubScheduler).installOn(avatar)
        from xquotient.mail import MailDeliveryAgent
        avatar.findOrCreate(MailDeliveryAgent).installOn(avatar)
        avatar.findOrCreate(ComposePreferenceCollection).installOn(avatar)

        defaultFrom = avatar.findOrCreate(FromAddress, _address=None)
        defaultFrom.setAsDefault()

        avatar.findOrCreate(Composer).installOn(avatar)
        avatar.findOrCreate(Drafts).installOn(avatar)


    def revoke(self, ticket, avatar):
        avatar.findUnique(Composer).deleteFromStore()
        avatar.findUnique(Drafts).deleteFromStore()


class ComposePreferenceCollection(item.Item, item.InstallableMixin, prefs.PreferenceCollectionMixin):
    """
    L{xmantissa.ixmantissa.IPreferenceCollection} which collects preferences
    that have something to do with compose or outgoing mail
    """
    implements(ixmantissa.IPreferenceCollection)

    schemaVersion = 3

    installedOn = attributes.reference()

    def installOn(self, other):
        super(ComposePreferenceCollection, self).installOn(other)
        other.powerUp(self, ixmantissa.IPreferenceCollection)

    def getPreferenceParameters(self):
        return None

    def getSections(self):
        return (FromAddressConfigFragment(self),)

    def getTabs(self):
        return (webnav.Tab('Mail', self.storeID, 0.0, children=(
                    webnav.Tab('Outgoing', self.storeID, 0.0),),
                    authoritative=False),)


registerAttributeCopyingUpgrader(ComposePreferenceCollection, 1, 2)

item.declareLegacyItem(ComposePreferenceCollection.typeName, 2,
                       dict(installedOn=attributes.reference(),
                            preferredSmarthost=attributes.text(),
                            smarthostUsername=attributes.text(),
                            smarthostPassword=attributes.text(),
                            smarthostPort=attributes.integer(),
                            smarthostAddress=attributes.text()))

def composePreferenceCollection2to3(old):
    """
    Create an L{FromAddress} out of the appropriate L{userbase.LoginMethod} in
    the store, using L{_getFromAddressFromStore}.  This probably should
    happen in the L{Composer} 2->3 upgrader, but we also make an
    L{FromAddress} item out the smarthost attributes of C{old} if they are
    set, and we need to do that after creating the initial L{FromAddress}, so
    it gets set as the default.

    Copy C{old.installedOn} onto the new L{ComposePreferenceCollection}
    """
    baseFrom = FromAddress(store=old.store,
                           address=_getFromAddressFromStore(old.store))

    if old.preferredSmarthost is not None:
        s = old.store
        smarthostFrom = FromAddress(store=s,
                                    address=old.smarthostAddress,
                                    smtpHost=old.preferredSmarthost,
                                    smtpPort=old.smarthostPort,
                                    smtpUsername=old.smarthostUsername,
                                    smtpPassword=old.smarthostPassword)
        smarthostFrom.setAsDefault()
    else:
        baseFrom.setAsDefault()

    return old.upgradeVersion(old.typeName, 2, 3,
                              installedOn=old.installedOn)

registerUpgrader(composePreferenceCollection2to3,
                 ComposePreferenceCollection.typeName,
                 2, 3)

class FromAddressConfigFragment(LiveElement):
    """
    Fragment which contains some stuff that helps users configure their from
    addresses, such as an L{xmantissa.liveform.LiveForm} for adding new ones,
    and an L{xmantissa.scrolltable.ScrollingFragment} for looking at and
    editing existing ones
    """
    implements(ixmantissa.INavigableFragment)
    fragmentName = 'from-address-config'
    title = 'From Addresses'

    def __init__(self, composePrefs):
        self.composePrefs = composePrefs
        LiveElement.__init__(self)

    def addAddress(self, address, smtpHost, smtpPort, smtpUsername, smtpPassword, default):
        """
        Add a L{FromAddress} item with the given attribute values
        """
        composer = self.composePrefs.store.findUnique(Composer)

        addr = FromAddress(store=self.composePrefs.store,
                           address=address,
                           smtpHost=smtpHost,
                           smtpPort=smtpPort,
                           smtpUsername=smtpUsername,
                           smtpPassword=smtpPassword)

        if default:
            addr.setAsDefault()

    def addAddressForm(self, req, tag):
        """
        @return: an L{xmantissa.liveform.LiveForm} instance which allows users
                 to add from addresses
        """
        def makeRequiredCoercer(paramName, coerce=lambda v: v):
            def notEmpty(value):
                if not value:
                    raise liveform.InvalidInput('value required for ' + paramName)
                return coerce(value)
            return notEmpty

        def textParam(name, label, *a):
            return liveform.Parameter(
                    name, liveform.TEXT_INPUT, makeRequiredCoercer(name), label, *a)

        # ideally we would only show the "address" input by default and have a
        # "SMTP Info" disclosure link which exposes the rest of them

        lf = liveform.LiveForm(
                self.addAddress,
                (textParam('address',  'Email Address'),
                 textParam('smtpHost', 'SMTP Host'),
                 liveform.Parameter(
                    'smtpPort',
                    liveform.TEXT_INPUT,
                    makeRequiredCoercer('smtpPort', int),
                    'SMTP Port',
                    default=25),
                 textParam('smtpUsername', 'SMTP Username'),
                 liveform.Parameter(
                    'smtpPassword',
                     liveform.PASSWORD_INPUT,
                     makeRequiredCoercer('smtpPassword'),
                     'SMTP Password'),
                 liveform.Parameter(
                    'default',
                    liveform.CHECKBOX_INPUT,
                    bool,
                    'Default?',
                    'Use this as default from address')),
                 description='Add From Address')
        lf.jsClass = u'Quotient.Compose.AddAddressFormWidget'
        lf.docFactory = getLoader('liveform-compact')
        lf.setFragmentParent(self)
        return lf
    renderer(addAddressForm)

    def fromAddressScrollTable(self, req, tag):
        """
        @return: L{FromAddressScrollTable}
        """
        f = FromAddressScrollTable(self.composePrefs.store)
        f.docFactory = getLoader(f.fragmentName)
        f.setFragmentParent(self)
        return f
    renderer(fromAddressScrollTable)

    def head(self):
        return None



class FromAddressAddressColumn(object):
    implements(ixmantissa.IColumn)

    attributeID = '_address'

    def sortAttribute(self):
        return FromAddress._address

    def extractValue(self, model, item):
        return item.address

    def getType(self):
        return 'text'



class FromAddressScrollTable(ScrollingFragment):
    """
    L{xmantissa.scrolltable.ScrollingFragment} subclass for browsing
    and editing L{FromAddress} items.
    """
    jsClass = u'Quotient.Compose.FromAddressScrollTable'

    def __init__(self, store):
        ScrollingFragment.__init__(
                self, store,
                FromAddress,
                None,
                (FromAddressAddressColumn(),
                 FromAddress.smtpHost,
                 FromAddress.smtpPort,
                 FromAddress.smtpUsername,
                 FromAddress._default))

    def action_setDefaultAddress(self, item):
        """
        Make the C[item} the default L{FromAddress} for outgoing mail
        """
        item.setAsDefault()

    def action_delete(self, item):
        """
        Delete the given L{FromAddress}
        """
        item.deleteFromStore()

    def getInitialArguments(self):
        """
        Include the web ID of the L{FromAddress} item which represents the
        system address, so the client can prevent it from being deleted
        """
        systemAddress = FromAddress.findSystemAddress(self.store)
        return super(FromAddressScrollTable, self).getInitialArguments() + [
            unicode(self.webTranslator.toWebID(systemAddress), 'ascii')]


class Draft(item.Item):
    """
    i only exist so my storeID can be exposed, instead of exposing the storeID
    of the underlying Message (which gets overwritten with each draft save).
    this stops draft-editing URLs from being invalidated every 30 seconds
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
    jsClass = u'Quotient.Compose.DraftListScrollingWidget'

    def __init__(self, original):
        from xquotient.exmess import MailboxSelector, DRAFT_STATUS
        sq = MailboxSelector(original.store)
        sq.refineByStatus(DRAFT_STATUS)
        ScrollingFragment.__init__(
            self,
            original.store,
            Message,
            sq._getComparison(),
            (Message.recipient, Message.subject, Message.sentWhen),
            defaultSortColumn=Message.sentWhen,
            defaultSortAscending=False)

        self.composerURL = self.webTranslator.linkTo(
                                self.store.findUnique(
                                    Composer).storeID)
        self.docFactory = getLoader(self.fragmentName)

    def constructRows(self, items):
        rows = ScrollingFragment.constructRows(self, items)
        for (item, row) in zip(items, rows):
            draft = self.store.findUnique(Draft, Draft.message==item)
            row['__id__'] = (self.composerURL
                                + u'?draft='
                                + self.webTranslator.toWebID(draft))
        return rows

    def head(self):
        return None

registerAdapter(DraftsScreen, Drafts, ixmantissa.INavigableFragment)
