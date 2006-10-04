"""
Test that a ComposePreferenceCollection without smarthost attributes doesn't
turn into a FromAddress item
"""

from axiom.test.historic.stubloader import StubbedTest

from xquotient.compose import ComposePreferenceCollection, Composer, FromAddress

class ComposePreferenceCollectionUpgradeTestCase(StubbedTest):
    def testUpgrade(self):
        cpc = self.store.findUnique(ComposePreferenceCollection)
        composer = self.store.findUnique(Composer)

        newFrom = self.store.findUnique(
                    FromAddress,
                    # foo/bar are the localpart/domain of the LoginMethod
                    FromAddress.address == u'foo@bar')

        self.assertEqual(newFrom.smtpHost, None)
        self.assertEqual(newFrom.smtpUsername, None)
        self.assertEqual(newFrom.smtpPassword, None)
