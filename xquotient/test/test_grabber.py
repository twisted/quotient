
import StringIO

from twisted.trial import unittest
from twisted.internet import defer, error
from twisted.mail import pop3
from twisted.cred import error as ecred

from epsilon import structlike, extime

from vertex.test import iosim

from axiom import store

from xquotient import grabber, mimepart


class AbortableStringIO(StringIO.StringIO):
    aborted = False

    def abort(self):
        self.aborted = True



class StubMessage:
    sentWhen = extime.Time()



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


class DelayedListMailbox(ListMailbox):
    """
    Like ListMailbox, but with hooks to arbitrarily delay responses.  This
    allows us to test various failure conditions in the client.
    """
    def __init__(self, *a, **kw):
        super(DelayedListMailbox, self).__init__(*a, **kw)
        self.messageRequestDeferreds = []


    def getMessage(self, index):
        d = defer.Deferred()
        self.messageRequestDeferreds.append(d)
        d.addCallback(lambda ign: super(DelayedListMailbox, self).getMessage(index))
        return d



class POP3GrabberTestCase(unittest.TestCase):
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
            ListMailbox(['First message', 'Second message', 'Last message']),
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


    def testFailedLogin(self):
        self.server.portal = NoPortal()
        c, s, pump = iosim.connectedServerAndClient(
            lambda : self.server,
            lambda : self.client)
        pump.flush()
        self.assertEquals(
            [evt[0] for evt in self.client.events if evt[0] != 'status'][-1],
            'stopped')


    def testLostConnectionDuringRetrieve(self):
        """
        Make sure that if a connection drops while waiting for a retrieve() to
        complete, it is properly noticed, the right Deferreds errback, and so
        forth.
        """
        mbox = DelayedListMailbox(['First message', 'Second message', 'Last message'])
        self.server.portal = Portal(mbox, lambda: None)
        c, s, pump = iosim.connectedServerAndClient(
            lambda : self.server,
            lambda : self.client)
        pump.flush()
        s.transport.loseConnection()
        pump.flush()
        self.assertEquals(self.client.events[-1][0], 'stopped')


    def testConnectionTimeout(self):
        """
        Make sure that if we receive no bytes for a really long time after
        issuing a retrieve command, we give up and disassociate ourself from
        our grabber object.
        """
        sched = []
        self.client.callLater = lambda n, f: sched.append((n, f))

        mbox = DelayedListMailbox(['First message', 'Second message', 'Last message'])
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
