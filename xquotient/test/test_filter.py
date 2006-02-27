
from twisted.trial import unittest

from axiom import store

from xquotient import filter, mimepart

class HeaderRuleTest(unittest.TestCase):
    def setUp(self):
        self.store = store.Store()
        self.headerRule = filter.HeaderRule(
            store=self.store,
            headerName=u"subject",
            value=u"subjval",
            operation=filter.EQUALS)


    def _testImpl(self, same, notsame, casenotsame):

        def act(on):
            return self.headerRule.applyToHeaders([on])[:2]

        self.assertEquals(act(same), (True, True))
        self.assertEquals(act(notsame), (False, True))

        self.headerRule.negate = True

        self.assertEquals(act(same), (False, True))
        self.assertEquals(act(notsame), (True, True))

        self.headerRule.negate = False
        self.headerRule.shortCircuit = True

        self.assertEquals(act(same), (True, False))
        self.assertEquals(act(notsame), (False, True))

        self.headerRule.negate = True

        self.assertEquals(act(same), (False, True))
        self.assertEquals(act(notsame), (True, False))

        self.headerRule.negate = False
        self.headerRule.shortCircuit = False
        self.headerRule.caseSensitive = True

        self.assertEquals(act(same), (True, True))
        self.assertEquals(act(casenotsame), (False, True))
        self.assertEquals(act(notsame), (False, True))


    def testEquals(self):
        same = mimepart.Header(u"subject", u"subjval")
        notsame = mimepart.Header(u"subject", u"different")
        casenotsame = mimepart.Header(u"subject", u"Subjval")
        return self._testImpl(same, notsame, casenotsame)


    def testStartswith(self):
        same = mimepart.Header(u"subject", u"subjval goes here")
        notsame = mimepart.Header(u"subject", u"something else lala")
        casenotsame = mimepart.Header(u"subject", u"SUBJVAL IS THIS")
        self.headerRule.operation = filter.STARTSWITH
        return self._testImpl(same, notsame, casenotsame)


    def testEndswith(self):
        same = mimepart.Header(u"subject", u"here goes subjval")
        notsame = mimepart.Header(u"subject", u"something else lala")
        casenotsame = mimepart.Header(u"subject", u"THIS IS SUBJVAL")
        self.headerRule.operation = filter.ENDSWITH
        return self._testImpl(same, notsame, casenotsame)


    def testContains(self):
        same = mimepart.Header(u"subject", u"here subjval goes")
        notsame = mimepart.Header(u"subject", u"something else lala")
        casenotsame = mimepart.Header(u"subject", u"IS SUBJVAL THIS?")
        self.headerRule.operation = filter.CONTAINS
        return self._testImpl(same, notsame, casenotsame)
