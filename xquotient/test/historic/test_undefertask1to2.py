from zope.interface import implements

from epsilon.extime import Time

from axiom.iaxiom import IScheduler
from axiom.item import Item
from axiom.test.historic.stubloader import StubbedTest

from xquotient.exmess import _UndeferTask, Message, INBOX_STATUS, CLEAN_STATUS
from xquotient.test.historic.stub_undefertask1to2 import FakeScheduler
from xquotient.test.historic import stub_undefertask1to2



class UndeferTaskTest(StubbedTest):
    def setUp(self):
        stub_undefertask1to2.SCHEDULE_LOG = []
        return StubbedTest.setUp(self)


    def getStatuses(self):
        """
        @return: A C{set} of statuses for the deferred message.
        """
        return set(self.store.findFirst(Message).iterStatuses())


    def test_correctScheduling(self):
        """
        Check that the old task has been unscheduled and the new task has been
        scheduled.
        """
        task = self.store.findFirst(_UndeferTask)
        self.assertEqual(list(zip(*stub_undefertask1to2.SCHEDULE_LOG)[0]),
                          ['unschedule', 'schedule'])
        self.assertEqual(stub_undefertask1to2.SCHEDULE_LOG[-1][1], task)
        self.assertNotEqual(stub_undefertask1to2.SCHEDULE_LOG[0][1], task)


    def test_notInInbox(self):
        """
        Test that the deferred message is not in the inbox.
        """
        stats = self.getStatuses()
        self.failIfIn(INBOX_STATUS, stats)


    def test_inAll(self):
        """
        Test that the deferred message does appear in the "all" view.
        """
        stats = self.getStatuses()
        self.failUnlessIn(CLEAN_STATUS, stats)


    def test_notFrozen(self):
        """
        Test that the deferred message is not 'frozen' with
        L{Message.freezeStatus}.
        """
        # NOTE: This is added as documentation, not TDD -- it passes already.
        for status in self.getStatuses():
            self.failIf(status.startswith('.'))
