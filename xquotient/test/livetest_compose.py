from nevow.livetrial import testcase
from nevow import tags, loaders

from axiom.store import Store

from xmantissa import ixmantissa
from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Person, EmailAddress

from xquotient.compose import Composer
from xquotient.inbox import Inbox

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

        composer = Composer(store=s)
        composer.installOn(s)

        composerFrag = ixmantissa.INavigableFragment(composer)
        composerFrag.jsClass = 'Quotient.Test.ComposeController'
        composerFrag.setFragmentParent(self)
        composerFrag.docFactory = getLoader(composerFrag.fragmentName)

        return ctx.tag[composerFrag]
