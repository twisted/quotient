# -*- test-case-name xquotient.test.test_historic.test_composePreferenceCollection1to2 -*-

"""
Create stub database for upgrade of
L{xquotient.compose.ComposePreferenceCollection} from version 1 to
version 2.
"""

from axiom.test.historic.stubloader import saveStub

from xquotient.compose import ComposePreferenceCollection

def createDatabase(s):
    """
    Install a Composer on the given store.
    """
    ComposePreferenceCollection(store=s).installOn(s)



if __name__ == '__main__':
    saveStub(createDatabase, 8183)
