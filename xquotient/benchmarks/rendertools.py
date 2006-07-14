# -*- test-case-name: xquotient.test.test_rendertools -*-

"""
Simpler Nevow-related rendering helpers for Quotient benchmarks.
"""

from nevow.rend import Page
from nevow.athena import LivePage
from nevow.loaders import stan
from nevow.testutil import FakeRequest
from nevow.context import WovenContext
from nevow.inevow import IRequest


def _makeContext():
    request = FakeRequest()
    context = WovenContext()
    context.remember(request, IRequest)
    return (request, context)

def render(fragment):
    """
    Render the given fragment in a LivePage.

    This can only work for fragments which can be rendered synchronously.
    Fragments which involve Deferreds will be silently rendered incompletely.

    @type fragment: L{nevow.athena.LiveFragment} or L{nevow.athena.LiveElement}
    @param fragment: The page component to render.

    @rtype: C{str}
    @return: The result of rendering the fragment.
    """
    page = LivePage(docFactory=stan(fragment))
    fragment.setFragmentParent(page)
    (request, context) = _makeContext()
    page.renderHTTP(context)
    page.action_close(context)
    return request.v

def renderPlainFragment(fragment):
    """
    same as L{render}, but expects an L{nevow.rend.Fragment} or any
    other L{nevow.inevow.IRenderer}
    """
    page = Page(docFactory=stan(fragment))
    (request, context) = _makeContext()
    page.renderHTTP(context)
    return request.v
