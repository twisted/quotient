
from twisted.trial.unittest import TestCase
from twisted.internet.defer import maybeDeferred, gatherResults, Deferred, AlreadyCalledError
from twisted.python.failure import Failure
from twisted.internet.error import ConnectionDone
from twisted.cred.portal import IRealm, Portal
from twisted.cred.checkers import ICredentialsChecker
from twisted.test.proto_helpers import StringTransport

from axiom.store import Store
from axiom.userbase import LoginSystem
from axiom.test.util import getPristineStore, QueryCounter

from xquotient.mail import DeliveryAgent
from xquotient.popout import POP3Up, POP3ServerFactory, _ndchain, MessageInfo

def createStore(testCase):
    location = testCase.mktemp()
    s = Store(location)
    da = DeliveryAgent(store=s)
    da.installOn(s)
    makeSomeMessages(testCase, da, location)
    POP3Up(store=s).installOn(s)
    return s

def makeSomeMessages(testCase, da, location):
    for msgText in testCase.messageTexts:
        receiver = da.createMIMEReceiver(u'test://' + location)
        receiver.feedStringNow(msgText)


class MailboxTestCase(TestCase):

    messageTexts = [
        "Message: value\n"
        "\n"
        "Bye\n",

        "Header: isn't it fun\n"
        "\n"
        "bye\n",

        "o/` They say every man must need protection o/`\n",
        "o/` They say every man must fall o/`\n",
        "o/` And I swear I see my reflection o/`\n",
        "o/` Someplace so high above the wall o/`\n",
        "o/` I see my light come shining, from the west down to the east o/`\n",
        "o/` Any day now, any day now, I shall be released o/`\n",

        'Third-Message: This One\n'
        '\n'
        'Okay\n',
        ]

    def setUp(self):
        self.store = getPristineStore(self, createStore)
        self.mailbox = self.store.findUnique(POP3Up)


    def test_cooperativeLogin(self):
        """
        Verify that the mailbox will be loaded without hanging the server for
        an inordinate period of time.
        """
        qc = QueryCounter(self.store)
        n = []
        def m():
            n.append(self.mailbox._realize())
        self.assertEquals(qc.measure(m), 0)
        [actual] = n; n[:] = []
        actual.coiterate = lambda x: n.append(x) or Deferred()
        actual.pagesize = 1
        da = self.store.findUnique(DeliveryAgent)
        location = u'extra'

        # this next line initializes the table for pop3, which accounts to a
        # fairly steep startup cost.  TODO: optimize axiom so this isn't as
        # steep.
        self.store.query(MessageInfo).deleteFromStore()

        self.assertEquals(qc.measure(actual.kickoff), 0)
        [tickit] = n; n[:] = []
        bootstrapBaseline = qc.measure(tickit.next)
        baseline = qc.measure(tickit.next)
        for x in range(2):
            self.store.query(MessageInfo).deleteFromStore()
            # Eliminate all the previously-created message information
            self.assertEquals(qc.measure(actual.kickoff), 0)
            # actual.kickoff()
            [tickit] = n; n[:] = []
            self.assertEquals(qc.measure(tickit.next), bootstrapBaseline)
            self.store.transact(makeSomeMessages, self, da, location)
            self.assertEquals(qc.measure(tickit.next), baseline)
            # exhaust it so we can start again
            while True:
                try:
                    # "<=" because the _last_ iteration will be 1 less than all
                    # the previous, due to the successful comparison/exit
                    # instruction
                    self.failUnless(qc.measure(tickit.next) <= baseline)
                except StopIteration:
                    break


    def test_listMessagesAggregate(self):
        """
        Test that the listMessages method, when invoked with no argument,
        returns the sizes of the messages in the mailbox.
        """
        d = maybeDeferred(self.mailbox.listMessages)
        d.addCallback(self.assertEquals, map(len, self.messageTexts))
        return d


    def test_listMessagesOverflow(self):
        """
        Test that listMessages properly raises a ValueError when passed an
        integer which would index past the end of the mailbox.
        """
        d = maybeDeferred(self.mailbox.listMessages, len(self.messageTexts))
        return self.assertFailure(d, ValueError)


    def test_listMessagesDeleted(self):
        """
        Test that listMessages properly returns 0 for the size of a deleted
        message.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, 0)
        def deleted(ign):
            d = maybeDeferred(self.mailbox.listMessages, 0)
            d.addCallback(self.assertEquals, 0)
            return d
        d.addCallback(deleted)
        return d


    def test_listMessages(self):
        """
        Test that listMessages properly returns the size of a specific message.
        """
        d = maybeDeferred(self.mailbox.listMessages, 1)
        d.addCallback(self.assertEquals, len(self.messageTexts[1]))
        return d


    def test_getMessageOverflow(self):
        """
        Test that getMessage properly raises a ValueError when passed an index
        beyond the end of the mailbox.
        """
        d = maybeDeferred(self.mailbox.getMessage, len(self.messageTexts))
        return self.assertFailure(d, ValueError)


    def test_getMessageDeleted(self):
        """
        Test that getMessage properly raises a ValueError when asked for a
        message which has been deleted.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, 1)
        def deleted(ign):
            d = maybeDeferred(self.mailbox.getMessage, 1)
            return self.assertFailure(d, ValueError)
        d.addCallback(deleted)
        return d


    def test_getMessage(self):
        """
        Test that a file-like object for a valid message index can be retrieved
        through getMessage.
        """
        d = maybeDeferred(self.mailbox.getMessage, 0)
        d.addCallback(lambda fObj: fObj.read())
        d.addCallback(self.assertEquals, self.messageTexts[0])
        return d


    def test_getUidlOverflow(self):
        """
        Test that getUidl properly raises a ValueError when asked for a message
        which is beyond the end of the mailbox.
        """
        d = maybeDeferred(self.mailbox.getUidl, len(self.messageTexts))
        return self.assertFailure(d, ValueError)


    def test_getUidlDeleted(self):
        """
        Test that getUidl properly raises a ValueError when asked to retrieve
        information about a deleted message.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, 1)
        def deleted(ign):
            d = maybeDeferred(self.mailbox.getUidl, 1)
            return self.assertFailure(d, ValueError)
        d.addCallback(deleted)
        return d


    def test_getUidl(self):
        """
        Test that getUidl returns a unique identifier for each message.
        """
        d = gatherResults([maybeDeferred(self.mailbox.getUidl, i)
                           for i
                           in xrange(len(self.messageTexts))])
        def gotUIDs(results):
            uids = set()
            for res in results:
                if res in uids:
                    self.fail("Duplicate UID: %r" % (res,))
                uids.add(res)
        d.addCallback(gotUIDs)
        return d


    def test_deleteMessageOverflow(self):
        """
        Test that deleteMessage properly raises a ValueError when asked to
        delete a message which is beyond the end of the mailbox.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, len(self.messageTexts))
        return self.assertFailure(d, ValueError)


    def test_deleteMessageDeleted(self):
        """
        Test that deleteMessage properly raises a ValueError when asked to
        delete a message which has already been deleted.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, 0)
        def deleted(ign):
            d = maybeDeferred(self.mailbox.deleteMessage, 0)
            return self.assertFailure(d, ValueError)
        d.addCallback(deleted)
        return d


    def test_undeleteMessages(self):
        """
        Test that messages which have previously been deleted once again become
        available after undeleteMessages is called.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, 0)
        def deleted(ign):
            return maybeDeferred(self.mailbox.undeleteMessages)
        d.addCallback(deleted)

        def undeleted(ign):
            d = maybeDeferred(self.mailbox.listMessages, 0)
            d.addCallback(self.assertEquals, len(self.messageTexts[0]))
            return d
        d.addCallback(undeleted)
        return d


    def test_sync(self):
        """
        Test that messages which have previously been deleted do not again
        become available after undeleteMessages is called if a call to sync is
        made in the intervening time.
        """
        d = maybeDeferred(self.mailbox.deleteMessage, 0)
        def deleted(ign):
            return maybeDeferred(self.mailbox.sync)
        d.addCallback(deleted)

        def synced(ign):
            return maybeDeferred(self.mailbox.undeleteMessages)
        d.addCallback(synced)

        def undeleted(ign):
            d = maybeDeferred(self.mailbox.listMessages)
            def retrieved(messages):
                self.assertEquals(len(messages), len(self.messageTexts) - 1)
                self.assertEquals(messages, map(len, self.messageTexts[1:]))
            d.addCallback(retrieved)
            return d
        d.addCallback(undeleted)
        return d



class ProtocolTestCase(TestCase):
    def setUp(self):
        """
        Create a store with a LoginSystem and a portal wrapped around it.
        """
        store = Store()
        LoginSystem(store=store).installOn(store)
        realm = IRealm(store)
        checker = ICredentialsChecker(store)
        self.portal = Portal(realm, [checker])


    def test_incompleteUsername(self):
        """
        Test that a login attempt using a username without a domain part
        results in a customized authentication failure message which points
        out that a domain part should be included in the username.
        """
        factory = POP3ServerFactory(self.portal)
        protocol = factory.buildProtocol(('192.168.1.1', 12345))
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.dataReceived("USER testuser\r\n")
        transport.clear()
        protocol.dataReceived("PASS password\r\n")
        written = transport.value()
        protocol.connectionLost(Failure(ConnectionDone()))

        self.assertEquals(
            written,
            '-ERR Username without domain name (ie "yourname" instead of '
            '"yourname@yourdomain") not allowed; try with a domain name.\r\n')




class UtilityTestCase(TestCase):
    """
    Test utility functionality which is currently specific to the POP3 module.
    """

    def test_nonDestructiveDeferredCallback(self):
        """
        Verify the use of non-destructive deferred chaining: a chained deferred is
        created with a callback that returns nothing - verify that a second
        callback on the original deferred receives the original value.
        """
        x = Deferred()
        chained = []
        notchained = []
        def ccb(val):
            chained.append(val)
            return 3
        ndc =_ndchain(x).addCallback(ccb)
        def ucb(val):
            notchained.append(val)
            return 4
        x.addCallback(ucb)
        x.callback(2)
        self.assertEquals(notchained, [2])
        self.assertEquals(chained, [2])
        self.assertEquals(ndc.result, 3)
        self.assertEquals(x.result, 4)


    def test_nonDestructiveDeferredAbuse(self):
        """
        Verify that the non-destructive deferred will not break its callback,
        even if its result is (incorrectly) called back externally.
        """
        x = Deferred()
        boom = _ndchain(x)
        boom.callback(1)
        l = []
        x.addCallback(lambda n : (l.append(n) or 9))
        x.callback(7)
        self.assertEquals(l, [7])
        self.assertEquals(x.result, 9)
        self.assertEquals(len(self.flushLoggedErrors(AlreadyCalledError)), 1)
