"""
Test that a ComposePreferenceCollection with smarthost attributes set turns
into a FromAddress item, and doesn't overwrite the FromAddress created from
the user's login credentials
"""

from axiom.test.historic.stubloader import StubbedTest

from xquotient.compose import ComposePreferenceCollection, Composer, FromAddress

class ComposePreferenceCollectionUpgradeTestCase(StubbedTest):
    def testUpgrade(self):
        cpc = self.store.findUnique(ComposePreferenceCollection)
        composer = self.store.findUnique(Composer)

        newFrom = self.store.findUnique(
                    FromAddress,
                    # this is the value of cpc.smarthostAddress in the database
                    FromAddress.address == u'foo2@bar')

        # these are the values of the smarthost* attributes on the in-database cpc
        self.assertEqual(newFrom.smtpHost, u'localhost')
        self.assertEqual(newFrom.smtpPort, 23)
        self.assertEqual(newFrom.smtpUsername, u'foo2')
        self.assertEqual(newFrom.smtpPassword, u'secret')

        self.store.findUnique(FromAddress, FromAddress.address == u'foo@bar')
