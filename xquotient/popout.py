
import os

from zope.interface import implements

from twisted.internet import protocol
from twisted.protocols import policies
from twisted.cred import portal
from twisted.mail import pop3
from twisted.application.service import IService

from axiom import item, attributes
from axiom.item import declareLegacyItem
from axiom.attributes import bytes, reference, integer
from axiom.errors import MissingDomainPart
from axiom.userbase import LoginSystem
from axiom.dependency import dependsOn, installOn
from axiom.upgrade import registerUpgrader

from xmantissa.ixmantissa import IProtocolFactoryFactory
from xmantissa.port import TCPPort, SSLPort

from xquotient.exmess import Message


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

    powerupInterfaces = (pop3.IMailbox,)

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
    powerupNames = ["xquotient.popout.POP3Up"]



class POP3Listener(item.Item):
    implements(IProtocolFactoryFactory)

    powerupInterfaces = (IProtocolFactoryFactory,)

    typeName = "quotient_pop3listener"
    schemaVersion = 3

    # A cred portal, a Twisted TCP factory and as many as two
    # IListeningPorts
    portal = attributes.inmemory()
    factory = attributes.inmemory()

    certificateFile = attributes.bytes(
        "The name of a file on disk containing a private key and certificate "
        "for use by the POP3 server when negotiating TLS.",
        default=None)

    userbase = dependsOn(LoginSystem)

    # When enabled, toss all traffic into logfiles.
    debug = False


    def activate(self):
        self.portal = None
        self.factory = None


    # IProtocolFactoryFactory
    def getFactory(self):
        if self.factory is None:
            self.portal = portal.Portal(self.userbase, [self.userbase])
            self.factory = POP3ServerFactory(self.portal)

            if self.debug:
                self.factory = policies.TrafficLoggingFactory(self.factory, 'pop3')
        return self.factory


    def setServiceParent(self, parent):
        """
        Compatibility hack necessary to prevent the Axiom service startup
        mechanism from barfing.  Even though this Item is no longer an IService
        powerup, it will still be found as one one more time and this method
        will be called on it.
        """



def pop3Listener1to2(old):
    p3l = old.upgradeVersion(POP3Listener.typeName, 1, 2)
    p3l.userbase = old.store.findOrCreate(LoginSystem)
    return p3l
registerUpgrader(pop3Listener1to2, POP3Listener.typeName, 1, 2)

declareLegacyItem(
    POP3Listener.typeName, 2, dict(portNumber=integer(default=6110),
                                   securePortNumber=integer(default=0),
                                   certificateFile=bytes(default=None),
                                   userbase=reference(doc="dependsOn(LoginSystem)")))

def pop3listener2to3(oldPOP3):
    """
    Create TCPPort and SSLPort items as appropriate.
    """
    newPOP3 = oldPOP3.upgradeVersion(
        POP3Listener.typeName, 2, 3,
        userbase=oldPOP3.userbase,
        certificateFile=oldPOP3.certificateFile)

    if oldPOP3.portNumber is not None:
        port = TCPPort(store=newPOP3.store, portNumber=oldPOP3.portNumber, factory=newPOP3)
        installOn(port, newPOP3.store)

    securePortNumber = oldPOP3.securePortNumber
    certificateFile = oldPOP3.certificateFile
    if securePortNumber is not None and certificateFile:
        oldCertPath = newPOP3.store.dbdir.preauthChild(certificateFile)
        if oldCertPath.exists():
            newCertPath = newPOP3.store.newFilePath('pop3.pem')
            oldCertPath.copyTo(newCertPath)
            port = SSLPort(store=newPOP3.store, portNumber=oldPOP3.securePortNumber, certificatePath=newCertPath, factory=newPOP3)
            installOn(port, newPOP3.store)

    newPOP3.store.powerDown(newPOP3, IService)

    return newPOP3
registerUpgrader(pop3listener2to3, POP3Listener.typeName, 2, 3)
