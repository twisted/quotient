from axiom.test.historic import stubloader
from xquotient.test.historic.stub_message1to2 import attrs
from xquotient.exmess import Message
from xquotient.mimestorage import Part

class MessageUpgradeTest(stubloader.StubbedTest):
    def testUpgrade(self):
        m = self.store.findUnique(Message)
        for (k, v) in attrs.iteritems():
            self.assertEquals(v, getattr(m, k))
        self.assertIdentical(self.store.findUnique(Part), m.impl)
        self.failIf(m.everDeferred)
