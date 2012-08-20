
from StringIO import StringIO

from spambayes.hammie import Hammie

from twisted.trial import unittest

from axiom import store, userbase
from axiom.dependency import installOn

from xquotient import spam
from xquotient.test.test_dspam import MessageCreationMixin


class SQLite3ClassifierTests(unittest.TestCase):
    """
    Tests for L{xquotient.spam._SQLite3Classifier}, a spambayes classifier which
    persists training data in a SQLite3 database.
    """
    def setUp(self):
        self.path = self.mktemp()
        self.bayes = spam._SQLite3Classifier(self.path)
        self.classifier = Hammie(self.bayes, mode='r')


    def test_nspam(self):
        """
        L{SQLite3Classifier} tracks, in memory, the number of spam messages it
        has been trained with.
        """
        self.classifier.train(StringIO("spam words of spamnfulness"), True)
        self.assertEqual(self.bayes.nspam, 1)


    def test_nspamPersisted(self):
        """
        L{SQLite3Classifier} tracks, in a database, the number of spam messages
        it has been trained with.
        """
        self.classifier.train(StringIO("spam words of spamfulness"), True)
        bayes = spam._SQLite3Classifier(self.path)
        self.assertEqual(bayes.nspam, 1)


    def test_nham(self):
        """
        L{SQLite3Classifier} tracks, in memory, the number of ham messages it
        has been trained with.
        """
        self.classifier.train(StringIO("very nice words"), False)
        self.assertEqual(self.bayes.nham, 1)


    def test_nhamPersisted(self):
        """
        L{SQLite3Classifier} tracks, in a database, the number of ham messages
        it has been trained with.
        """
        self.classifier.train(StringIO("very nice words"), False)
        bayes = spam._SQLite3Classifier(self.path)
        self.assertEqual(bayes.nham, 1)


    def test_spamClassification(self):
        """
        L{SQLite3Classifier} can be trained with a spam message so as to later
        classify messages like that one as spam.
        """
        self.classifier.train(StringIO("spam words of spamfulness"), True)
        self.assertTrue(
            self.classifier.score(StringIO("spamfulness words of spam")) > 0.99)


    def test_hamClassification(self):
        """
        L{SQLite3Classifier} can be trained with a ham message so as to later
        classify messages like that one as ham.
        """
        self.classifier.train(StringIO("very nice words"), False)
        self.assertTrue(
            self.classifier.score(StringIO("words, very nice")) < 0.01)



class SpambayesFilterTestCase(unittest.TestCase, MessageCreationMixin):
    """
    Tests for L{xquotient.spam.SpambayesFilter}.
    """
    def setUp(self):
        dbdir = self.mktemp()
        self.store = s = store.Store(dbdir)
        def account():
            ls = userbase.LoginSystem(store=s)
            installOn(ls, s)
            acc = ls.addAccount('username', 'dom.ain', 'password')
            return acc.avatars.open()
        ss = s.transact(account)
        def spambayes():
            self.df = spam.SpambayesFilter(store=ss)
            installOn(self.df, ss)
            self.f = self.df.filter
        ss.transact(spambayes)


    def test_messageClassification(self):
        """
        When L{SpambayesFilter} is installed, L{Filter} uses it to classify
        items it processes.
        """
        self.store.transact(self.f.processItem, self._message())
        # XXX And the actual test here would be ... ?  lp:#1039197


    def test_messageTraining(self):
        """
        L{SpambayesFilter.train} adds tokens from the given message to the
        training dataset for either ham or spam.
        """
        m = self._message()
        self.df.classify(m)
        self.df.train(True, m)
        # XXX Really, unit tests should make _some_ assertions.  lp:#1039197


    def test_messageRetraining(self):
        """
        Test that removing the training data and rebuilding it succeeds.
        """
        self.test_messageTraining()
        self.df.forgetTraining()
        # XXX The docstring is a total lie, there is no actual testing going on
        # here.  lp:#1039197
