# -*- test-case-name: xquotient.test.test_popout -*-

import os

from OpenSSL import SSL

from zope.interface import implements

from twisted.python import log

from twisted.application import service
from twisted.internet import defer, reactor, protocol
from twisted.protocols import policies
from twisted.cred import portal, checkers
from twisted.mail import pop3

from epsilon.cooperator import iterateInReactor as coiterate

from xmantissa.stats import BandwidthMeasuringFactory

from xquotient.exmess import Message

from epsilon import sslverify

from axiom import item, attributes
from axiom.errors import MissingDomainPart

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


class _ActualMailbox:
    """
    This is an in-memory implementation of all the transient state associated
    with a user's authenticated POP3 session.
    """

    listingDeferred = None
    pagesize = 1

    def __init__(self, store):
        """
        Create a mailbox implementation from an L{axiom.store.Store}.

        @type store: L{axiom.store.Store}

        @param store: a user store containing L{Message} and possibly also
        L{MessageInfo} objects.
        """
        self.store = store
        self.undeleteMessages()
        self.messageList = None
        self.messageListInProgress = None
        self.coiterate = coiterate


    def whenReady(self):
        """
        Return a deferred which will fire when the mailbox is ready, or a
        deferred which has already fired if the mailbox is already ready.
        """
        if self.listingDeferred is None:
            self.listingDeferred = self.kickoff()
        return _ndchain(self.listingDeferred)


    def kickoff(self):
        """
        Begin loading all POP-accessible messages into an in-memory list.

        @return: a Deferred which will fire with a list of L{MessageInfo}
        instances when complete.
        """
        self.messageListInProgress = True
        def _(ignored):
            self.messageListInProgress = False
            return self.messageList
        return self.coiterate(self._buildMessageList()).addCallback(_)


    def _buildMessageList(self):
        """
        @return: a generator, designed to be run to completion in coiterate(),
        which will alternately yield None and L{MessageInfo} instances as it
        loads them from the database.
        """
        infoList = []
        for message in self.store.query(Message
                                        ).paginate(pagesize=self.pagesize):
            # Find the POP information for this message.
            messageInfos = list(self.store.query(MessageInfo,
                                                 MessageInfo.message == message))
            if len(messageInfos) == 0:
                messageInfo = MessageInfo(store=self.store,
                                          localPop3Deleted=False,
                                          localPop3UID=os.urandom(16).encode('hex'),
                                          message=message)
            else:
                messageInfo = messageInfos[0]
            if messageInfo.localPop3Deleted:
                yield None
            else:
                infoList.append(messageInfo)
                yield messageInfo
        self.messageList = infoList


    def messageSize(self, index):
        if index in self.deletions:
            return 0
        i = self._getMessageImpl(index).message.impl
        return i.bodyOffset + (i.bodyLength or 0)



    def listMessages(self, index=None):
        if index is None:
            return [self.messageSize(idx) for idx in
                    xrange(len(self.messageList))]
        else:
            return self.messageSize(index)


    def _getMessageImpl(self, index):
        msgList = self.messageList
        try:
            msg = msgList[index]
        except IndexError:
            raise ValueError(index)
        else:
            return msg


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
        ml = self.messageList
        for delidx in self.deletions:
            ml[delidx].localPop3Deleted = True
        self.messageList = None
        self.deletions = set()
        self.listingDeferred = None
        return self.whenReady()


    def undeleteMessages(self):
        self.deletions = set()


def _ndchain(d1):
    """
    Create a deferred based on another deferred's results, without altering the
    value which will be passed to callbacks of the input deferred.

    @param d1: a L{Deferred} which will fire in the future.

    @return: a L{Deferred} which will fire at the same time as the given input,
    with the same value.
    """
    # XXX this is what Twisted's chainDeferred _should_ have done in the first
    # place.
    d2 = defer.Deferred()
    def cb(value):
        try:
            d2.callback(value)
        except:
            log.err()
        return value
    d1.addBoth(cb)
    return d2


class POP3Up(item.Item, item.InstallableMixin):
    """
    This is a powerup which provides POP3 mailbox functionality to a user.

    The actual work of implementing L{IMailbox} is done in a separate,
    transient in-memory class.
    """

    typeName = 'quotient_pop3_user_powerup'

    implements(pop3.IMailbox)

    actualMailbox = attributes.inmemory()

    installedOn = attributes.reference()


    def installOn(self, other):
        super(POP3Up, self).installOn(other)
        other.powerUp(self, pop3.IMailbox)


    def _realize(self):
        """
        Generate the object which will implement this user's mailbox.

        @return: an L{_ActualMailbox} instance.
        """
        r = _ActualMailbox(self.store)
        self.actualMailbox = r
        return r

    def _deferOperation(self, methodName):
        """
        This generates methods which, when invoked, will tell my mailbox
        implementation to load all of its messages if necessary and then
        perform the requested operation.

        @type methodName: L{str}

        @param methodName: the name of the method being potentially deferred.
        Should be in L{IMailbox}.

        @return: a callable which returns a Deferred that fires with the
        results of the given IMailbox method.
        """
        actualMailbox = getattr(self, 'actualMailbox', None)
        if actualMailbox is None:
            actualMailbox = self._realize()
        actualMethod = getattr(actualMailbox, methodName)
        def inner(*a, **k):
            def innerinner(ignored):
                return actualMethod(*a, **k)
            return actualMailbox.whenReady().addCallback(innerinner)
        return inner


    def __getattr__(self, name):
        """
        Provides normal attribute access, except for methods from
        L{pop3.IMailbox}, which are handled with L{_deferOperation}.

        @param name: the name of the attribute being requested.
        """
        if name in pop3.IMailbox:
            return self._deferOperation(name)
        return super(POP3Up, self).__getattr__(self, name)



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
