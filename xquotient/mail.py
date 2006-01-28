
import itertools

try:
    from OpenSSL import SSL
except ImportError:
    SSL = None

from zope.interface import implements

from twisted.application import service
from twisted.internet import defer, reactor
from twisted.protocols import policies
from twisted.python import components, log
from twisted.cred import portal, checkers
from twisted.mail import smtp

from vertex import sslverify

from axiom import store, item, attributes, userbase

from xquotient import iquotient, exmess, mimestorage

class MailConfigurationError(RuntimeError):
    """You specified some invalid configuration.
    """

class MessageDelivery(object):
    implements(smtp.IMessageDelivery)

    def __init__(self, portal):
        self.portal = portal

    def receivedHeader(self, helo, origin, recipients):
        return "" # Maybe put something here?

    def validateFrom(self, helo, origin):
        return origin

    def validateTo(self, user):
        def cbLogin((iface, avatar, logout)):
            logout() # XXX???
            return avatar.createMIMEReceiver
        def ebLogin(err):
            log.msg("Failed validateTo")
            log.err(err)
            return defer.fail(smtp.SMTPBadRcpt("Denied!"))
        creds = userbase.Preauthenticated('@'.join((user.dest.local, user.dest.domain)))
        d = self.portal.login(creds, None, iquotient.IMIMEDelivery)
        d.addCallbacks(cbLogin, ebLogin)
        return d

class DeliveryAgentMixin(object):
    implements(iquotient.IMIMEDelivery)

    def createMIMEReceiver(self):
        fObj = self.installedOn.newFile('messages', str(self.messageCount))
        self.messageCount += 1
        return mimestorage.MIMEMessageStorer(
            self.installedOn, fObj)


class DeliveryFactoryMixin(object):
    implements(smtp.IMessageDeliveryFactory)

    def getMessageDelivery(self):
        return MessageDelivery(self.portal)


class MailTransferAgent(item.Item, service.Service, DeliveryFactoryMixin, DeliveryAgentMixin):
    typeName = "mantissa_mta"
    schemaVersion = 1

    messageCount = attributes.integer(
        "The number of messages which have been delivered through this agent.",
        default=0)
    installedOn = attributes.reference(
        "A reference to the store or avatar which we have powered up.")

    portNumber = attributes.integer(
        "The TCP port to bind to serve SMTP.",
        default=6025)
    securePortNumber = attributes.integer(
        "The TCP port to bind to serve SMTP/SSL.",
        default=0)
    certificateFile = attributes.bytes(
        "The name of a file on disk containing a private "
        "key and certificate for use by the SMTP/SSL server.",
        default=None)

    domain = attributes.bytes(
        "The canonical name of this host.  Used when greeting SMTP clients.",
        default=None)

    # These are for the Service stuff
    parent = attributes.inmemory()
    running = attributes.inmemory()

    # A cred portal, a Twisted TCP factory and as many as two
    # IListeningPorts
    portal = attributes.inmemory()
    factory = attributes.inmemory()
    port = attributes.inmemory()
    securePort = attributes.inmemory()

    # When enabled, toss all traffic into logfiles.
    debug = False

    def activate(self):
        self.portal = None
        self.factory = None
        self.port = None
        self.securePort = None

    def installOn(self, other):
        assert self.installedOn is None, "You cannot install a MailTransferAgent on more than one thing"
        other.powerUp(self, service.IService)
        other.powerUp(self, iquotient.IMIMEDelivery)
        other.powerUp(self, smtp.IMessageDeliveryFactory)
        self.installedOn = other
        self.setServiceParent(other)

    def privilegedStartService(self):
        if SSL is None and self.securePortNumber is not None:
            raise MailConfigurationError(
                "No SSL support: you need to install OpenSSL to server SMTP/SSL")

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

        self.portal = portal.Portal(realm, [chk, checkers.AllowAnonymousAccess()])
        self.factory = smtp.SMTPFactory(self.portal)
        if self.domain is not None:
            self.factory.domain = self.domain

        if self.debug:
            self.factory = policies.TrafficLoggingFactory(self.factory, 'smtp')

        if self.portNumber is not None:
            self.port = reactor.listenTCP(self.portNumber, self.factory)

        if self.securePortNumber is not None and self.certificateFile is not None:
            cert = sslverify.PrivateCertificate.loadPEM(file(self.certificateFile).read())
            certOpts = sslverify.OpenSSLCertificateOptions(
                cert.privateKey.original,
                cert.original,
                requireCertificate=False,
                method=SSL.SSLv23_METHOD)
            self.securePort = reactor.listenSSL(self.securePortNumber, self.factory, certOpts)

    def stopService(self):
        L = []
        if self.port is not None:
            L.append(defer.maybeDeferred(self.port.stopListening))
            self.port = None
        if self.securePort is not None:
            L.append(defer.maybeDeferred(self.securePort.stopListening))
            self.securePort = None
        return defer.DeferredList(L)

