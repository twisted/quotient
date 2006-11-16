# Copyright (c) 2006 Divmod.
# See LICENSE for details.

"""
Runs Quotient javascript tests as part of the Quotient python test suite
"""

from twisted.python.filepath import FilePath
from nevow.testutil import JavaScriptTestSuite, setJavascriptInterpreterOrSkip

class QuotientJavaScriptTestSuite(JavaScriptTestSuite):
    """
    Run all the Quotient javascript tests
    """
    path = FilePath(__file__).parent()

    def testJSAutoComplete(self):
        return self.onetest('test_autocomplete.js')

setJavascriptInterpreterOrSkip(QuotientJavaScriptTestSuite)
