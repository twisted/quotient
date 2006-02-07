import datetime, rfc822

from zope.interface import implements

from twisted.python.components import registerAdapter
from twisted.python import log, failure
from twisted.mail import smtp, relaymanager
from twisted.names import client
from twisted.internet import error

from nevow import tags, inevow, flat

from epsilon import extime

from axiom import iaxiom, attributes, item, scheduler, userbase

from xmantissa.fragmentutils import dictFillSlots
from xmantissa import webnav, ixmantissa, people, liveform

from xquotient import iquotient, mail

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


    def run(self):
        sch = iaxiom.IScheduler(self.store)
        if self.tries < len(self.RETRANS_TIMES):
            # Set things up to try again, if this attempt fails
            nextTry = datetime.timedelta(seconds=self.RETRANS_TIMES[self.tries])
            sch.schedule(self, extime.Time() + nextTry)

        if not self.running:
            self.running = True
            self.tries += 1

            resolver = client.Resolver(resolv='/etc/resolv.conf')
            mxc = relaymanager.MXCalculator(resolver)
            d = mxc.getMX(self.toAddress.split('@', 1)[1])

            def gotMX(mx):
                resolver.protocol.transport.stopListening()
                return mx
            d.addCallback(gotMX)

            def sendMail(mx):
                host = str(mx.name)
                return smtp.sendmail(
                    host,
                    self.composer.fromAddress,
                    [self.toAddress],
                    # XXX
                    self.message.impl.source.open())
            d.addCallback(sendMail)

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
        print 'X' * 50
        print 'OMFG IT BOUNCED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        print 'X' * 50


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

    cabinet = attributes.reference(allowNone=False)

class FileCabinet(item.Item):

    implements(inevow.IResource)

    typeName = 'quotient_file_cabinet'
    schemaVersion = 1

    name = attributes.text()
    filesCount = attributes.integer(default=0)

    def renderHTTP(self, ctx):
        req = inevow.IRequest(ctx)
        if req.method == 'GET':
            req.setHeader("content/type", "text/html")
            return '''
            <html>
            <head>
            <script type="text/javascript">
            function reportProgressToParent() {
                document.getElementsByTagName("form")[0].style.display = "none";
                /* do something magical */
            }
            </script>
            </head>
            <body>
            <form enctype="multipart/form-data" method="POST" onsubmit="reportProgressToParent(); return true;">
            <input name="uploaddata" type="file" />
            <input type="submit" name="upload" value="Upload" />
            </form></body></html>
            '''
        if req.method == 'POST':
            uploadedFileArg = req.fields['uploaddata']
            def txn():
                self.filesCount += 1
                outf = self.store.newFile('cabinet-'+str(self.storeID),
                                          str(self.filesCount))
                outf.write(uploadedFileArg.file.read())
                outf.close()

                File(store=self.store,
                     body=outf.finalpath,
                     name=unicode(uploadedFileArg.filename),
                     type=unicode(uploadedFileArg.type),
                     cabinet=self)

            self.store.transact(txn)
            req.setHeader("content/type", "text/plain")
            return 'OK '+str(self.filesCount)

    def locateChild(self, ctx, segments):
        return self, ()



class ComposeFragment(liveform.LiveForm):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'compose'
    live = 'athena'
    jsClass = 'Quotient.Compose.Controller'
    title = ''

    iface = allowedMethods = dict(getPeople=True, invoke=True)

    def __init__(self, original, toAddress='', subject='', messageBody='', attachments=()):
        self.original = original
        super(ComposeFragment, self).__init__(
            callable=self._sendMail,
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
                                           coercer=unicode)])
        self.toAddress = toAddress
        self.subject = subject
        self.messageBody = messageBody
        self.attachments = attachments

        self.docFactory = None


    def getPeople(self):
        peeps = []
        for person in self.original.store.query(people.Person):
            peeps.append((person.name, person.getEmailAddress()))
        return peeps


    def render_compose(self, ctx, data):
        return dictFillSlots(ctx.tag, dict(to=self.toAddress,
                                           subject=self.subject,
                                           body=self.messageBody))


    def render_fileCabinet(self, ctx, data):
        cabinet = self.original.store.findOrCreate(FileCabinet)
        return inevow.IQ(self.docFactory).onePattern('cabinet-iframe').fillSlots(
                    'src', ixmantissa.IWebTranslator(cabinet.store).linkTo(cabinet.storeID))

    def head(self):
        yield tags.script(type='text/javascript',
                          src='/Quotient/static/js/tiny_mce/tiny_mce.js')
        yield tags.link(rel='stylesheet', type='text/css',
                        href='/Quotient/static/reader.css')


    _mxCalc = None
    def _sendMail(self, toAddress, subject, messageBody, cc, bcc):

        from email import Generator as G, MIMEBase as MB, MIMEMultipart as MMP, MIMEText as MT
        import StringIO as S

        s = S.StringIO()
        m = MMP.MIMEMultipart(
            'alternative',
            None,
            [MT.MIMEText(messageBody, 'plain'),
             MT.MIMEText(flat.flatten(tags.html[tags.body[messageBody]]), 'html')])

        if 0 < len(self.attachments):
            attachmentParts = []
            for a in self.attachments:
                part = MB.MIMEBase(*a.type.split('/'))
                part.set_payload(a.part.getBody(decode=True))
                attachmentParts.append(part)

            m = MMP.MIMEMultipart('mixed', None, [m] + attachmentParts)

        m['From'] = self.original.fromAddress
        m['To'] = toAddress
        m['Subject'] = subject
        m['Date'] = rfc822.formatdate()
        m['Message-ID'] = smtp.messageid('divmod.xquotient')

        m['Cc'] = cc

        G.Generator(s).flatten(m)
        s.seek(0)

        def createMessageAndQueueIt():
            mr = iquotient.IMIMEDelivery(self.original.store).createMIMEReceiver()
            for L in s:
                mr.lineReceived(L.rstrip('\n'))
            mr.messageDone()
            msg = mr.message

            addresses = [toAddress]
            if cc:
                addresses.append(cc)

            self.original.sendMessage(addresses, msg)
        self.original.store.transact(createMessageAndQueueIt)

registerAdapter(ComposeFragment, Composer, ixmantissa.INavigableFragment)


class ComposeBenefactor(item.Item, item.InstallableMixin):
    endowed = attributes.integer(default=0)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(scheduler.SubScheduler).installOn(avatar)
        avatar.findOrCreate(mail.MailTransferAgent).installOn(avatar)
        avatar.findOrCreate(Composer).installOn(avatar)

    def revoke(self, ticket, avatar):
        avatar.findUnique(Composer).deleteFromStore()
