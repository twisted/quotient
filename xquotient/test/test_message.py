import zipfile

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import text

from nevow.test.test_rend import req
from nevow import context

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
    def testPartDisplayerScrubs(self):
        s = Store()

        PrivateApplication(store=s).installOn(s)

        innocuousHTML = u'<html><body>hi</body></html>'
        part = PartItem(store=s,
                        contentType=u'text/html',
                        body=innocuousHTML)

        pd = PartDisplayer(None)
        pd.item = part

        def render(resource, request=None):
            if request is None:
                request = req()
            return pd.renderHTTP(
                    context.PageContext(
                        tag=pd, parent=context.RequestContext(
                            tag=request)))

        self.assertEquals(render(pd), innocuousHTML)

        suspectHTML = u'<html><script>hi</script><body>hi</body></html>'
        part.body = suspectHTML

        res = render(pd)
        self.failIf('<script>' in res)

        myreq = req()
        myreq.args = {'noscrub': 1}
        self.assertEquals(render(pd, myreq), suspectHTML)
