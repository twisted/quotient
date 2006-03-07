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

VERBOSE = False

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
        id = self.storeID
        s = self.store
        def finalize():
            idx = d.get('_index', None)
            if idx is not None:
                if VERBOSE:
                    log.msg("Closing %r from finalizer of %s/%d" % (idx, s, id))
                idx.close()
        return finalize


    def activate(self):
        assert not hasattr(self, '_index')
        self._index = None
        if VERBOSE:
            log.msg("Activating %s/%d with null index" % (self.store, self.storeID))


    def installOn(self, other):
        super(SyncIndexer, self).installOn(other)
        self.store.findUnique(mail.MessageSource).addReliableListener(self, iaxiom.REMOTE)


    def suspend(self):
        if VERBOSE:
            log.msg("%s/%d suspending" % (self.store, self.storeID))
        self._closeIndex()
        return defer.succeed(None)


    def resume(self):
        if VERBOSE:
            log.msg("%s/%d resuming" % (self.store, self.storeID))
        return defer.succeed(None)


    def _getIndex(self, mode):
        if self._index is None:
            hypedir = self.store.newDirectory(HYPE_INDEX_DIR)
            self._index = hype.Database(hypedir.path, mode | hype.ESTDBCREAT)
            if VERBOSE:
                log.msg("Opened Hype %s/%d with mode %d" % (self.store, self.storeID, mode))
        return self._index


    def _closeIndex(self):
        if VERBOSE:
            log.msg("%s/%d closing index" % (self.store, self.storeID))
        if self._index is not None:
            if VERBOSE:
                log.msg("%s/%d *really* closing index" % (self.store, self.storeID))
            self._index.close()
            self._index = None


    def indexMessage(self, message):
        reactor.callLater(10, lambda: self)

        doc = hype.Document()
        doc.add_hidden_text(message.subject.encode('utf-8'))
        doc['@uri'] = message.storeID

        for part in message.impl.getTypedParts('text/plain', 'text/rtf'):
            doc.add_text(part.getUnicodeBody().encode('utf-8'))

        if VERBOSE:
            log.msg("%s/%d indexing document" % (self.store, self.storeID))
        self._getIndex(hype.ESTDBWRITER).put_doc(doc)
        self.indexCount += 1

    processItem = indexMessage


    def search(self, aString, count=None, offset=None):
        b = iaxiom.IBatchService(self.store)
        if VERBOSE:
            log.msg("%s/%d issueing suspend" % (self.store, self.storeID))
        d = b.suspend(self.storeID)

        def reallySearch(ign):
            if VERBOSE:
                log.msg("%s/%d getting reader index" % (self.store, self.storeID))
            idx = self._getIndex(hype.ESTDBREADER | hype.ESTDBLCKNB)
            try:
                results = idx.search(aString.encode('utf-8'))
                if count is not None and offset is not None:
                    results = results[offset:offset+count]
                return list(results)
            finally:
                self._closeIndex()
        d.addCallback(reallySearch)

        def resumeIndexing(results):
            if VERBOSE:
                log.msg("%s/%s issueing resume" % (self.store, self.storeID))
            b.resume(self.storeID).addErrback(log.err)
            return results
        d.addBoth(resumeIndexing)
        return d
