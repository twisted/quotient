# -*- test-case-name: xquotient.test.historic.test_inbox3to4filter -*-

"""
Create a stub database for upgrade of L{xquotient.inbox.Inbox} from version 3
to version 4, where there is a L{xquotient.spam.Filter} in the store
"""

from axiom.test.historic.stubloader import saveStub
from axiom.dependency import installOn

from xquotient.inbox import Inbox
from xquotient import spam

def createDatabase(s):
    installOn(Inbox(store=s, uiComplexity=2, showMoreDetail=True), s)
    installOn(spam.Filter(store=s), s)

if __name__ == '__main__':
    saveStub(createDatabase, 11096)
