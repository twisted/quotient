import time

from twisted.internet import reactor
from twisted.trial import unittest

from axiom import store, userbase

from xquotient import spam
from xquotient.test.test_dspam import MESSAGE, MessageCreationMixin


class SpambayesFilterTestCase(unittest.TestCase, MessageCreationMixin):

    def setUp(self):
        dbdir = self.mktemp()
        self.store = s = store.Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()
        self.df = spam.SpambayesFilter(store=ss)
        self.f = spam.Filter(store=ss)
        self.f.installedOn = ss #XXX sorta cheating
        self.df.installOn(self.f)

    def testMessageClassification(self):
        self.f.processItem(self._message())

    def testMessageTraining(self):
        m = self._message()
        self.df.classify(m)
        self.df.train(True, m)

