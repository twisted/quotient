from twisted.trial.unittest import TestCase

from xmantissa.test.test_theme import testHead
from xquotient.quotienttheme import QuotientTheme

class QuotientThemeTestCase(TestCase):
    def test_head(self):
        testHead(QuotientTheme(''))
