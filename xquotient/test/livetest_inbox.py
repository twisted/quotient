from datetime import datetime

from nevow.livetrial import testcase
from nevow import tags, loaders

from epsilon.extime import Time

from axiom.store import Store
from axiom.item import Item
from axiom import attributes
from axiom.tags import Catalog

from xmantissa import ixmantissa
from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Organizer, Person, EmailAddress

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

        c = Catalog(store=s)

        def makeMessage(subj, spam=False, date=None, archived=False, sender=u'joe@divmod.com', tags=()):
            if date is None:
                date = Time()

            m = Message(store=s,
                        sender=sender,
                        subject=subj,
                        receivedWhen=date,
                        sentWhen=date,
                        spam=spam,
                        impl=_Part(store=s),
                        archived=archived,
                        read=False)

            for t in tags:
                c.tag(m, t)

        makeMessage(u'Message 1', date=Time.fromDatetime(datetime(1999, 12, 13)), tags=(u"Joe's Stuff",))
        makeMessage(u'Message 2', tags=(u"Joe's Stuff",))
        makeMessage(u'SPAM SPAM SPAM', spam=True)

        PrivateApplication(store=s).installOn(s)
        QuotientPreferenceCollection(store=s).installOn(s)
        o = Organizer(store=s)
        o.installOn(s)

        def makePerson(name, address):
            EmailAddress(store=s,
                         person=Person(store=s, organizer=o, name=name),
                         address=address,
                         type=u'default')

        makePerson(u'Joe', u'joe@divmod.com')

        makeMessage(u'Archived Message 1',
                    archived=True,
                    sender=u'bob@divmod.com',
                    tags=(u"Bob's Stuff", u'Archived'))

        makeMessage(u'Archived Message 2',
                    archived=True,
                    sender=u'bob@divmod.com',
                    tags=(u"Bob's Stuff", u'Archived'))

        makePerson(u'Bob', u'bob@divmod.com')

        inbox = Inbox(store=s)
        inbox.installOn(s)

        inboxFrag = ixmantissa.INavigableFragment(inbox)

        inboxFrag.jsClass = 'Quotient.Test.TestableMailboxSubclass'
        inboxFrag.setFragmentParent(self)
        inboxFrag.docFactory = getLoader(inboxFrag.fragmentName)

        return ctx.tag[inboxFrag]

class BatchActionsTestCase(testcase.TestCase):
    jsClass = u'Quotient.Test.BatchActionsTestCase'

    docFactory = loaders.stan(tags.div[
                    tags.div(render=tags.directive('liveTest'))['BatchActionsTestCase'],
                    tags.div(render=tags.directive('inbox'),
                             style='visibility: hidden'),
                    tags.div(id='mantissa-footer')])

    def render_inbox(self, ctx, data):
        s = Store()

        def makeMessage(subj, spam=False, date=None, sender=u'joe@divmod.com', read=False):
            if date is None:
                date = Time()

            m = Message(store=s,
                        sender=sender,
                        subject=subj,
                        receivedWhen=date,
                        sentWhen=date,
                        spam=spam,
                        impl=_Part(store=s),
                        archived=False,
                        read=read)

        PrivateApplication(store=s).installOn(s)
        QuotientPreferenceCollection(store=s).installOn(s)
        o = Organizer(store=s)
        o.installOn(s)

        for i in xrange(10):
            Message(store=s,
                    sender=u'joe@divmod.com',
                    subject=u'Message #' + str(9 - i),
                    receivedWhen=Time(),
                    sentWhen=Time(),
                    spam=False,
                    impl=_Part(store=s))

        inbox = Inbox(store=s)
        inbox.installOn(s)

        inboxFrag = ixmantissa.INavigableFragment(inbox)

        inboxFrag.jsClass = 'Quotient.Test.TestableMailboxSubclass'
        inboxFrag.setFragmentParent(self)
        inboxFrag.docFactory = getLoader(inboxFrag.fragmentName)

        return ctx.tag[inboxFrag]
