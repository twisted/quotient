# -*- test-case-name: xquotient.test.test_mta -*-

"""
Support for SMTP servers in Quotient.

Implementations of L{twisted.mail.smtp.IMessageDeliveryFactory},
L{twisted.mail.smtp.IMessageDelivery}, and L{twisted.mail.smtp.IMessage} can be
found here.  There are classes for handling anonymous SMTP delivery into the
system (the typical case for receiving messages for Quotient users from
elsewhere) and authenticated SMTP (the way Quotient users will send messages to
other people).  SMTP, SMTP/SSL, and STARTTLS are all supported, mainly for free
from Twisted's SSL and SMTP support code.
"""

import datetime

try:
    from OpenSSL import SSL
except ImportError:
    SSL = None

from zope.interface import implements

from twisted.application import service
from twisted.internet import defer, reactor
from twisted.protocols import policies
from twisted.python import failure
from twisted.cred import portal, checkers
from twisted.mail import smtp

from epsilon import extime
from epsilon import sslverify

from axiom import item, attributes, userbase, scheduler, batch
from axiom.upgrade import registerUpgrader

from xmantissa.stats import BandwidthMeasuringFactory

from xquotient import iquotient, exmess, mimestorage

MessageSource = batch.processor(exmess.Message)

class MailConfigurationError(RuntimeError):
    """You specified some invalid configuration.
    """

class MessageDelivery(object):
    """
    Message Delivery implementation used by anonymous senders.

    This implementation only allows messages to be delivered to local users
    (ie, it does not perform relaying) and rejects sender addresses which
    belong to local users.
    """
    implements(smtp.IMessageDelivery)

    def __init__(self, store, portal):
        self.store = store
        self.portal = portal


    def receivedHeader(self, helo, origin, recipients):
        return "" # Maybe put something here?


    def validateFrom(self, helo, origin):
        if origin.domain in userbase.getDomainNames(self.store):
            return defer.fail(smtp.SMTPBadSender(origin))
        return defer.succeed(origin)


    def validateTo(self, user):
        addr = '@'.join((user.dest.local, user.dest.domain))
        d = self.portal.login(
            userbase.Preauthenticated(addr), None, iquotient.IMIMEDelivery)
        def loggedIn((iface, avatar, logout)):
            logout() # XXX???
            def createMIMEReceiver():
                return avatar.createMIMEReceiver(
                    u"smtp://%s@%s" % (user.dest.local, user.dest.domain))
            return createMIMEReceiver
        def notLoggedIn(err):
            err.trap(userbase.NoSuchUser)
            return defer.fail(smtp.SMTPBadRcpt(user))
        d.addCallbacks(loggedIn, notLoggedIn)
        return d



class SafeMIMEParserWrapper(object):
    """
    Simple wrapper around a real MIME parser which captures errors from
    lineReceived and saves them until messageDone().
    """
    implements(smtp.IMessage)

    failure = None

    def __init__(self, receiver):
        self.receiver = receiver


    def lineReceived(self, line):
        if self.failure is None:
            try:
                return self.receiver.lineReceived(line)
            except:
                self.failure = failure.Failure()


    def messageDone(self):
        if self.failure is not None:
            self.failure.raiseException()
        else:
            return self.receiver.messageDone()


    def __getattr__(self, name):
        # Let people get at feedStringNow and that junk, if they want.
        # We won't help them out if they try.
        return getattr(self.receiver, name)



class DeliveryAgent(item.Item, item.InstallableMixin):
    """
    Entrypoint for MIME-formatted content into a Quotient-enabled Store.

    @ivar messageCount: The number of MIME receivers which have ever been
    created. (Not necessarily the number of messages which have been delivered
    - XXX rename this to receiverCount and add messageCount which counts
    messages).
    """
    implements(iquotient.IMIMEDelivery)

    installedOn = attributes.reference()
    messageCount = attributes.integer(default=0)

    def installOn(self, other):
        super(DeliveryAgent, self).installOn(other)
        other.powerUp(self, iquotient.IMIMEDelivery)


    def createMIMEReceiver(self, source):
        today = datetime.date.today()
        fObj = self.installedOn.newFile(
            'messages',
            str(today.year),
            str(today.month),
            str(today.day),
            str(self.messageCount % 100),
            str(self.messageCount))
        self.messageCount += 1
        return SafeMIMEParserWrapper(mimestorage.MIMEMessageStorer(
            self.installedOn, fObj, source))



class DeliveryFactoryMixin(object):
    implements(smtp.IMessageDeliveryFactory)

    def getMessageDelivery(self):
        if self.portal is not None:
            return MessageDelivery(self.store, self.portal)
        raise RuntimeError("Cannot create MessageDelivery without portal.")



class MailTransferAgent(item.Item, item.InstallableMixin,
                        service.Service, DeliveryFactoryMixin):
    """
    Service responsible for binding server ports for SMTP and SMTP/SSL
    protocols.  Also responsible for attaching an appropriately Axiomified cred
    portal to the factories for those servers.
    """

    typeName = "mantissa_mta"
    schemaVersion = 2

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
        super(MailTransferAgent, self).installOn(other)
        other.powerUp(self, service.IService)
        other.powerUp(self, smtp.IMessageDeliveryFactory)
        if self.store.parent is None:
            other.powerUp(self, service.IService)
            if self.parent is None:
                self.setServiceParent(other)


    def privilegedStartService(self):
        if SSL is None and self.securePortNumber is not None:
            raise MailConfigurationError(
                "No SSL support: you need to install "
                "OpenSSL to server SMTP/SSL")

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

        self.portal = portal.Portal(
            realm, [chk, checkers.AllowAnonymousAccess()])
        self.factory = smtp.SMTPFactory(self.portal)
        self.factory.protocol = smtp.ESMTP
        if self.domain is not None:
            self.factory.domain = self.domain

        if self.debug:
            self.factory = policies.TrafficLoggingFactory(self.factory, 'smtp')

        if self.portNumber is not None:
            self.port = reactor.listenTCP(
                self.portNumber,
                BandwidthMeasuringFactory(self.factory, 'smtp'))

        if (self.securePortNumber is not None and
            self.certificateFile is not None):
            cert = sslverify.PrivateCertificate.loadPEM(
                file(self.certificateFile).read())
            certOpts = sslverify.OpenSSLCertificateOptions(
                cert.privateKey.original,
                cert.original,
                requireCertificate=False,
                method=SSL.SSLv23_METHOD)
            self.securePort = reactor.listenSSL(
                self.securePortNumber,
                BandwidthMeasuringFactory(self.factory, 'smtps'), certOpts)


    def stopService(self):
        L = []
        if self.port is not None:
            L.append(defer.maybeDeferred(self.port.stopListening))
            self.port = None
        if self.securePort is not None:
            L.append(defer.maybeDeferred(self.securePort.stopListening))
            self.securePort = None
        return defer.DeferredList(L)


def upgradeMailTransferAgent1to2(oldMTA):
    """
    MailTransferAgent has been replaced with MailDeliveryAgent on B{user
    stores}.  Delete it from user stores and create a MailDelivery agent
    there, but leave it alone on the site store.
    """
    loginSystem = oldMTA.store.findUnique(userbase.LoginSystem, default=None)
    if loginSystem is not None:
        newMTA = oldMTA.upgradeVersion(
            'mantissa_mta', 1, 2,
            messageCount=oldMTA.messageCount,
            installedOn=oldMTA.installedOn,
            portNumber=oldMTA.portNumber,
            securePortNumber=oldMTA.securePortNumber,
            certificateFile=oldMTA.certificateFile,
            domain=oldMTA.domain)
        return newMTA
    else:
        mda = MailDeliveryAgent(store=oldMTA.store)
        mda.installOn(mda.store)
        oldMTA.installedOn.powerDown(oldMTA, smtp.IMessageDeliveryFactory)
        oldMTA.deleteFromStore()
        # The MTA was deleted, there's no sensible Item to return here.
        return mda

registerUpgrader(upgradeMailTransferAgent1to2, 'mantissa_mta', 1, 2)


class NullMessage(object):
    """
    Void implementation of L{smtp.IMessage}.  Accepts and discards all events
    which can occur.
    """
    implements(smtp.IMessage)

    def lineReceived(self, line):
        pass


    def messageDone(self):
        pass



class OutgoingMessageWrapper(object):
    """
    L{smtp.IMessage} provider which wraps another provider of the same
    interface and uses an L{iquotient.IMessageSender} to deliver the message
    someplace else after it has been completed.

    @type sender: L{iquotient.IMessageSender} provider
    @ivar sender: The object which will be used to send the created message
    when it is ready.

    @type recipients: C{list} of C{unicode}
    @ivar recipients: RFC2822 addresses to which the message will be sent.

    @ivar mimeReceiver: The wrapped L{smtp.IMessage} provider.  In addition to
    providing that interface, it must also have a C{message} attribute after
    C{messageDone} returns.  This is typically expected to be an instance of
    L{xquotient.mimestorage.MIMEMessageStorer}.
    """
    implements(smtp.IMessage)

    def __init__(self, sender, recipients, mimeReceiver):
        self.sender = sender
        self.recipients = recipients
        self.mimeReceiver = mimeReceiver


    def lineReceived(self, line):
        """
        Accept the next line from the message and pass it through to the
        wrapped L{smtp.IMessage}.
        """
        return self.mimeReceiver.lineReceived(line)


    def messageDone(self):
        """
        Pass completion notification through to the wrapped L{smtp.IMessage}
        and then send the resulting message using C{self.sender.sendMessage}.
        """
        self.mimeReceiver.messageDone()
        self.sender.sendMessage(
            self.recipients,
            self.mimeReceiver.message)



class MailDeliveryAgent(item.Item, item.InstallableMixin):
    """
    Class responsible for authenticated delivery.
    """
    implements(smtp.IMessageDeliveryFactory)

    installedOn = attributes.reference()

    def installOn(self, other):
        super(MailDeliveryAgent, self).installOn(other)
        other.powerUp(self, smtp.IMessageDeliveryFactory)


    def getMessageDelivery(self):
        realm = portal.IRealm(self.store.parent)
        chk = checkers.ICredentialsChecker(self.store.parent)
        return AuthenticatedMessageDelivery(
            iquotient.IMIMEDelivery(self.store),
            iquotient.IMessageSender(self.store),
            portal.Portal(
                realm, [chk, checkers.AllowAnonymousAccess()]))



class AuthenticatedMessageDelivery(object):
    """
    Class responsible for delivering messages from authenticated users.
    """
    implements(smtp.IMessageDelivery)

    origin = None
    _recipientAddresses = None

    def __init__(self, avatar, composer, portal):
        self.avatar = avatar
        self.composer = composer
        self.portal = portal


    def validateFrom(self, helo, origin):
        """
        Verify that the given origin address is one this user is allowed to
        claim.
        """
        for local, domain in userbase.getAccountNames(self.avatar.store):
            if local == origin.local and domain == origin.domain:
                self.origin = origin
                return defer.succeed(origin)
        return defer.fail(smtp.SMTPBadSender(origin))


    def validateTo(self, user):
        """
        Determine whether the recipient is local to this system or not and
        dispatch to the appropriate helper method.
        """
        siteStore = self.avatar.store.parent
        if user.dest.domain in userbase.getDomainNames(siteStore):
            return self.localValidateTo(user)
        else:
            return self.remoteValidateTo(user)


    def localValidateTo(self, user):
        """
        Determine whether the given user exists locally.  If they do not,
        reject the address as invalid.  If they do, return a delivery object
        appropriate for that user.  Currently this delivery object is the same
        as the remote delivery object, but at some point it may make sense to
        optimize this codepath and skip the network for local<->local delivery.
        """
        siteStore = self.avatar.store.parent
        loginSystem = siteStore.findUnique(userbase.LoginSystem)
        account = loginSystem.accountByAddress(
            user.dest.local.decode('ascii'),
            user.dest.domain.decode('ascii'))
        if account is None:
            return defer.fail(smtp.SMTPBadRcpt(user))
        else:
            # XXX TODO - We could skip the network here.
            return self.remoteValidateTo(user)


    def remoteValidateTo(self, user):
        """
        Either create a new L{OutgoingMessageWrapper} around a MIME receiver
        which delivers into this user's store or add the given address to the
        list of addresses an existing L{OutgoingMessageWrapper} will deliver
        to.

        This takes care to only create one C{smtp.IMessage} provider per
        message so that only one sent message will appear in a user's account
        regardless of the number of recipients they specify.
        """
        address = u'@'.join((user.dest.local, user.dest.domain))
        if self._recipientAddresses is not None:
            self._recipientAddresses.append(address)
            return defer.succeed(NullMessage)
        self._recipientAddresses = [address]
        def createMIMEReceiver():
            return OutgoingMessageWrapper(
                self.composer,
                self._recipientAddresses,
                self.avatar.createMIMEReceiver(
                    u"sent://%s@%s" % (self.origin.local, self.origin.domain)))
        return defer.succeed(createMIMEReceiver)
