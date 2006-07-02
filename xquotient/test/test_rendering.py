from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from epsilon.extime import Time

from nevow import loaders, tags, athena, context
from nevow.test.test_rend import req as makeRequest

from axiom.store import Store

from xmantissa.webapp import PrivateApplication
from xmantissa.webtheme import getLoader

from xquotient.exmess import Message, MessageDetail
from xquotient.inbox import Inbox, InboxScreen
from xquotient.compose import Composer
from xquotient.quotientapp import QuotientPreferenceCollection
from xquotient.test.util import MIMEReceiverMixin, PartMaker


def makeMessage(receiver, parts, impl):
    """
    Create a new L{exmess.Message}, either by parsing C{parts} or by wrapping
    one around C{impl}.
    """
    if impl is None:
        return receiver.feedStringNow(parts)
    else:
        return Message(store=impl.store,
                       receivedWhen=Time(),
                       sentWhen=Time(),
                       spam=False,
                       impl=impl)



# Trial is excruciating.  Temporary hack until Twisted ticket #1870 is
# resolved
_theBaseStorePath = None
def getBaseStorePath(messageParts):
    """
    Create a minimal database usable for some mail functionality and place
    a single message into it.
    """
    global _theBaseStorePath
    if _theBaseStorePath is None:
        class DBSetup(MIMEReceiverMixin, TestCase):
            def test_x():
                pass
        receiver = DBSetup('test_x').setUpMailStuff()
        store = receiver.store
        PrivateApplication(store=store).installOn(store)
        QuotientPreferenceCollection(store=store).installOn(store)
        makeMessage(receiver, messageParts, None)
        store.close()
        _theBaseStorePath = store.dbdir
    return _theBaseStorePath



class RenderingTestCase(TestCase, MIMEReceiverMixin):
    aBunchOfRelatedParts = PartMaker(
        'multipart/related', 'related',
        *(list(PartMaker('text/html', '<p>html-' + str(i) + '</p>')
               for i in xrange(100)) +
          list(PartMaker('image/gif', '')
               for i in xrange(100)))).make()


    def setUp(self):
        """
        Make a copy of the very minimal database for a single test method to
        mangle.
        """
        self.dbdir = self.mktemp()
        src = getBaseStorePath(self.aBunchOfRelatedParts)
        dst = FilePath(self.dbdir)
        src.copyTo(dst)
        self.store = Store(self.dbdir)


    def wrapFragment(self, f):
        """
        Wrap a L{athena.LivePage}, including a minimal amount of html
        scaffolding, around the given fragment.

        The fragment will have its fragment parent and docFactory (based on
        fragmentName) set.

        @param f: The fragment to include in the page.
        @return: An page instance which will include the given fragment when
        rendered.
        """
        class _Page(athena.LivePage):
            docFactory = loaders.stan(
                            tags.html[
                                tags.body[
                                    tags.directive('fragment')]])

            def render_fragment(self, ctx, data):
                f.setFragmentParent(self)
                f.docFactory = getLoader(f.fragmentName)
                return f

        return _Page()


    def renderLivePage(self, res, topLevelContext=context.WebContext):
        """
        Render the given resource.  Return a Defered which fires when it has
        rendered.
        """

        D = res.renderHTTP(
                  topLevelContext(
                      tag=res, parent=context.RequestContext(tag=makeRequest())))
        return D.addCallback(lambda x: (res._messageDeliverer.close(), x)[1])


    def test_messageRendering(self):
        """
        Test rendering of message detail for an extremely complex message.
        """
        msg = self.store.findUnique(Message)
        return self.renderLivePage(
                    self.wrapFragment(
                        MessageDetail(msg)))


    def test_inboxRendering(self):
        """
        Test rendering of the inbox with a handful of extremely complex
        messages in it.
        """
        def deliverMessages():
            msg = self.store.findUnique(Message)
            for i in xrange(5):
                makeMessage(None, None, msg.impl)
        self.store.transact(deliverMessages)

        inbox = Inbox(store=self.store)
        inbox.installOn(self.store)

        composer = Composer(store=self.store)
        composer.installOn(self.store)

        return self.renderLivePage(
                    self.wrapFragment(
                        InboxScreen(inbox)))
