from itertools import cycle

from twisted.web import microdom
from twisted.trial.unittest import TestCase

from nevow.flat import flatten

from xquotient import mimepart
from xquotient import renderers
from xquotient.benchmarks.rendertools import renderPlainFragment

class RenderersTestCase(TestCase):
    """
    Tests for L{xquotient.renderers}
    """

    def testSpacePreservingStringRenderer(self):
        """
        Check that L{renderers.SpacePreservingStringRenderer} does the
        right thing with newlines and spaces
        """

        def assertRenderedEquals(input, output):
            renderer = renderers.SpacePreservingStringRenderer(input)
            self.assertEqual(renderPlainFragment(renderer), output)

        assertRenderedEquals('', '')
        assertRenderedEquals('hello', 'hello')
        assertRenderedEquals('h ello', 'h ello')
        assertRenderedEquals('  x  ', '&#160; x &#160;')
        assertRenderedEquals('x\ny\n  z', 'x<br />y<br />&#160; z')

    def _renderQuotedMessage(self, levels):
        text = '\n'.join(('>' * i) + str(i) for i in xrange(levels))
        return renderPlainFragment(
                    renderers.ParagraphRenderer(
                        mimepart.FlowedParagraph.fromRFC2646(text)))

    def testParagraphNesting(self):
        """
        Check that L[renderers.ParagraphRenderer} doesn't explode
        if asked to render a deep tree of paragraphs
        """
        self._renderQuotedMessage(1000)

    def testQuotingLevels(self):
        """
        Check that L{renderers.ParagraphRenderer} assigns the
        right quoting levels to things
        """

        doc = microdom.parseString('<msg>' + self._renderQuotedMessage(5) + '</msg>')
        quoteClass = cycle(renderers.ParagraphRenderer.quoteClasses).next
        self.assertEqual(doc.firstChild().firstChild().nodeValue.strip(), '0')

        for (i, div) in enumerate(doc.getElementsByTagName('div')):
            self.assertEqual(div.attributes['class'], quoteClass())
            self.assertEqual(div.firstChild().nodeValue.strip(), str(i + 1))

        self.assertEqual(i, 3)

    def testParagraphRendererPreservesWhitespace(self):
        self.assertEqual(
            renderPlainFragment(
                renderers.ParagraphRenderer(
                    mimepart.FixedParagraph.fromString('  foo'))).strip(),
            '&#160; foo')
