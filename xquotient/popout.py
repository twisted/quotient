
import os

from OpenSSL import SSL

from zope.interface import implements

from twisted.application import service
from twisted.internet import defer, reactor, protocol
from twisted.protocols import policies
from twisted.cred import portal, checkers

from xmantissa.stats import BandwidthMeasuringFactory

from xquotient.exmess import Message

from vertex import sslverify

from axiom import item, attributes

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


class POP3Up(item.Item, item.InstallableMixin):

    typeName = 'quotient_pop3_user_powerup'

    implements(pop3.IMailbox)

    messageList = attributes.inmemory()
    deletions = attributes.inmemory()

    installedOn = attributes.reference()

    def activate(self):
        self.messageList = None
        self.deletions = None


    def installOn(self, other):
        super(POP3Up, self).installOn(other)
        other.powerUp(self, pop3.IMailbox)


    def getMessageList(self):
        # XXX could be made more incremental by screwing with login, making it
        # return a deferred
        if self.messageList == None:
            # load it
            oldMessages = list(self.store.query(
                Message,
                attributes.AND(Message.storeID == MessageInfo.message,
                               MessageInfo.localPop3Deleted == False),
                sort=Message.storeID.asc))
            newMessages = list(self.store.query(
                Message, Message.storeID.notOneOf(self.store.query(MessageInfo).getColumn('message', raw=True)),
                sort=Message.storeID.asc))
            for message in newMessages:
                MessageInfo(store=self.store,
                            localPop3Deleted=False,
                            localPop3UID = os.urandom(16).encode('hex'),
                            message=message)
            self.messageList = list(self.store.query(MessageInfo))
            self.deletions = []
        return self.messageList
    getMessageList = item.transacted(getMessageList)

    def listMessages(self, index=None):
        """
        """
        if index is None:
            return [self.messageSize(idx) for idx in
                    xrange(len(self.getMessageList()))]
        else:
            return self.messageSize(index)


    def _getMessageImpl(self, index):
        return self.getMessageList()[index].message.impl

    def messageSize(self, index):
        if index in self.deletions:
            return 0
        i = self._getMessageImpl(index)
        return i.bodyOffset + (i.bodyLength or 0)

    def deleteMessage(self, index):
        self.deletions.append(index)

    def getMessage(self, index):
        if index in self.deletions:
            raise Exception("Deleted message retrieved.")
        return self._getMessageImpl(index).source.open()

    def getUidl(self, index):
        return self.getMessageList()[index].localPop3UID

    def sync(self):
        ml = self.getMessageList()
        for delidx in self.deletions:
            ml[delidx].localPop3Deleted = True
        self.messageList = None
        self.deletions = []
        self.getMessageList()



class POP3ServerFactory(protocol.Factory):

    implements(pop3.IServerFactory)

    protocol = pop3.POP3

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

    def endow(self, ticket, avatar):
        for cls in (POP3Up,):
            avatar.findOrCreate(POP3Up).installOn(avatar)


    def revoke(self, ticket, avatar):
        avatar.findUnique(POP3Up).deleteFromStore()



class POP3Listener(item.Item, item.InstallableMixin, service.Service):

    typeName = "quotient_pop3listener"
    schemaVersion = 1

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

    # When enabled, toss all traffic into logfiles.
    debug = False


    def activate(self):
        self.portal = None
        self.factory = None
        self.port = None
        self.securePort = None

    def installOn(self, other):
        super(POP3Listener, self).installOn(other)
        other.powerUp(self, service.IService)
        self.setServiceParent(other)

    def privilegedStartService(self):
        realm = portal.IRealm(self.installedOn, None)
        if realm is None:
            raise MailConfigurationError(
                "No realm: "
                "you need to install a userbase before using this service.")

        chk = checkers.ICredentialsChecker(self.installedOn, None)
        if chk is None:
            raise MailConfigurationError(
                "No checkers: "
                "you need to install a userbase before using this service.")

        self.portal = portal.Portal(realm, [chk])
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
