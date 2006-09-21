from twisted.application.service import IService
from twisted.trial.unittest import TestCase

from axiom.store import Store

from xquotient.quotientapp import INDEXER_TYPE
from xmantissa.plugins.mailoff import indexingBenefactorFactory
from xquotient.exmess import Message
from xquotient.test.util import MIMEReceiverMixin, PartMaker

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

    def testKeywordSearch(self):
        """
        Test that we get the expected results when searching for messages by
        keyword name and value
        """
        msg = self._makeSimpleMsg(u'')

        msg.subject=u'hello world'

        self._indexSomething(msg)

        reader = self.indexer.openReadIndex()
        self.assertEqual(list(reader.search(u'', {u'subject': u'world'})),
                         [msg.storeID])
