from nevow.livetrial.testcase import TestCase
from nevow import tags

class ShowNodeAsDialogTestCase(TestCase):
    """
    Tests for Quotient.Common.Util.showNodeAsDialog
    """

    jsClass = u'Quotient.Test.ShowNodeAsDialogTestCase'

    def getWidgetDocument(self):
        return tags.h1(style='display: none',
                       class_=self.__class__.__name__ + '-dialog')['Hello']
