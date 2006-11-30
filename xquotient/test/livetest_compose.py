from epsilon.extime import Time

from nevow.livetrial import testcase
from nevow import tags, loaders
from nevow.athena import expose

from axiom.store import Store
from axiom.userbase import LoginMethod, LoginSystem
from axiom.dependency import installOn

from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Person, EmailAddress

from xquotient import compose
from xquotient.inbox import Inbox
from xquotient.exmess import Message
from xquotient.test.test_inbox import testMessageFactory

class _ComposeTestMixin:
    def _getComposeFragment(
            self, composeFragFactory=compose.ComposeFragment):

        s = Store()

        installOn(Inbox(store=s), s)

        compose.FromAddress(
            store=s,
            address=u'moe@divmod.com').setAsDefault()

        composer = compose.Composer(store=s)
        installOn(composer, s)

        composeFrag = composeFragFactory(composer)
        composeFrag.jsClass = u'Quotient.Test.ComposeController'
        composeFrag.setFragmentParent(self)
        composeFrag.docFactory = getLoader(composeFrag.fragmentName)
        return (s, composeFrag)

class ComposeTestCase(testcase.TestCase, _ComposeTestMixin):
    """
    Tests for Quotient.Compose.Controller
    """

    jsClass = u'Quotient.Test.ComposeTestCase'

    docFactory = loaders.stan(tags.div[
            tags.div(render=tags.directive('liveTest'))[
                tags.div(render=tags.directive('composer'),
                         style='visibility: hidden'),
                tags.div(id='mantissa-footer')]])

    def mktemp(self):
        """
        This is ten kinds of terrible.
        """
        import os, tempfile
        if not os.path.exists("_trial_temp"):
            os.mkdir("_trial_temp")
        return tempfile.mktemp(dir="_trial_temp")

    def render_composer(self, ctx, data):
        """
        Make a bunch of people and give them email addresses
        """

        (s, composeFrag) = self._getComposeFragment()


        def makePerson(email, name):
            EmailAddress(store=s,
                         address=email,
                         person=Person(store=s,
                                       name=name))

        makePerson(u'maboulkheir@divmod.com', u'Moe Aboulkheir')
        makePerson(u'localpart@domain', u'Tobias Knight')
        makePerson(u'madonna@divmod.com', u'Madonna')
        makePerson(u'kilroy@foo', u'')
        return ctx.tag[composeFrag]


class AddrPassthroughComposeFragment(compose.ComposeFragment):
    """
    L{xquotient.compose.ComposeFragment} subclass which overrides
    L{_sendOrSave} to return a list of the flattened recipient addresses that
    were submitted via the compose form
    """

    def _sendOrSave(self, **k):
        """
        @return: sequence of C{unicode} email addresses
        """
        return [addr.pseudoFormat() for addr in k['toAddresses']]

class ComposeToAddressTestCase(testcase.TestCase, _ComposeTestMixin):
    """
    Tests for the behaviour of recipient addresses in
    L{xquotient.compose.ComposeFragment}
    """

    jsClass = u'Quotient.Test.ComposeToAddressTestCase'

    def __init__(self):
        testcase.TestCase.__init__(self)
        self.perTestData = {}

    def getComposeWidget(self, key, toAddress):
        """
        @param key: unique identifier for the test method
        @param toAddress: comma separated C{str} of email addresses which
        should be passed to the L{ComposeFragment} constructor.  This string
        will be used as the initial content of the client-side toAddresses
        form input when the fragment is rendered
        @rtype: L{AddrPassthroughComposeFragment}
        """
        def composeFragFactory(composer):
            return AddrPassthroughComposeFragment(
                        composer, toAddresses=toAddress)

        (s, frag) = self._getComposeFragment(
                        composeFragFactory=composeFragFactory)
        self.perTestData[key] = (s, frag)
        return frag
    expose(getComposeWidget)


class DraftsTestCase(testcase.TestCase):
    """
    Tests for the L{xquotient.compose.DraftsScreen} scrolltable
    """

    jsClass = u'Quotient.Test.DraftsTestCase'

    def getWidgetDocument(self):
        s = Store()
        composer = compose.Composer(store=s)
        installOn(composer, s)

        for i in xrange(5):
            compose.Draft(
                store=s,
                message=testMessageFactory(store=s,
                                           spam=False,
                                           draft=True,
                                           subject=unicode(i),
                                           receivedWhen=Time(),
                                           sentWhen=Time()))

        f = compose.DraftsScreen(composer.drafts)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f


class FromAddressScrollTableTestCase(testcase.TestCase):
    """
    Tests for L{xquotient.compose.FromAddressScrollTable}
    """

    jsClass = u'Quotient.Test.FromAddressScrollTableTestCase'

    def getFromAddressScrollTable(self):
        s = Store()

        installOn(compose.Composer(store=s), s)

        LoginMethod(store=s,
                    internal=False,
                    protocol=u'email',
                    localpart=u'default',
                    domain=u'host',
                    verified=True,
                    account=s)

        compose.FromAddress(
            store=s,
            address=u'notdefault@host',
            smtpHost=u'host',
            smtpUsername=u'notdefault')

        f = compose.FromAddressScrollTable(s)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f
    expose(getFromAddressScrollTable)


class ComposeAutoCompleteTestCase(testcase.TestCase):
    """
    Tests for compose autocomplete
    """

    jsClass = u'Quotient.Test.ComposeAutoCompleteTestCase'
