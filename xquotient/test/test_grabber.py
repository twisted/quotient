
import StringIO

from twisted.trial import unittest
from twisted.internet import defer
from twisted.mail import pop3
from twisted.cred import error as ecred

from epsilon import structlike

from vertex.test import iosim

from xquotient import grabber, mimepart

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
        s = StringIO.StringIO()
        self.events.append(('receiver', source, s))
        return mimepart.MIMEMessageReceiver(s)


    def markSuccess(self, uid, part):
        self.events.append(('success', uid, part))


    def markFailure(self, uid, reason):
        self.events.append(('failure', uid, reason))


    def paused(self):
        self.events.append(('paused',))
        return False


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



class POP3GrabberTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestPOP3Grabber()
        self.client.setCredentials('test_user', 'test_pass')

        self.server = pop3.POP3()
        self.server.portal = Portal(
            ListMailbox(['First message', 'Second message', 'Last message']),
            lambda: None)


    def tearDown(self):
        pass


    def testBasicGrabbing(self):
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
