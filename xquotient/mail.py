
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

from xquotient import iquotient

class MailConfigurationError(RuntimeError):
    """You specified some invalid configuration.
    """

class DeliveryFactory(object):
    implements(smtp.IMessageDeliveryFactory)

    def __init__(self, store):
        self.store = store
        realm = portal.IRealm(store)
        chk = checkers.ICredentialsChecker(store)
        self.portal = portal.Portal(realm, [chk])

    def getMessageDelivery(self):
        return MessageDelivery(self.portal)

components.registerAdapter(DeliveryFactory, store.Store, smtp.IMessageDeliveryFactory)

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
        creds = userbase.Preauthenticated('@'.join((user.local, user.domain)))
        d = self.portal.login(creds, None, iquotient.IMIMEDelivery)
        d.addCallbacks(cbLogin, ebLogin)
        return d

class MailTransferAgent(item.Item, service.Service):
    implements(smtp.IMessageDeliveryFactory)

    typeName = "mantissa_mta"
    schemaVersion = 1

    messageCount = attributes.integer(
        "The number of messages which have been delivered through this agent.",
        default=0)
    installedOn = attributes.reference()

    portNumber = attributes.integer(default=0)
    securePortNumber = attributes.integer(default=0)
    certificateFile = attributes.bytes(default=None)

    domain = attributes.bytes(default=None)

    parent = attributes.inmemory()
    running = attributes.inmemory()

    port = attributes.inmemory()
    securePort = attributes.inmemory()
    factory = attributes.inmemory()

    debug = False

    def activate(self):
        self.port = None
        self.securePort = None

    def installOn(self, other):
        assert self.installedOn is None, "You cannot install a MailTransferAgent on more than one thing"
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

        p = portal.Portal(realm, [chk, checkers.AllowAnonymousAccess()])
        self.factory = smtp.SMTPFactory(p)
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
