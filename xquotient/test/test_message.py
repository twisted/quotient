import zipfile

from twisted.trial.unittest import TestCase

from axiom.store import Store

from xquotient.exmess import Message, ZippedAttachments

class MockPart:
    def __init__(self, filename, body):
        self.part = self
        self.filename = filename
        self.body = body

    def getBody(self, decode):
        return self.body

class MockMessage:
    def __init__(self, attachmentParts):
        self.attachmentParts = attachmentParts

    def walkAttachments(self):
        return self.attachmentParts

class MessageTestCase(TestCase):
    def testDeletion(self):
        s = Store()
        m = Message(store=s)
        m.deleteFromStore()

    def testAttachmentZipping(self):
        s = Store(self.mktemp())
        z = ZippedAttachments(store=s)

        m = MockMessage((MockPart('foo.bar', 'XXX'),
                         MockPart('bar.baz', 'YYY')))

        path = z.getZippedAttachments(m)

        zf = zipfile.ZipFile(path)
        zf.testzip()

        self.assertEqual(sorted(zf.namelist()), ['bar.baz', 'foo.bar'])

        self.assertEqual(zf.read('foo.bar'), 'XXX')
        self.assertEqual(zf.read('bar.baz'), 'YYY')
