from axiom.test.historic import stubloader

from xmantissa.ixmantissa import IPreferenceAggregator
from xquotient.quotientapp import QuotientPreferenceCollection

class PrefsUpgradeTest(stubloader.StubbedTest):
    def testUpgrade(self):
        pc = self.store.findUnique(QuotientPreferenceCollection)

        def assertPrefs(**k):
            for (prefname, val) in k.iteritems():
                self.assertEquals(getattr(pc, prefname), val)

        assertPrefs(preferredMimeType='image/png',
                    preferredMessageDisplay='invisible',
                    showRead=False,
                    showMoreDetail=False)


