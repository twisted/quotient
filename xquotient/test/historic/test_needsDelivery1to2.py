"""
Test that attributes are preserved, and fromAddress is set to None for
_NeedsDelivery version 2
"""

from axiom.test.historic.stubloader import StubbedTest

from xquotient.compose import _NeedsDelivery, Composer

class NeedsDeliveryUpgradeTestCase(StubbedTest):
    def testUpgrade(self):
        nd = self.store.findUnique(_NeedsDelivery)
        self.assertIdentical(nd.fromAddress, None)
        self.assertIdentical(nd.composer, self.store.findUnique(Composer))
        self.assertEqual(nd.tries, 21)
        self.assertIdentical(nd.message, self.store)
        self.assertEqual(nd.toAddress, 'to@host')
