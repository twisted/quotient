# -*- test-case-name: xquotient.test.test_inbox.InboxTestCase.testUnreadMessageCount -*-

from datetime import datetime, timedelta

from twisted.trial.unittest import TestCase

from epsilon.extime import Time

from axiom.store import Store
from axiom.scheduler import Scheduler

from axiom.tags import Catalog
from axiom.attributes import integer
from axiom.item import Item

from xmantissa.ixmantissa import INavigableFragment, IWebTranslator
from xmantissa.webapp import PrivateApplication
from xmantissa.people import Organizer, Person, EmailAddress

from xquotient.exmess import (Message, _UndeferTask as UndeferTask,
                              MailboxSelector, UNREAD_STATUS, READ_STATUS,
                              Correspondent, SENDER_RELATION, DRAFT_STATUS,
                              SENT_STATUS, DEFERRED_STATUS,
                              EVER_DEFERRED_STATUS, RECIPIENT_RELATION,
                              COPY_RELATION, BLIND_COPY_RELATION)

from xquotient.inbox import (Inbox, InboxScreen, replaceControlChars, VIEWS,
                             replyToAll, MailboxScrollingFragment)
from xquotient.quotientapp import QuotientPreferenceCollection
from xquotient import compose, mimeutil
from xquotient.test.test_workflow import (DummyMessageImplementation, QueryCounter,
                                          DummyMessageImplementationMixin)



def testMessageFactory(store, archived=False, spam=None, read=False,
                       sentWhen=None, receivedWhen=None, subject=u'',
                       trash=False, outgoing=False, draft=False, impl=None,
                       sender=None, recipient=u''):
    """
    Provide a simulacrum of message's old constructor signature to avoid
    unnecessarily deep modification of tests.

    @return: an exmess.Message object.
    """
    if impl is None:
        impl = DummyMessageImplementation(store=store)
        if sender is not None:
            impl.senderInfo = sender
    if outgoing:
        m = Message.createDraft(store, impl, u'test://test/draft')
        if not draft:
            # XXX: this is *actually* the status change that transpires when
            # you transition a message from "draft" to "sent" status.
            m.removeStatus(DRAFT_STATUS)
            m.addStatus(SENT_STATUS)
        if spam is not None:
            assert spam is False, "That doesn't make any sense."
    else:
        m = Message.createIncoming(store, impl, u'test://test')
        if spam is not None:
            if spam:
                m.classifySpam()
            else:
                m.classifyClean()

    m.subject = subject
    m.recipient = recipient     # should this be handled somewhere else?  ugh.
    if read:
        m.markRead()
    if archived:
        m.archive()
    if trash:
        m.moveToTrash()

    # these next bits are definitely wrong.  they should be set up by analysis
    # of the body part, probably?
    if receivedWhen:
        m.receivedWhen = receivedWhen
        # we're supplying our own received date, after message creation, but
        # this won't be reflected in the statusDate of the statuses that were
        # added to the message as a result of createIncoming, so we'll remove
        # them all and re-add them
        for s in m.iterStatuses():
            m.removeStatus(s)
            m.addStatus(s)
    if sentWhen:
        m.sentWhen = sentWhen
    if sender:
        m.sender = sender
        m.senderDisplay = sender
        # Cheat so that nit test setup will work; this is gross, but inverting
        # it to be specified properly (in the tests' impl) would be even more
        # of a pain in the ass right now... -glyph
        Correspondent(store=store,
                      relation=SENDER_RELATION,
                      message=m,
                      address=sender)
    return m



class _MessageRetrievalMixin:
    """
    Provides a useful C{setUp} for test cases that retrieve messages
    """
    def setUp(self):
        """
        Create a handful of messages spread out over a brief time period so
        that tests can assert things about methods which operate on messages.
        """
        self.store = Store()

        # Inbox requires but does not provide IWebTranslator.
        self.privateApplication = PrivateApplication(store=self.store)
        self.privateApplication.installOn(self.store)
        self.webTranslator = IWebTranslator(self.store)

        baseTime = datetime(year=2001, month=3, day=6)
        self.msgs = []
        for i in xrange(5):
            self.msgs.append(
                testMessageFactory(store=self.store,
                        read=False,
                        spam=False,
                        receivedWhen=Time.fromDatetime(
                            baseTime + timedelta(seconds=i))))
        self.inbox = InboxScreen(Inbox(store=self.store))


class MessageRetrievalTestCase(_MessageRetrievalMixin, TestCase):
    """
    Test various methods for finding messages.
    """
    def test_getInitialArguments(self):
        """
        Test that L{InboxScreen} properly initializes its client-side
        complement with the number of messages in the current view, an
        identifier for the first message, and the persistent complexity
        setting.
        """
        [complexity] = self.inbox.getInitialArguments()
        self.assertEqual(complexity, 1)

        self.inbox.inbox.uiComplexity = 2
        [complexity] = self.inbox.getInitialArguments()
        self.assertEqual(complexity, 2)



class InboxTestCase(TestCase):
    def testControlChars(self):
        s = ''.join(map(chr, range(1, 32))) + 'foobar'
        # ord('\t') < ord('\n') < ord('\r')
        self.assertEquals(replaceControlChars(s), '\t\n\rfoobar')


    def testAdaption(self):
        """
        Test that an Inbox can be adapted to INavigableFragment so that it can
        be displayed on a webpage.
        """
        s = Store()
        PrivateApplication(store=s).installOn(s)
        inbox = Inbox(store=s)
        self.assertNotIdentical(INavigableFragment(inbox, None), None)


    def test_userTagNames(self):
        """
        Verify that tags created in the axiom tags system will show up to the
        inbox via getUserTagNames
        """
        s = Store()
        m = testMessageFactory(store=s)
        c = Catalog(store=s)
        c.tag(m, u'tag1')
        c.tag(m, u'taga')
        c.tag(m, u'tagstart')

        PrivateApplication(store=s).installOn(s) # IWebTranslator
        ib = Inbox(store=s)
        ibs = InboxScreen(ib)
        self.assertEquals(ibs.getUserTagNames(),
                          [u'tag1', u'taga', u'tagstart'])

    def test_unreadMessageCount(self):
        """
        Check that the count returned by
        L{xquotient.inbox.InboxScreen.getUnreadMessageCount} matches our
        expectations for a variety of views
        """
        s = Store()

        for i in xrange(6):
            testMessageFactory(store=s, read=True, spam=False, receivedWhen=Time())
        for i in xrange(13):
            m = testMessageFactory(store=s, read=False, spam=False, receivedWhen=Time())

        PrivateApplication(store=s).installOn(s) # IWebTranslator

        # *seems* like we shouldn't have to adapt Inbox, but
        # the view state variables (inAllView, inSpamView, etc)
        # seem pretty clearly to belong on InboxScreen, carrying
        # most of the interesting methods with them

        # we're in the "Inbox" view
        inbox = Inbox(store=s)
        inboxScreen = InboxScreen(inbox)
        viewSelection = dict(inboxScreen.viewSelection)
        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 13)
        sq = MailboxSelector(s)
        sq.refineByStatus(READ_STATUS)
        iter(sq).next().markUnread()
        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 14)

        viewSelection["view"] = 'spam'
        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 0)

        sq = MailboxSelector(s)
        sq.refineByStatus(UNREAD_STATUS)
        sq.setLimit(6)
        spam = []
        for m in sq:
            m.classifySpam()
            spam.append(m)

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 6)

        for m in spam:
            m.classifyClean()
        m.archive()

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 0)

        viewSelection["view"] = 'all'

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 14)

        viewSelection["view"] = 'sent'

        self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 0)

        m.archive()
        # the next bit tests a totally nonsense situation.
#         m.outgoing = True

#         self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 1)

#         viewSelection["view"] = 'inbox'

#         self.assertEqual(inboxScreen.getUnreadMessageCount(viewSelection), 13)


    def test_unreadCountComplexityLimit(self):
        """
        Verify that unread counts on arbitrarily large mailboxes only perform
        counting work up to a specified limit.
        """
        s = Store()
        COUNT_LIMIT = 10
        assert ((COUNT_LIMIT // 2) * 2) == COUNT_LIMIT, "count limit must be even"
        def makeSomeMessages():
            for i in xrange(COUNT_LIMIT // 2):
                testMessageFactory(store=s, read=False, spam=False,
                                   receivedWhen=Time())

        PrivateApplication(store=s).installOn(s) # IWebTranslator

        inbox = Inbox(store=s)
        inboxScreen = InboxScreen(inbox)
        inboxScreen.countLimit = COUNT_LIMIT
        viewSelection = dict(inboxScreen.viewSelection)
        def countit():
            return inboxScreen.getUnreadMessageCount(viewSelection)
        makeSomeMessages()
        self.assertEqual(countit(), COUNT_LIMIT // 2)
        makeSomeMessages()
        self.assertEqual(countit(), COUNT_LIMIT)
        makeSomeMessages()
        self.assertEqual(countit(), COUNT_LIMIT)
        # Now make sure the DB's work is limited too, not just the result
        # count.
        qc = QueryCounter(s)
        m1 = qc.measure(countit)
        makeSomeMessages()
        m2 = qc.measure(countit)
        self.assertEqual(m1, m2)


    def test_mailViewCounts(self):
        """
        Test that L{mailViewCounts} shows the correct number of unread
        messages for each view, and that it updates as new messages are
        added to those views.
        """
        s = Store()
        PrivateApplication(store=s).installOn(s)
        inboxScreen = InboxScreen(Inbox(store=s))

        def makeMessages(number, **flags):
            for i in range(number):
                testMessageFactory(store=s, receivedWhen=Time(), **flags)

        def assertCountsAre(**d):
            for k in VIEWS:
                if not k in d:
                    d[k] = 0
            self.assertEqual(inboxScreen.mailViewCounts(), d)

        makeMessages(9, read=False, spam=False)
        makeMessages(3, read=False, spam=False, archived=True)
        assertCountsAre(inbox=9, all=12, archive=3)

        makeMessages(4, read=False, spam=True)
        makeMessages(3, read=True, spam=True)
        assertCountsAre(inbox=9, all=12, archive=3, spam=4)

        makeMessages(2, read=False, trash=True)
        assertCountsAre(inbox=9, all=12, archive=3, spam=4, trash=2)

        makeMessages(4, read=False, outgoing=True)
        assertCountsAre(inbox=9, all=12, archive=3, spam=4, trash=2, sent=4)


    def testDefer(self):
        s = Store()
        inbox = Inbox(store=s)

        scheduler = Scheduler(store=s)
        scheduler.installOn(s)

        message = testMessageFactory(store=s, read=True)
        task = inbox.action_defer(message, 365, 0, 0)
        self.failUnless(message.hasStatus(DEFERRED_STATUS), 'message was not deferred')
        # XXX I don't think this test is a good idea.  there's no reason
        # action_defer should return anything.
        scheduler.reschedule(task, task.deferredUntil, Time())
        scheduler.tick()
        self.failIf(message.hasStatus(DEFERRED_STATUS), 'message is still deferred')
        self.failIf(message.read, 'message is marked read')
        self.failUnless(message.hasStatus(EVER_DEFERRED_STATUS), 'messsage does not have "ever deferred" status')
        self.assertEquals(s.count(UndeferTask), 0)

    def testDeferCascadingDelete(self):
        s = Store()
        inbox = Inbox(store=s)

        scheduler = Scheduler(store=s)
        scheduler.installOn(s)

        message = testMessageFactory(store=s)
        task = inbox.action_defer(message, 365, 0, 0)
        message.deleteFromStore()
        self.assertEquals(s.count(UndeferTask), 0)

    def _setUpInbox(self):
        s = Store()

        QuotientPreferenceCollection(store=s).installOn(s)

        self.translator = PrivateApplication(store=s)
        self.translator.installOn(s)

        msgs = list(testMessageFactory(
                store=s,
                subject=unicode(str(i)),
                spam=False,
                receivedWhen=Time(),
                sentWhen=Time())
                    for i in xrange(5))
        msgs.reverse()

        self.inboxScreen = InboxScreen(Inbox(store=s))
        self.viewSelection = dict(self.inboxScreen.viewSelection)
        self.msgs = msgs
        self.msgIds = map(self.translator.toWebID, self.msgs)
        self.store = s


    def testLookaheadWithActions(self):
        """
        Test that message lookahead is correct when the process
        of moving from one message to the next is accomplished by
        eliminating the current message from the active view (e.g.
        by acting on it), rather than doing it explicitly with
        selectMessage().  Do this all the way down, until there
        are no messages left
        """
        self._setUpInbox()

        for i in range(len(self.msgs) - 2):
            readCount, unreadCount = self.inboxScreen.actOnMessageIdentifierList(
                'archive',
                [self.msgIds[i]])

            self.assertEquals(readCount, 1)
            self.assertEquals(unreadCount, 0)

        readCount, unreadCount = self.inboxScreen.actOnMessageIdentifierList(
            'archive',
            [self.msgIds[i + 1]])

        self.assertEquals(readCount, 1)
        self.assertEquals(unreadCount, 0)

        readCount, unreadCount = self.inboxScreen.actOnMessageIdentifierList(
            'archive',
            [self.msgIds[i + 2]])

        self.assertEquals(readCount, 1)
        self.assertEquals(unreadCount, 0)
    testLookaheadWithActions.todo = "read/unread flag not managed properly yet."


    def test_fastForward(self):
        """
        Test fast forwarding to a particular message by id sets that message
        to read.
        """
        self._setUpInbox()
        fragment = self.inboxScreen.fastForward(self.viewSelection, self.msgIds[2])
        self.failUnless(self.msgs[2].read)


    def test_messagesForBatchType(self):
        """
        Test that the correct messages are returned from
        L{Inbox.messagesForBatchType}.
        """
        store = Store()
        inbox = Inbox(store=store)

        viewSelection = {
            u"view": "inbox",
            u"tag": None,
            u"person": None,
            u"account": None}

        # Test that even with no messages, it spits out the right value (an
        # empty list).
        for batchType in ("read", "unread", "all"):
            self.assertEquals(
                list(inbox.messagesForBatchType(batchType, viewSelection)),
                [])

        # Make one message and assert that it only comes back from queries for
        # the batch type which applies to it.
        message = testMessageFactory(store=store, spam=False)

        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [message])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message])

        message.markRead()
        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [message])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message])

        # Make one more and make sure the batch is correct with various
        # combinations of states between the two.
        other = testMessageFactory(store=store, spam=False)

        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [message])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [other])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message, other])

        other.markRead()
        self.assertEquals(list(inbox.messagesForBatchType("read", viewSelection)), [message, other])
        self.assertEquals(list(inbox.messagesForBatchType("unread", viewSelection)), [])
        self.assertEquals(list(inbox.messagesForBatchType("all", viewSelection)), [message, other])

    def testGetComposer(self):
        """
        Test L{xquotient.inbox.InboxScreen.getComposer}
        """
        self._setUpInbox()
        compose.Composer(store=self.store).installOn(self.store)
        composer = self.inboxScreen.getComposer()

        self.failIf(composer.toAddresses)
        self.failIf(composer.subject)
        self.failIf(composer.messageBody)
        self.failIf(composer.attachments)

        self.failUnless(composer.inline)



class ReadUnreadTestCase(TestCase):
    """
    Tests for all operations which should change the read/unread state of
    messages.
    """
    NUM_MESSAGES = 5

    def setUp(self):
        self.store = Store()

        # Required for InboxScreen to even be instantiated
        self.translator = PrivateApplication(store=self.store)
        self.translator.installOn(self.store)

        # Required for InboxScreen.fastForward to be called successfully.
        self.preferences = QuotientPreferenceCollection(store=self.store)

        self.inbox = Inbox(store=self.store)
        self.inbox.installOn(self.store)
        self.messages = []
        for i in range(self.NUM_MESSAGES):
            self.messages.append(
                testMessageFactory(store=self.store,
                        spam=False,
                        receivedWhen=Time(),
                        subject=u''
                        ))
        self.messages.reverse()


    def test_screenCreation(self):
        """
        Test that creating the view for an inbox marks the first message in
        that mailbox as read.

        XXX - Uhhh, is this actually the desired behavior?  It seems kind of
        broken. -exarkun
        """

        # Make sure things start out in the state we expect
        for msg in self.messages:
            self.failIf(msg.read, "Messages should start unread.")

        screen = InboxScreen(self.inbox)

        # All but the first message should still be unread
        for msg in self.messages[:-1]:
            self.failIf(msg.read, "Subsequent messages should be unread.")

        # But the first message in the mailbox should now be read
        self.failUnless(self.messages[-1].read, "First message should be read.")


    def test_fastForward(self):
        """
        Test that fast forwarding to a message marks that message as read.
        """
        screen = InboxScreen(self.inbox)
        viewSelection = screen.viewSelection

        screen.fastForward(viewSelection, self.translator.toWebID(self.messages[-2]))

        # All but the first two messages should still be unread
        for msg in self.messages[:-2]:
            self.failIf(msg.read, "Subsequent messages should be unread.")

        # But the first two should be read.
        for msg in self.messages[-2:]:
            self.failUnless(msg.read, "First two messages should be read.")

        # Jump to the end of the mailbox
        screen.fastForward(viewSelection, self.translator.toWebID(self.messages[0]))

        for msg in self.messages[1:-2]:
            self.failIf(msg.read, "Middle messages should be unread.")

        for msg in self.messages[:1] + self.messages[-2:]:
            self.failUnless(msg.read, "Outter messages should be read.")


    def test_actOnMessageIdentifierList(self):
        """
        Test that when an unread message is revealed as a result of performing
        some action, that message becomes marked as read.
        """
        screen = InboxScreen(self.inbox)

        screen.actOnMessageIdentifierList(
            'archive',
            [self.translator.toWebID(self.messages[-1])])

        for msg in self.messages[:-1]:
            self.failIf(msg.read, "Subsequent messages should be unread.")

        for msg in self.messages[-1:]:
            self.failUnless(msg.read, "Initial and revealed message should be read.")


class MessagesByPersonRetrievalTestCase(_MessageRetrievalMixin, TestCase):
    """
    Test finding messages by specifying a person who we'd like to see messages
    from
    """

    def setUp(self):
        """
        Extend L{_MessageRetrievalMixin.setUp} to also install an
        L{Organizer}, L{Person} and L{EmailAddress}, and an L{Message} from
        that person
        """
        super(MessagesByPersonRetrievalTestCase, self).setUp()

        self.organizer = Organizer(store=self.store)
        self.organizer.installOn(self.store)

        self.person = Person(store=self.store,
                             organizer=self.organizer,
                             name=u'The Person')

        EmailAddress(store=self.store,
                     address=u'the@person',
                     person=self.person)

        self.messageFromPerson = testMessageFactory(
            store=self.store,
            read=False,
            spam=False,
            receivedWhen=Time(),
            sender=u'the@person')


    def test_initialQueryIncludesPeople(self):
        """
        Test that the intial view selection/query includes messages that were
        sent by a person in the address book
        """
        self.assertEquals(
            self.inbox.scrollingFragment.requestCurrentSize(),
            len(self.msgs) + 1)


    def test_countChangesIfQueryChanges(self):
        """
        Test that the number of messages in the model changes when the view
        selection/query specifies only messages from a particular person
        """
        viewSelection = self.inbox.scrollingFragment.viewSelection.copy()
        viewSelection['person'] = self.webTranslator.toWebID(self.person)

        self.inbox.scrollingFragment.setViewSelection(viewSelection)

        self.assertEquals(
            self.inbox.scrollingFragment.requestCurrentSize(),
            1)



class DummyMessageImplWithABunchOfAddresses(Item, DummyMessageImplementationMixin):
    """
    Mock L{xquotient.iquotient.IMessageData} which returns a bunch of things
    from L{relatedAddresses}
    """
    z = integer()

    def relatedAddresses(self):
        """
        Return one address for each relation type
        """
        EmailAddress = mimeutil.EmailAddress
        for (rel, addr) in ((SENDER_RELATION, 'sender@host'),
                            (RECIPIENT_RELATION, 'recipient@host'),
                            (COPY_RELATION, 'copy@host'),
                            (BLIND_COPY_RELATION, 'blind-copy@host')):
            yield (rel, mimeutil.EmailAddress(addr, False))



class ComposeActionsTestCase(TestCase):
    """
    Tests for the compose-related actions of L{xquotient.inbox.InboxScreen}
    (reply, forward, etc) and related functionality
    """

    def setUp(self):
        self.store = Store()
        self.privateApplication = PrivateApplication(store=self.store)
        self.privateApplication.installOn(self.store)

        self.inbox = Inbox(store=self.store)
        self.inbox.installOn(self.store)
        self.inboxScreen = InboxScreen(self.inbox)

        self.msg = testMessageFactory(
                    store=self.store,
                    spam=False,
                    impl=DummyMessageImplWithABunchOfAddresses(store=self.store))


    def testReplyToAll(self):
        """
        Test L{xquotient.inbox.replyToAll}
        """
        self.assertEquals(
            sorted(e.email for e in replyToAll(self.msg)),
            ['blind-copy@host', 'copy@host', 'recipient@host', 'sender@host'])


    def test_replyToAllFromAddress(self):
        """
        Test that L{xquotient.inbox.replyToAll} doesn't include addresses of
        L{xquotient.compose.FromAddress} items that exist in the same store as
        the message that is being replied to
        """
        addrs = set(u'blind-copy@host copy@host recipient@host sender@host'.split())
        for addr in addrs:
            fromAddr = compose.FromAddress(address=addr, store=self.msg.store)
            self.assertEquals(
                sorted(e.email for e in replyToAll(self.msg)),
                sorted(addrs - set([addr])))
            fromAddr.deleteFromStore()


    def testReplyAllToMessage(self):
        """
        Test L{xquotient.inbox.replyAllToMessage}
        """
        fromAddrs = []
        def _composeSomething(_fromAddrs, *a, **k):
            fromAddrs.append([e.email for e in _fromAddrs])
        self.inboxScreen._composeSomething = _composeSomething

        webID = self.privateApplication.toWebID(self.msg)
        self.inboxScreen.replyAllToMessage(webID)
        self.assertEquals(len(fromAddrs), 1)
        self.assertEquals(
            sorted(fromAddrs[0]),
            ['blind-copy@host', 'copy@host', 'recipient@host', 'sender@host'])



class ScrollingFragmentTestCase(TestCase):
    """
    Tests for L{xquotient.inbox.MailboxScrollingFragment}
    """

    def setUp(self):
        """
        Create a store, three messages and a scrolling fragment
        """
        self.store = Store()

        def makeMessage(subject, receivedWhen):
            testMessageFactory(
                store=self.store,
                read=False,
                spam=False,
                subject=subject,
                receivedWhen=receivedWhen)

        makeMessage(u'3', Time.fromPOSIXTimestamp(67))
        makeMessage(u'1', Time.fromPOSIXTimestamp(43))
        makeMessage(u'2', Time.fromPOSIXTimestamp(55))

        self.scrollingFragment = MailboxScrollingFragment(self.store)


    def test_sortAscending(self):
        """
        Test that the default sort of
        L{xquotient.inbox.MailboxScrollingFragment} is ascending on the
        C{receivedWhen} column
        """
        subjects = list(m.subject for m in
            self.scrollingFragment.performQuery(0, 3))

        self.assertEquals(
            subjects,
            list(self.store.query(
                Message, sort=Message.receivedWhen.asc).getColumn('subject')))
