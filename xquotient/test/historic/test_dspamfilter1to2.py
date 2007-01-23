from axiom.test.historic import stubloader
from xquotient.spam import DSPAMFilter, Filter


class DSPAMFilterTestCase(stubloader.StubbedTest):
    def testUpgrade(self):
        """
        Ensure upgraded fields refer to correct items.
        """
        self.assertEqual(self.store.findUnique(DSPAMFilter).filter,
                         self.store.findUnique(Filter))
