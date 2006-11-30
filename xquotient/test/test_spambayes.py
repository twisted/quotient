import time

from twisted.internet import reactor
from twisted.trial import unittest

from axiom import store, userbase
from axiom.dependency import installOn
from axiom.scheduler import Scheduler

from xquotient import spam
from xquotient.test.test_dspam import MESSAGE, MessageCreationMixin


class SpambayesFilterTestCase(unittest.TestCase, MessageCreationMixin):

    def setUp(self):
        dbdir = self.mktemp()
        self.store = s = store.Store(dbdir)
        installOn(Scheduler(store=s), s)
        ls = userbase.LoginSystem(store=s)
        installOn(ls, s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()
        self.df = spam.SpambayesFilter(store=ss)
        installOn(self.df, ss)
        self.f = self.df.filter

    def testMessageClassification(self):
        self.f.processItem(self._message())

    def testMessageTraining(self):
        m = self._message()
        self.df.classify(m)
        self.df.train(True, m)

