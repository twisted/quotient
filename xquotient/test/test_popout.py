
from twisted.trial.unittest import TestCase
from twisted.internet.defer import maybeDeferred, gatherResults
from twisted.python.filepath import FilePath

from axiom.store import Store

from xquotient.mail import DeliveryAgent
from xquotient.popout import POP3Up

_theBaseStorePath = None
def getBaseStorePath(creator):
    global _theBaseStorePath
    if _theBaseStorePath is None:
        s = creator()
        _theBaseStorePath = s.dbdir
        s.close()
    return _theBaseStorePath


def createStore(location, messageTexts):
    s = Store(location)
    da = DeliveryAgent(store=s)
    da.installOn(s)
    for msgText in messageTexts:
        receiver = da.createMIMEReceiver(u'test://' + location)
        receiver.feedStringNow(msgText)
    POP3Up(store=s).installOn(s)
    return s


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
        ]

    def setUp(self):
        self.dbdir = self.mktemp()
        basePath = getBaseStorePath(
            lambda: createStore(self.mktemp(),
                                self.messageTexts))
        basePath.copyTo(FilePath(self.dbdir))
        self.store = Store(self.dbdir)
        self.mailbox = self.store.findUnique(POP3Up)


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
