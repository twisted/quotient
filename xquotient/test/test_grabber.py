
import StringIO

from datetime import timedelta

from twisted.trial import unittest
from twisted.internet import defer, error
from twisted.mail import pop3, imap4
from twisted.cred import error as ecred

from epsilon import structlike, extime

from epsilon.test import iosim
from epsilon.structlike import record

from axiom import store

from xquotient import grabber, mimepart


class AbortableStringIO(StringIO.StringIO):
    aborted = False

    def abort(self):
        self.aborted = True



class StubMessage:
    sentWhen = extime.Time()
    _wasArchived = False

    def archive(self):
        """
        Emulate L{Message.archive}.
        """
        self._wasArchived = True



class StubMIMEReceiver(mimepart.MIMEMessageReceiver):
    def messageDone(self):
        mimepart.MIMEMessageReceiver.messageDone(self)
        self.message = StubMessage()



class TestPOP3Grabber(grabber.POP3GrabberProtocol):
    def connectionMade(self):
        grabber.POP3GrabberProtocol.connectionMade(self)
        self.events = []


    def getSource(self):
        self.events.append(('source',))
        return u"test-pop3"


    def setStatus(self, msg, success=True):
        self.events.append(('status', msg, success))


    def shouldRetrieve(self, uidList):
        self.events.append(('retrieve', uidList))
        return list(uidList)


    def createMIMEReceiver(self, source):
        s = AbortableStringIO()
        self.events.append(('receiver', source, s))
        return StubMIMEReceiver(s)


    def markSuccess(self, uid, msg):
        self.events.append(('success', uid, msg))


    def markFailure(self, uid, reason):
        self.events.append(('failure', uid, reason))


    def paused(self):
        self.events.append(('paused',))
        return False


    def transientFailure(self, err):
        self.events.append(('transient', err))


    def stoppedRunning(self):
        self.events.append(('stopped',))



class Portal(structlike.record('avatar logout')):
    def login(self, credentials, mind, interface):
        return defer.succeed((interface, self.avatar, self.logout))



class NoPortal:
    def login(self, credentials, mind, interface):
        return defer.fail(ecred.UnauthorizedLogin())


class DelayedPortal(object):
    def __init__(self):
        self.loginAttempts = []


    def login(self, credentials, mind, interface):
        result = defer.Deferred()
        self.loginAttempts.append((result, credentials, mind, interface))
        return result



class ListMailbox(object):
    def __init__(self, msgs):
        self.msgs = msgs
        self.deleted = []

    def listMessages(self, index=None):
        if index is None:
            return map(len, self.msgs)
        return len(self.msgs[index])

    def getMessage(self, index):
        return StringIO.StringIO(self.msgs[index])

    def getUidl(self, index):
        return hash(self.msgs[index])

    def deleteMessage(self, index):
        self.deleted.append(index)

    def sync(self):
        self.deleted.sort()
        self.deleted.reverse()
        for idx in self.deleted:
            del self.msgs[idx]
        self.deleted = []



class POP3WithoutAPOP(pop3.POP3):
    def connectionMade(self):
        self.successResponse('Hello')
        self.setTimeout(self.timeOut)



class DelayedListMailbox(ListMailbox):
    """
    Like ListMailbox, but with hooks to arbitrarily delay responses.  This
    allows us to test various failure conditions in the client.
    """
    def __init__(self, *a, **kw):
        super(DelayedListMailbox, self).__init__(*a, **kw)
        self.messageListDeferreds = []
        self.messageRequestDeferreds = []


    def deferredListMessages(self, index=None):
        d = defer.Deferred()
        self.messageListDeferreds.append(d)
        d.addCallback(lambda ign: super(DelayedListMailbox, self).listMessages(index))
        return d


    def deferredGetMessage(self, index):
        d = defer.Deferred()
        self.messageRequestDeferreds.append(d)
        d.addCallback(lambda ign: super(DelayedListMailbox, self).getMessage(index))
        return d


    def defer(self, what):
        """
        Replace the indicated method with one which returns a Deferred which
        must be explicitly fired.  Return a list to which Deferreds which
        need to be serviced are appended.
        """
        originals = {
            'listMessages': 'listMessages',
            'getMessage': 'getMessage'}
        replacements = {
            'listMessages': 'deferredListMessages',
            'getMessage': 'deferredGetMessage'}
        deferreds = {
            'listMessages': self.messageListDeferreds,
            'getMessage': self.messageRequestDeferreds}
        setattr(self, originals[what], getattr(self, replacements[what]))
        return deferreds[what]



class POP3GrabberTestCase(unittest.TestCase):
    testMessageStrings = ['First message', 'Second message', 'Last message']


    def setUp(self):
        self.client = TestPOP3Grabber()
        self.client.setCredentials('test_user', 'test_pass')
        self.server = pop3.POP3()
        self.server.schedule = list
        self.server.timeOut = None


    def tearDown(self):
        pass


    def testBasicGrabbing(self):
        self.server.portal = Portal(
            ListMailbox(self.testMessageStrings),
            lambda: None)
        c, s, pump = iosim.connectedServerAndClient(
            lambda: self.server,
            lambda: self.client)
        pump.flush()
        self.assertEquals(
            len([evt for evt in self.client.events if evt[0] == 'success']),
            3)
        self.assertEquals(
            [evt[0] for evt in self.client.events if evt[0] != 'status'][-1],
            'stopped')


    def testLineTooLong(self):
        """
        Make sure a message illegally served with a line longer than we will
        accept is handled and marked as a failure, but doesn't completely
        derail the grabber.
        """
        self.server.portal = Portal(
            ListMailbox(['X' * (2 ** 16)]),
            lambda: None)
        c, s, pump = iosim.connectedServerAndClient(
            lambda: self.server,
            lambda: self.client)
        pump.flush()
        for evt in self.client.events:
            if evt[0] == 'transient':
                evt[1].trap(pop3.LineTooLong)
                break
        else:
            self.fail("No transient failure recorded.")


    def testFailedLogin(self):
        self.server.portal = NoPortal()
        c, s, pump = iosim.connectedServerAndClient(
            lambda : self.server,
            lambda : self.client)
        pump.flush()

        status = [evt[1] for evt in self.client.events if evt[0] == 'status'][-1]
        lastEvent = [evt[0] for evt in self.client.events if evt[0] != 'status'][-1]

        self.assertEquals(status, u'Login failed: Authentication failed')
        self.assertEquals(lastEvent, u'stopped')


    def testInsecureLogin(self):
        """
        Test that if login isn't even attempted because there is no way to do
        it without revealing a password that the grabber status is set
        properly.
        """
        self.server = POP3WithoutAPOP()
        self.server.schedule = list
        self.server.timeOut = None

        c, s, pump = iosim.connectedServerAndClient(
            lambda : self.server,
            lambda : self.client)
        pump.flush()

        status = [evt[1] for evt in self.client.events if evt[0] == 'status'][-1]
        lastEvent = [evt[0] for evt in self.client.events if evt[0] != 'status'][-1]

        self.assertEquals(status, u'Login aborted: server not secure.')
        self.assertEquals(lastEvent, u'stopped')


    def test_lostConnectionDuringLogin(self):
        """
        Make sure that if a connection drops while logging in, it is
        properly noticed and the status is updated correctly.
        """
        self.server.portal = DelayedPortal()
        c, s, pump = iosim.connectedServerAndClient(
            lambda: self.server,
            lambda: self.client)
        pump.flush()

        # Should have been one login attempt
        ([loginDeferred, credentials, mind, interface],) = self.server.portal.loginAttempts

        s.transport.loseConnection()
        pump.flush()
        self.assertEquals(self.client.events[-1][0], 'stopped')


    def _disconnectTest(self, mbox, blocked):
        self.server.portal = Portal(mbox, lambda: None)
        c, s, pump = iosim.connectedServerAndClient(
            lambda: self.server,
            lambda: self.client)
        pump.flush()
        self.assertEquals(
            len(blocked), 1,
            "Expected a pending Deferred for listMessages, found %r" % (
                blocked,))
        s.transport.loseConnection()
        pump.flush()
        self.assertEquals(self.client.events[-1][0], 'stopped')


    def test_lostConnectionDuringListing(self):
        """
        Make sure that if a connection drops while waiting for a listUID()
        to complete, it is properly noticed, the right Deferreds errback,
        and so forth.
        """
        mbox = DelayedListMailbox(self.testMessageStrings)
        return self._disconnectTest(mbox, mbox.defer('listMessages'))


    def testLostConnectionDuringRetrieve(self):
        """
        Make sure that if a connection drops while waiting for a retrieve() to
        complete, it is properly noticed, the right Deferreds errback, and so
        forth.
        """
        mbox = DelayedListMailbox(self.testMessageStrings)
        return self._disconnectTest(mbox, mbox.defer('getMessage'))


    def testConnectionTimeout(self):
        """
        Make sure that if we receive no bytes for a really long time after
        issuing a retrieve command, we give up and disassociate ourself from
        our grabber object.
        """
        sched = []
        self.client.callLater = lambda n, f: sched.append((n, f))

        mbox = DelayedListMailbox(self.testMessageStrings)
        self.server.portal = Portal(mbox, lambda: None)
        c, s, pump = iosim.connectedServerAndClient(
            lambda: self.server,
            lambda: self.client)
        self.assertEquals(len(sched), 1)
        sched.pop()[1]()
        self.assertEquals(self.client.events[-2][0], 'transient')
        self.client.events[-2][1].trap(error.TimeoutError)
        self.assertEquals(self.client.events[-1][0], 'stopped')



class PersistentControllerTestCase(unittest.TestCase):
    """
    Tests for the Axiom-y parts of L{xquotient.grabber.POP3Grabber}.
    """
    def setUp(self):
        self.store = store.Store()
        self.grabber = grabber.POP3Grabber(
            store=self.store,
            username=u"testuser",
            domain=u"example.com",
            password=u"password")
        for i in xrange(100, 200):
            grabber.POP3UID(store=self.store,
                            grabberID=self.grabber.grabberID,
                            value=str(i))


    def testShouldRetrieve(self):
        self.assertEquals(
            self.grabber.shouldRetrieve([(1, '99'), (2, '100'),
                                         (3, '150'), (4, '200')]),
            [(1, '99'), (4, '200')])


    def testMarkSuccess(self):
        """
        Test that a message marked as successfully retrieved is not returned
        from subsequent calls to L{shouldRetrieve}.
        """
        self.testShouldRetrieve()

        msg = StubMessage()
        self.grabber.markSuccess('50', msg)
        self.assertEquals(
            self.grabber.shouldRetrieve([(49, '49'), (50, '50'),
                                         (51, '51')]),
            [(49, '49'), (51, '51')])


    def test_markSuccessArchivesOldmessages(self):
        """
        Verify that 'sufficiently old' messages are archived automatically by
        the POP grabber as they are retrieved.
        """
        msg = StubMessage()
        msg.sentWhen = self.grabber.created - timedelta(days=1, seconds=1)
        self.grabber.markSuccess('50', msg)
        self.failUnless(msg._wasArchived)


    def testMarkFailure(self):
        """
        Test that a message marked as having incurred an error during retrieval
        is not returned from subsequent calls to L{shouldRetrieve}.
        """
        self.testShouldRetrieve()

        msg = StubMessage()
        self.grabber.markFailure('50', msg)
        self.assertEquals(
            self.grabber.shouldRetrieve([(49, '49'), (50, '50'),
                                         (51, '51')]),
            [(49, '49'), (51, '51')])



class StubIMAP4Client(object):
    def __init__(self):
        self._mailboxes = {}
        self._activeMailbox = None
        self._state = 'AUTHORIZED'


    def _normalizeMailboxName(self, name):
        if name.lower() == 'inbox':
            return 'INBOX'
        return name


    def status(self, mailboxName, *fields):
        mailboxName = self._normalizeMailboxName(mailboxName)
        return self._mailboxes[mailboxName].status(fields)


    def examine(self, mailboxName):
        if self._state != 'AUTHORIZED':
            raise ValueError("Cannot examine while a mailbox is active.")
        mailboxName = self._normalizeMailboxName(mailboxName)
        if mailboxName not in self._mailboxes:
            raise ValueError("%r is not a known mailbox." % (mailboxName,))
        self._state = 'SELECTING'
        d = defer.maybeDeferred(self._mailboxes[mailboxName].examine)
        def cbExamine(result):
            self._state = 'SELECTED'
            self._active = mailboxName
            return result
        def ebExamine(err):
            self._state = 'AUTHORIZED'
            return err
        d.addCallbacks(cbExamine, ebExamine)
        return d


    def fetchMessage(self, which, uid=False):
        if self._state != 'SELECTED':
            raise ValueError("Cannot fetch while mailbox is not active.")
        results = []
        messages = imap4.parseIdList(which)
        for msg in self._mailboxes[self._active].fetch([m - 1 for m in messages], uid):
            result = {'RFC822': msg.rfc822}
            if uid:
                result['UID'] = str(msg.uid)
            results.append(result)
        return defer.succeed(results)



class StubIMAP4Mailbox(record('statuses messages')):
    def status(self, fields):
        return defer.succeed(
            dict([(f, self.statuses[f]) for f in fields]))


    def examine(self):
        pass


    def fetch(self, messages, uid):
        for m in messages:
            if uid:
                for m2 in self.messages:
                    if m2.uid == m:
                        yield m2
            else:
                if m < len(self.messages):
                    yield self.messages[m]



class GmailboxMaybeChangedTests(unittest.TestCase):
    def test_firstTime(self):
        """
        The first time L{GmailGrabber.maybeChanged} is called for a particular
        mailbox, it returns a L{Deferred} which fires with C{True}.
        """
        client = StubIMAP4Client()
        client._mailboxes[u'INBOX'] = StubIMAP4Mailbox({'UIDNEXT': '1'}, [])

        mailbox = grabber.Gmailbox(name=u'INBOX')

        d = mailbox.maybeChanged(client)
        d.addCallback(
            self.assertTrue,
            "Uninitialized mailbox should be considered potentially changed")
        return d


    def test_sameUIDNEXT(self):
        """
        L{GmailGrabber.maybeChanged} returns a L{Deferred} which fires with
        C{False} if the status of the given mailbox indicates the I{UIDNEXT}
        value is not changed since the previous check.
        """
        client = StubIMAP4Client()
        client._mailboxes[u'INBOX'] = StubIMAP4Mailbox({'UIDNEXT': '2'}, [])

        mailbox = grabber.Gmailbox(name=u'INBOX', next=2)

        d = mailbox.maybeChanged(client)
        d.addCallback(
            self.assertFalse,
            "UIDNEXT status matching known UIDNEXT value should indicate "
            "no change possible")
        return d


    def test_differentUIDNEXT(self):
        """
        L{GmailGrabber.maybeChanged} returns a L{Deferred} which fires with
        C{True} if the status of the given mailbox indicates the I{UIDNEXT}
        value changed since the previous check.
        """
        client = StubIMAP4Client()
        client._mailboxes[u'INBOX'] = StubIMAP4Mailbox({'UIDNEXT': '3'}, [])

        mailbox = grabber.Gmailbox(name=u'INBOX', next=2)

        d = mailbox.maybeChanged(client)
        d.addCallback(
            self.assertTrue,
            "UIDNEXT status not matching known UIDNEXT value should "
            "indicate a possible change")
        return d



class StubIMAP4Message(record('uid rfc822')):
    pass



class StubRecorder:
    pass


class GmailboxRetrieveTests(unittest.TestCase):
    def test_retrieve(self):
        """
        L{Gmailbox.retrieve} requests new messages using the L{IMAP4Client}
        passed to it and calls L{Gmailbox.record} with each.
        """
        client = StubIMAP4Client()
        client._mailboxes[u'INBOX'] = StubIMAP4Mailbox(
            {'UIDNEXT': '7'},
            [StubIMAP4Message(6, 'some text')])

        mailbox = grabber.Gmailbox(name=u'INBOX', next=3)

        recorded = []
        mailbox.record = lambda *args: recorded.append(args)

        d = mailbox.retrieve(client, '7')
        def cbRetrieved(ignored):
            self.assertEqual(recorded, [(6, 'some text')])
        d.addCallback(cbRetrieved)
        return d


    def test_record(self):
        """
        L{Gmailbox.record} creates a new L{Message} for the retrieved message
        and updates the C{next} attribute of the L{Gmailbox} instance.
        """
        store = store.Store()
        mailbox = grabber.Gmailbox(store=store, name=u'INBOX', next=4)
        mailbox.record(6, 'some text')
        self.assertEqual(store.query(Message).count(), 1)



class UnchangedMailbox(object):
    def maybeChanged(self, client):
        return defer.succeed(False)



class GmailGrabberCheckTests(unittest.TestCase):
    def test_unchangedStatus(self):
        """
        If the I{UIDNEXT} status of a mailbox is unchanged,
        L{GmailGrabber.check} makes no attempt to examine the mailbox or
        retrieve messages from it.
        """
        class UnexaminableMailbox(StubIMAP4Mailbox):
            def examine(self):
                raise RuntimeError(
                    "Cannot examine this mailbox, nor should you want to.")

        mailbox = UnchangedMailbox()

        client = StubIMAP4Client()
        client._mailboxes[u'INBOX'] = UnexaminableMailbox({'UIDNEXT': '3'}, [])

        gmail = grabber.GmailGrabber()
        # This has no interesting result except to not fail as a consequence of
        # trying to examine an unchanged and unexaminable mailbox.
        return gmail.check(client, mailbox)


    def test_retrieveMessages(self):
        """
        L
        """
