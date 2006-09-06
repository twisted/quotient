from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from epsilon.extime import Time

from nevow import loaders, tags, athena, context, rend
from nevow.test.test_rend import req as makeRequest

from axiom.store import Store

from xmantissa.webapp import PrivateApplication
from xmantissa.webtheme import getLoader
from xmantissa.people import Person, EmailAddress

from xquotient.exmess import Message, MessageDetail, PartDisplayer
from xquotient.inbox import Inbox, InboxScreen
from xquotient import compose
from xquotient.test.util import MIMEReceiverMixin, PartMaker
from xquotient.qpeople import MessageList, MessageLister


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
        Render the given resource.  Return a Deferred which fires when it has
        rendered.
        """
        D = self.renderPage(res, topLevelContext)
        return D.addCallback(lambda x: (res._messageDeliverer.close(), x)[1])


    def renderPage(self, res, topLevelContext=context.WebContext):
        return res.renderHTTP(
                    topLevelContext(
                        tag=res, parent=context.RequestContext(tag=makeRequest())))


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

        inbox = self.store.findUnique(Inbox)

        composer = compose.Composer(store=self.store)
        composer.installOn(self.store)

        return self.renderLivePage(
                    self.wrapFragment(
                        InboxScreen(inbox)))

    def test_peopleMessageListRendering(self):
        mlister = MessageLister(store=self.store)
        mlister.installOn(self.store)

        p = Person(store=self.store,
                   name=u'Bob')

        EmailAddress(store=self.store,
                     person=p,
                     address=u'bob@internet')

        for i in xrange(5):
            Message(store=self.store,
                    subject=unicode(str(i)),
                    receivedWhen=Time(),
                    spam=False,
                    sender=u'bob@internet')


        self.assertEqual(len(list(mlister.mostRecentMessages(p))), 5)
        return self.renderPage(rend.Page(docFactory=loaders.stan(MessageList(mlister, p))))

    def test_draftsRendering(self):
        """
        Test that L{xquotient.compose.DraftsScreen} renders without error.
        """
        for i in xrange(5):
            compose.Draft(store=self.store,
                          message=Message(store=self.store,
                                          draft=True,
                                          spam=False,
                                          subject=u'Foo'))

        compose.Composer(store=self.store)
        drafts = compose.Drafts(store=self.store)
        return self.renderLivePage(
                    self.wrapFragment(
                        compose.DraftsScreen(drafts)))


class PartTestCase(TestCase):
    def setUp(self):
        self.partDisplayer = PartDisplayer(None)


    def test_scrubbingInvalidDocument(self):
        """
        Pass a completely malformed document to L{PartDisplay.scrubbedHTML}
        and assert that it returns C{None} instead of raising an exception.
        """
        self.assertIdentical(None, self.partDisplayer.scrubbedHTML('<foo / bar>'))


    def test_scrubbingSimpleDocument(self):
        """
        Pass a trivial document to L{PartDisplay.scrubbedHMTL} and make sure
        it comes out the other side in-tact.
        """
        self.assertEquals('<div></div>', self.partDisplayer.scrubbedHTML('<div></div>'))
