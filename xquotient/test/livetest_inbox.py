from datetime import datetime, timedelta

from nevow.livetrial import testcase
from nevow.athena import LiveFragment, expose

from epsilon.extime import Time

from axiom.store import Store
from axiom.item import Item
from axiom import attributes
from axiom.tags import Catalog
from axiom.scheduler import Scheduler

from xmantissa.website import WebSite
from xmantissa.webtheme import getLoader
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Organizer, Person, EmailAddress
from xmantissa.test.livetest_scrolltable import ScrollElement

from xquotient.inbox import Inbox, InboxScreen, MailboxScrollingFragment
from xquotient.exmess import Message
from xquotient.compose import Composer, ComposeFragment
from xquotient.quotientapp import QuotientPreferenceCollection


class ThrobberTestCase(testcase.TestCase):
    """
    Tests for the inbox activity indicator.
    """
    jsClass = u'Quotient.Test.ThrobberTestCase'



class ScrollingWidgetTestCase(testcase.TestCase):
    """
    More tests for the inbox-specific ScrollingWidget subclass.
    """
    jsClass = u'Quotient.Test.ScrollingWidgetTestCase'

    def getScrollingWidget(self, howManyElements=0):
        store = Store()
        PrivateApplication(store=store).installOn(store)
        elements = [ScrollElement(store=store) for n in xrange(howManyElements)]
        columns = [ScrollElement.column]
        f = MailboxScrollingFragment(store, lambda view: None, None, ScrollElement, columns)
        f.docFactory = getLoader(f.fragmentName)
        f.setFragmentParent(self)
        return f
    expose(getScrollingWidget)



class ScrollTableTestCase(ScrollingWidgetTestCase):
    """
    Tests for the inbox-specific ScrollingWidget subclass.
    """
    jsClass = u'Quotient.Test.ScrollTableTestCase'

    def getWidgetDocument(self):
        return self.getScrollingWidget()



class _Part(Item):
    typeName = 'mock_part_item'
    schemaVersion = 1

    junk = attributes.text()

    def walkMessage(self, *z):
        return ()
    walkAttachments = walkMessage

    def getHeader(self, *z):
        return u'hi!\N{WHITE SMILING FACE}<>'



class StubComposeFragment(LiveFragment):
    jsClass = ComposeFragment.jsClass
    fragmentName = ComposeFragment.fragmentName

    def __init__(self, composer, toAddress, subject, messageBody, attachments, inline):
        self.composer = composer
        self.toAddress = toAddress
        self.subject = subject
        self.messageBody = messageBody
        self.attachments = attachments
        self.inline = inline
        self.invokeArguments = []


    def getInvokeArguments(self):
        """
        Return a list of form arguments which have been passed to
        C{self.invoke}.
        """
        return self.invokeArguments
    expose(getInvokeArguments)


    # These are the Athena methods required to be exposed
    def invoke(self, arguments):
        self.invokeArguments.append(arguments)
    expose(invoke)


    def getInitialArguments(self):
        return (self.inline, ())


    # Render stuff
    def rend(self, ctx, data):
        """
        Fill the slots the template requires to be filled in order to be
        rendered.
        """
        ctx.fillSlots('to', 'alice@example.com')
        ctx.fillSlots('cc', 'bob@example.com')
        ctx.fillSlots('subject', 'Test Message')
        ctx.fillSlots('attachments', '')
        ctx.fillSlots('body', 'message body text')
        return LiveFragment.rend(self, ctx, data)


    # These are the renderers required by the template.
    def render_fileCabinet(self, ctx, data):
        return ctx.tag


    def render_compose(self, ctx, data):
        return ctx.tag


    def render_inboxLink(self, ctx, data):
        return ctx.tag


    def render_button(self, ctx, data):
        return ctx.tag



class _ControllerMixin:
    aliceEmail = u'alice@example.com'
    bobEmail = u'bob@example.com'

    sent = Time.fromDatetime(datetime(1999, 12, 13))

    def getInbox(self):
        """
        Return a newly created Inbox, in a newly created Store which has all of
        the Inbox dependencies (you know this function is broken because it is
        more than C{return Inbox(store=Store())}
        """
        s = Store()
        Scheduler(store=s).installOn(s)
        Catalog(store=s)
        WebSite(store=s).installOn(s)
        PrivateApplication(store=s).installOn(s)
        QuotientPreferenceCollection(store=s).installOn(s)
        Composer(store=s).installOn(s)
        Organizer(store=s).installOn(s)
        inbox = Inbox(store=s)
        inbox.installOn(s)
        return inbox



class ControllerTestCase(testcase.TestCase, _ControllerMixin):
    jsClass = u'Quotient.Test.ControllerTestCase'

    def getControllerWidget(self):
        """
        Retrieve the Controller widget for a mailbox in a particular
        configuration.

        The particulars of the email in this configuration are::

            There are 5 messages total.

            The inbox contains 2 unread messages.

            The archive contains 2 read messages.

            The spam folder contains 1 unread message.

            The sent folter contains 1 read message.

            The trash folder contains 2 read messages.

        There are also some people.  They are::

            Alice - alice@example.com

            Bob - bob@example.com

        The 1st message in the inbox is tagged "foo".
        The 2nd message in the inbox is tagged "bar".
        """
        inbox = self.getInbox()
        organizer = inbox.store.findUnique(Organizer)
        application = inbox.store.findUnique(PrivateApplication)
        catalog = inbox.store.findUnique(Catalog)

        offset = timedelta(seconds=30)

        impl = _Part(store=inbox.store)

        # Inbox messages
        m1 = Message(
            store=inbox.store, sender=self.aliceEmail, subject=u'1st message',
            receivedWhen=self.sent, sentWhen=self.sent, spam=False,
            archived=False, read=False, impl=impl)
        catalog.tag(m1, u"foo")

        m2 = Message(
            store=inbox.store, sender=self.aliceEmail, subject=u'2nd message',
            receivedWhen=self.sent + offset, sentWhen=self.sent,
            spam=False, archived=False, read=False, impl=impl)
        catalog.tag(m2, u"bar")

        # Archive messages
        m3 = Message(
            store=inbox.store, sender=self.aliceEmail, subject=u'3rd message',
            receivedWhen=self.sent + offset * 2, sentWhen=self.sent,
            spam=False, archived=True, read=True, impl=impl)

        m4 = Message(
            store=inbox.store, sender=self.aliceEmail, subject=u'4th message',
            receivedWhen=self.sent + offset * 3, sentWhen=self.sent,
            spam=False, archived=True, read=True, impl=impl)

        # Spam message
        m5 = Message(
            store=inbox.store, sender=self.bobEmail, subject=u'5th message',
            receivedWhen=self.sent + offset * 4, sentWhen=self.sent,
            spam=True, archived=False, read=False, impl=impl)

        # Sent message
        m6 = Message(
            store=inbox.store, sender=self.bobEmail, subject=u'6th message',
            receivedWhen=self.sent + offset * 5, sentWhen=self.sent,
            spam=False, archived=False, read=True, outgoing=True,
            impl=impl)

        # Trash messages
        m7 = Message(
            store=inbox.store, sender=self.bobEmail, subject=u'7th message',
            receivedWhen=self.sent + offset * 6, sentWhen=self.sent,
            spam=False, archived=False, read=True, outgoing=False,
            trash=True, impl=impl)

        m8 = Message(
            store=inbox.store, sender=self.bobEmail, subject=u'8th message',
            receivedWhen=self.sent + offset * 7, sentWhen=self.sent,
            spam=False, archived=False, read=True, outgoing=False,
            trash=True, impl=impl)

        # Alice
        alice = Person(store=inbox.store, organizer=organizer, name=u"Alice")
        EmailAddress(store=inbox.store, person=alice, address=self.aliceEmail)

        # Bob
        bob = Person(store=inbox.store, organizer=organizer, name=u"Bob")
        EmailAddress(store=inbox.store, person=bob, address=self.bobEmail)

        self.names = {
            application.toWebID(alice): u'Alice',
            application.toWebID(bob): u'Bob'}

        self.messages = dict(
            (application.toWebID(m), m)
            for m
            in [m1, m2, m3, m4, m5, m6, m7, m8])

        fragment = InboxScreen(inbox)
        fragment.composeFragmentFactory = StubComposeFragment
        fragment.setFragmentParent(self)
        return fragment
    expose(getControllerWidget)


    def personNamesByKeys(self, *keys):
        """
        Return the names of the people with the given webIDs.
        """
        return [self.names[k] for k in keys]
    expose(personNamesByKeys)


    def deletedFlagsByWebIDs(self, *ids):
        """
        Return the deleted flag of the messages with the given webIDs.
        """
        return [self.messages[id].trash for id in ids]
    expose(deletedFlagsByWebIDs)


    def archivedFlagsByWebIDs(self, *ids):
        """
        Return the archived flag of the messages with the given webIDs.
        """
        return [self.messages[id].archived for id in ids]
    expose(archivedFlagsByWebIDs)


    def trainedStateByWebIDs(self, *ids):
        """
        Return a dictionary describing the spam training state of the messages
        with the given webID.
        """
        return [{u'trained': self.messages[id].trained,
                 u'spam': self.messages[id].spam}
                for id in ids]
    expose(trainedStateByWebIDs)


    def deferredStateByWebIDs(self, *ids):
        """
        Return the deferred flag of the messages with the given webIDs.
        """
        return [self.messages[id].deferred for id in ids]
    expose(deferredStateByWebIDs)



class EmptyInitialViewControllerTestCase(testcase.TestCase, _ControllerMixin):
    """
    Tests for behaviors where the mailbox loads and the initial view is empty,
    but other views contain messages.
    """
    jsClass = u'Quotient.Test.EmptyInitialViewControllerTestCase'

    def getControllerWidget(self):
        """
        Retrieve the Controller widget for a mailbox with no message in the
        inbox view but several messages in the archive view.
        """
        inbox = self.getInbox()


        offset = timedelta(seconds=30)

        impl = _Part(store=inbox.store)

        # Archive messages
        m1 = Message(
            store=inbox.store, sender=self.aliceEmail, subject=u'1st message',
            receivedWhen=self.sent, sentWhen=self.sent, spam=False,
            archived=True, read=False, impl=impl)

        m2 = Message(
            store=inbox.store, sender=self.aliceEmail, subject=u'2nd message',
            receivedWhen=self.sent + offset, sentWhen=self.sent,
            spam=False, archived=True, read=False, impl=impl)

        fragment = InboxScreen(inbox)
        fragment.composeFragmentFactory = StubComposeFragment
        fragment.setFragmentParent(self)
        return fragment
    expose(getControllerWidget)



class EmptyControllerTestCase(testcase.TestCase, _ControllerMixin):
    jsClass = u'Quotient.Test.EmptyControllerTestCase'

    def getEmptyControllerWidget(self):
        """
        Retrieve the Controller widget for a mailbox with no messages in it.
        """
        inbox = self.getInbox()
        fragment = InboxScreen(inbox)
        fragment.composeFragmentFactory = StubComposeFragment
        fragment.setFragmentParent(self)
        return fragment
    expose(getEmptyControllerWidget)
