from twisted.application.service import IService
from twisted.trial.unittest import TestCase

from axiom.store import Store

from nevow.flat import flatten
from nevow.testutil import renderLivePage

from xmantissa.plugins.mailoff import indexingBenefactorFactory
from xmantissa import ixmantissa

from xquotient.quotientapp import INDEXER_TYPE
from xquotient.exmess import Message, splitAddress
from xquotient.test.util import MIMEReceiverMixin, PartMaker, ThemedFragmentWrapper

class MsgSearchTestCase(TestCase, MIMEReceiverMixin):
    def setUp(self):
        self.mimeReceiver = self.setUpMailStuff(
                             (indexingBenefactorFactory,))

        self.indexer = self.mimeReceiver.store.findUnique(INDEXER_TYPE)

    def _indexSomething(self, thing):
        writer = self.indexer.openWriteIndex()
        writer.add(thing)
        writer.close()

    def _makeSimpleMsg(self, bodyText):
        return self.mimeReceiver.feedStringNow(
                    PartMaker('text/plain', bodyText).make()).message

    def testBodySearch(self):
        """
        Test that we can search for tokens that appear in the body of an
        indexed message and get a meaningful result
        """
        msg = self._makeSimpleMsg(u'hello world')

        self._indexSomething(msg)

        reader = self.indexer.openReadIndex()
        self.assertEqual(list(reader.search(u'hello')), [msg.storeID])

    def testKeywordValuesInBodySearch(self):
        """
        Test that we can search for tokens that appear as the values of
        keywords of indexed messages, without specifying the keyword name, and
        get meaningful results
        """
        msg = self._makeSimpleMsg(u'')

        msg.subject = u'hello world'

        self._indexSomething(msg)

        reader = self.indexer.openReadIndex()
        self.assertEqual(list(reader.search(u'hello')), [msg.storeID])

    def testEmailAddressSplitter(self):
        """
        Ensure that we take an email address and break it on non-alphanumeric
        characters for indexing.
        """
        splitted = splitAddress('john.smith@alum.mit.edu')
        self.assertEqual(splitted, ['john', 'smith', 'alum', 'mit', 'edu'])

    def testKeywordSearch(self):
        """
        Test that we get the expected results when searching for messages by
        keyword name and value
        """
        msg = self._makeSimpleMsg(u'')

        msg.subject=u'hello world'
        msg.sender=u'foo@jethro.org'
        msg.senderDisplay=u'Fred Oliver Osgood'

        self._indexSomething(msg)

        reader = self.indexer.openReadIndex()
        self.assertEqual(list(reader.search(u'', {u'subject': u'world'})),
                         [msg.storeID])
        self.assertEqual(list(reader.search(u'', {u'sender': u'foo'})),
                         [msg.storeID])
        self.assertEqual(list(reader.search(u'', {u'sender': u'jethro'})),
                         [msg.storeID])
        self.assertEqual(list(reader.search(u'', {u'sender': u'osgood'})),
                         [msg.storeID])

class ViewTestCase(TestCase, MIMEReceiverMixin):
    def setUp(self):
        self.mimeReceiver = self.setUpMailStuff(
                                (indexingBenefactorFactory,))
        self.indexer = self.mimeReceiver.store.findUnique(INDEXER_TYPE)

    def testNoResults(self):
        """
        Test that the string 'no results' appears in the flattened HTML
        response to a search on an empty index
        """
        service = IService(self.indexer.store.parent)
        service.startService()

        def gotSearchResult((fragment,)):
            deferred = renderLivePage(ThemedFragmentWrapper(fragment))
            def rendered(res):
                self.assertIn('no results', res.lower())
                return service.stopService()
            return deferred.addCallback(rendered)

        s = self.indexer.store
        deferred = ixmantissa.ISearchAggregator(s).search(u'hi', {}, None, None)
        return deferred.addCallback(gotSearchResult)
