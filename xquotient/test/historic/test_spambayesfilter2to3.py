import sqlite3
from axiom.test.historic import stubloader

from xquotient.spam import SpambayesFilter
from xquotient.test.historic.stub_spambayesfilter2to3 import (
        SPAM_A, SPAM_B, HAM, AMBIGUOUS)
from xquotient.test.historic.test_spambayesfilter1to2 import SpambayesFilterTestCase

class SpambayesFilterTestCase(SpambayesFilterTestCase):
    def test_upgradedTrainingDataset(self):
        """
        The upgrade converts the pickled training set into a SQLite3 training
        set.  All of the training data is retained.
        """
        bayes = self.store.findUnique(SpambayesFilter)
        db = sqlite3.connect(bayes._classifierPath().path)
        cursor = db.cursor()
        self.addCleanup(cursor.close)
        self.addCleanup(db.close)

        cursor.execute('SELECT word, nham, nspam FROM bayes')
        expected = set(
            [(word, 0, 1) for word in SPAM_A] +
            [(word, 0, 1) for word in SPAM_B] +
            [(word, 1, 0) for word in HAM] +
            [(AMBIGUOUS, 1, 1)])
        found = set(cursor.fetchall())

        # There may be extra tokens due to funny extra spambayes logic.  That's
        # fine.  As long as we see all the tokens we put there, the upgrade is a
        # success.
        self.assertEqual(expected, found & expected)

        cursor.execute('SELECT nham, nspam FROM state')
        nham, nspam = cursor.fetchone()
        self.assertEqual(nham, 1)
        self.assertEqual(nspam, 2)
