from epsilon.extime import Time

from axiom.store import Store
from axiom import attributes
from axiom.item import Item

from nevow.livetrial import testcase
from nevow import tags, loaders

from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication

from xquotient.exmess import Message, MessageDetail
from xquotient.quotientapp import QuotientPreferenceCollection
from xquotient.inbox import Inbox

_headers = {'cc': u'cc@host'}

class _Part(Item):
    z = attributes.integer()

    def getHeader(self, k):
        return _headers[k]

    def walkMessage(self, *junk):
        return ()
    walkAttachments = walkMessage

def _docFactoryFactory(testName, renderMethod='msgDetail'):
    return loaders.stan(tags.div[
                tags.div(render=tags.directive('liveTest'))[testName],
                tags.div(render=tags.directive('msgDetail'))])

class MsgDetailTestCase(testcase.TestCase):
    """
    Tests for L{xquotient.exmess.MessageDetail}
    """
    jsClass = u'Quotient.Test.MsgDetailTestCase'

    docFactory = _docFactoryFactory('MsgDetailTestCase')

    def _setUpMsg(self):
        s = Store()
        PrivateApplication(store=s).installOn(s)
        QuotientPreferenceCollection(store=s).installOn(s)
        Inbox(store=s).installOn(s)

        return Message(store=s,
                       sender=u'sender@host',
                       recipient=u'recipient@host',
                       subject=u'the subject',
                       impl=_Part(store=s),
                       sentWhen=Time.fromPOSIXTimestamp(0),
                       receivedWhen=Time.fromPOSIXTimestamp(1))

    def render_msgDetail(self, ctx, data):
        """
        Setup & populate a store, and render a L{xquotient.exmess.MessageDetail}
        """
        f = MessageDetail(self._setUpMsg())
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        return f

class MsgDetailInitArgsTestCase(MsgDetailTestCase):
    """
    Test for L{xquotient.exmess.MessageDetail}'s initargs
    """

    jsClass = u'Quotient.Test.MsgDetailInitArgsTestCase'

    docFactory = _docFactoryFactory('MsgDetailInitArgsTestCase')

    def _setUpMsg(self):
        m = super(MsgDetailInitArgsTestCase, self)._setUpMsg()
        m.store.findUnique(Inbox).showMoreDetail = True
        return m
