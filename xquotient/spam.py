# -*- test-case-name: xquotient.test.test_spam -*-

import cPickle, errno
from decimal import Decimal
import sqlite3

from spambayes import hammie, classifier

from zope.interface import implements

from twisted.python import log, components
from twisted.internet.task import coiterate

from nevow import athena

from axiom import iaxiom, item, attributes, userbase
from axiom.upgrade import registerAttributeCopyingUpgrader
from axiom.dependency import dependsOn
from axiom.upgrade import registerUpgrader

from xmantissa import ixmantissa, liveform
from xmantissa.webtheme import ThemedFragment, getLoader

from xquotient import iquotient
from xquotient.mail import MessageSource
from xquotient.exmess import (_TrainingInstructionSource, _TrainingInstruction,
                              Message, TRAINED_STATUS, MailboxSelector)
from xquotient.equotient import NoSuchHeader

try:
    from xquotient import dspam
    dspam                       # shut up, pyflakes
except ImportError:
    dspam = None

SPAM_THRESHHOLD = 0.3

class Filter(item.Item):
    """
    Aggregates message classification tools and calls appropriate methods on
    Message objects according to their results.

    Items will power this up for L{iquotient.IHamFilter} to participate in the
    spam/ham classification process.  Only one Filter is currently supported.
    Future versions may expand on this and allow multiple filters to contribute
    to the final decision.  These items will also receive training feedback
    from the user, though they may choose to disregard it if they are not
    trainable.

    C{Filter} can also be configured to just look at Postini headers and make a
    determination based on them.
    """
    schemaVersion = 4

    usePostiniScore = attributes.boolean(doc="""
    Indicate whether or not to classify based on Postini headers.
    """, default=False, allowNone=False)

    postiniThreshhold = attributes.ieee754_double(doc="""
    A C{float} between 0 and 100 indicating at what Postini level messages are
    considered spam.
    """, default=0.03)

    _filters = attributes.inmemory()
    messageSource = dependsOn(MessageSource)
    tiSource = dependsOn(_TrainingInstructionSource)

    def installed(self):
        self.messageSource.addReliableListener(self, style=iaxiom.REMOTE)
        self.tiSource.addReliableListener(self, style=iaxiom.REMOTE)

    def processItem(self, item):
        assert isinstance(item, (_TrainingInstruction, Message))
        if isinstance(item, _TrainingInstruction):
            self._train(item)
        else:
            self._classify(item)


    def _filters(self):
        return list(self.store.powerupsFor(iquotient.IHamFilter))


    def _train(self, instruction):
        for f in self._filters():
            f.train(instruction.spam, instruction.message)
        instruction.deleteFromStore()


    def _parsePostiniHeader(self, s):
        """
        Postini spam headers look like this:
        X-pstn-levels: (S:99.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )
        X-pstn-levels: (S: 0.0901 R:95.9108 P:95.9108 M:99.5542 C:79.5348 )
        X-pstn-levels: (S:99.9000/99.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )
        S means "spam level".  Smaller is spammier. Value after the slash is
        the 'blatant spam blocking' score, ignored by this code.

        R means "Racially insensitive spam score"
        P means "Sexually explicit (pornography) spam score"
        M means "Make-money-fast (MMF) spam score"
        C means "Commercial or 'special offer' spam score"

        @return: A mapping from 'R', 'P', 'M', 'C', and 'S' to the values
        from the header, or None if the header could not be parsed.
        """
        s = s.strip()
        if s[:1] == '(' and s[-1:] == ')':
            parts = filter(None, s[1:-1].replace(':', ' ').split())
            if '/' in parts[1]:
                parts[1], _ = parts[1].split('/')
            return dict((parts[i], Decimal(parts[i + 1]))
                        for i
                        in (0, 2, 4, 6, 8))
        return None


    def _classify(self, msg):
        if not msg.shouldBeClassified:
            log.msg("Skipping classification of message already user-specified as "
                    + msg.spamStatus())
            return

        # Allow Postini to override anything we might determine, if the user
        # has indicated that is desirable.
        if self.usePostiniScore:
            try:
                postiniHeader = msg.impl.getHeader(u'X-pstn-levels')
            except NoSuchHeader:
                pass
            else:
                postiniLevels = self._parsePostiniHeader(postiniHeader)
                if postiniLevels is not None:
                    postiniScore = postiniLevels['S']
                    if float(postiniScore) < self.postiniThreshhold:
                        msg.classifySpam()
                        log.msg("Postini classified message as spam")
                    else:
                        msg.classifyClean()
                        log.msg("Postini classified message as clean")
                    return

        _filters = self._filters()
        if len(_filters) > 1:
            raise NotImplementedError("multiple spam filters not yet supported")
        if not _filters:
            msg.classifyClean()
            log.msg("Message classified as clean due to an absence of filters")
            return

        isSpam, score = _filters[0].classify(msg)
        if isSpam:
            msg.classifySpam()
        else:
            msg.classifyClean()
        log.msg("spam batch processor scored message at %0.2f: %r" % (score, isSpam))


    def reclassify(self):
        """
        Forget whatever progress has been made in processing messages and start
        over.

        This should only be called in the batch process.
        """
        self.messageSource.removeReliableListener(self)
        self.messageSource.addReliableListener(self, style=iaxiom.REMOTE)


    def retrain(self):
        """
        Force all L{iquotient.IHamFilter}s to forget their trained state,
        then retrain them based on L{exmess.Message}s with C{trained} set to
        C{True}, then reclassify all messages.

        This should only be called in the batch process.
        """
        filters = list(self.store.powerupsFor(iquotient.IHamFilter))
        for f in filters:
            f.forgetTraining()

        sq = MailboxSelector(self.store)
        sq.setLimit(5000)
        sq.refineByStatus(TRAINED_STATUS)
        work = iter(list(sq))


        # XXX This really should use in-database state, otherwise a restart in
        # the middle will muck things up.
        def go():
            for msg in work:
                for f in filters:
                    f.train(msg._spam, msg)
                yield None
            self.reclassify()
        return coiterate(go())

registerAttributeCopyingUpgrader(Filter, 1, 2)

item.declareLegacyItem(Filter.typeName, 2,
    dict(installedOn = attributes.reference(),
         usePostiniScore = attributes.boolean(default=False,allowNone=False),
         postiniThreshhold = attributes.ieee754_double(default=0.03)))



def _filter2to3(old):
    """
    add dependencies as attributes, remove installedOn
    """
    filter = old.upgradeVersion(old.typeName, 2, 3)
    s = old.store
    filter.usePostiniScore = old.usePostiniScore
    filter.postiniThreshhold = old.postiniThreshhold
    filter.messageSource = s.findOrCreate(MessageSource)
    filter.tiSource = s.findOrCreate(_TrainingInstructionSource)
    return filter

registerUpgrader(_filter2to3, Filter.typeName, 2, 3)

item.declareLegacyItem(Filter.typeName, 3,
    dict(messageSource=attributes.reference(),
         scheduler=attributes.reference(),
         tiSource=attributes.reference(),
         usePostiniScore=attributes.boolean(default=False,allowNone=False),
         postiniThreshhold=attributes.ieee754_double(default=0.03)))

def _filter3to4(old):
    """
    Drop the scheduler reference, preserve everything else.
    """
    return old.upgradeVersion(
        old.typeName, 3, 4,
        usePostiniScore=old.usePostiniScore,
        postiniThreshhold=old.postiniThreshhold,
        messageSource=old.messageSource,
        tiSource=old.tiSource)

registerUpgrader(_filter3to4, Filter.typeName, 3, 4)


class HamFilterFragment(ThemedFragment):
    fragmentName = 'ham-filter'
    title = 'Spam Filtering'

    jsClass = u'Quotient.Filter.HamConfiguration'


    def __init__(self, filter, fragmentParent=None):
        """
        @type filter: L{xquotient.spam.Filter}
        @param filter: The ham filter to be configured.
        """
        ThemedFragment.__init__(self, fragmentParent)
        self.filter = filter


    def head(self):
        return ()


    def configurePostini(self, usePostiniScore, postiniThreshhold):
        """
        @type usePostiniScore: C{bool}
        @param usePostiniScore: A boolean indicating whether Postini headers
        will be respected when classifying mail as ham or spam.

        @type postiniThreshhold: C{float}
        @param postiniThreshhold: The score at which to divide ham from spam,
        with scores below this value being spam and scores above it being ham.
        """
        print 'Configuring postini', usePostiniScore, postiniThreshhold
        self.filter.usePostiniScore = usePostiniScore
        self.filter.postiniThreshhold = min(100, max(0, postiniThreshhold))


    def render_postiniForm(self, ctx, data):
        f = liveform.LiveForm(
            self.configurePostini,
            [liveform.Parameter('usePostiniScore',
                                liveform.CHECKBOX_INPUT,
                                bool,
                                u'Use Postini Score',
                                u'Classify messages based on Postini scores.',
                                default=self.filter.usePostiniScore),
             liveform.Parameter('postiniThreshhold',
                                liveform.TEXT_INPUT,
                                float,
                                u'Postini Threshold',
                                u'Score below which to consider messages spam.',
                                default=self.filter.postiniThreshhold)],
            description='Configure Postini')
        f.jsClass = u"Quotient.Spam.PostiniSettings"
        f.setFragmentParent(self)
        f.docFactory = getLoader('liveform-compact')
        return ctx.tag[f]


    def retrain(self):
        return iaxiom.IBatchService(self.filter.store).call(self.filter.retrain)
    athena.expose(retrain)


    def reclassify(self):
        return iaxiom.IBatchService(self.filter.store).call(self.filter.reclassify)
    athena.expose(reclassify)

components.registerAdapter(HamFilterFragment, Filter, ixmantissa.INavigableFragment)


class DSPAMFilter(item.Item):
    """
    libdspam-based L{iquotient.IHamFilter} powerup.
    """
    implements(iquotient.IHamFilter)
    schemaVersion = 2
    classifier = attributes.inmemory()
    username = attributes.inmemory()
    lib = attributes.inmemory()
    globalPath = attributes.bytes()
    filter = dependsOn(Filter)

    powerupInterfaces = (iquotient.IHamFilter,)
    def installed(self):
        self.globalPath = self.store.parent.newFilePath("dspam").path

    def _homePath(self):
        return self.store.newFilePath('dspam-%d' % (self.storeID,))

    def activate(self):
        username, domain = userbase.getAccountNames(self.store).next()
        self.username = ("%s@%s" % (username, domain)).encode('ascii')
        self.lib = dspam.startDSPAM(self.username, self._homePath().path.encode('ascii'))

    def classify(self, item):
        result, clas, conf = dspam.classifyMessageWithGlobalGroup(
            self.lib, self.username, 'global',
            self._homePath().path.encode('ascii'),
            self.globalPath,
            item.impl.source.open().read(), train=True)
        return result == dspam.DSR_ISSPAM, conf

    def train(self, spam, item):
        dspam.trainMessageFromError(
            self.lib, self.username, self._homePath().path.encode('ascii'),
            item.impl.source.open().read(),
            spam and dspam.DSR_ISSPAM or dspam.DSR_ISINNOCENT)

    def forgetTraining(self):
        p = self._homePath()
        if p.exists():
            p.remove()


item.declareLegacyItem(DSPAMFilter.typeName, 1, dict(
    globalPath=attributes.bytes(),
    installedOn=attributes.reference()))

def _dspamFilter1to2(old):
    df = old.upgradeVersion(DSPAMFilter.typeName, 1, 2,
                            globalPath=old.globalPath,
                            filter=old.store.findOrCreate(Filter))
    return df
registerUpgrader(_dspamFilter1to2, DSPAMFilter.typeName, 1, 2)

class _SQLite3Classifier(object, classifier.Classifier):
    """
    A Spambayes classifier which implements training dataset persistence in a
    SQLite3 database.

    The dataset is persisted in a dedicated SQLite3 database rather than in the
    user store because the data is accessed from the batch process.  A dedicated
    database will lead to fewer contention problems than re-using the user
    store.

    Axiom is not used for the training dataset database because of the
    complicated, inflexible hooks supplied by the base
    L{spambayes.classifier.Classifier}, which in particular make getting
    transaction management difficult with Axiom.

    @cvar SCHEMA: A C{list} of C{str} giving the schema initialization
        statements.  These are executed any time the classifier database is
        opened, with the expected failure which occurs any time the schema has
        already been initialized handled and disregarded.

    @ivar _readCache: Word information that is already known, either because it
        has already been read from the database once or because we wrote the
        information to the database.  Keys are unicode tokens, values are
        three-sequences of token, nspam, and nham counts.  This is used to hold
        word info between two different Spambayes hooks, C{_getclues} and
        C{_wordinfoget}.  The former has access to all tokens in a particular
        document, the latter is a potato-programming mistake.  Loading all of
        the values at once in C{_getclues} is a big performance win.

    @ivar _writeCache: Word information that is on its way to the database due
        to training.  This has the same shape as C{_readCache}.  Word info is
        held here until training on one document is complete, then all the word
        info is dumped into the database in a single SQL operation (via
        I{executemany}).
    """

    SCHEMA = [
        "CREATE TABLE bayes ("
        "  word TEXT NOT NULL DEFAULT '',"
        "  nspam INTEGER NOT NULL DEFAULT 0,"
        "  nham INTEGER NOT NULL DEFAULT 0,"
        "  PRIMARY KEY(word)"
        ")",
        "CREATE INDEX bayes_word ON bayes(word)",
        "CREATE TABLE state ("
        "  nspam INTEGER NOT NULL,"
        "  nham INTEGER NOT NULL"
        ")",
        "INSERT INTO state (nspam, nham) VALUES (0, 0)",
        ]

    def nspam():
        doc = """
        A property which reflects the number of messages trained as spam, while
        also automatically persisting any changes to this value (which the base
        class will make) to the database.
        """
        def get(self):
            return self._nspam
        def set(self, value):
            self._nspam = value
            self._recordState()
        return get, set, None, doc
    nspam = property(*nspam())


    def nham():
        doc = """
        A property which reflects the number of messages trained as ham, while
        also automatically persisting any changes to this value (which the base
        class will make) to the database.
        """
        def get(self):
            return self._nham
        def set(self, value):
            self._nham = value
            self._recordState()
        return get, set, None, doc
    nham = property(*nham())

    db = cursor = databaseName = None

    def __init__(self, databaseName):
        """
        Initialize this classifier.

        @param databaseName: The path to the SQLite3 database from which to load
            and to which to store training data.
        """
        classifier.Classifier.__init__(self)
        self.databaseName = databaseName
        self._readCache = {}
        self._writeCache = {}

        # Open the database, possibly initializing it if it has not yet been
        # initialized, and then load the necessary global state from it (nspam,
        # nham).
        self.load()


    def load(self):
        """
        Open the training dataset database, initializing it if necessary, and
        loading necessary initial state from it.
        """
        self.db = sqlite3.connect(self.databaseName, isolation_level='IMMEDIATE')
        self.cursor = self.db.cursor()
        try:
            for statement in self.SCHEMA:
                self.cursor.execute(statement)
        except sqlite3.OperationalError as e:
            # Table already exists
            self.db.rollback()
        else:
            self.db.commit()

        self.cursor.execute('SELECT nspam, nham FROM state')
        rows = self.cursor.fetchall()
        self._nspam, self._nham = rows[0]


    def close(self):
        """
        Close the training dataset database.
        """
        self.cursor.close()
        self.db.close()
        self.db = self.cursor = None


    def _recordState(self):
        """
        Save nspam and nham, if the database has been opened (it will not have
        been opened when this gets run from the nspam/nham property setters
        invoked from Classifier.__init__, and that's just fine with us).
        """
        if self.cursor is not None:
            self.cursor.execute('UPDATE state SET nspam=?, nham=?', (self._nspam, self._nham))


    def _getclues(self, wordstream):
        """
        Hook into the classification process to speed it up.

        See the base implementation for details about what C{_getclues} is
        supposed to do.  This implementation extends the base to look into
        wordstream and load all the necessary information with the minimum
        amount of SQLite3 work, then calls up to the base implementation to let
        it do the actual classification-related work.

        @param wordstream: An iterable (probably a generator) of tokens from the
            document to be classified.
        """
        # Make sure we can consume it and give it to the base implementation for
        # consumption.
        wordstream = list(wordstream)

        # Find all the tokens we don't have in memory already
        missing = []
        for word in wordstream:
            if isinstance(word, str):
                word = word.decode('utf-8', 'replace')
            if word not in self._readCache:
                missing.append(word)

        # Load their state
        while missing:
            # SQLite3 allows a maximum of 999 variables.
            load = missing[:999]
            del missing[:999]
            self.cursor.execute(
                "SELECT word, nspam, nham FROM bayes WHERE word IN (%s)" % (
                    ", ".join("?" * len(load))),
                load)
            rows = self.cursor.fetchall()

            # Save them for later
            for row in rows:
                self._readCache[row[0]] = row

        # Let the base class do its thing, which will involve asking us about
        # that state we just cached.
        return classifier.Classifier._getclues(self, wordstream)


    def _get(self, word):
        """
        Load the training data for the given word.

        @param word: A word (or any other kind of token) to load information about.
        @type word: C{str} or C{unicode} (but really, C{unicode} please)

        @return: C{None} if there is no training data for the given word,
            otherwise a two-sequence of the number of times the token has been
            trained as spam and the number of times it has been trained as ham.
        """
        if isinstance(word, str):
            word = word.decode('utf-8', 'replace')
        try:
            # Check to see if we already have this word's info in memory.
            row = self._readCache[word]
        except KeyError:
            # If not, load it from the database.
            self.cursor.execute(
                "SELECT word, nspam, nham FROM bayes WHERE word=?", (word,))
            rows = self.cursor.fetchall()
            if rows:
                # Add it to the cache and return it.
                self._readCache[rows[0][0]] = rows[0]
                return rows[0]
            return None
        else:
            # Otherwise return what we knew already.
            return row


    def _set(self, word, nspam, nham):
        """
        Update the training data for a particular word.

        @param word: A word (or any other kind of token) to store training
            information about.
        @type word: C{str} or C{unicode} (but really, C{unicode} please)

        @param nspam: The number of times the token has been trained as spam.
        @param nham: The number of times the token has been trained as ham.
        """
        if isinstance(word, str):
            word = word.decode('utf-8', 'replace')
        self._readCache[word] = self._writeCache[word] = (word, nspam, nham)


    def _delete(self, word):
        """
        Forget the training data for a particular word.

        @param word: A word (or any other kind of token) to lose training
            information about.
        @type word: C{str} or C{unicode} (but really, C{unicode} please)

        @raise NotImplementedError: Deletion is not actually supported in this
            backend.  Fortunately, Quotient does not need it (it never calls
            C{unlearn}).
        """
        raise NotImplementedError("There is no support for deletion.")


    def _post_training(self):
        """
        L{Classifier} hook invoked after all other steps of training a message
        have been completed.  This is used to commit the currently active
        transaction, which contains all of the database modifications for each
        token in that message.
        """
        writes = self._writeCache.itervalues()
        self._writeCache = {}
        self.cursor.executemany(
            "INSERT OR REPLACE INTO bayes (word, nspam, nham) "
            "VALUES (?, ?, ?)", writes)
        self.db.commit()


    def _bulkwordinfoset(self, words):
        """
        Upgrade helper for recording spam and ham information for many words at
        once.
        """
        self.cursor.executemany(
            "INSERT OR REPLACE INTO bayes (word, nspam, nham) "
            "VALUES (?, ?, ?)",
            ((word.decode('utf-8', 'replace'), record.spamcount, record.hamcount)
             for (word, record)
             in words))


    def _wordinfoset(self, word, record):
        """
        L{Classifier} hook invoked to record a changed spam and ham data for a
        single word.
        """
        self._set(word, record.spamcount, record.hamcount)


    def _wordinfoget(self, word):
        """
        L{Classifier} hook invoked to retrieve persisted spam and ham data for a
        single word.
        """
        row = self._get(word)
        if row:
            item = self.WordInfoClass()
            item.__setstate__((row[1], row[2]))
            return item
        return None


    def _wordinfodel(self, word):
        """
        L{Classifier} hook invoked to discard the persisted spam and ham data
        for a single word.
        """
        self._delete(word)



class SpambayesFilter(item.Item):
    """
    Spambayes-based L{iquotient.IHamFilter} powerup.
    """
    implements(iquotient.IHamFilter)
    schemaVersion = 3
    classifier = attributes.inmemory()
    guesser = attributes.inmemory()
    filter = dependsOn(Filter)

    powerupInterfaces = (iquotient.IHamFilter,)

    def _classifierPath(self):
        return self.store.newFilePath('spambayes-%d-classifier.sqlite' % (self.storeID,))


    def activate(self):
        self.classifier = _SQLite3Classifier(self._classifierPath().path)
        self.guesser = hammie.Hammie(self.classifier, mode='r')


    # IHamFilter
    def classify(self, item):
        # SpamBayes thinks 0 is ham, 1 is spam.  We have a different idea.
        score = 1.0 - self.guesser.score(item.impl.source.open())
        return score <= SPAM_THRESHHOLD, score


    def train(self, spam, item):
        """
        Train the classifier.

        @param spam: A boolean indicating whether C{item} is spam or not.
        @param item: A Message to train with.
        """
        for i in xrange(10):
            self.guesser.train(item.impl.source.open(), spam)
            if spam:
                if self.classify(item) < SPAM_THRESHHOLD:
                    break
            else:
                if self.classify(item) > SPAM_THRESHHOLD:
                    break


    def forgetTraining(self):
        p = self._classifierPath()
        if p.exists():
            p.remove()
            self.activate()


item.declareLegacyItem(SpambayesFilter.typeName, 1, dict(
    installedOn=attributes.reference()))

def _sbFilter1to2(old):
    sbf = old.upgradeVersion(SpambayesFilter.typeName, 1, 2,
                            filter=old.store.findOrCreate(Filter))
    return sbf
registerUpgrader(_sbFilter1to2, SpambayesFilter.typeName, 1, 2)

item.declareLegacyItem(SpambayesFilter.typeName, 2, dict(
    filter=attributes.reference()))


def _sbFilter2to3(old):
    """
    Convert the pickled spambayes data to a SQLite3 database of the same data.
    """
    sbf = old.upgradeVersion(
        SpambayesFilter.typeName, 2, 3, filter=old.filter)
    path = sbf.store.newFilePath('spambayes-%d-classifier.pickle' % (sbf.storeID,))
    try:
        fObj = path.open()
    except IOError, e:
        if e.errno != errno.ENOENT:
            raise
        else:
            return sbf
    try:
        dataset = cPickle.load(fObj)
    finally:
        fObj.close()

    words = dataset._wordinfokeys()
    sbf.classifier._bulkwordinfoset(
        ((word, dataset._wordinfoget(word)) for word in words))
    sbf.classifier.nspam = dataset.nspam
    sbf.classifier.nham = dataset.nham
    sbf.classifier._post_training()
    return sbf
registerUpgrader(_sbFilter2to3, SpambayesFilter.typeName, 2, 3)


class SpambayesBenefactor(item.Item):
    endowed = attributes.integer(default=0)
    powerupNames = ["xquotient.spam.SpambayesFilter"]

class DSPAMBenefactor(item.Item):
    endowed = attributes.integer(default=0)
    powerupNames = ["xquotient.spam.DSPAMFilter"]
