
"""
Test that a version 1 MailTransferAgent in a site store is unchanged by
this upgrade but that in a user store it is replaced with a
MailDeliveryAgent.
"""

from twisted.mail.smtp import IMessageDeliveryFactory

from axiom.test.historic.stubloader import StubbedTest
from axiom.userbase import LoginSystem
from axiom.item import transacted

from xquotient.mail import MailTransferAgent, MailDeliveryAgent


class MailTransferAgentUpgradeTestCase(StubbedTest):
    def testUpgrade(self):
        mta = IMessageDeliveryFactory(self.store)
        self.failUnless(isinstance(mta, MailTransferAgent))

        loginSystem = self.store.findUnique(LoginSystem)
        account = loginSystem.accountByAddress(u'testuser', u'localhost')
        avatar = account.avatars.open()
        mda = avatar.transact(IMessageDeliveryFactory, account, None)
        self.failUnless(isinstance(mda, MailDeliveryAgent))
    testUpgrade = transacted(testUpgrade)
