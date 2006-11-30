# -*- test-case-name: xquotient.test.test_spam -*-

import cPickle, errno
from decimal import Decimal

from spambayes import hammie, classifier

from zope.interface import implements

from twisted.python import log, components

from nevow import athena

from epsilon import cooperator

from axiom import iaxiom, item, attributes, userbase
from axiom.upgrade import registerAttributeCopyingUpgrader

from xmantissa import ixmantissa, liveform
from xmantissa.webtheme import ThemedFragment, getLoader

from xquotient import mail, iquotient, exmess
from xquotient.equotient import NoSuchHeader

try:
    from xquotient import dspam
    dspam                       # shut up, pyflakes
except ImportError:
    dspam = None

SPAM_THRESHHOLD = 0.3

class Filter(item.Item, item.InstallableMixin):
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
    schemaVersion = 2

    installedOn = attributes.reference()

    usePostiniScore = attributes.boolean(doc="""
    Indicate whether or not to classify based on Postini headers.
    """, default=False, allowNone=False)

    postiniThreshhold = attributes.ieee754_double(doc="""
    A C{float} between 0 and 100 indicating at what Postini level messages are
    considered spam.
    """, default=0.03)

    _filters = attributes.inmemory()

    def installOn(self, other):
        super(Filter, self).installOn(other)
        self.store.findUnique(mail.MessageSource).addReliableListener(self, style=iaxiom.REMOTE)
        self.store.findOrCreate(exmess._TrainingInstructionSource).addReliableListener(self, style=iaxiom.REMOTE)


    def processItem(self, item):
        assert isinstance(item, (exmess._TrainingInstruction, exmess.Message))
        if isinstance(item, exmess._TrainingInstruction):
            self._train(item)
        else:
            self._classify(item)


    def _filters(self):
        return list(self.powerupsFor(iquotient.IHamFilter))


    def _train(self, instruction):
        for f in self._filters():
            f.train(instruction.spam, instruction.message)
        instruction.deleteFromStore()


    def _parsePostiniHeader(self, s):
        """
        Postini spam headers look like this:
        X-pstn-levels: (S:99.9000 R:95.9108 P:91.9078 M:100.0000 C:96.6797 )
        X-pstn-levels: (S: 0.0901 R:95.9108 P:95.9108 M:99.5542 C:79.5348 )

        S means "spam level".  Smaller is spammier.

        R means ???
        P means ???
        M means ???
        C means ???

        @return: A mapping from 'R', 'P', 'M', 'C', and 'S' to the values
        from the header, or None if the header could not be parsed.
        """
        s = s.strip()
        if s[:1] == '(' and s[-1:] == ')':
            parts = filter(None, s[1:-1].replace(':', ' ').split())
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
        ms = self.store.findUnique(mail.MessageSource)
        ms.removeReliableListener(self)
        ms.addReliableListener(self, style=iaxiom.REMOTE)


    def retrain(self):
        """
        Force all L{iquotient.IHamFilter}s to forget their trained state,
        then retrain them based on L{exmess.Message}s with C{trained} set to
        C{True}, then reclassify all messages.

        This should only be called in the batch process.
        """
        filters = list(self.powerupsFor(iquotient.IHamFilter))
        for f in filters:
            f.forgetTraining()

        sq = exmess.MailboxSelector(self.store)
        sq.setLimit(5000)
        sq.refineByStatus(exmess.TRAINED_STATUS)
        work = iter(list(sq))

        # XXX This really should use in-database state, otherwise a restart in
        # the middle will muck things up.
        def go():
            for msg in work:
                for f in filters:
                    f.train(msg._spam, msg)
                yield None
            self.reclassify()
        return cooperator.iterateInReactor(go())

registerAttributeCopyingUpgrader(Filter, 1, 2)


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


class DSPAMFilter(item.Item, item.InstallableMixin):
    """
    libdspam-based L{iquotient.IHamFilter} powerup.
    """
    implements(iquotient.IHamFilter)

    installedOn = attributes.reference()
    classifier = attributes.inmemory()
    username = attributes.inmemory()
    lib = attributes.inmemory()
    globalPath = attributes.bytes()

    def installOn(self, other):
        super(DSPAMFilter, self).installOn(other)
        other.powerUp(self, iquotient.IHamFilter)
        self.globalPath = other.installedOn.parent.newFilePath("dspam").path

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

class SpambayesFilter(item.Item, item.InstallableMixin):
    """
    Spambayes-based L{iquotient.IHamFilter} powerup.
    """
    implements(iquotient.IHamFilter)

    installedOn = attributes.reference()

    classifier = attributes.inmemory()
    guesser = attributes.inmemory()

    def installOn(self, other):
        super(SpambayesFilter, self).installOn(other)
        other.powerUp(self, iquotient.IHamFilter)


    def _classifierPath(self):
        return self.store.newFilePath('spambayes-%d-classifier.pickle' % (self.storeID,))


    def activate(self):
        try:
            try:
                c = cPickle.load(self._classifierPath().open())
            except IOError, e:
                if e.errno != errno.ENOENT:
                    raise
                c = classifier.Classifier()
        except:
            log.msg("Loading Spambayes trained state failed:")
            log.err()
            c = classifier.Classifier()
        self.classifier = c
        self.guesser = hammie.Hammie(c)


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
        sc = self.classify(item)
        p = self._classifierPath()
        if not p.parent().exists():
            p.parent().makedirs()
        t = p.temporarySibling()
        cPickle.dump(self.classifier, t.open())
        t.moveTo(p)


    def forgetTraining(self):
        p = self._classifierPath()
        if p.exists():
            p.remove()
            self.classifier = classifier.Classifier()
            self.guesser = hammie.Hammie(self.classifier)
            self.installedOn.retrain()



class SpambayesBenefactor(item.Item):
    endowed = attributes.integer(default=0)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(SpambayesFilter).installOn(avatar.findUnique(Filter))


    def revoke(self, ticket, avatar):
        avatar.findUnique(SpambayesFilter).deleteFromStore()


class DSPAMBenefactor(item.Item):
    endowed = attributes.integer(default=0)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(DSPAMFilter).installOn(avatar.findUnique(Filter))


    def revoke(self, ticket, avatar):
        avatar.findUnique(DSPAMFilter).deleteFromStore()

