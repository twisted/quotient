from twisted.trial.unittest import TestCase

from axiom.store import Store

from xquotient.exmess import Message

class MessageTestCase(TestCase):
    def testDeletion(self):
        s = Store()
        m = Message(store=s)
        m.deleteFromStore()

