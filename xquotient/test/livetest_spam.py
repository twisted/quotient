
from nevow.livetrial.testcase import TestCase
from nevow.athena import expose
from nevow.tags import div, directive
from nevow.loaders import stan

from axiom.store import Store

from xquotient.spam import Filter, HamFilterFragment

class PostiniConfigurationTestCase(TestCase):
    """
    Tests for configuring Postini-related behavior.
    """
    jsClass = u'Quotient.Test.PostiniConfigurationTestCase'

    docFactory = stan(
        div(render=directive('liveTest'))[
            'Postini Configuration Test Case',
            div(render=directive('postiniConfig'))])


    def __init__(self, *a, **kw):
        super(PostiniConfigurationTestCase, self).__init__(*a, **kw)
        self.store = Store()
        self.filter = Filter(store=self.store)


    def render_postiniConfig(self, ctx, data):
        f = HamFilterFragment(self.filter)
        f.setFragmentParent(self)
        return f


    def checkConfiguration(self):
        """
        Test that postini filtering has been turned on and that the threshhold
        has been set to 5.0.
        """
        self.failUnless(self.filter.usePostiniScore)
        self.assertEquals(self.filter.postiniThreshhold, 5.0)
    expose(checkConfiguration)
