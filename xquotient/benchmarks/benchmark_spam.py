
"""
Run a message through the Quotient spam classification interface a large number
of times.
"""

import StringIO

from axiom import store, userbase

from xquotient import spam


class Message(object):
    def __init__(self):
        self.trained = False

    impl = property(lambda self: self)
    source = property(lambda self: self)

    def open(self):
        return StringIO.StringIO(
            'Hello world\r\n'
            'Goodbye.\r\n')

def main():
    s = store.Store("spam.axiom")

    # xquotient.dspam requires an account name to work at all.
    account = userbase.LoginAccount(store=s)
    userbase.LoginMethod(store=s,
                         account=account,
                         localpart=u"testuser",
                         domain=u"example.com",
                         verified=True,
                         internal=False,
                         protocol=userbase.ANY_PROTOCOL)

    classifier = spam.Filter(store=s)
    dspam = spam.DSPAMFilter(store=s).installOn(classifier)

    def process():
        for i in xrange(10000):
            classifier.processItem(Message())
    s.transact(process)


if __name__ == '__main__':
    main()
