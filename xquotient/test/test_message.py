import zipfile

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import text

from nevow import context
from nevow.testutil import AccumulatingFakeRequest as makeRequest
from nevow.test.test_rend import deferredRender

from xmantissa.webapp import PrivateApplication
from xquotient.exmess import Message, PartDisplayer, addMessageSource, getMessageSources


class UtilityTestCase(TestCase):
    """
    Test various utilities associated with L{exmess.Message}.
    """
    def test_sourceTracking(self):
        """
        Test that message sources added with L{addMessageSource} can be
        retrieved with L{getMessageSources} in alphabetical order.
        """
        s = Store()
        addMessageSource(s, u"one")
        addMessageSource(s, u"two")
        addMessageSource(s, u"three")
        self.assertEquals(
            list(getMessageSources(s)),
            [u"one", u"three", u"two"])


    def test_distinctSources(self):
        """
        Test that any particular message source is only returned once from
        L{getMessageSources}.
        """
        s = Store()
        addMessageSource(s, u"a")
        addMessageSource(s, u"a")
        self.assertEquals(list(getMessageSources(s)), [u"a"])



class MockPart:
    def __init__(self, filename, body):
        self.part = self
        self.filename = filename
        self.body = body

    def getBody(self, decode):
        return self.body



class PartItem(Item):
    typeName = 'xquotient_test_part_item'
    schemaVersion = 1

    contentType = text()
    body = text()

    def walkAttachments(self):
        return (MockPart('foo.bar', 'XXX'),
                MockPart('bar.baz', 'YYY'))

    def getContentType(self):
        assert self.contentType is not None
        return self.contentType

    def getUnicodeBody(self):
        assert self.body is not None
        return self.body



class MessageTestCase(TestCase):
    def testDeletion(self):
        s = Store()
        m = Message(store=s)
        m.deleteFromStore()

    def testAttachmentZipping(self):
        s = Store(self.mktemp())

        path = Message(store=s, impl=PartItem(store=s)).zipAttachments()

        zf = zipfile.ZipFile(path)
        zf.testzip()

        self.assertEqual(sorted(zf.namelist()), ['bar.baz', 'foo.bar'])

        self.assertEqual(zf.read('foo.bar'), 'XXX')
        self.assertEqual(zf.read('bar.baz'), 'YYY')



class WebTestCase(TestCase):
    def _testPartDisplayerScrubbing(self, input, scrub=True):
        """
        Set up a store, a PartItem with a body of C{input},
        pass it to the PartDisplayer, render it, and return
        a deferred that'll fire with the string result of
        the rendering.

        @param scrub: if False, the noscrub URL arg will
                      be added to the PartDisplayer request
        """
        s = Store()
        PrivateApplication(store=s).installOn(s)

        part = PartItem(store=s,
                        contentType=u'text/html',
                        body=input)

        pd = PartDisplayer(None)
        pd.item = part

        req = makeRequest()
        if not scrub:
            req.args = {'noscrub': True}

        return deferredRender(pd, req)

    def testPartDisplayerScrubbingDoesntAlterInnocuousHTML(self):
        """
        Test that PartDisplayer/scrubber doesn't alter HTML
        that doesn't contain anything suspicious
        """
        innocuousHTML = u'<html><body>hi</body></html>'
        D = self._testPartDisplayerScrubbing(innocuousHTML)
        D.addCallback(lambda s: self.assertEqual(s, innocuousHTML))
        return D

    suspectHTML = u'<html><script>hi</script><body>hi</body></html>'

    def testPartDisplayerScrubs(self):
        """
        Test that the PartDisplayer/scrubber alters HTML that
        contains suspicious stuff
        """
        D = self._testPartDisplayerScrubbing(self.suspectHTML)
        D.addCallback(lambda s: self.failIf('<script>' in s))
        return D

    def testPartDisplayerObservesNoScrubArg(self):
        """
        Test that the PartDisplayer doesn't alter suspicious HTML
        if it's told not to use the scrubber
        """
        D = self._testPartDisplayerScrubbing(self.suspectHTML, scrub=False)
        D.addCallback(lambda s: self.assertEqual(s, self.suspectHTML))
        return D
