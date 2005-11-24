from zope.interface import implements
from nevow import rend, inevow, tags
from xmantissa.publicresource import getLoader
from itertools import imap

class SpacePreservingStringRenderer(object):
    implements(inevow.IRenderer)

    def __init__(self, text):
        self.text = text

    def rend(self, context, line):
        # rethink this at some point, we probably dont need to do
        # strange things with stan here.  or do we.
        lines = self.text.split('\n')
        return self.intersperse(tags.br, imap(self.cruftifyMultipleSpaces, lines))

    def cruftifyMultipleSpaces(text):
        """Replace multiple spaces with &nbsp; such that they are rendered as we want."""
        if text.startswith(' '):
            yield tags.xml('&nbsp;')
            text = text[1:]
        chunks = text.split('  ')
        for i in SpacePreservingStringRenderer.intersperse(tags.xml(' &nbsp;'), chunks):
            yield i

    cruftifyMultipleSpaces = staticmethod(cruftifyMultipleSpaces)

    def intersperse(sep, seq):
        """yield 'seq' with 'sep' inserted between each element."""
        iterSeq = iter(seq)
        try:
            next = iterSeq.next()
        except StopIteration:
            return

        while True:
            yield next
            try:
                next = iterSeq.next()
            except StopIteration:
                return
            yield sep

    intersperse = staticmethod(intersperse)

quoteClasses = ('quote-one', 'quote-two', 'quote-three')

class ParagraphRenderer(rend.Fragment):
    """
    slot content: filled with the content of this paragraph.

    pattern quoting-level: The pattern to use around quoted
        paragraphs. This pattern will be wrapped around the
        actual paragraph text once for each quoting depth.
        slot content: The content, either the unquoted-paragraph
            pattern or a previous quoting-level pattern when
            quote depth > 1
        slot color: The CSS color to use for this paragraph, pulled
            from the quoteColors list.
    """
    docFactory = getLoader('message-detail-patterns')

    def render_paragraph(self, context, data):
        def render_children(context, data):
            paraPattern = inevow.IQ(self.docFactory).patternGenerator('paragraph')

            for child in self.original.children:
                if isinstance(child, (str, unicode)):
                    yield SpacePreservingStringRenderer(child)
                else:
                    if hasattr(child, 'depth') and 0 < child.depth:
                        qc = quoteClasses[child.depth % len(quoteClasses)]
                    else:
                        qc = 'no-quote'

                    childPara = paraPattern()
                    childPara.fillSlots('content', ParagraphRenderer(child))
                    childPara.fillSlots('quote-class', qc)
                    yield childPara

        context.fillSlots('content', render_children)
        return context.tag
