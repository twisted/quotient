import datetime, rfc822

from zope.interface import implements

from twisted.python.components import registerAdapter
from twisted.python import log
from twisted.mail import smtp, relaymanager
from twisted.names import client
from twisted.internet import error, defer, reactor

from nevow import tags, inevow, flat, rend, json

from epsilon import extime

from axiom import iaxiom, attributes, item, scheduler, userbase

from xmantissa.fragmentutils import dictFillSlots
from xmantissa import webnav, ixmantissa, people, liveform, prefs, tdb, tdbview
from xmantissa.webtheme import getLoader

from xquotient import iquotient, mail, equotient
from xquotient.exmess import Message
from xquotient.mimestorage import Header, Part

def _esmtpSendmail(username, password, smtphost, from_addr, to_addrs, msg):
    d = defer.Deferred()
    f = smtp.ESMTPSenderFactory(username, password, from_addr, to_addrs, msg, d, requireTransportSecurity=False)
    reactor.connectTCP(smtphost, 25, f)
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
        # XXX
        # Why aren't these self.compose.foo?  They probably should be.
        prefCollection = self.store.findUnique(ComposePreferenceCollection)
        if prefCollection.preferredSmarthost is not None:
            return _esmtpSendmail(
                prefCollection.smarthostUsername,
                prefCollection.smarthostPassword,
                prefCollection.preferredSmarthost,
                self.composer.fromAddress,
                [self.toAddress],
                self.message.impl.source.open())
        else:
            d = self.getMailExchange(self.toAddress.split('@', 1)[1])
            def sendMail(mx):
                host = str(mx.name)
                return smtp.sendmail(
                    host,
                    self.composer.fromAddress,
                    [self.toAddress],
                    # XXX
                    self.message.impl.source.open())
            d.addCallback(sendMail)
            return d


    def run(self):
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
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_composer'
    schemaVersion = 1

    installedOn = attributes.reference()

    fromAddress = attributes.inmemory()

    def activate(self):
        for (localpart, domain) in userbase.getAccountNames(self.store):
            self.fromAddress = localpart + '@' + domain
            return

    def installOn(self, other):
        super(Composer, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)


    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Compose', self.storeID, 0.1)],
                authoritative=False)]


    def sendMessage(self, toAddresses, msg):
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

        bounceText = 'Your message bounced.'

        s = S.StringIO()
        original = P.Parser().parse(msg.impl.source.open())

        m = MMP.MIMEMultipart(
            'mixed',
            None,
            [MT.MIMEText(bounceText, 'plain'),
             MT.MIMEText(log, 'plain'),
             MM.MIMEMessage(original)])

        m['Subject'] = 'Unable to deliver message'
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

class FileCabinetPage(rend.Page):
    lastFile = None

    def __init__(self, original):
        rend.Page.__init__(self, original, docFactory=getLoader('file-upload'))

    def renderHTTP(self, ctx):
        req = inevow.IRequest(ctx)
        if req.method == 'POST':
            uploadedFileArg = req.fields['uploaddata']
            def txn():
                self.original.filesCount += 1

                outf = self.original.store.newFile(
                                'cabinet-'+str(self.original.storeID),
                                str(self.original.filesCount))

                outf.write(uploadedFileArg.file.read())
                outf.close()

                self.lastFile = File(store=self.original.store,
                                     body=outf.finalpath,
                                     name=unicode(uploadedFileArg.filename),
                                     type=unicode(uploadedFileArg.type),
                                     cabinet=self.original)

            self.original.store.transact(txn)

        return rend.Page.renderHTTP(self, ctx)

    def render_lastFileData(self, ctx, data):
        if self.lastFile is None:
            return ''
        return json.serialize({u'id': self.lastFile.storeID,
                               u'name': self.lastFile.name})

registerAdapter(FileCabinetPage, FileCabinet, inevow.IResource)

class ComposeFragment(liveform.LiveForm):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'compose'
    live = 'athena'
    jsClass = 'Quotient.Compose.Controller'
    title = ''

    iface = allowedMethods = dict(getPeople=True, invoke=True)

    _savedDraft = None

    def __init__(self, original, toAddress='', subject='', messageBody='', attachments=()):
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

        self.docFactory = None
        self.translator = ixmantissa.IWebTranslator(original.store)

    def invoke(self, formPostEmulator):
        coerced = self._coerced(formPostEmulator)
        # we want to allow the javascript to submit an
        # list of filenames of arbitrary length with the form
        coerced['files'] = formPostEmulator.get('files', ())
        self.callable(**coerced)

    def getPeople(self):
        peeps = []
        for person in self.original.store.query(people.Person):
            peeps.append((person.name, person.getEmailAddress()))
        return peeps

    def render_inboxLink(self, ctx, data):
        from xquotient.inbox import Inbox
        return self.translator.linkTo(self.original.store.findUnique(Inbox).storeID)

    def render_compose(self, ctx, data):
        req = inevow.IRequest(ctx)
        draftWebID = req.args.get('draft', [None])[0]

        if draftWebID is not None:
            draft = self.translator.fromWebID(draftWebID)
            # i think this will suffice until we have a rich text compose
            (alt,) = list(draft.message.impl.getTypedParts('multipart/alternative'))
            (txt,) = list(alt.getTypedParts('text/plain'))
            try:
                cc = draft.message.impl.getHeader(u'cc')
            except equotient.NoSuchHeader:
                cc = ''

            attachments = []
            attachmentPattern = inevow.IQ(self.docFactory).patternGenerator('attachment')
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
            slotData = dict(to=self.toAddress,
                            subject=self.subject,
                            body=self.messageBody,
                            cc='',
                            attachments='')

        return dictFillSlots(ctx.tag, slotData)

    def render_fileCabinet(self, ctx, data):
        cabinet = self.original.store.findOrCreate(FileCabinet)
        return inevow.IQ(self.docFactory).onePattern('cabinet-iframe').fillSlots(
                    'src', ixmantissa.IWebTranslator(cabinet.store).linkTo(cabinet.storeID))

    def head(self):
        return None

    def createMessage(self, toAddress, subject, messageBody, cc, bcc, files):
        from email import Generator as G, MIMEBase as MB, MIMEMultipart as MMP, MIMEText as MT
        import StringIO as S

        s = S.StringIO()
        m = MMP.MIMEMultipart(
            'alternative',
            None,
            [MT.MIMEText(messageBody, 'plain'),
             MT.MIMEText(flat.flatten(tags.html[tags.body[messageBody]]), 'html')])

        fileItems = []
        if self.attachments or files:
            attachmentParts = []
            for a in self.attachments:
                part = MB.MIMEBase(*a.type.split('/'))
                part.set_payload(a.part.getBody(decode=True))
                fname = a.part.getParam('filename', header=u'content-disposition')
                if fname is not None:
                    part.add_header('content-disposition', 'attachment', filename=fname)
                attachmentParts.append(part)

            for storeID in files:
                a = self.original.store.getItemByID(long(storeID))
                fileItems.append(a)
                part = MB.MIMEBase(*a.type.split('/'))
                part.set_payload(a.body.getContent())
                part.add_header('content-disposition', 'attachment', filename=a.name)
                attachmentParts.append(part)

            m = MMP.MIMEMultipart('mixed', None, [m] + attachmentParts)

        m['From'] = self.original.fromAddress
        m['To'] = toAddress
        m['Subject'] = subject
        m['Date'] = rfc822.formatdate()
        m['Message-ID'] = smtp.messageid('divmod.xquotient')

        if cc:
            m['Cc'] = cc

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
        avatar.findOrCreate(mail.MailTransferAgent).installOn(avatar)
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



class ComposePreferenceCollection(item.Item, item.InstallableMixin):
    implements(ixmantissa.IPreferenceCollection)

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
                'smarthost-host': _SmarthostPreference(self.preferredSmarthost, self),
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
        else:
            assert False, "Bogus preference input: %r %r" % (pref, value)
        setattr(pref, 'value', value)


    def getSections(self):
        return None

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

class DraftColumnView(tdbview.ColumnViewBase):
    translator = None

    def __init__(self, name, displayName=None, default=None):
        super(DraftColumnView, self).__init__(name, displayName=displayName)
        self.default = default

    def stanFromValue(self, idx, item, value):
        if self.translator is None:
            self.translator = ixmantissa.IWebTranslator(item.store)
            self.composerURL = self.translator.linkTo(
                                  item.store.findUnique(Composer).storeID)
        if isinstance(value, extime.Time):
            value = value.asHumanly()
        else:
            if not value:
                value = self.default

        draft = item.store.findUnique(Draft, Draft.message == item)
        return tags.a(href=self.composerURL+'?draft='+self.translator.toWebID(draft))[value]

class DraftsScreen(tdbview.TabularDataView):
    def __init__(self, original):
        prefs = ixmantissa.IPreferenceAggregator(original.store)
        tdm = tdb.TabularDataModel(
                    original.store,
                    Message, (Message.sentWhen,
                              Message.subject,
                              Message.recipient),
                    baseComparison=Message.draft == True,
                    defaultSortColumn='sentWhen',
                    defaultSortAscending=False,
                    itemsPerPage=prefs.getPreferenceValue('itemsPerPage'))

        views = (DraftColumnView('sentWhen'),
                 DraftColumnView('subject', default='No Subject'),
                 DraftColumnView('recipient', 'Recipients', 'No Recipients'))

        tdbview.TabularDataView.__init__(self, tdm, views)
        self.docFactory = getLoader(self.fragmentName)

registerAdapter(DraftsScreen, Drafts, ixmantissa.INavigableFragment)
