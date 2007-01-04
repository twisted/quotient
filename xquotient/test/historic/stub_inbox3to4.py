# -*- test-case-name: xquotient.test.historic.test_inbox3to4 -*-

"""
Create a stub database for upgrade of L{xquotient.inbox.Inbox} from version 3
to version 4.
"""

from axiom.test.historic.stubloader import saveStub
from axiom.dependency import installOn

from xquotient.inbox import Inbox

def createDatabase(s):
    installOn(Inbox(store=s, uiComplexity=2, showMoreDetail=True), s)

if __name__ == '__main__':
    saveStub(createDatabase, 11096)
