try:
    import hype
except ImportError:
    hype = None

from twisted.python import log
from twisted.internet import defer, reactor

from axiom.item import Item, InstallableMixin
from axiom import attributes, iaxiom

from xquotient import mail

HYPE_INDEX_DIR = 'hype.index'

class SyncIndexer(Item, InstallableMixin):
    """
    Implements a full-text indexer.

    Indexing is performed using the Axiom REMOTE batching mechanism.  Searches
    are performed synchronously in the main process.
    """

    schemaVersion = 1
    typeName = 'quotient_syncindexer'
    indexCount = attributes.integer(default=0)

    _index = attributes.inmemory()


    def __repr__(self):
        return '<SyncIndexer %d>' % (self.storeID,)


    def __finalizer__(self):
        d = self.__dict__
        def finalize():
            idx = d.get('_index', None)
            if idx is not None:
                idx.close()
        return finalize


    def activate(self):
        assert not hasattr(self, '_index')
        self._index = None


    def installOn(self, other):
        super(SyncIndexer, self).installOn(other)
        self.store.findUnique(mail.MessageSource).addReliableListener(self, iaxiom.REMOTE)


    def suspend(self):
        self._closeIndex()
        return defer.succeed(None)


    def resume(self):
        return defer.succeed(None)


    def _getIndex(self):
        if self._index is None:
            hypedir = self.store.newDirectory(HYPE_INDEX_DIR)
            self._index = hype.Database(hypedir.path)
        return self._index


    def _closeIndex(self):
        if self._index is not None:
            self._index.close()
            self._index = None


    def indexMessage(self, message):
        reactor.callLater(10, lambda: self)

        doc = hype.Document()
        doc.add_hidden_text(message.subject.encode('utf-8'))
        doc['@uri'] = message.storeID

        for part in message.impl.getTypedParts('text/plain', 'text/rtf'):
            doc.add_text(part.getUnicodeBody().encode('utf-8'))

        self._getIndex().put_doc(doc)
        self.indexCount += 1

    processItem = indexMessage


    def search(self, aString, count=None, offset=None):
        b = iaxiom.IBatchService(self.store)
        d = b.suspend(self.storeID)

        def reallySearch(ign):
            idx = self._getIndex()
            try:
                results = idx.search(aString.encode('utf-8'))
                if count is not None and offset is not None:
                    results = results[offset:offset+count]
                return list(results)
            finally:
                self._closeIndex()
        d.addCallback(reallySearch)

        def resumeIndexing(results):
            b.resume(self.storeID).addErrback(log.err)
            return results
        d.addBoth(resumeIndexing)
        return d
