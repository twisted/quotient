
"""
Test that a version 1 POP3UID is unchanged by the upgrade except that it gains a
value for the new C{retrieved} attribute set to something near the current time.
"""

from epsilon.extime import Time

from axiom.userbase import LoginSystem
from axiom.test.historic.stubloader import StubbedTest

from xquotient.test.historic.stub_pop3uid1to2 import VALUE, FAILED, GRABBER_ID
from xquotient.grabber import POP3UID

class POP3UIDUpgradeTestCase(StubbedTest):
    def test_attributes(self):
        loginSystem = self.store.findUnique(LoginSystem)
        account = loginSystem.accountByAddress(u'testuser', u'localhost')
        subStore = account.avatars.open()

        d = subStore.whenFullyUpgraded()
        def upgraded(ignored):
            [pop3uid] = list(subStore.query(POP3UID))
            self.assertEqual(VALUE, pop3uid.value)
            self.assertEqual(FAILED, pop3uid.failed)
            self.assertEqual(GRABBER_ID, pop3uid.grabberID)

            # This will be close enough.
            elapsed = (Time() - pop3uid.retrieved).total_seconds()
            self.assertTrue(abs(elapsed) < 60)
        d.addCallback(upgraded)
        return d
