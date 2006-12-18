from nevow.livetrial import testcase
from nevow.athena import expose

from axiom.store import Store
from axiom.userbase import LoginMethod

from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication

from xquotient import compose, smtpout


class FromAddressScrollTableTestCase(testcase.TestCase):
    """
    Tests for L{xquotient.smtpout.FromAddressScrollTable}
    """

    jsClass = u'Quotient.Test.FromAddressScrollTableTestCase'

    def getFromAddressScrollTable(self):
        s = Store()

        PrivateApplication(store=s).installOn(s)
        compose.Composer(store=s).installOn(s)

        LoginMethod(store=s,
                    internal=False,
                    protocol=u'email',
                    localpart=u'default',
                    domain=u'host',
                    verified=True,
                    account=s)

        # system address
        smtpout.FromAddress(store=s).setAsDefault()

        smtpout.FromAddress(
            store=s,
            address=u'notdefault@host',
            smtpHost=u'host',
            smtpUsername=u'notdefault')

        f = smtpout.FromAddressScrollTable(s)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f
    expose(getFromAddressScrollTable)
