
from datetime import datetime, timedelta

from twisted.trial.unittest import TestCase

from epsilon.extime import Time

from axiom.store import Store
from axiom.scheduler import Scheduler

from xmantissa.ixmantissa import INavigableFragment
from xmantissa.webapp import PrivateApplication
from xmantissa.webtheme import getLoader

from xquotient.exmess import Message
from xquotient.inbox import Inbox, InboxScreen, replaceControlChars, UndeferTask


class MessageRetrievalTestCase(TestCase):
    """
    Test various methods for finding messages.
    """
    def setUp(self):
        """
        Create a handful of messages spread out over a brief time period so
        that tests can assert things about methods which operate on messages.
        """
        s = Store()

        # Inbox requires but does not provide IWebTranslator.
        PrivateApplication(store=s).installOn(s)

        baseTime = datetime(year=2001, month=3, day=6)
        self.msgs = []
        for i in xrange(5):
            self.msgs.append(
                Message(store=s,
                        read=False,
                        spam=False,
                        receivedWhen=Time.fromDatetime(
                            baseTime + timedelta(seconds=i))))
        self.inbox = InboxScreen(Inbox(store=s))


    def testGetFirstMessage(self):
        """
        Test that InboxScreen.getFirstMessage returns the first message,
        ordered by received time.
        """
        self.assertIdentical(self.msgs[0], self.inbox.getFirstMessage())


    def testGetLastMessage(self):
        """
        Test that InboxScreen.getLastMessage returns the last message, ordered
        by received time.
        """
        self.assertIdentical(self.msgs[-1], self.inbox.getLastMessage())


    def testGetMessageAfter(self):
        """
        Test that the next message, chronologically, is returned by
        InboxScreen.getMessageAfter.  Also test that None is returned if there
        is no such message.
        """
        self.assertIdentical(self.msgs[1],
                             self.inbox.getMessageAfter(self.msgs[0]))
        self.assertIdentical(None,
                             self.inbox.getMessageAfter(self.msgs[-1]))


    def testGetMessageBefore(self):
        """
        Test that the previous message, chronologically, is returned by
        InboxScreen.getMessageBefore.  Also test that None is returned if there
        is no such message.
        """
        self.assertIdentical(self.msgs[-2],
                             self.inbox.getMessageBefore(self.msgs[-1]))
        self.assertIdentical(None,
                             self.inbox.getMessageBefore(self.msgs[0]))


    def testGetFirstMessageWithFlags(self):
        """
        Test that messages which do not satisfy the view requirements of the
        inbox are not considered for return by InboxScreen.getFirstMessage.
        """
        self.msgs[0].archived = True
        self.assertIdentical(self.msgs[1], self.inbox.getFirstMessage())


    def testGetLastMessageWithFlags(self):
        """
        Test that messages which do not satisfy the view requirements of the
        inbox are not considered for return by InboxScreen.getLastMessage.
        """
        self.msgs[-1].archived = True
        self.assertIdentical(self.msgs[-2], self.inbox.getLastMessage())


    def testGetMessageAfterWithFlags(self):
        """
        Test that messages which do not satisfy the view requirements of the
        inbox are not considered for return by InboxScreen.getMessageAfter.
        """
        self.msgs[1].archived = True
        self.assertIdentical(self.msgs[2], self.inbox.getMessageAfter(self.msgs[0]))


    def testGetMessageBeforeWithFlags(self):
        """
        Test that messages which do not satisfy the view requirements of the
        inbox are not considered for return by InboxScreen.getMessageAfter.
        """
        self.msgs[-2].archived = True
        self.assertIdentical(self.msgs[-3], self.inbox.getMessageBefore(self.msgs[-1]))



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
        self.assertEqual(inboxScreen.getUnreadMessageCount(), 13)
        s.findFirst(Message, Message.read == True).read = False
        self.assertEqual(inboxScreen.getUnreadMessageCount(), 14)

        inboxScreen.changeView('Spam')
        self.assertEqual(inboxScreen.getUnreadMessageCount(), 0)

        spam = []
        for m in s.query(Message, Message.read == False, limit=6):
            m.spam = True
            spam.append(m)

        self.assertEqual(inboxScreen.getUnreadMessageCount(), 6)

        for m in spam:
            m.spam = False
        m.archived = True

        self.assertEqual(inboxScreen.getUnreadMessageCount(), 0)

        inboxScreen.changeView('All')

        self.assertEqual(inboxScreen.getUnreadMessageCount(), 14)

        inboxScreen.changeView('Sent')

        self.assertEqual(inboxScreen.getUnreadMessageCount(), 0)

        m.archived = False
        m.outgoing = True

        self.assertEqual(inboxScreen.getUnreadMessageCount(), 1)

        inboxScreen.changeView('Inbox')

        self.assertEqual(inboxScreen.getUnreadMessageCount(), 13)

    def testMailViewCounts(self):
        s = Store()

        for i in xrange(9):
            Message(store=s, read=False, spam=False, receivedWhen=Time())
        for i in xrange(3):
            Message(store=s, read=False, spam=False, archived=True, receivedWhen=Time())

        PrivateApplication(store=s).installOn(s)
        inboxScreen = InboxScreen(Inbox(store=s))
        self.assertEqual(inboxScreen.getCurrentViewName(), 'Inbox')

        def assertCountsAre(**d):
            for k in ('Trash', 'Sent', 'Spam', 'All', 'Inbox', 'Deferred'):
                if not k in d:
                    d[k] = 0
            self.assertEqual(inboxScreen.mailViewCounts(), d)

        # the Inbox will mark the first Message in it's query as read,
        # so we subtract one from the expected counts

        assertCountsAre(Inbox=8, All=11)

        for i in xrange(4):
            Message(store=s, read=False, spam=True, receivedWhen=Time())
        for i in xrange(3):
            Message(store=s, read=True, spam=True, receivedWhen=Time())

        assertCountsAre(Inbox=8, All=11, Spam=4)

        for i in xrange(2):
            Message(store=s, read=False, trash=True, receivedWhen=Time())

        assertCountsAre(Inbox=8, All=11, Spam=4, Trash=2)

        for i in xrange(4):
            Message(store=s, read=False, outgoing=True, receivedWhen=Time())

        assertCountsAre(Inbox=8, All=11, Spam=4, Trash=2, Sent=4)
        self.assertEqual(inboxScreen.getCurrentViewName(), 'Inbox')

    def testViewSwitching(self):
        s = Store()
        PrivateApplication(store=s).installOn(s)
        inboxScreen = InboxScreen(Inbox(store=s))

        for view in ('Inbox', 'All', 'Spam', 'Trash', 'Sent'):
            inboxScreen.changeView(view)
            self.assertEqual(inboxScreen.getCurrentViewName(), view)

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
        PrivateApplication(store=s).installOn(s)

        msgs = list(Message(store=s,
                            subject=unicode(str(i)),
                            spam=False,
                            receivedWhen=Time(),
                            sentWhen=Time(),
                            impl=None)
                        for i in xrange(5))
        msgs.reverse()

        self.inboxScreen = InboxScreen(Inbox(store=s))
        self.msgs = msgs

    def assertMsgSubjectsAre(self, s1, s2):
        self.assertEquals(self.inboxScreen.currentMessage.subject, s1)
        self.assertEquals(self.inboxScreen.nextMessage.subject, s2)

    def testLookahead(self):
        """
        Test that the one message lookahead feature of the inbox
        works in the right direction (from newest message to oldest).
        We test this in two places: after instantiating InboxScreen,
        where the currentMessage and nextMessage attributes are initially
        set, and after calling InboxScreen.selectMessage(), which changes
        both attributes
        """

        self._setUpInbox()
        assertMsgSubjectsAre = self.assertMsgSubjectsAre
        msgs = self.msgs
        inboxScreen =self.inboxScreen

        # '4' is the newest message
        assertMsgSubjectsAre('4', '3')
        inboxScreen.selectMessage(msgs[1])
        assertMsgSubjectsAre('3', '2')
        inboxScreen.selectMessage(msgs[2])
        assertMsgSubjectsAre('2', '1')
        inboxScreen.selectMessage(msgs[3])
        assertMsgSubjectsAre('1', '0')
        inboxScreen.selectMessage(msgs[4])
        assertMsgSubjectsAre('0', '1')

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
        assertMsgSubjectsAre = self.assertMsgSubjectsAre
        inboxScreen = self.inboxScreen

        # XXX this is a temporary hack.  ideally the methods
        # we are calling would live on the model, and we wouldn't
        # need to set up a bunch of rendering junk or whatever
        # in order to archive a message and progress to the next
        # message, but they don't, and it's a substantial refactoring.
        # for now we'll kill the method that does all of the
        # annoying things

        inboxScreen._current = lambda: None

        assertMsgSubjectsAre('4', '3')
        inboxScreen.archiveCurrentMessage(advance=True)
        assertMsgSubjectsAre('3', '2')
        inboxScreen.archiveCurrentMessage(advance=True)
        assertMsgSubjectsAre('2', '1')
        inboxScreen.archiveCurrentMessage(advance=True)
        assertMsgSubjectsAre('1', '0')
        inboxScreen.archiveCurrentMessage(advance=True)
        self.assertEquals(inboxScreen.currentMessage.subject, '0')
        self.failUnless(inboxScreen.nextMessage is None)
        inboxScreen.archiveCurrentMessage(advance=True)
        self.failUnless(inboxScreen.currentMessage is None)
        self.failUnless(inboxScreen.nextMessage is None)

    def testLookaheadWithActionsLastMessage(self):
        """
        Similar to L{testLookaheadWithActions}, but only
        dismiss the penultimate message, asserting that
        afterwards, the lookahead correctly points to the
        pre-penultimate message
        """

        self._setUpInbox()
        assertMsgSubjectsAre = self.assertMsgSubjectsAre
        inboxScreen = self.inboxScreen

        # XXX see comment in L{testLookaheadWithActions}

        inboxScreen._current = lambda: None

        assertMsgSubjectsAre('4', '3')
        inboxScreen.selectMessage(self.msgs[3])
        assertMsgSubjectsAre('1', '0')
        inboxScreen.archiveCurrentMessage(advance=True)
        assertMsgSubjectsAre('0', '2')
