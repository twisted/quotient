try:
    import hype
except ImportError:
    hype = None

from axiom.item import Item
from axiom import attributes

HYPE_INDEX_DIR = 'hype.index'

class SyncIndexer(Item):
    """
    Implements a synchronous in-process full-text indexer.
    """

    schemaVersion = 1
    typeName = 'quotient_syncindexer'
    indexCount = attributes.integer(default=0)

    def indexMessage(self, message):
        if hype is None:
            return
        doc = hype.Document()
        doc.add_hidden_text(message.subject.encode('utf-8'))
        doc['@uri'] = message.storeID

        for part in message.impl.getTypedParts('text/plain', 'text/rtf'):
            doc.add_text(part.getUnicodeBody().encode('utf-8'))

        hypedir = self.store.newDirectory(HYPE_INDEX_DIR)
        hypeindex = hype.Database(hypedir.path)
        hypeindex.put_doc(doc)
        hypeindex.close()
        self.indexCount += 1

    def search(self, aString, count=None, offset=None):
        if hype is None:
            return []
        hypedir = self.store.newDirectory(HYPE_INDEX_DIR)
        hypeindex = hype.Database(hypedir.path, hype.ESTDBREADER)
        results = hypeindex.search(aString.encode('utf-8'))
        if count is not None and offset is not None:
            results = results[offset:offset+count]
        results = list(results)
        hypeindex.close()
        return results
