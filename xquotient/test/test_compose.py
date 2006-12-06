import quopri

from twisted.trial import unittest
from twisted.python.filepath import FilePath

from email import Parser

from axiom import store
from axiom import scheduler
from axiom import item
from axiom import attributes
from axiom import userbase

from xmantissa import webapp

from xquotient import compose, mail, mimeutil, exmess, equotient
from xquotient.test.util import PartMaker



class CompositionTestMixin(object):
    """
    A mixin for setting up an appropriately-factored composition
    environment.

    * Set up a L{store.Store}, optionally on-disk with the 'dbdir'
      argument to setUp.
    * Sets up a C{reactor} attribute on your test case to a
      L{Reactor} that will collect data about connectTCP calls (made
      by the ESMTP-sending code in compose.py; FIXME: make it work
      for the non-smarthost case too).
    * Set up a composer object
    * Set up 2 from addresses
    """

    def setUp(self, dbdir=None):
        self.reactor = Reactor()
        self._originalSendmail = compose._esmtpSendmail
        compose._esmtpSendmail = self._esmtpSendmail

        self.store = store.Store(dbdir=dbdir)
        scheduler.Scheduler(store=self.store).installOn(self.store)
        self.defaultFromAddr = compose.FromAddress(
                                store=self.store,
                                smtpHost=u'example.org',
                                smtpUsername=u'radix',
                                smtpPassword=u'secret',
                                address=u'radix@example')
        self.defaultFromAddr.setAsDefault()

        self.composer = compose.Composer(store=self.store)
        self.composer.installOn(self.store)


    def _esmtpSendmail(self, *args, **kwargs):
        kwargs['reactor'] = self.reactor
        return self._originalSendmail(*args, **kwargs)

    def tearDown(self):
        compose._esmtpSendmail = self._originalSendmail



class StubStoredMessageAndImplAndSource(item.Item):
    """
    Mock several objects at once:

    1. An L{exmess.Message}

    2. The 'impl' attribute of that message, typically a L{mimestore.Part}

    3. The message file returned from the C{open} method of C{impl}.
       XXX: This returns something that doesn't conform to the file protocol,
       but the code that triggers the usage of that protocol isn't triggered
       by the following tests.
    """

    calledStartedSending = attributes.boolean(default=False)
    impl = property(lambda s: s)
    source = property(lambda s: FilePath(__file__))

    def open(self):
        return "HI DUDE"

    def startedSending(self):
        self.calledStartedSending = True


class Reactor(object):
    """
    Act as a reactor that collects connectTCP call data.
    """
    def connectTCP(self, host, port, factory):
        self.host = host
        self.port = port
        self.factory = factory



class ComposeFromTest(CompositionTestMixin, unittest.TestCase):

    def test_sendmailSendsToAppropriatePort(self):
        """
        Sending a message should deliver to the smarthost on the
        configured port.
        """
        self.defaultFromAddr.smtpPort = 26
        message = StubStoredMessageAndImplAndSource(store=self.store)
        self.composer.sendMessage(
            self.defaultFromAddr, [u'testuser@example.com'], message)
        self.assertEquals(self.reactor.port, 26)


    def test_sendmailSendsFromAppropriateAddress(self):
        """
        If there are smarthost preferences, the from address that they
        specify should be used.
        """
        message = StubStoredMessageAndImplAndSource(store=self.store)
        self.composer.sendMessage(
            self.defaultFromAddr, [u'targetuser@example.com'], message)
        self.failUnless(message.calledStartedSending)
        self.assertEquals(str(self.reactor.factory.fromEmail),
                          self.defaultFromAddr.address)



class RedirectTestCase(CompositionTestMixin, unittest.TestCase):
    """
    Tests for mail redirection
    """
    def setUp(self):
        CompositionTestMixin.setUp(self, dbdir=self.mktemp())
        mail.DeliveryAgent(store=self.store).installOn(self.store)

    def test_createRedirectedMessage(self):
        """
        Test that L{compose.Composer.createRedirectedMessage} sets the right
        headers
        """
        message = StubStoredMessageAndImplAndSource(store=self.store)
        msg = self.composer.createRedirectedMessage(
                self.defaultFromAddr,
                [mimeutil.EmailAddress(
                    u'testuser@localhost',
                    mimeEncoded=False)],
                message)
        m = Parser.Parser().parse(msg.impl.source.open())
        self.assertEquals(m['Resent-To'], 'testuser@localhost')
        self.assertEquals(m['Resent-From'], self.defaultFromAddr.address)


    def test_redirect(self):
        """
        Test L{compose.Composer.redirect}
        """
        message = StubStoredMessageAndImplAndSource(store=self.store)
        msg = self.composer.redirect(
                self.defaultFromAddr,
                [mimeutil.EmailAddress(
                    u'testuser@localhost',
                    mimeEncoded=False)],
                message)

        self.assertEquals(
            str(self.reactor.factory.fromEmail),
            self.defaultFromAddr.address)

        self.assertEquals(
            list(self.reactor.factory.toEmail),
            ['testuser@localhost'])

        m = Parser.Parser().parse(
                self.store.findUnique(
                    exmess.Message).impl.source.open())

        self.assertEquals(m['Resent-From'], self.defaultFromAddr.address)
        self.assertEquals(m['Resent-To'], 'testuser@localhost')

    def test_redirectNameAddr(self):
        """
        Test that L{compose.Composer.redirect} removes the display name
        portion of an email address if present before trying to deliver
        directed mail to it
        """
        message= StubStoredMessageAndImplAndSource(store=self.store)
        msg = self.composer.redirect(
                self.defaultFromAddr,
                [mimeutil.EmailAddress(
                    u'Joe <joe@nowhere>',
                    mimeEncoded=False)],
                message)

        self.assertEquals(
            list(self.reactor.factory.toEmail),
            ['joe@nowhere'])



class ComposeFragmentTest(CompositionTestMixin, unittest.TestCase):
    """
    Test the L{ComposeFragment}.
    """

    def setUp(self):
        """
        Create an *on-disk* store (XXX This is hella slow) and set up
        some dependencies that ComposeFragment needs.
        """
        CompositionTestMixin.setUp(self, dbdir=self.mktemp())

        webapp.PrivateApplication(store=self.store).installOn(self.store)
        da = mail.DeliveryAgent(store=self.store)
        da.installOn(self.store)
        self.cabinet = compose.FileCabinet(store=self.store)
        self.cf = compose.ComposeFragment(self.composer)


    def test_createMessageHonorsSmarthostFromAddress(self):
        """
        Sending a message through the Compose UI should honor the from
        address we give to it
        """
        self.defaultFromAddr.address = u'from@example.com'
        msg = self.cf.createMessage(
            self.defaultFromAddr,
            [mimeutil.EmailAddress(
                    'testuser@example.com',
                    mimeEncoded=False)],
            u'Sup dood', u'A body', (), (), u'')
        file = msg.impl.source.open()
        msg = Parser.Parser().parse(file)
        self.assertEquals(msg["from"], 'from@example.com')

    def test_createMessageHonorsBCC(self):
        """
        Sending a message through the compose UI should honor the BCC
        addresses we give to it
        """
        self.cf._sendMail(
            self.defaultFromAddr,
            [mimeutil.EmailAddress(
                'to@example.com',
                mimeEncoded=False)],
            u'', u'', [],
            [mimeutil.EmailAddress(
                'bcc1@example.com',
                 mimeEncoded=False),
             mimeutil.EmailAddress(
                'bcc2@example.com',
                mimeEncoded=False)],
            u'')
        self.assertEquals(
            list(self.store.query(compose._NeedsDelivery).getColumn('toAddress')),
            ['to@example.com', 'bcc1@example.com', 'bcc2@example.com'])

    def _createMessage(self, cc=(), bcc=()):
        """
        Use L{xquotient.compose.ComposeFragment.createMessage} to make a
        simple message, optionally with CC/BCC headers set

        @param cc: addresses to CC the message to.  defaults to no addresses
        @type cc: sequence of L{xquotient.mimeutils.EmailAddress}
        @param bcc: addresses to BCC the message to.  defaults to no addresses
        @type bcc: sequence of L{xquotient.mimeutils.EmailAddress}

        @return: L{xquotient.exmess.Message}
        """
        return self.cf.createMessage(
            self.defaultFromAddr,
            [mimeutil.EmailAddress(
                'to@example.com',
                mimeEncoded=False)],
            u'', u'', cc, bcc, u'')


    def _createBCCMessage(self):
        """
        Use L{xquotient.compose.ComposeFragment.createMessage} to make a
        message with a BCC
        """
        return self._createMessage(
            bcc=[mimeutil.EmailAddress(
                'bcc@example.com',
                 mimeEncoded=False)])


    def _createCCMessage(self):
        """
        Use L{xquotient.compose.ComposeFragment.createMessage} to make a
        message with a BCC
        """
        return self._createMessage(
            cc=[mimeutil.EmailAddress(
                'cc@example.com',
                mimeEncoded=False)])


    def test_noBCCInTo(self):
        """
        Test that L{xquotient.compose.ComposeFragment.createMessage} doesn't
        stick the BCC address it's passed into the "To" header
        """
        msg = self._createBCCMessage()
        (addr,) = mimeutil.parseEmailAddresses(msg.impl.getHeader(u'To'))
        self.assertEquals(addr.email, 'to@example.com')

    def test_noBCCHeader(self):
        """
        Test that L{xquotient.compose.ComposeFragment.createMessage} doesn't
        result in a BCC header on the message it makes, when it's passed a BCC
        address
        """
        msg = self._createBCCMessage()
        self.assertRaises(
            equotient.NoSuchHeader, lambda: msg.impl.getHeader(u'bcc'))


    def test_ccHeader(self):
        """
        Test that the message created by
        L{xquotient.compose.ComposeFragment.createMessage} has the "cc" header
        set if the C{cc} argument contains an address
        """
        msg = self._createCCMessage()
        self.assertEquals(msg.impl.getHeader(u'cc'), 'cc@example.com')


    def _createMessageWithFiles(self, files):
        """
        Make an L{xquotient.compose.ComposeFragment}, use it to create a
        message with attachments corresponding to the
        L{xquotient.compose.File} items C{files}
        """
        cf = compose.ComposeFragment(self.composer)
        return cf.createMessage(self.defaultFromAddr,
                                [mimeutil.EmailAddress(
                                    'testuser@example.com',
                                    mimeEncoded=False)],
                                u'subject', u'body', (), (),
                                files=list(f.storeID for f in files))

    def _assertFilenameParamEquals(self, part, filename):
        """
        Assert that the C{filename} parameter of the C{content-disposition}
        header of the L{xquotient.mimestorage.Part} C{part} is equal to
        C{filename}

        @type part: L{xquotient.mimestorage.Part}
        @type filename: C{unicode}
        """
        self.assertEquals(
            part.getParam(
                u'filename', header=u'content-disposition'),
                filename)


    def test_createMessageAttachment(self):
        """
        Test L{xquotient.compose.ComposeFragment.createMessage} when there is an
        attachment
        """
        fileItem = self.cabinet.createFileItem(
                    u'the filename', u'text/plain', 'some text/plain')
        msg = self._createMessageWithFiles((fileItem,))
        (_, attachment) = msg.walkMessage()
        self.assertEquals(
            attachment.part.getBody(decode=True),
            'some text/plain\n')
        self.assertEquals(attachment.type, 'text/plain')
        self._assertFilenameParamEquals(attachment.part, 'the filename')

    def test_createMessageWithMessageAttachment(self):
        """
        Test L{xquotient.compose.ComposeFragment.createMessage} when there is
        an attachment of type message/rfc822
        """
        fileItem = self.cabinet.createFileItem(
                    u'a message', u'message/rfc822',
                    PartMaker('text/plain', 'some text/plain').make())
        msg = self._createMessageWithFiles((fileItem,))
        rfc822part = list(msg.impl.walk())[-2]
        self.assertEquals(rfc822part.getContentType(), 'message/rfc822')
        self._assertFilenameParamEquals(rfc822part, 'a message')

        (_, textPlainPart) = rfc822part.walk()
        self.assertEquals(textPlainPart.getContentType(), 'text/plain')
        self.assertEquals(textPlainPart.getBody(), 'some text/plain\n')

    def test_createMessageWithMultipartAttachment(self):
        """
        Test L{xquotient.compose.ComposeFragment.createMessage} when there is
        a multipart attachment
        """
        fileItem = self.cabinet.createFileItem(
                    u'a multipart', u'multipart/mixed',
                    PartMaker('multipart/mixed', 'mixed',
                        PartMaker('text/plain', 'text/plain #1'),
                        PartMaker('text/plain', 'text/plain #2')).make())
        msg = self._createMessageWithFiles((fileItem,))
        multipart = list(msg.impl.walk())[-3]
        self.assertEquals(multipart.getContentType(), 'multipart/mixed')
        self._assertFilenameParamEquals(multipart, 'a multipart')

        (_, textPlain1, textPlain2) = multipart.walk()
        self.assertEquals(textPlain1.getContentType(), 'text/plain')
        self.assertEquals(textPlain1.getBody(), 'text/plain #1\n')

        self.assertEquals(textPlain2.getContentType(), 'text/plain')
        self.assertEquals(textPlain2.getBody(), 'text/plain #2\n')


    def test_createMessageWithBinaryAttachment(self):
        """
        Test L{xquotient.compose.ComposeFragment.createMessage} when there is
        a binary attachment.  The attachment's part should be encoded as
        base64, with the appropriate content-transfer-encoding header
        """
        fileItem = self.cabinet.createFileItem(
                        u'some stuff', u'application/octet-stream',
                        u'this is the body')
        msg = self._createMessageWithFiles((fileItem,))
        (binPart,) = msg.walkAttachments()
        self.assertEquals(
            binPart.part.getHeader(u'content-transfer-encoding'),
            'base64')
        self.assertEquals(
            binPart.part.getBody(),
            'this is the body'.encode('base64'))


    def test_createMessageWithTextAttachment(self):
        """
        Test L{xquotient.compose.ComposeFragment.createMessage} when there is
        a text attachment.  The attachment's part should be encoded as
        quoted-printable, with the appropriate content-transfer-encoding
        header
        """
        fileItem = self.cabinet.createFileItem(
                        u'some stuff', u'text/plain',
                        u'this is the body\t')
        msg = self._createMessageWithFiles((fileItem,))
        (textPart,) = msg.walkAttachments()
        self.assertEquals(
            textPart.part.getHeader(u'content-transfer-encoding'),
            'quoted-printable')
        self.assertEquals(
            textPart.part.getBody(),
            quopri.encodestring(
                'this is the body\t', quotetabs=True) + '\n')


    def test_createMessageNotIncoming(self):
        """
        Verify that a message composed via the compose form does not deposit
        anything into the 'incoming' state, so the spam filter will not be
        triggered.
        """
        sq = exmess.MailboxSelector(self.store)
        msg = self.cf.createMessage(
            self.defaultFromAddr,
            [mimeutil.EmailAddress(
                    'testuser@example.com',
                    mimeEncoded=False)],
            u'Sup dood', u'A body', u'', u'', u'')
        sq.refineByStatus(exmess.INCOMING_STATUS)
        self.assertEquals(list(sq), [])
        self.assertEquals(msg.hasStatus(exmess.CLEAN_STATUS), False)
        self.failIf(msg.shouldBeClassified)


    def test_clientFacingAPIDraft(self):
        """
        Verify that the client-facing '_sendOrSave' method, invoked by the
        liveform, generates a draft message when told to save the message.

        This is a white-box test.
        """
        self.cf._sendOrSave(
            fromAddress=self.defaultFromAddr,
            toAddresses=[mimeutil.EmailAddress(
                    u'testuser@127.0.0.1',
                    mimeEncoded=False)],
            subject=u'The subject of the message.',
            messageBody=u'The body of the message.',
            cc=[],
            bcc=[],
            files=[],
            draft=True)
        m = self.store.findUnique(exmess.Message)
        self.assertEquals(set(m.iterStatuses()),
                          set([exmess.UNREAD_STATUS, exmess.DRAFT_STATUS]))
        self.assertEquals(list(self.store.query(compose._NeedsDelivery)),
                          [])


    def test_clientFacingAPISend(self):
        """
        Verify that the client-facing '_sendOrSave' method, invoked by the
        liveform, generates a sent message when told to send the message.

        This is a white-box test.
        """
        self.cf._sendOrSave(
            fromAddress=self.defaultFromAddr,
            toAddresses=[mimeutil.EmailAddress(
                    u'testuser@127.0.0.1',
                    mimeEncoded=False)],
            subject=u'The subject of the message.',
            messageBody=u'The body of the message.',
            cc=[],
            bcc=[],
            files=[],
            draft=False)
        m = self.store.findUnique(exmess.Message)
        self.assertEquals(set(m.iterStatuses()),
                          set([exmess.UNREAD_STATUS, exmess.SENT_STATUS]))
        nd = self.store.findUnique(compose._NeedsDelivery)
        self.assertIdentical(nd.message, m)



class FromAddressConfigFragmentTest(unittest.TestCase):
    """
    Test L{compose.FromAddressConfigFragment}
    """

    def setUp(self):
        self.store = store.Store()
        cprefs = compose.ComposePreferenceCollection(store=self.store)
        cprefs.installOn(self.store)
        self.composer = compose.Composer(store=self.store)
        self.frag = compose.FromAddressConfigFragment(cprefs)

    def test_addAddress(self):
        """
        Test that L{compose.FromAddressConfigFragment.addAddress} creates
        L{compose.FromAddress} items with the right attribute values
        """
        attrs = dict(address=u'foo@bar',
                     smtpHost=u'bar',
                     smtpUsername=u'foo',
                     smtpPort=25,
                     smtpPassword=u'secret')

        self.frag.addAddress(default=False, **attrs)
        item = self.store.findUnique(compose.FromAddress)
        for (k, v) in attrs.iteritems():
            self.assertEquals(getattr(item, k), v)
        # make sure it didn't make it the default
        self.assertEquals(
                self.store.count(
                    compose.FromAddress,
                    compose.FromAddress._default == True),
                0)
        item.deleteFromStore()

        self.frag.addAddress(default=True, **attrs)
        item = self.store.findUnique(compose.FromAddress)
        for (k, v) in attrs.iteritems():
            self.assertEquals(getattr(item, k), v)
        # make sure it did
        self.assertEquals(compose.FromAddress.findDefault(self.store), item)

class FromAddressExtractionTest(unittest.TestCase):
    """
    Test  L{compose._getFromAddressFromStore}
    """

    def testPolicy(self):
        """
        Test that only internal or verified L{userbase.LoginMethod}s with
        protocol=email are considered candidates for from addresses
        """
        s = store.Store(self.mktemp())
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)

        acc = ls.addAccount('username', 'dom.ain', 'password', protocol=u'not email')
        ss = acc.avatars.open()

        # not verified or internal, should explode
        self.assertRaises(
            RuntimeError, lambda: compose._getFromAddressFromStore(ss))

        # ANY_PROTOCOL
        acc.addLoginMethod(u'yeah', u'x.z', internal=True)

        # should work
        self.assertEquals(
            'yeah@x.z',
            compose._getFromAddressFromStore(ss))

        ss.findUnique(
            userbase.LoginMethod,
            userbase.LoginMethod.localpart == u'yeah').deleteFromStore()

        # external, verified
        acc.addLoginMethod(u'yeah', u'z.a', internal=False, verified=True)

        # should work
        self.assertEquals(
            'yeah@z.a',
            compose._getFromAddressFromStore(ss))


class FromAddressTestCase(unittest.TestCase):
    """
    Test L{compose.FromAddress}
    """

    def testDefault(self):
        """
        Test L{compose.FromAddress.setAsDefault} and
        L{compose.FromAddress.findDefault}
        """
        s = store.Store()

        addrs = dict((localpart, compose.FromAddress(
                                    store=s, address=localpart + '@host'))
                        for localpart in u'foo bar baz'.split())

        qux = compose.FromAddress(store=s, address=u'qux@host')
        qux.setAsDefault()

        self.assertEquals(compose.FromAddress.findDefault(s).address, u'qux@host')

        addrs['foo'].setAsDefault()

        self.assertEquals(compose.FromAddress.findDefault(s).address, u'foo@host')

    def testSystemAddress(self):
        """
        Test L{compose.FromAddress.findSystemAddress}
        """
        s = store.Store(self.mktemp())
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)

        acc = ls.addAccount('foo', 'host', 'password', protocol=u'email')
        ss = acc.avatars.open()

        fa = compose.FromAddress(store=ss)
        self.assertIdentical(compose.FromAddress.findSystemAddress(ss), fa)
        self.assertEquals(fa.address, 'foo@host')
