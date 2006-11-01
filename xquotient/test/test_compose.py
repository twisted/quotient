from twisted.trial import unittest

from email import Parser

from axiom import store
from axiom import scheduler
from axiom import item
from axiom import attributes
from axiom import userbase

from xmantissa import webapp

from xquotient import compose, mail, mimeutil



class SmarthostCompositionTestMixin(object):
    """
    A mixin for setting up an appropriately-factored composition
    environment.

    * Set up a L{store.Store}, optionally on-disk with the 'dbdir'
      argument to setUp.
    * Sets up a C{reactor} attribute on your test case to a
      L{Reactor} that will collect data about connectTCP calls (made
      by the ESMTP-sending code in compose.py; FIXME: make it work
      for the non-smarthost case too.
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
    outgoing = attributes.boolean()
    impl = property(lambda s: s)
    source = property(lambda s: s)

    def open(self):
        return "HI DUDE"



class Reactor(object):
    """
    Act as a reactor that collects connectTCP call data.
    """
    def connectTCP(self, host, port, factory):
        self.host = host
        self.port = port
        self.factory = factory



class ComposeFromTest(SmarthostCompositionTestMixin, unittest.TestCase):

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
        self.assertEquals(str(self.reactor.factory.fromEmail),
                          self.defaultFromAddr.address)



class ComposeFragmentTest(SmarthostCompositionTestMixin, unittest.TestCase):
    """
    Test the L{ComposeFragment}.
    """

    def setUp(self):
        """
        Create an *on-disk* store (XXX This is hella slow) and set up
        some dependencies that ComposeFragment needs.
        """
        SmarthostCompositionTestMixin.setUp(self, dbdir=self.mktemp())

        webapp.PrivateApplication(store=self.store).installOn(self.store)
        da = mail.DeliveryAgent(store=self.store)
        da.installOn(self.store)


    def test_createMessageHonorsSmarthostFromAddress(self):
        """
        Sending a message through the Compose UI should honor the from
        address we give to it
        """
        self.defaultFromAddr.address = u'from@example.com'
        cf = compose.ComposeFragment(self.composer)
        msg = cf.createMessage(self.defaultFromAddr,
                               [mimeutil.EmailAddress(
                                    'testuser@example.com',
                                    mimeEncoded=False)],
                               u'Sup dood', u'A body', u'', u'', u'')
        file = msg.impl.source.open()
        msg = Parser.Parser().parse(file)
        self.assertEquals(msg["from"], 'from@example.com')

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
