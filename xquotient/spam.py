
import cPickle, errno

from spambayes import hammie, classifier

from zope.interface import implements

from twisted.internet import reactor
from twisted.python import log, components

from nevow import athena

from epsilon import cooperator

from axiom import iaxiom, item, attributes

from xmantissa import ixmantissa

from xquotient import mail, iquotient, exmess

SPAM_THRESHHOLD = 0.3

class Filter(item.Item, item.InstallableMixin):
    """
    Aggregates message classification tools and assigns the
    L{exmess.Message.spam} attribute according to their results.

    Items will power this up for L{iquotient.IHamFilter} to participate in the
    spam/ham classification process.  Each will have an opportunity to
    contribute to the overall score (currently a geometric average - this will
    probably change when we figure out what a good aggregator is).  These items
    will also receive training feedback from the user, though they may choose
    to disregard it if they are not trainable.
    """
    installedOn = attributes.reference()

    _filters = attributes.inmemory()

    def installOn(self, other):
        super(Filter, self).installOn(other)
        self.store.findUnique(mail.MessageSource).addReliableListener(self, style=iaxiom.REMOTE)
        self.store.findOrCreate(exmess._TrainingInstructionSource).addReliableListener(self, style=iaxiom.REMOTE)


    def processItem(self, item):

        # Do two things that seem weird here:

        #   1> Toss this do-nothing callable into the reactor's call queue so
        #   that there will be a strong reference to prevent filter from being
        #   garbage collected.
        reactor.callLater(10, lambda: self)

        #   2> Keep a list of references to all the current filter powerups so
        #   that they, too, will not be garbage collected.  This isn't strictly
        #   necessary, but it is a useful (if somewhat unsightly) optimization.
        self._filters = list(self.powerupsFor(iquotient.IHamFilter))

        if isinstance(item, exmess._TrainingInstruction):
            for f in self._filters:
                f.train(item.spam, item.message)
            item.deleteFromStore()
        elif not item.trained:
            score = 1.0
            n = 1.0
            for n, f in enumerate(self._filters):
                n += 1
                score *= f.score(item)
            score = score ** (1.0 / n)
            item.spam = (score < SPAM_THRESHHOLD)
            log.msg("spam batch processor scored message at %0.2f: %r" % (score, item.spam))
        else:
            log.msg("Skipping classification of message already user-specified as " + (item.spam and "spam" or "ham"))


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

        work = iter(list(self.store.query(exmess.Message, attributes.AND(exmess.Message.trained == True,
                                                                         exmess.Message.spam != None),
                                          sort=exmess.Message.storeID.descending)))

        # XXX This really should use in-database state, otherwise a restart in
        # the middle will muck things up.
        def go():
            for msg in work:
                for f in filters:
                    f.train(msg.spam, msg)
                yield None
            self.reclassify()
        cooperator.iterateInReactor(go())



class HamFilterFragment(athena.LiveFragment):
    fragmentName = 'ham-filter'
    title = 'Spam/Ham Filtering Configuration'

    jsClass = u'Quotient.Filter.HamConfiguration'

    def head(self):
        return ()


    def retrain(self):
        return iaxiom.IBatchService(self.original.store).call(self.original.retrain)
    athena.expose(retrain)


    def reclassify(self):
        return iaxiom.IBatchService(self.original.store).call(self.original.reclassify)
    athena.expose(reclassify)

components.registerAdapter(HamFilterFragment, Filter, ixmantissa.INavigableFragment)



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
    def score(self, item):
        # SpamBayes thinks 0 is ham, 1 is spam.  We have a different idea.
        return 1.0 - self.guesser.score(item.impl.source.open())


    def train(self, spam, item):
        """
        Train the classifier.

        @param spam: A boolean indicating whether C{item} is spam or not.
        @param item: A Message to train with.
        """
        for i in xrange(10):
            self.guesser.train(item.impl.source.open(), spam)
            if spam:
                if self.score(item) < SPAM_THRESHHOLD:
                    break
            else:
                if self.score(item) > SPAM_THRESHHOLD:
                    break
        sc = self.score(item)
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
