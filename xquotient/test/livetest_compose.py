from epsilon.extime import Time

from nevow.livetrial import testcase
from nevow import tags, loaders

from axiom.store import Store

from xmantissa import ixmantissa
from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Person, EmailAddress

from xquotient import compose
from xquotient.inbox import Inbox
from xquotient.exmess import Message

class ComposeTestCase(testcase.TestCase):
    """
    Tests for Quotient.Compose.Controller
    """

    jsClass = u'Quotient.Test.ComposeTestCase'

    docFactory = loaders.stan(tags.div[
            tags.div(render=tags.directive('liveTest'))[
                tags.div(render=tags.directive('composer'),
                         style='visibility: hidden'),
                tags.div(id='mantissa-footer')]])

    def render_composer(self, ctx, data):
        """
        Make a bunch of people and give them email addresses
        """
        s = Store()

        def makePerson(email, name):
            EmailAddress(store=s,
                         address=email,
                         person=Person(store=s,
                                       name=name))

        makePerson(u'maboulkheir@divmod.com', u'Moe Aboulkheir')
        makePerson(u'localpart@domain', u'Tobias Knight')
        makePerson(u'madonna@divmod.com', u'Madonna')
        makePerson(u'kilroy@foo', u'')

        PrivateApplication(store=s).installOn(s)
        Inbox(store=s).installOn(s)

        composer = compose.Composer(store=s)
        composer.installOn(s)

        composerFrag = ixmantissa.INavigableFragment(composer)
        composerFrag.jsClass = u'Quotient.Test.ComposeController'
        composerFrag.setFragmentParent(self)
        composerFrag.docFactory = getLoader(composerFrag.fragmentName)

        return ctx.tag[composerFrag]

class DraftsTestCase(testcase.TestCase):
    """
    Tests for the L{xquotient.compose.DraftsScreen} scrolltable
    """

    jsClass = u'Quotient.Test.DraftsTestCase'

    def getWidgetDocument(self):
        s = Store()

        PrivateApplication(store=s).installOn(s)
        compose.Composer(store=s).installOn(s)

        drafts = compose.Drafts(store=s)
        drafts.installOn(s)

        for i in xrange(5):
            compose.Draft(store=s,
                          message=Message(store=s,
                                          spam=False,
                                          draft=True,
                                          subject=unicode(i),
                                          receivedWhen=Time(),
                                          sentWhen=Time()))

        f = compose.DraftsScreen(drafts)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f

class FromAddressScrollTableTestCase(testcase.TestCase):
    """
    Tests for L{xquotient.compose.FromAddressScrollTable}
    """

    jsClass = u'Quotient.Test.FromAddressScrollTableTestCase'

    def getWidgetDocument(self):
        s = Store()

        PrivateApplication(store=s).installOn(s)
        compose.Composer(store=s).installOn(s)

        compose.FromAddress(
            store=s,
            address=u'default@host').setAsDefault()

        compose.FromAddress(
            store=s,
            address=u'notdefault@host',
            smtpHost=u'host',
            smtpUsername=u'notdefault')

        f = compose.FromAddressScrollTable(s)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f
