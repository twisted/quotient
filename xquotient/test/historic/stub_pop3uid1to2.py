# -*- test-case-name: xquotient.test.historic.test_pop3uid1to2 -*-

"""
Create stub database for upgrade of L{xquotient.grabber.POP3UID} from version 1
to version 2.
"""

from axiom.test.historic.stubloader import saveStub

from axiom.userbase import LoginSystem
from axiom.dependency import installOn

from xquotient.grabber import POP3UID

VALUE = b"12345678abcdefgh"
FAILED = False
GRABBER_ID = u"alice@example.com:1234"

def createDatabase(s):
    """
    Create an account in the given store and create a POP3UID item in it.
    """
    loginSystem = LoginSystem(store=s)
    installOn(loginSystem, s)

    account = loginSystem.addAccount(u'testuser', u'localhost', None)
    subStore = account.avatars.open()

    POP3UID(
        store=subStore,
        value=VALUE,
        failed=FAILED,
        grabberID=GRABBER_ID)


if __name__ == '__main__':
    saveStub(createDatabase, 'exarkun@twistedmatrix.com-20120913121256-tg7d6l1w3rkpfehr')
