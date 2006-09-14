
from decimal import Decimal

from zope.interface import implements

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import boolean

from xquotient.iquotient import IHamFilter
from xquotient.spam import Filter
from xquotient.mimestorage import Part
from xquotient.exmess import Message, _TrainingInstruction


class TestFilter(Item):
    """
    Ultra stupid classifier.  Always classifies every message as whatever you
    tell it to at creation time.
    """
    implements(IHamFilter)

    result = boolean(allowNone=False)

    def installOn(self, other):
        other.powerUp(self, IHamFilter)


    def classify(self, item):
        return self.result, 0



class FilterTestCase(TestCase):
    def test_postiniHeaderParsing(self):
        """
        Test that Postini's spam levels header can be parsed and structured
        data extracted from it.
        """
        f = Filter()
        self.assertEquals(
            f._parsePostiniHeader(
                '(S:99.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )'),
            {'S': Decimal('99.9'),
             'R': Decimal('95.9108'),
             'P': Decimal('91.9078'),
             'M': Decimal('100'),
             'C': Decimal('96.6797')})
        self.assertEquals(
            f._parsePostiniHeader(
                '(S: 0.0901 R:95.9108 P:95.9108 M:99.5542 C:79.5348 )'),
            {'S': Decimal('.0901'),
             'R': Decimal('95.9108'),
             'P': Decimal('95.9108'),
             'M': Decimal('99.5542'),
             'C': Decimal('79.5348')})

    def test_postiniHeaderWithWhitespace(self):
        """
        Test that a Postini header with leading or trailing whitespace can
        also be parsed correctly.  Headers like this probably shouldn't ever
        show up, but investigation of old messages indicates they seem to
        sometimes.
        """
        f = Filter()
        self.assertEquals(
            f._parsePostiniHeader(
                '  (S:99.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )  \r'),
            {'S': Decimal('99.9'),
             'R': Decimal('95.9108'),
             'P': Decimal('91.9078'),
             'M': Decimal('100'),
             'C': Decimal('96.6797')})


    def _messageWithPostiniHeader(self, header):
        part = Part()
        part.addHeader(u'X-pstn-levels', header)
        msg = Message(impl=part)
        return msg


    def test_postiniHeaderSpamFiltering(self):
        """
        Test that if a message has a low enough spam level in a Postini
        C{X-pstn-levels} header and the Filter has been configured to use it,
        it is classified as spam.
        """
        msg = self._messageWithPostiniHeader(
            u'(S: 0.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )')
        msg.trained = False
        f = Filter(usePostiniScore=True, postiniThreshhold=1.0)
        f.processItem(msg)
        self.failUnless(msg.spam)


    def test_postiniHeaderHamFiltering(self):
        """
        Test that if a message has a high enough spam level in a Postini
        C{X-pstn-levels} header and the Filter has been configured to use it,
        it is classified as ham.
        """
        msg = self._messageWithPostiniHeader(
            u'(S:90.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )')
        msg.trained = False
        f = Filter(usePostiniScore=True, postiniThreshhold=1.0)
        f.processItem(msg)
        self.failIf(msg.spam)


    def test_disablePostiniSpamFiltering(self):
        """
        Test that if C{usePostiniScore} is False the header is ignored and
        another filter is consulted.
        """
        self.store = Store()
        msg = self._messageWithPostiniHeader(
            u'(S:90.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )')
        msg.trained = False
        f = Filter(store=self.store, usePostiniScore=False, postiniThreshhold=None)
        TestFilter(store=self.store, result=True).installOn(f)
        f.processItem(msg)
        self.failUnless(msg.spam)


    def test_disablePostiniHamFiltering(self):
        """
        Test that if C{usePostiniScore} is False the header is ignored and
        another filter is consulted.
        """
        self.store = Store()
        msg = self._messageWithPostiniHeader(
            u'(S: 0.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )')
        msg.trained = False
        f = Filter(store=self.store, usePostiniScore=False, postiniThreshhold=None)
        TestFilter(store=self.store, result=False).installOn(f)
        f.processItem(msg)
        self.failIf(msg.spam)


    def test_postiniRespectsTraining(self):
        """
        If a user trains a message as ham or spam, the postini code should not
        clobber that value, even though postini is not really trainable itself.
        """
        self.store = Store()
        msg = self._messageWithPostiniHeader(
            u'(S:99.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )')
        msg.trained = True
        msg.spam = True
        f = Filter(store=self.store, usePostiniScore=True, postiniThreshhold=1.0)
        f.processItem(msg)
        self.failUnless(msg.spam)
        self.failUnless(msg.trained)

    def test_processTrainingInstructions(self):
        """
        When a user trains a message, a _TrainingInstruction item gets
        created to signal the batch processor to do the training. Make
        that gets run OK.
        """
        self.store = Store()
        f = Filter(store=self.store, usePostiniScore=True, postiniThreshhold=1.0)
        ti = _TrainingInstruction(store=self.store, spam=True)
        f.processItem(ti)
