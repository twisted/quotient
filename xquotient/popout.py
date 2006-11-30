
import os

from OpenSSL import SSL

from zope.interface import implements

from twisted.application import service
from twisted.internet import defer, reactor, protocol
from twisted.protocols import policies
from twisted.cred import portal, checkers

from xmantissa.stats import BandwidthMeasuringFactory

from xquotient.exmess import Message

from epsilon import sslverify

from axiom import item, attributes
from axiom.errors import MissingDomainPart
from axiom.userbase import LoginSystem
from axiom.dependency import dependsOn

from twisted.mail import pop3

# XXX Ugh.  This whole file is basically a straight copy of mail.py, and it
# SUCKS.  I am not going to think too hard about it now (SHIP! SHIP! SHIP!)


class MailConfigurationError(Exception):
    '''
    Horrible.
    '''

class MessageInfo(item.Item):
    typeName = 'quotient_pop3_message'
    schemaVersion = 2

    localPop3UID = attributes.bytes()
    localPop3Deleted = attributes.boolean(indexed=True)

    message = attributes.reference()


class POP3Up(item.Item):

    typeName = 'quotient_pop3_user_powerup'

    implements(pop3.IMailbox)

    messageList = attributes.inmemory()
    deletions = attributes.inmemory()

    installedOn = attributes.reference()

    powerupInterfaces = (pop3.IMailbox)

    def activate(self):
        self.messageList = None
        self.deletions = set()

    def getMessageList(self):
        # XXX could be made more incremental by screwing with login, making it
        # return a deferred
        if self.messageList is None:
            # load it
            oldMessages = list(self.store.query(
                Message,
                attributes.AND(Message.storeID == MessageInfo.message,
                               MessageInfo.localPop3Deleted == False),
                sort=Message.storeID.asc))
            newMessages = list(self.store.query(
                Message,
                Message.storeID.notOneOf(
                        self.store.query(MessageInfo).getColumn('message',
                                                                raw=True)),
                sort=Message.storeID.asc))
            for message in newMessages:
                MessageInfo(store=self.store,
                            localPop3Deleted=False,
                            localPop3UID=os.urandom(16).encode('hex'),
                            message=message)
            self.messageList = list(self.store.query(
                    MessageInfo,
                    MessageInfo.localPop3Deleted == False))
        return self.messageList
    getMessageList = item.transacted(getMessageList)


    def listMessages(self, index=None):
        if index is None:
            return [self.messageSize(idx) for idx in
                    xrange(len(self.getMessageList()))]
        else:
            return self.messageSize(index)


    def _getMessageImpl(self, index):
        msgList = self.getMessageList()
        try:
            msg = msgList[index]
        except IndexError:
            raise ValueError(index)
        else:
            return msg


    def messageSize(self, index):
        if index in self.deletions:
            return 0
        i = self._getMessageImpl(index).message.impl
        return i.bodyOffset + (i.bodyLength or 0)


    def deleteMessage(self, index):
        if index in self.deletions:
            raise ValueError(index)
        self._getMessageImpl(index)
        self.deletions.add(index)


    def getMessage(self, index):
        if index in self.deletions:
            raise ValueError(index)
        return self._getMessageImpl(index).message.impl.source.open()


    def getUidl(self, index):
        if index in self.deletions:
            raise ValueError(index)
        return self._getMessageImpl(index).localPop3UID


    def sync(self):
        ml = self.getMessageList()
        for delidx in self.deletions:
            ml[delidx].localPop3Deleted = True
        self.messageList = None
        self.deletions = set()
        self.getMessageList()


    def undeleteMessages(self):
        self.deletions = set()



class QuotientPOP3(pop3.POP3):
    """
    Trivial customization of the basic POP3 server: when this server notices
    a login which fails with L{axiom.errors.MissingDomainPart} it reports a
    special error message to the user suggesting they add a domain to their
    username.
    """
    def _ebMailbox(self, err):
        if err.check(MissingDomainPart):
            self.failResponse(
                'Username without domain name (ie "yourname" instead of '
                '"yourname@yourdomain") not allowed; try with a domain name.')
        else:
            return pop3.POP3._ebMailbox(self, err)



class POP3ServerFactory(protocol.Factory):

    implements(pop3.IServerFactory)

    protocol = QuotientPOP3

    def __init__(self, portal):
        self.portal = portal


    def cap_IMPLEMENTATION(self):
        from xquotient import version
        return "Quotient " + str(version)


    def cap_EXPIRE(self):
        raise NotImplementedError()


    def cap_LOGIN_DELAY(self):
        return 120


    def perUserLoginDelay(self):
        return True


    def buildProtocol(self, addr):
        p = protocol.Factory.buildProtocol(self, addr)
        p.portal = self.portal
        return p



class POP3Benefactor(item.Item):
    endowed = attributes.integer(default=0)

class POP3Listener(item.Item, service.Service):

    typeName = "quotient_pop3listener"
    schemaVersion = 1
    powerupInterfaces = (service.IService)

    # These are for the Service stuff
    parent = attributes.inmemory()
    running = attributes.inmemory()

    # A cred portal, a Twisted TCP factory and as many as two
    # IListeningPorts
    portal = attributes.inmemory()
    factory = attributes.inmemory()
    port = attributes.inmemory()
    securePort = attributes.inmemory()

    installedOn = attributes.reference(
        "A reference to the store or avatar which we have powered up.")

    portNumber = attributes.integer(
        "The TCP port to bind to serve SMTP.",
        default=6110)

    securePortNumber = attributes.integer(
        "The TCP port to bind to serve SMTP/SSL.",
        default=0)

    certificateFile = attributes.bytes(
        "The name of a file on disk containing a private "
        "key and certificate for use by the SMTP/SSL server.",
        default=None)

    userbase = dependsOn(LoginSystem)

    # When enabled, toss all traffic into logfiles.
    debug = False


    def activate(self):
        self.portal = None
        self.factory = None
        self.port = None
        self.securePort = None



    def installed(self):
        self.setServiceParent(self.store)

    def privilegedStartService(self):

        self.portal = portal.Portal(self.userbase, [self.userbase])
        self.factory = POP3ServerFactory(self.portal)

        if self.debug:
            self.factory = policies.TrafficLoggingFactory(self.factory, 'pop3')

        if self.portNumber is not None:
            self.port = reactor.listenTCP(self.portNumber, BandwidthMeasuringFactory(self.factory, 'pop3'))

        if self.securePortNumber is not None and self.certificateFile is not None:
            cert = sslverify.PrivateCertificate.loadPEM(file(self.certificateFile).read())
            certOpts = sslverify.OpenSSLCertificateOptions(
                cert.privateKey.original,
                cert.original,
                requireCertificate=False,
                method=SSL.SSLv23_METHOD)
            self.securePort = reactor.listenSSL(self.securePortNumber, BandwidthMeasuringFactory(self.factory, 'pop3s'), certOpts)

    def stopService(self):
        L = []
        if self.port is not None:
            L.append(defer.maybeDeferred(self.port.stopListening))
            self.port = None
        if self.securePort is not None:
            L.append(defer.maybeDeferred(self.securePort.stopListening))
            self.securePort = None
        return defer.DeferredList(L)
