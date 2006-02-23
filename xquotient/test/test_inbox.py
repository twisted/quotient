from twisted.trial.unittest import TestCase

from xmantissa.scrolltable import ScrollingFragment

from xquotient.inbox import Inbox

from axiom.item import Item
from axiom.store import Store
from axiom import attributes

class SimpleMessage(Item):
    typeName = 'simple_message'
    schemaVersion = 1

    read = attributes.boolean()
    index = attributes.integer()

class _ScrollingFragment(ScrollingFragment):
    def __init__(self, *a, **k):
        ScrollingFragment.__init__(self, *a, **k)
        self.queryRanges = []

    def performQuery(self, start, stop):
        self.queryRanges.append((start, stop))
        return ScrollingFragment.performQuery(self, start, stop)

class FindNextUnreadTestCase(TestCase):
    def setUp(self):
        s = Store()
        self.msgs = []
        for i in xrange(29):
            self.msgs.append(SimpleMessage(store=s, index=i, read=True))
        self.msgs.append(SimpleMessage(store=s, index=29, read=False))

        self.sf = _ScrollingFragment(s, SimpleMessage, None, ['index'])
        self.inbox = Inbox(store=s)


    def testNextUnreadSimple(self):
        # test the case where the current result set of the
        # scroll table contains the next unread message
        self.sf.performQuery(20, 30)
        # let's say the message before the only unread message
        # is the current message
        msg = self.inbox.findNextUnread(self.sf, self.msgs[-2], perPage=10)
        self.failIf(msg.read)
        # make sure nobody besides us called performQuery(),
        # because it's not necessary in this case
        self.assertEqual(self.sf.queryRanges, [(20, 30)])

    def testNextUnread(self):
        # ensure the result set is empty
        self.sf.performQuery(0, 0)
        # set the furthest message from the target as the
        # current message
        msg = self.inbox.findNextUnread(self.sf, self.msgs[0], perPage=10)
        self.failIf(msg.read)
        self.assertEqual(self.sf.queryRanges, [(0, 0), (0, 10), (10, 20), (20, 30)])

    def testNextUnreadAgain(self):
        # empty the result set
        self.sf.performQuery(0, 0)
        # set the unread message to be on the second page
        self.msgs[-1].read = True
        self.msgs[12].read = False
        # set the current message to be the first one
        msg = self.inbox.findNextUnread(self.sf, self.msgs[0], perPage=10)
        self.failIf(msg.read)
        # make sure we didn't query past the item we need
        self.assertEqual(self.sf.queryRanges, [(0, 0), (0, 10), (10, 20)])

    def testAllUnread(self):
        for msg in self.msgs:
            msg.read = False
        self.sf.performQuery(0, 0)
        self.msgs[0].read = True
        msg = self.inbox.findNextUnread(self.sf, self.msgs[0], perPage=10)
        self.assertIdentical(msg.index, self.msgs[1].index)
        self.msgs[1].read = True
        msg = self.inbox.findNextUnread(self.sf, self.msgs[1], perPage=10)
        self.assertIdentical(msg.index, self.msgs[2].index)
