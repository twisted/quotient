
from datetime import datetime, timedelta

from twisted.trial.unittest import TestCase

from epsilon.extime import Time

from axiom.store import Store
from axiom.scheduler import Scheduler

from xmantissa.ixmantissa import INavigableFragment, IWebTranslator
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Organizer, Person, EmailAddress

from xquotient.exmess import Message
from xquotient.inbox import Inbox, InboxScreen, replaceControlChars, UndeferTask
from xquotient.quotientapp import QuotientPreferenceCollection
from xquotient import compose

class _MessageRetrievalMixin:
    """
    Provides a useful C{setUp} for test cases that retrieve messages
    """
    def setUp(self):
        """
        Create a handful of messages spread out over a brief time period so
        that tests can assert things about methods which operate on messages.
        """
        self.store = Store()

        # Inbox requires but does not provide IWebTranslator.
        self.privateApplication = PrivateApplication(store=self.store)
        self.privateApplication.installOn(self.store)
        self.webTranslator = IWebTranslator(self.store)

        baseTime = datetime(year=2001, month=3, day=6)
        self.msgs = []
        for i in xrange(5):
            self.msgs.append(
                Message(store=self.store,
                        read=False,
                        spam=False,
                        receivedWhen=Time.fromDatetime(
                            baseTime + timedelta(seconds=i))))
        self.inbox = InboxScreen(Inbox(store=self.store))


class MessageRetrievalTestCase(_MessageRetrievalMixin, TestCase):
    """
    Test various methods for finding messages.
    """
    def test_getInitialArguments(self):
        """
        Test that L{InboxScreen} properly initializes its client-side
        complement with the number of messages in the current view, an
        identifier for the first message, and the persistent complexity
        setting.
        """
        [complexity] = self.inbox.getInitialArguments()
        self.assertEqual(complexity, 1)

        self.inbox.inbox.uiComplexity = 2
        [complexity] = self.inbox.getInitialArguments()
        self.assertEqual(complexity, 2)



class InboxTestCase(TestCase):
    def testControlChars(self):
        s = ''.join(map(chr, range(1, 32))) + 'foobar'
        # ord('\t') < ord('\n') < ord('\r')
        self.assertEquals(replaceControlChars(s), '\t\n\rfoobar')


    def testAdaption(self):
        """
        Test that an Inbox can be adapted to INavigableFragment so that it can
        be displayed on a webpage.
        """
        s = Store()
        PrivateApplication(store=s).installOn(s)
        inbox = Inbox(store=s)
        self.assertNotIdentical(INavigableFragment(inbox, None), None)


    def testUnreadMessageCount(self):
        s = Store()

        for i in xrange(13):
            m = Message(store=s, read=False, spam=False, receivedWhen=Time())
        for i in xrange(6):
            Message(store=s, read=True, spam=False, receivedWhen=Time())

        PrivateApplication(store=s).installOn(s) # IWebTranslator

        # *seems* like we shouldn't have to adapt Inbox, but
        # the view state variables (inAllView, inSpamView, etc)
        # seem pretty clearly to belong on InboxScreen, carrying
        # most of the interesting methods with them

        # we're in the "Inbox" view
        inbox = Inbox(store=s)
        inboxScreen = InboxScreen(inbox)
        viewSelection = dict(inboxScreen.viewSelection)
        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 13)
        s.findFirst(Message, Message.read == True).read = False
        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 14)

        viewSelection["view"] = 'spam'
        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 0)

        spam = []
        for m in s.query(Message, Message.read == False, limit=6):
            m.spam = True
            spam.append(m)

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 6)

        for m in spam:
            m.spam = False
        m.archived = True

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 0)

        viewSelection["view"] = 'all'

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 14)

        viewSelection["view"] = 'sent'

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 0)

        m.archived = False
        m.outgoing = True

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 1)

        viewSelection["view"] = 'inbox'

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 13)

    def testMailViewCounts(self):
        s = Store()

        for i in xrange(9):
            Message(store=s, read=False, spam=False, receivedWhen=Time())
        for i in xrange(3):
            Message(store=s, read=False, spam=False, archived=True, receivedWhen=Time())

        PrivateApplication(store=s).installOn(s)
        inboxScreen = InboxScreen(Inbox(store=s))
        self.assertEqual(inboxScreen.viewSelection["view"], 'inbox')

        def assertCountsAre(**d):
            for k in ('trash', 'sent', 'spam', 'all', 'inbox', 'deferred'):
                if not k in d:
                    d[k] = 0
            self.assertEqual(inboxScreen.mailViewCounts(), d)

        # the Inbox will mark the first Message in it's query as read,
        # so we subtract one from the expected counts

        assertCountsAre(inbox=8, all=11)

        for i in xrange(4):
            Message(store=s, read=False, spam=True, receivedWhen=Time())
        for i in xrange(3):
            Message(store=s, read=True, spam=True, receivedWhen=Time())

        assertCountsAre(inbox=8, all=11, spam=4)

        for i in xrange(2):
            Message(store=s, read=False, trash=True, receivedWhen=Time())

        assertCountsAre(inbox=8, all=11, spam=4, trash=2)

        for i in xrange(4):
            Message(store=s, read=False, outgoing=True, receivedWhen=Time())

        assertCountsAre(inbox=8, all=11, spam=4, trash=2, sent=4)
        self.assertEqual(inboxScreen.viewSelection["view"], 'inbox')

    def testDefer(self):
        s = Store()
        inbox = Inbox(store=s)

        scheduler = Scheduler(store=s)
        scheduler.installOn(s)

        message = Message(store=s, deferred=False, read=True)
        task = inbox.action_defer(message, 365, 0, 0)
        self.failUnless(message.deferred, 'message was not deferred')
        scheduler.reschedule(task, task.deferredUntil, Time())
        scheduler.tick()
        self.failIf(message.deferred, 'message is still deferred')
        self.failIf(message.read, 'message is marked read')
        self.failUnless(message.everDeferred, 'everDeferred is not set')
        self.assertEquals(s.count(UndeferTask), 0)

    def testDeferCascadingDelete(self):
        s = Store()
        inbox = Inbox(store=s)

        scheduler = Scheduler(store=s)
        scheduler.installOn(s)

        message = Message(store=s)
        task = inbox.action_defer(message, 365, 0, 0)
        message.deleteFromStore()
        self.assertEquals(s.count(UndeferTask), 0)

    def _setUpInbox(self):
        s = Store()

        QuotientPreferenceCollection(store=s).installOn(s)

        self.translator = PrivateApplication(store=s)
        self.translator.installOn(s)

        msgs = list(Message(store=s,
                            subject=unicode(str(i)),
                            spam=False,
                            receivedWhen=Time(),
                            sentWhen=Time(),
                            impl=None)
                        for i in xrange(5))
        msgs.reverse()

        self.inboxScreen = InboxScreen(Inbox(store=s))
        self.viewSelection = dict(self.inboxScreen.viewSelection)
        self.msgs = msgs
        self.msgIds = map(self.translator.toWebID, self.msgs)
        self.store = s


    def testLookaheadWithActions(self):
        """
        Test that message lookahead is correct when the process
        of moving from one message to the next is accomplished by
        eliminating the current message from the active view (e.g.
        by acting on it), rather than doing it explicitly with
        selectMessage().  Do this all the way down, until there
        are no messages left
        """
        self._setUpInbox()

        for i in range(len(self.msgs) - 2):
            readCount, unreadCount = self.inboxScreen.actOnMessageIdentifierList(
                'archive',
                [self.msgIds[i]])

            self.assertEquals(readCount, 1)
            self.assertEquals(unreadCount, 0)

        readCount, unreadCount = self.inboxScreen.actOnMessageIdentifierList(
            'archive',
            [self.msgIds[i + 1]])

        self.assertEquals(readCount, 1)
        self.assertEquals(unreadCount, 0)

        readCount, unreadCount = self.inboxScreen.actOnMessageIdentifierList(
            'archive',
            [self.msgIds[i + 2]])

        self.assertEquals(readCount, 1)
        self.assertEquals(unreadCount, 0)
    testLookaheadWithActions.todo = "read/unread flag not managed properly yet."


    def test_fastForward(self):
        """
        Test fast forwarding to a particular message by id sets that message
        to read.
        """
        self._setUpInbox()
        fragment = self.inboxScreen.fastForward(self.viewSelection, self.msgIds[2])
        self.failUnless(self.msgs[2].read)


    def test_messagesForBatchType(self):
        """
        Test that the correct messages are returned from
        L{Inbox.messagesForBatchType}.
        """
        store = Store()
        inbox = Inbox(store=store)

        viewSelection = {
            u"view": "inbox",
            u"tag": None,
            u"person": None,
            u"account": None}

        # Test that even with no messages, it spits out the right value (an
        # empty list).
        for batchType in ("read", "unread", "all"):
            self.assertEquals(
                list(inbox.messagesForBatchType(batchType, viewSelection)),
                [])

        # Make one message and assert that it only comes back from queries for
        # the batch type which applies to it.
        message = Message(store=store, spam=False)

        message.read = False
        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [message])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message])

        message.read = True
        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [message])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message])

        # Make one more and make sure the batch is correct with various
        # combinations of states between the two.
        other = Message(store=store, spam=False)

        other.read = False
        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [message])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [other])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message, other])

        other.read = True
        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [message, other])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message, other])

    def testGetComposer(self):
        """
        Test L{xquotient.inbox.InboxScreen.getComposer}
        """
        self._setUpInbox()
        compose.Composer(store=self.store).installOn(self.store)
        composer = self.inboxScreen.getComposer()

        self.failIf(composer.toAddresses)
        self.failIf(composer.subject)
        self.failIf(composer.messageBody)
        self.failIf(composer.attachments)

        self.failUnless(composer.inline)



class ReadUnreadTestCase(TestCase):
    """
    Tests for all operations which should change the read/unread state of
    messages.
    """
    NUM_MESSAGES = 5

    def setUp(self):
        self.store = Store()

        # Required for InboxScreen to even be instantiated
        self.translator = PrivateApplication(store=self.store)
        self.translator.installOn(self.store)

        # Required for InboxScreen.fastForward to be called successfully.
        self.preferences = QuotientPreferenceCollection(store=self.store)

        self.inbox = Inbox(store=self.store)
        self.inbox.installOn(self.store)
        self.messages = []
        for i in range(self.NUM_MESSAGES):
            self.messages.append(
                Message(store=self.store,
                        spam=False,
                        receivedWhen=Time(),
                        subject=u''
                        ))


    def test_screenCreation(self):
        """
        Test that creating the view for an inbox marks the first message in
        that mailbox as read.

        XXX - Uhhh, is this actually the desired behavior?  It seems kind of
        broken. -exarkun
        """

        # Make sure things start out in the state we expect
        for msg in self.messages:
            self.failIf(msg.read, "Messages should start unread.")

        screen = InboxScreen(self.inbox)

        # All but the first message should still be unread
        for msg in self.messages[:-1]:
            self.failIf(msg.read, "Subsequent messages should be unread.")

        # But the first message in the mailbox should now be read
        self.failUnless(self.messages[-1].read, "First message should be read.")


    def test_fastForward(self):
        """
        Test that fast forwarding to a message marks that message as read.
        """
        screen = InboxScreen(self.inbox)
        viewSelection = screen.viewSelection

        screen.fastForward(viewSelection, self.translator.toWebID(self.messages[-2]))

        # All but the first two messages should still be unread
        for msg in self.messages[:-2]:
            self.failIf(msg.read, "Subsequent messages should be unread.")

        # But the first two should be read.
        for msg in self.messages[-2:]:
            self.failUnless(msg.read, "First two messages should be read.")

        # Jump to the end of the mailbox
        screen.fastForward(viewSelection, self.translator.toWebID(self.messages[0]))

        for msg in self.messages[1:-2]:
            self.failIf(msg.read, "Middle messages should be unread.")

        for msg in self.messages[:1] + self.messages[-2:]:
            self.failUnless(msg.read, "Outter messages should be read.")


    def test_actOnMessageIdentifierList(self):
        """
        Test that when an unread message is revealed as a result of performing
        some action, that message becomes marked as read.
        """
        screen = InboxScreen(self.inbox)

        screen.actOnMessageIdentifierList(
            'archive',
            [self.translator.toWebID(self.messages[-1])])

        for msg in self.messages[:-1]:
            self.failIf(msg.read, "Subsequent messages should be unread.")

        for msg in self.messages[-1:]:
            self.failUnless(msg.read, "Initial and revealed message should be read.")


class MessagesByPersonRetrievalTestCase(_MessageRetrievalMixin, TestCase):
    """
    Test finding messages by specifying a person who we'd like to see messages
    from
    """

    def setUp(self):
        """
        Extend L{_MessageRetrievalMixin.setUp} to also install an
        L{Organizer}, L{Person} and L{EmailAddress}, and an L{Message} from
        that person
        """
        super(MessagesByPersonRetrievalTestCase, self).setUp()

        self.organizer = Organizer(store=self.store)
        self.organizer.installOn(self.store)

        self.person = Person(store=self.store,
                             organizer=self.organizer,
                             name=u'The Person')

        EmailAddress(store=self.store,
                     address=u'the@person',
                     person=self.person)

        self.messageFromPerson = Message(store=self.store,
                                         read=False,
                                         spam=False,
                                         receivedWhen=Time(),
                                         sender=u'the@person')

    def test_initialQueryIncludesPeople(self):
        """
        Test that the intial view selection/query includes messages that were
        sent by a person in the address book
        """
        self.assertEquals(
            self.inbox.scrollingFragment.requestCurrentSize(),
            len(self.msgs) + 1)

    def test_countChangesIfQueryChanges(self):
        """
        Test that the number of messages in the model changes when the view
        selection/query specifies only messages from a particular person
        """
        viewSelection = self.inbox.scrollingFragment.viewSelection.copy()
        viewSelection['person'] = self.webTranslator.toWebID(self.person)

        self.inbox.scrollingFragment.setViewSelection(viewSelection)

        self.assertEquals(
            self.inbox.scrollingFragment.requestCurrentSize(),
            1)
