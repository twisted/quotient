from twisted.trial.unittest import TestCase

from epsilon.extime import Time

from axiom.store import Store

from xmantissa.ixmantissa import INavigableFragment
from xmantissa.webapp import PrivateApplication

from xquotient.exmess import Message
from xquotient.inbox import Inbox, replaceControlChars


class InboxTestCase(TestCase):
    def testControlChars(self):
        s = ''.join(map(chr, range(1, 32))) + 'foobar'
        # ord('\t') < ord('\n') < ord('\r')
        self.assertEquals(replaceControlChars(s), '\t\n\rfoobar')

    def testUnreadMessageCount(self):
        s = Store()

        for i in xrange(13):
            Message(store=s, read=False, spam=False, receivedWhen=Time())
        for i in xrange(6):
            Message(store=s, read=True, spam=False, receivedWhen=Time())

        PrivateApplication(store=s).installOn(s) # IWebTranslator

        # *seems* like we shouldn't have to adapt Inbox, but
        # the view state variables (inAllView, inSpamView, etc)
        # seem pretty clearly to belong on InboxScreen, carrying
        # most of the interesting methods with them

        # we're in the "Inbox" view

        inboxScreen = INavigableFragment(Inbox(store=s))
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
        inboxScreen = INavigableFragment(Inbox(store=s))
        self.assertEqual(inboxScreen.getCurrentViewName(), 'Inbox')

        def assertCountsAre(**d):
            for k in ('Trash', 'Sent', 'Spam', 'All', 'Inbox'):
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
        inboxScreen = INavigableFragment(Inbox(store=s))

        for view in ('Inbox', 'All', 'Spam', 'Trash', 'Sent'):
            inboxScreen.changeView(view)
            self.assertEqual(inboxScreen.getCurrentViewName(), view)
