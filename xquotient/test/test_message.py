import zipfile

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import text

from xquotient.exmess import Message

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

    z = text()

    def walkAttachments(self):
        return (MockPart('foo.bar', 'XXX'),
                MockPart('bar.baz', 'YYY'))

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
