
from OpenSSL import SSL

from zope.interface import implements

from twisted.mail import imap4

from twisted.internet.protocol import Factory
from twisted.internet import defer

from epsilon.extime import Time

from axiom import item, attributes

from xquotient import exmess

from twisted.protocols import policies

from twisted.cred import portal, checkers

from vertex import sslverify

from twisted.internet import reactor

from twisted.application import service


class MailConfigurationError(Exception):
    pass

class IMAP4PartInfo:
    implements(imap4.IMessagePart)

    def __init__(self, part):
        self.part = part

    def getHeaders(self, negate, *names):
        result = {}
        hdrs = self.part.getAllHeaders()
        for hdr in hdrs:
            if (hdr.name in names) ^ negate:
                result[hdr.name] = hdr.value
        return result

    def getBodyFile(self):
        """Retrieve a file object containing only the body of this message.
        """
        f = self.part.source.open()
        f.seek(self.part.bodyOffset)
        return f

    def getSize(self):
        """Retrieve the total size, in octets, of this message.

        @rtype: C{int}
        """
        return self.part.source.getsize()

    def isMultipart(self):
        from xquotient.mimestorage import Part
        return bool(self.part.store.query(Part, Part.parent == self.part).count())

    def getSubPart(self, part):
        return IMAP4PartInfo(self.part.getSubPart(part))


class IMAP4MessageInfo(item.Item):
    implements(imap4.IMessage)

    message = attributes.reference(allowNone=False)

    imapUID = attributes.integer(allowNone=False)
    imapMailbox = attributes.reference(allowNone=False)
    imapSequenceNumber = attributes.integer(allowNone=False)

    _rootPart = attributes.inmemory()

    def activate(self):
        self._rootPart = None

    def _getRootPart(self):
        if self._rootPart is None:
            self._rootPart = IMAP4PartInfo(self.message.impl)
        return self._rootPart

    rootPart = property(_getRootPart)

    # Just messages

    def getUID(self):
        """Retrieve the unique identifier associated with this message.
        """

    def getFlags(self):
        """Retrieve the flags associated with this message.

        @rtype: C{iterable}
        @return: The flags, represented as strings.
        """
        return ['']

    def getInternalDate(self):
        return self.message.received.asRFC2822()

    # All parts

    def getHeaders(self, negate, *names):
        return self.rootPart.getHeaders(negate, *names)

    def getBodyFile(self):
        return self.rootPart.getBodyFile()

    def getSize(self):
        return self.rootPart.getSize()

    def isMultipart(self):
        return self.rootPart.isMultipart()

    def getSubPart(self, part):
        return self.rootPart.getSubPart(part)


class IMAP4MailboxImpl:
    def __init__(self, mboxitem):
        self.mbox = mboxitem

    def getHierarchicalDelimiter(self):
        return '/'


    def getUIDValidity(self):
        return int(self.mbox.uidValidity.asPOSIXTimestamp())


    def getUIDNext(self):
        """Return the likely UID for the next message added to this mailbox.

        @rtype: C{int}
        """
        return self.mbox.uidCounter + 1

    def getUID(self, message):
        """Return the UID of a message in the mailbox

        @type message: C{int}
        @param message: The message sequence number

        @rtype: C{int}
        @return: The UID of the message.
        """
        return self.mbox.store.findUnique(
            IMAP4MessageInfo,
            attributes.AND(IMAP4MessageInfo.imapMailbox == self.mbox,
                           IMAP4MessageInfo.imapSequenceNumber == message)).imapUID

    def getMessageCount(self):
        """Return the number of messages in this mailbox.

        @rtype: C{int}
        """
        return self.mbox.store.query(IMAP4MessageInfo,
                                     IMAP4MessageInfo.imapMailbox == self.mbox)

    def getRecentCount(self):
        """Return the number of messages with the 'Recent' flag.

        @rtype: C{int}
        """
        # what's 'recent'?
        return 0

    def getUnseenCount(self):
        """Return the number of messages with the 'Unseen' flag.

        @rtype: C{int}
        """
        return self.mbox.store.query(
            IMAP4MessageInfo,
            attributes.AND(IMAP4MessageInfo.imapMailbox == self.mbox,
                           IMAP4MessageInfo.message == exmess.Message.storeID,
                           exmess.Message.read == False))

    def isWriteable(self):
        return True

    def destroy(self):
        """Called before this mailbox is deleted, permanently.

        If necessary, all resources held by this mailbox should be cleaned
        up here.  This function _must_ set the \\Noselect flag on this
        mailbox.
        """

    def requestStatus(self, names):
        return imap4.statusRequestHelper(self, names)

    def addListener(self, listener):
        pass

    def removeListener(self, listener):
        pass

    def addMessage(self, message, flags = (), date = None):
        """Add the given message to this mailbox.

        @type message: A file-like object
        @param message: The RFC822 formatted message

        @type flags: Any iterable of C{str}
        @param flags: The flags to associate with this message

        @type date: C{str}
        @param date: If specified, the date to associate with this
        message.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with the message
        id if the message is added successfully and whose errback is
        invoked otherwise.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
        read-write.
        """
        return defer.fail(RuntimeError("adding messages not supported"))

    def expunge(self):
        """Remove all messages flagged \\Deleted.

        @rtype: C{list} or C{Deferred}
        @return: The list of message sequence numbers which were deleted,
        or a C{Deferred} whose callback will be invoked with such a list.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
        read-write.
        """

    def fetch(self, messages, uid):
        if uid:
            determinant = IMAP4MessageInfo.imapUID
        else:
            determinant = IMAP4MessageInfo.imapSequenceNumber

        fetcher = lambda objid: self.mbox.store.findUnique(
                IMAP4MessageInfo,
                attributes.AND(determinant == objid,
                               IMAP4MessageInfo.imapMailbox == self.mbox))

        for ojd in messages:
            m = fetcher(ojd)
            yield m.imapSequenceNumber, m

    def store(self, messages, flags, mode, uid):
        """Set the flags of one or more messages.

        @type messages: A MessageSet object with the list of messages requested
        @param messages: The identifiers of the messages to set the flags of.

        @type flags: sequence of C{str}
        @param flags: The flags to set, unset, or add.

        @type mode: -1, 0, or 1
        @param mode: If mode is -1, these flags should be removed from the
        specified messages.  If mode is 1, these flags should be added to
        the specified messages.  If mode is 0, all existing flags should be
        cleared and these flags should be added.

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs;
        otherwise they are message sequence IDs.

        @rtype: C{dict} or C{Deferred}
        @return: A C{dict} mapping message sequence numbers to sequences of C{str}
        representing the flags set on the message after this operation has
        been performed, or a C{Deferred} whose callback will be invoked with
        such a C{dict}.

        @raise ReadOnlyMailbox: Raised if this mailbox is not open for
        read-write.
        """

    def getFlags(self):
        return ['\\NoSelect',
                '\\Seen',
                '\\Answered',
                '\\Forwarded',
                '\\Redirected']


class IMAP4MailboxItem(item.Item):
    typeName = 'quotient_imap4_mailbox'

    uidValidity = attributes.timestamp()
    uidCounter = attributes.integer(default=0)

    implements(imap4.IMailbox)

    def __init__(self):
        self.uidValidity = Time()



class IMAP4Up(item.Item):
    typeName = 'quotient_imap4_user_powerup'

    implements(imap4.IAccount)


    def addMailbox(self, name, mbox = None):
        raise imap4.MailboxException("Adding mailboxes not yet implemented.")


    def create(self, pathspec):
        raise imap4.MailboxException("Adding mailboxes not yet implemented.")

    def select(self, name, rw=True):
        pass

    def delete(self, name):
        """Delete the mailbox with the specified name.

        @type name: C{str}
        @param name: The mailbox to delete.

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is successfully deleted, or a
        C{Deferred} whose callback will be invoked when the deletion
        completes.

        @raise MailboxException: Raised if this mailbox cannot be deleted.
        This may also be raised asynchronously, if a C{Deferred} is returned.
        """

    def rename(self, oldname, newname):
        """Rename a mailbox

        @type oldname: C{str}
        @param oldname: The current name of the mailbox to rename.

        @type newname: C{str}
        @param newname: The new name to associate with the mailbox.

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is successfully renamed, or a
        C{Deferred} whose callback will be invoked when the rename operation
        is completed.

        @raise MailboxException: Raised if this mailbox cannot be
        renamed.  This may also be raised asynchronously, if a C{Deferred}
        is returned.
        """

    def isSubscribed(self, name):
        """Check the subscription status of a mailbox

        @type name: C{str}
        @param name: The name of the mailbox to check

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the given mailbox is currently subscribed
        to, a false value otherwise.  A C{Deferred} may also be returned
        whose callback will be invoked with one of these values.
        """

    def subscribe(self, name):
        """Subscribe to a mailbox

        @type name: C{str}
        @param name: The name of the mailbox to subscribe to

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is subscribed to successfully,
        or a Deferred whose callback will be invoked with this value when
        the subscription is successful.

        @raise MailboxException: Raised if this mailbox cannot be
        subscribed to.  This may also be raised asynchronously, if a
        C{Deferred} is returned.
        """

    def unsubscribe(self, name):
        """Unsubscribe from a mailbox

        @type name: C{str}
        @param name: The name of the mailbox to unsubscribe from

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is unsubscribed from successfully,
        or a Deferred whose callback will be invoked with this value when
        the unsubscription is successful.

        @raise MailboxException: Raised if this mailbox cannot be
        unsubscribed from.  This may also be raised asynchronously, if a
        C{Deferred} is returned.
        """

    def listMailboxes(self, ref, wildcard):
        """List all the mailboxes that meet a certain criteria

        @type ref: C{str}
        @param ref: The context in which to apply the wildcard

        @type wildcard: C{str}
        @param wildcard: An expression against which to match mailbox names.
        '*' matches any number of characters in a mailbox name, and '%'
        matches similarly, but will not match across hierarchical boundaries.

        @rtype: C{list} of C{tuple}
        @return: A list of C{(mailboxName, mailboxObject)} which meet the
        given criteria.  C{mailboxObject} should implement either
        C{IMailboxInfo} or C{IMailbox}.  A Deferred may also be returned. 
        """



class IMAP4ServerFactory(Factory):
    def __init__(self, portal):
        self.portal = portal

    def buildProtocol(self, addr):
        s = imap4.IMAP4Server()
        s.portal = self.portal
        s.factory = self
        return s


class IMAP4Listener(item.Item, service.Service):

    typeName = "quotient_imap4_listener"
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
        default=6143)

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
        assert self.installedOn is None, "You cannot install an IMAP4Listener on more than one thing"
        other.powerUp(self, service.IService)
        self.installedOn = other

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
        self.factory = IMAP4ServerFactory(self.portal)

        if self.debug:
            self.factory = policies.TrafficLoggingFactory(self.factory, 'imap4')

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
