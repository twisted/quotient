
from twisted.trial import unittest
from twisted.python.filepath import FilePath

from axiom import store, tags, scheduler

from xquotient import filter, mimepart, mail
from xquotient.mimestorage import Part
from xquotient.exmess import Message


class HeaderRuleTest(unittest.TestCase):
    def setUp(self):
        self.storepath = self.mktemp()
        self.store = store.Store(self.storepath)
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

    def testMailingListFilter(self):
        """
        Ensures that mailing list messages are not handled by
        RuleFilteringPowerup but are handled by MailingListFilteringPowerup.
        """
        self.tagcatalog = tags.Catalog(store=self.store)
        scheduler.Scheduler(store=self.store).installOn(self.store)
        mail.MessageSource(store=self.store)
        mlfb = filter.MailingListFilterBenefactor(store=self.store)
        rfb = filter.RuleFilterBenefactor(store=self.store)

        part = Part()
        part.addHeader(u'X-Mailman-Version', u"2.1.5")
        part.addHeader(u'List-Id',
                       u"Some mailing list <some-list.example.com>")
        part.source = FilePath(self.storepath).child("files").child("x")
        msg = Message.createIncoming(self.store, part,
                                     u'test://test_mailing_list_filter')
        rfb.endow(None, self.store)
        rfp = self.store.findUnique(filter.RuleFilteringPowerup)
        rfp.processItem(msg)
        self.assertEqual(list(self.tagcatalog.tagsOf(msg)), [])
        mlfb.endow(None, self.store)
        mlfp = self.store.findUnique(filter.MailingListFilteringPowerup)
        mlfp.processItem(msg)
        self.assertEqual(list(self.tagcatalog.tagsOf(msg)),
                         [u'some-list.example.com'])
