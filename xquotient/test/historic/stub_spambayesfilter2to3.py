from StringIO import StringIO

from axiom.test.historic.stubloader import saveStub
from axiom.userbase import LoginMethod
from axiom.dependency import installOn

from xquotient.spam import SpambayesFilter

SPAM_A = ["spam", "bad"]
SPAM_B = ["junk", "evil"]
HAM = ["ham", "good", "wonderful", "justice"]
AMBIGUOUS = "ambiguous"


class Document(object):
    def __init__(self, text):
        self.impl = self
        self.source = self
        self.text = text


    def open(self):
        return StringIO(self.text)



def createDatabase(s):
    bayes = SpambayesFilter(store=s)
    installOn(bayes, s)
    bayes.train(True, Document(" ".join(SPAM_A)))
    bayes.train(True, Document(" ".join(SPAM_B + [AMBIGUOUS])))
    bayes.train(False, Document(" ".join(HAM + [AMBIGUOUS])))


if __name__ == '__main__':
    saveStub(createDatabase, 'exarkun@twistedmatrix.com-20120811233233-fxrt1q924l6wmgxp')
