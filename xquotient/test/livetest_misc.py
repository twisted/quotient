from nevow.livetrial.testcase import TestCase
from nevow import tags

from xquotient.renderers import ButtonRenderingMixin

class ShowNodeAsDialogTestCase(TestCase):
    """
    Tests for Quotient.Common.Util.showNodeAsDialog
    """

    jsClass = u'Quotient.Test.ShowNodeAsDialogTestCase'

    def getWidgetDocument(self):
        return tags.h1(style='display: none',
                       class_=self.__class__.__name__ + '-dialog')['Hello']

class ButtonTogglerTestCase(TestCase, ButtonRenderingMixin):
    """
    Tests for Quotient.Common.ButtonToggler
    """

    jsClass = u'Quotient.Test.ButtonTogglerTestCase'

    def getWidgetDocument(self):
        return tags.div(render=tags.directive('button'))[
                    tags.a(href='#')['A link']]
