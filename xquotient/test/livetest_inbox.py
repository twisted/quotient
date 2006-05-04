from datetime import datetime

from nevow.livetrial import testcase
from nevow import tags, loaders

from epsilon.extime import Time

from axiom.store import Store
from axiom.item import Item
from axiom import attributes

from xmantissa import ixmantissa
from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication

from xquotient.inbox import Inbox
from xquotient.exmess import Message
from xquotient.quotientapp import QuotientPreferenceCollection

class _Part(Item):
    typeName = 'mock_part_item'
    schemaVersion = 1

    junk = attributes.text()

    def walkMessage(self, *z):
        return ()
    walkAttachments = walkMessage

    def getHeader(self, *z):
        return u'hi!\N{WHITE SMILING FACE}<>'



class InboxTestCase(testcase.TestCase):
    jsClass = u'Quotient.Test.InboxTestCase'

    docFactory = loaders.stan(tags.div[
                    tags.div(render=tags.directive('liveTest'))['InboxTestCase'],
                    tags.div(render=tags.directive('inbox'),
                             style='visibility: hidden'),
                    tags.div(id='mantissa-footer')])

    def render_inbox(self, ctx, data):
        s = Store()

        def makeMessage(subj, spam=False, date=None):
            if date is None:
                date = Time()
            Message(store=s,
                    sender=u'joe@divmod.com',
                    subject=subj,
                    receivedWhen=date,
                    sentWhen=date,
                    spam=spam,
                    impl=_Part(store=s))

        makeMessage(u'Message 1', date=Time.fromDatetime(datetime(1999, 12, 13)))
        makeMessage(u'Message 2')
        makeMessage(u'SPAM SPAM SPAM', spam=True)

        PrivateApplication(store=s).installOn(s)
        QuotientPreferenceCollection(store=s).installOn(s)

        inbox = Inbox(store=s)
        inbox.installOn(s)

        inboxFrag = ixmantissa.INavigableFragment(inbox)
        inboxFrag.jsClass = 'Quotient.Test.TestableMailboxSubclass'
        inboxFrag.setFragmentParent(self)
        inboxFrag.docFactory = getLoader(inboxFrag.fragmentName)

        return ctx.tag[inboxFrag]
