from nevow.livetrial.testcase import TestCase

from axiom.store import Store

from xmantissa.webtheme import getLoader

from xquotient import grabber

class AddGrabberTestCase(TestCase):
    """
    Tests for the add grabber liveform
    """

    jsClass = 'Quotient.Test.AddGrabberTestCase'

    def getWidgetDocument(self):
        s = Store()

        grabberConfig = grabber.GrabberConfiguration(store=s)
        grabberConfig.installOn(s)

        f = grabber.GrabberConfigFragment(grabberConfig)
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f
