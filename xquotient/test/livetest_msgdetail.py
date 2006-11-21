from epsilon.extime import Time

from axiom.store import Store
from axiom import attributes
from axiom.item import Item

from nevow.livetrial import testcase
from nevow import tags, loaders
from nevow.athena import expose

from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication
from xmantissa import people

from xquotient.exmess import Message, MessageDetail
from xquotient.quotientapp import QuotientPreferenceCollection
from xquotient.inbox import Inbox
from xquotient import equotient

_headers = {'cc': u'cc@host'}

class _Part(Item):
    z = attributes.integer()

    def getHeader(self, k):
        try:
            return _headers[k]
        except KeyError:
            raise equotient.NoSuchHeader()

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

    def _setUpStore(self):
        s = Store()
        PrivateApplication(store=s).installOn(s)
        QuotientPreferenceCollection(store=s).installOn(s)
        Inbox(store=s).installOn(s)
        return s

    def _setUpMsg(self):
        s = self._setUpStore()

        return Message(store=s,
                       sender=u'sender@host',
                       senderDisplay=u'Sender',
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

class MsgDetailAddPersonTestCase(MsgDetailTestCase):
    """
    Test adding a person from the msg detail
    """
    jsClass = u'Quotient.Test.MsgDetailAddPersonTestCase'

    docFactory = _docFactoryFactory('MsgDetailAddPersonTestCase')

    def _setUpStore(self):
        s = MsgDetailTestCase._setUpStore(self)
        people.Organizer(store=s).installOn(s)
        self.store = s
        return s

    def verifyPerson(self):
        """
        Called from the client after a person has been added.  Verifies that
        there is only one person, and that his details match those of the
        sender of the single message in our store
        """
        p = self.store.findUnique(people.Person)
        self.assertEquals(p.getEmailAddress(), 'sender@host')
        self.assertEquals(p.getDisplayName(), 'Sender')
    expose(verifyPerson)


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
