# -*- test-case-name: xquotient.test.test_inbox.InboxTestCase.testUnreadMessageCount -*-

from datetime import datetime, timedelta

from twisted.trial.unittest import TestCase
from twisted.internet import defer

from epsilon.extime import Time

from axiom.store import Store
from axiom.dependency import installOn

from axiom.tags import Catalog
from axiom.attributes import integer
from axiom.item import Item

from xmantissa.ixmantissa import INavigableFragment, IWebTranslator
from xmantissa.people import Organizer, Person, EmailAddress

from xquotient.exmess import (Message, _UndeferTask as UndeferTask,
                              MailboxSelector, UNREAD_STATUS,
                              READ_STATUS, Correspondent,
                              SENDER_RELATION, DEFERRED_STATUS,
                              ARCHIVE_STATUS, TRASH_STATUS,
                              EVER_DEFERRED_STATUS,
                              RECIPIENT_RELATION, COPY_RELATION,
                              BLIND_COPY_RELATION)

from xquotient.inbox import (Inbox, InboxScreen, VIEWS, replyToAll,
                             MailboxScrollingFragment)
from xquotient import compose, mimeutil, smtpout
from xquotient.test.test_workflow import (DummyMessageImplementation, QueryCounter,
                                          DummyMessageImplementationMixin)



def testMessageFactory(store, archived=False, spam=None, read=False,
                       sentWhen=None, receivedWhen=None, subject=u'',
                       trash=False, outgoing=False, draft=False, impl=None,
                       sent=True, bounced=False, sender=None, recipient=u''):
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
            m.startedSending()
            if sent:
                m.sent()
                m.finishedSending()
            elif bounced:
                m.allBounced()
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

        inboxItem = Inbox(store=self.store)
        installOn(inboxItem, self.store)
        self.privateApplication = inboxItem.privateApplication
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

        self.inbox = InboxScreen(inboxItem)


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



class InboxTest(TestCase):
    def setUp(self):
        self.store = Store()
        self.inbox = Inbox(store=self.store)
        installOn(self.inbox, self.store)
        self.translator = self.inbox.privateApplication
        self.inboxScreen = InboxScreen(self.inbox)
        self.scheduler = self.inbox.scheduler
        self.viewSelection = dict(self.inboxScreen.viewSelection)


    def makeMessages(self, number, **flags):
        messages = []
        for i in xrange(number):
            m = testMessageFactory(store=self.store, receivedWhen=Time(),
                                   **flags)
            messages.append(m)
        return messages



class InboxTestCase(InboxTest):
    def test_adaption(self):
        """
        Test that an Inbox can be adapted to INavigableFragment so that it can
        be displayed on a webpage.
        """

        self.assertNotIdentical(INavigableFragment(self.inbox, None),
                                None)

    def test_userTagNames(self):
        """
        Verify that tags created in the axiom tags system will show up to the
        inbox via getUserTagNames
        """
        m = testMessageFactory(store=self.store)
        c = Catalog(store=self.store)
        c.tag(m, u'tag1')
        c.tag(m, u'taga')
        c.tag(m, u'tagstart')


        self.assertEquals(self.inboxScreen.getUserTagNames(),
                          [u'tag1', u'taga', u'tagstart'])


    def test_defer(self):
        """
        Test that L{action_defer} moves a message to the DEFERRED status.
        """
        message = testMessageFactory(store=self.store, read=True)
        self.inbox.action_defer(message, 365, 0, 0)
        self.failUnless(message.hasStatus(DEFERRED_STATUS),
                        'message was not deferred')



    def test_undefer(self):
        """
        Test that the message is undeferred (has the DEFERRED status removed)
        after the deferred time period elapses.
        """
        # XXX I don't think this test is a good idea.  there's no reason
        # action_defer should return anything. -- glyph
        message = testMessageFactory(store=self.store, read=True)
        task = self.inbox.action_defer(message, 365, 0, 0)

        self.scheduler.reschedule(task, task.deferredUntil, Time())
        self.scheduler.tick()
        self.failIf(message.hasStatus(DEFERRED_STATUS),
                    'message is still deferred')
        self.failIf(message.read, 'message is marked read')
        self.failUnless(message.hasStatus(EVER_DEFERRED_STATUS),
                        'message does not have "ever deferred" status')
        self.assertEquals(self.store.count(UndeferTask), 0)


    def test_deferCascadingDelete(self):
        """
        Check that the L{UndeferTask} for a deferred message is removed when
        that message is deleted from the store.
        """
        message = testMessageFactory(store=self.store)
        self.inbox.action_defer(message, 365, 0, 0)
        message.deleteFromStore()
        self.assertEquals(self.store.count(UndeferTask), 0)


    def test_getComposer(self):
        """
        Test L{xquotient.inbox.InboxScreen.getComposer}
        """
        installOn(compose.Composer(store=self.store), self.store)
        composer = self.inboxScreen.getComposer()
        self.failIf(composer.recipients)
        self.failIf(composer.subject)
        self.failIf(composer.messageBody)
        self.failIf(composer.attachments)

        self.failUnless(composer.inline)



class MessageCountTest(InboxTest):
    def unreadCount(self, view=None):
        if view is not None:
            self.viewSelection['view'] = view
        return self.inboxScreen.getUnreadMessageCount(self.viewSelection)


    def assertCountsAre(self, **d):
        for k in VIEWS:
            if not k in d:
                d[k] = 0
        self.assertEqual(self.inboxScreen.mailViewCounts(), d)


    def test_unreadMessageCount(self):
        """
        Check that L{InboxScreen.getUnreadMessageCount} return the correct
        message count under a variety of conditions.
        """
        self.makeMessages(13, read=False, spam=False)
        self.makeMessages(6, read=True, spam=False)

        self.assertEqual(self.unreadCount('inbox'), 13)
        self.assertEqual(self.unreadCount('all'), 13)
        self.assertEqual(self.unreadCount('sent'), 0)
        self.assertEqual(self.unreadCount('spam'), 0)

        # mark 1 read message as unread
        sq = MailboxSelector(self.store)

        sq.refineByStatus(READ_STATUS)
        iter(sq).next().markUnread()
        self.assertEqual(self.unreadCount('inbox'), 14)

        # mark 6 unread messages as spam
        sq = MailboxSelector(self.store)
        sq.refineByStatus(UNREAD_STATUS)
        sq.setLimit(6)
        spam = []
        for m in sq:
            m.classifySpam()
            spam.append(m)
        self.assertEqual(self.unreadCount('spam'), 6)

        # return all spam messages to the inbox
        for m in spam:
            m.classifyClean()
        m.archive()
        self.assertEqual(self.unreadCount('spam'), 0)


    def test_outgoingUnreadCount(self):
        """
        Check that the count of messages in the outbox view is correct.
        """
        self.makeMessages(4, read=False, outgoing=True, draft=False, sent=False)
        self.assertEqual(self.unreadCount('outbox'), 4)
        self.makeMessages(3, read=False, outgoing=True, draft=False, sent=False,
                          bounced=True)
        self.assertEqual(self.unreadCount('bounce'), 3)
        self.assertEqual(self.unreadCount('outbox'), 4)


    def test_unreadCountLimit(self):
        """
        Verify that unread counts on arbitrarily large mailboxes only count up
        to a specified limit.
        """
        halfCount = 5
        countLimit = 2 * halfCount
        self.inboxScreen.countLimit = countLimit

        self.makeMessages(halfCount, read=False, spam=False)
        self.assertEqual(self.unreadCount(), halfCount)

        self.makeMessages(halfCount, read=False, spam=False)
        self.assertEqual(self.unreadCount(), countLimit)

        self.makeMessages(halfCount, read=False, spam=False)
        self.assertEqual(self.unreadCount(), countLimit)


    def test_unreadCountComplexityLimit(self):
        """
        Verify that unread counts on arbitrarily large mailboxes only perform
        counting work up to a specified limit.
        """
        # Now make sure the DB's work is limited too, not just the result
        # count.
        halfCount = 5
        countLimit = 2 * halfCount
        self.inboxScreen.countLimit = countLimit

        self.makeMessages(3 * halfCount, read=False, spam=False)
        qc = QueryCounter(self.store)
        m1 = qc.measure(self.unreadCount)


        self.makeMessages(halfCount, read=False, spam=False)
        m2 = qc.measure(self.unreadCount)
        self.assertEqual(m1, m2)


    def test_mailViewCounts(self):
        """
        Test that L{mailViewCounts} shows the correct number of unread messages
        for each view, and that it updates as new messages are added to those
        views.
        """
        self.makeMessages(9, read=False, spam=False)
        self.makeMessages(3, read=False, spam=False, archived=True)
        self.assertCountsAre(inbox=9, all=12, archive=3)

        self.makeMessages(4, read=False, spam=True)
        self.makeMessages(3, read=True, spam=True)
        self.assertCountsAre(inbox=9, all=12, archive=3, spam=4)

        self.makeMessages(2, read=False, trash=True)
        self.assertCountsAre(inbox=9, all=12, archive=3, spam=4, trash=2)

        self.makeMessages(4, read=False, outgoing=True)
        self.assertCountsAre(inbox=9, all=12, archive=3, spam=4, trash=2, sent=4)


    def test_outgoingMailViewCounts(self):
        """
        Test that L{mailViewCounts} shows the correct number of unread messages
        for each 'outgoing' view (bounced, sent and outbox).
        """
        self.makeMessages(4, read=False, outgoing=True, sent=False)
        self.assertCountsAre(outbox=4)
        self.makeMessages(3, read=False, outgoing=True, sent=False,
                          bounced=True)
        self.assertCountsAre(outbox=4, bounce=3)


class PopulatedInboxTest(InboxTest):
    def setUp(self):
        super(PopulatedInboxTest, self).setUp()
        self.msgs = self.makeMessages(5, spam=False)
        self.msgs.reverse()
        self.msgIds = map(self.translator.toWebID, self.msgs)


    def test_lookaheadWithActions(self):
        """
        Test that message lookahead is correct when the process of moving from
        one message to the next is accomplished by eliminating the current
        message from the active view (e.g.  by acting on it), rather than
        doing it explicitly with selectMessage().  Do this all the way down,
        until there are no messages left
        """
        def makeCountChecker(readCount, unreadCount):
            def _check((_readCount, _unreadCount)):
                self.assertEquals(readCount, _readCount)
                self.assertEquals(unreadCount, _unreadCount)
            return _check

        def makeArchiver(msgs):
            def _archive(ign):
                return self.inboxScreen.actOnMessageIdentifierList(
                            'archive', msgs)
            return _archive

        D = defer.Deferred()

        for i in range(len(self.msgs) - 2):
            D.addCallback(makeArchiver([self.msgIds[i]]))
            D.addCallback(makeCountChecker(1, 0))

        D.addCallback(makeArchiver([self.msgIds[i + 1]]))
        D.addCallback(makeCountChecker(1, 0))

        D.addCallback(makeArchiver([self.msgIds[i + 2]]))
        D.addCallback(makeCountChecker(1, 0))

        D.callback(None)
        return D
    test_lookaheadWithActions.todo = "read/unread flag not managed properly yet."


    def test_performMany(self):
        """
        Test L{Inbox.performMany} does what we tell it, and returns the
        correct read/unread counts
        """
        D = self.inbox.performMany("archive", self.msgs)

        def check((readCount, unreadCount)):
            for m in self.msgs:
                self.failUnless(m.hasStatus(ARCHIVE_STATUS))

            self.assertEquals(readCount, 0)
            self.assertEquals(unreadCount, len(self.msgs))

        D.addCallback(check)
        return D


    def test_peformManyDeletions(self):
        """
        Test L{Inbox.performMany} with the delete action
        """
        D = self.inbox.performMany("delete", self.msgs)

        def check((readCount, unreadCount)):
            for m in self.msgs:
                self.failUnless(m.hasStatus(TRASH_STATUS))

            self.assertEquals(readCount, 0)
            self.assertEquals(unreadCount, len(self.msgs))

        D.addCallback(check)
        return D


    def test_performManyError(self):
        """
        Test that L{Inbox.performMany} properly forwards errors which happen
        inside the generator passed to the cooperator.
        """
        D = self.inbox.performMany("delete", None)
        self.assertFailure(D, TypeError)
        return D


    def test_performManyProportionalWork(self):
        """
        Test that the number of calls that L{Inbox._performManyAct} makes to
        the action it is passed corresponds to the number of its values we
        consume
        """
        def action(m):
            action.calls += 1
        action.calls = 0

        it = self.inbox._performManyAct(
            action, {}, self.msgs, defer.Deferred())

        self.assertEquals(action.calls, 0)
        for i in xrange(len(self.msgs)):
            it.next()
            self.assertEquals(action.calls, i+1)


    def test_performManyProportionalDatabaseWork(self):
        """
        Test that the cost of the SQL executed by  L{Inbox._performManyAct} in
        a single step is independent of the number of messages in the batch
        """
        qc = QueryCounter(self.store)

        measure = lambda: qc.measure(
            lambda: self.inbox._performManyAct(
                lambda m: None,
                {},
                self.store.query(Message).paginate(pagesize=2),
                defer.Deferred()).next())

        first = measure()

        Message(store=self.store)

        self.assertEquals(first, measure())


    def test_fastForward(self):
        """
        Test fast forwarding to a particular message by id sets that message
        to read.
        """
        fragment = self.inboxScreen.fastForward(
            self.viewSelection, self.msgIds[2])
        self.failUnless(self.msgs[2].read)



class MessagesForBatchType(InboxTest):
    def messagesForBatchType(self, batchType, *a, **k):
        """
        Convenience method to return the list of C{messagesForBatchType} on
        C{self.inbox}.
        """
        return list(self.inbox.messagesForBatchType(
            batchType, self.viewSelection, *a, **k))


    def test_messagesForBatchTypeEmpty(self):
        """
        Test that even with no messages, L{Inbox.messagesForBatchType} spits
        out the right value (an empty list).
        """
        for batchType in ("read", "unread", "all"):
            self.assertEquals(self.messagesForBatchType(batchType), [])


    def test_messagesForBatchTypeOneUnread(self):
        """
        Make one unread message and check that it only comes back from
        queries for the batch type which applies to it.
        """
        message = testMessageFactory(store=self.store, spam=False)
        self.assertEquals(self.messagesForBatchType('read'), [])
        self.assertEquals(self.messagesForBatchType('unread'), [message])
        self.assertEquals(self.messagesForBatchType('all'), [message])


    def test_messagesForBatchTypeOneRead(self):
        """
        Make one read message and check that it only comes back from the
        queries for the batch type which applies to it.
        """
        message = testMessageFactory(store=self.store, spam=False)
        message.markRead()
        self.assertEquals(self.messagesForBatchType('read'), [message])
        self.assertEquals(self.messagesForBatchType("unread"), [])
        self.assertEquals(self.messagesForBatchType('all'), [message])


    def test_messagesForBatchTypeTwo(self):
        """
        Take one read message and another message and make sure that the batch
        is correct with various combinations of states between the two.
        """
        message = testMessageFactory(store=self.store, spam=False)
        message.markRead()
        other = testMessageFactory(store=self.store, spam=False)
        self.assertEquals(self.messagesForBatchType("read"), [message])
        self.assertEquals(self.messagesForBatchType("unread"), [other])
        self.assertEquals(self.messagesForBatchType('all'), [message, other])

        other.markRead()
        self.assertEquals(self.messagesForBatchType("read"), [message, other])
        self.assertEquals(self.messagesForBatchType("unread"), [])
        self.assertEquals(self.messagesForBatchType('all'), [message, other])


    def test_messagesForBatchTypeExclude(self):
        """
        Test that the messages given in the list passed as the C{exclude} arg
        really are excluded from the batch
        """
        exclude = testMessageFactory(store=self.store, spam=False)
        messages = [
            testMessageFactory(store=self.store, spam=False)
                for i in xrange(5)]

        self.assertEquals(
            self.messagesForBatchType('all', exclude=[exclude]),
            messages)



class ReadUnreadTestCase(TestCase):
    """
    Tests for all operations which should change the read/unread state of
    messages.
    """
    NUM_MESSAGES = 5

    def setUp(self):
        self.store = Store()

        self.inbox = Inbox(store=self.store)
        installOn(self.inbox, self.store)
        self.translator = self.inbox.privateApplication
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

        D = screen.actOnMessageIdentifierList(
                'archive',
                [self.translator.toWebID(self.messages[-1])])

        def check():
            for msg in self.messages[:-1]:
                self.failIf(msg.read, "Subsequent messages should be unread.")

            for msg in self.messages[-1:]:
                self.failUnless(msg.read, "Initial and revealed message should be read.")

        D.addCallback(lambda ign: check())
        return D



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
        installOn(self.organizer, self.store)

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

        self.inbox = Inbox(store=self.store)
        installOn(self.inbox, self.store)
        self.privateApplication = self.inbox.privateApplication
        self.inboxScreen = InboxScreen(self.inbox)

        self.msg = testMessageFactory(
                    store=self.store,
                    spam=False,
                    impl=DummyMessageImplWithABunchOfAddresses(store=self.store))


    def _recipientsToStrings(self, recipients):
        """
        Convert a mapping of "strings to lists of
        L{xquotient.mimeutil.EmailAddress} instances" into a mapping of
        "strings to lists of string email addresses"
        """
        result = {}
        for (k, v) in recipients.iteritems():
            result[k] = list(e.email for e in v)
        return result

    def test_replyToAll(self):
        """
        Test L{xquotient.inbox.replyToAll}
        """
        self.assertEquals(
            self._recipientsToStrings(
                replyToAll(self.msg)),
            {'bcc': ['blind-copy@host'],
             'cc': ['copy@host'],
             'to': ['sender@host']})


    def test_replyToAllFromAddress(self):
        """
        Test that L{xquotient.inbox.replyToAll} doesn't include addresses of
        L{xquotient.smtpout.FromAddress} items that exist in the same store as
        the message that is being replied to
        """
        addrs = set(u'blind-copy@host copy@host sender@host'.split())
        for addr in addrs:
            fromAddr = smtpout.FromAddress(address=addr, store=self.msg.store)
            gotAddrs = set()
            for l in replyToAll(self.msg).itervalues():
                gotAddrs.update(e.email for e in l)
            self.assertEquals(
                gotAddrs,
                addrs - set([addr]))
            fromAddr.deleteFromStore()


    def test_replyAllToMessage(self):
        """
        Test L{xquotient.inbox.InboxScreen.replyAllToMessage}
        """
        def _composeSomething(recipients, *a, **k):
            _composeSomething.recipients = recipients
        self.inboxScreen._composeSomething = _composeSomething

        webID = self.privateApplication.toWebID(self.msg)
        self.inboxScreen.replyAllToMessage(webID)

        recipients = self._recipientsToStrings(
            _composeSomething.recipients)

        self.assertEquals(
            recipients,
            {'bcc': ['blind-copy@host'],
             'cc': ['copy@host'],
             'to': ['sender@host']})



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
