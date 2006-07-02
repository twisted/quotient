
"""
Benchmark server-side rendering performance of some lightly nested
LiveFragments.
"""

from epsilon.scripts.benchmark import start, stop

from nevow.athena import LiveFragment
from nevow.loaders import stan
from nevow.tags import p, directive

from axiom.store import Store

from xquotient.benchmarks.rendertools import render

N_RENDERS = 500
DEPTH = 3

def renderOnce(fragmentClass):
    """
    Create L{DEPTH} LiveFragments, each nested within the next, and then render
    the result.
    """
    innerFragment = fragmentClass(
        docFactory=stan(p(render=directive('liveFragment'))[
                'Hello, world.']))
    for i in xrange(DEPTH - 1):
        outerFragment = fragmentClass(
            docFactory=stan(p(render=directive('liveFragment'))[
                    innerFragment]))
        innerFragment.setFragmentParent(outerFragment)
        innerFragment = outerFragment
    render(outerFragment)


def main(fragmentClass):
    """
    Benchmark L{N_RENDERS} calls of L{renderOnce}.
    """
    s = Store()
    start()
    for i in xrange(N_RENDERS):
        renderOnce(fragmentClass)
    stop()


if __name__ == '__main__':
    main(LiveFragment)
