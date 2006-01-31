# -*- test-case-name: xquotient.test.test_grabber -*-

from zope.interface import implements

from twisted.mail import pop3
from twisted.internet import protocol, defer
from twisted.python import log, components, failure
from twisted.protocols import policies

from nevow import loaders, tags, athena

from epsilon import descriptor

from axiom import item, attributes

from xmantissa import ixmantissa, webnav, webapp, webtheme, liveform, tdb, tdbview

from xquotient import mail


PROTOCOL_LOGGING = True


class Status(item.Item):
    """
    Represents the latest status of a particular grabber.
    """

    message = attributes.text(doc="""
    A short string describing the current state of the grabber.
    """)

    changeObservers = attributes.inmemory(doc="""
    List of single-argument callables which will be invoked each time
    this status changes.
    """)


    def __repr__(self):
        return '<Status %r>' % (self.message,)


    def activate(self):
        self.changeObservers = []
        self.message = u"idle"


    def addChangeObserver(self, observer):
        self.changeObservers.append(observer)
        return lambda: self.changeObservers.remove(observer)


    def setStatus(self, message):
        self.message = message
        for L in self.changeObservers:
            try:
                L(message)
            except:
                log.err()



class GrabberBenefactor(item.Item):
    """
    Installs a GrabberConfiguration (and any requisite website
    powerups) on avatars.
    """

    endowed = attributes.integer(doc="""
    The number of avatars who have been endowed by this benefactor.
    """, default=0)

    def endow(self, ticket, avatar):
        for cls in webapp.PrivateApplication, GrabberConfiguration:
            avatar.findOrCreate(cls).installOn(avatar)


    def deprive(self, ticket, avatar):
        avatar.findUnique(GrabberConfiguration, GrabberConfiguration.installedOn == avatar).deleteFromStore()



class GrabberConfiguration(item.Item, item.InstallableMixin):
    """
    Manages the creation, operation, and destruction of grabbers
    (items which retrieve information from remote sources).
    """
    implements(ixmantissa.INavigableElement)

    paused = attributes.boolean(doc="""
    Flag indicating whether grabbers created by this Item will be
    allowed to run.
    """, default=False)

    installedOn = attributes.reference(doc="""
    A reference to the avatar which has been powered up by this item.
    """)

    def installOn(self, other):
        super(GrabberConfiguration, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)


    def getTabs(self):
        return [webnav.Tab('Grabbers', self.storeID, 0.3)]


    def addGrabber(self, username, password, domain, port):
        POP3Grabber(
            store=self.store,
            username=username,
            password=password,
            domain=domain,
            port=port,
            config=self,
            ssl=False)


class POP3UID(item.Item):
    grabber = attributes.reference(doc="""
    A reference to the grabber which retrieved this UID.
    """)

    value = attributes.bytes(doc="""
    A POP3 UID which has already been retrieved.
    """, indexed=True)

    failed = attributes.boolean(doc="""
    When set, indicates that an attempt was made to retrieve this UID,
    but for some reason was unsuccessful.
    """, indexed=True, default=False)



class POP3Grabber(item.Item, mail.DeliveryAgentMixin):
    """
    Item for retrieving email messages from a remote POP server.
    """

    config = attributes.reference(doc="""
    The L{GrabberConfiguration} which created this grabber.
    """)

    status = attributes.reference(doc="""
    The current state of this grabber.  This indicates whether a grab
    is currently being run, if a password is incorrect, etc.
    """)

    paused = attributes.boolean(doc="""
    Flag indicating whether this particular grabber will try to get
    scheduled to retrieve messages.
    """, default=False)

    username = attributes.text(doc="""
    Username in the remote system with which to authenticate.
    """, allowNone=False)

    password = attributes.text(doc="""
    Password in the remote system with which to authenticate.
    """, allowNone=False)

    domain = attributes.text(doc="""
    The address of the remote system to which to connect.
    """, allowNone=False)

    port = attributes.integer(doc="""
    TCP port number on the remote system to which to connect.
    """, default=110)

    ssl = attributes.boolean(doc="""
    Flag indicating whether to connect using SSL (note: this does not
    affect whether TLS will be negotiated post-connection.)
    """, default=False)

    messageCount = attributes.integer(doc="""
    The number of messages which have been retrieved by this grabber.
    """, default=0)

    running = attributes.inmemory(doc="""
    Flag indicating whether an attempt to retrieve messages is
    currently in progress.  Only one attempt is allowed outstanding at
    any given time.
    """)

    debug = attributes.boolean(doc="""
    Flag indicating whether to log traffic from this grabber or not.
    """, default=False)


    class installedOn(descriptor.attribute):
        def get(self):
            return self.config.installedOn


    def activate(self):
        self.running = False
        if self.status is None:
            self.status = Status(store=self.store, message=u'idle')


    def run(self):
        """
        Retrieve some messages from the account associated with this
        grabber.
        """
        assert not self.running, "Tried to grab concurrently with %r" % (self,)
        self.running = True

        from twisted.internet import reactor

        port = self.port
        if self.ssl:
            if port is None:
                port = 995
            connect = reactor.connectSSL
        else:
            if port is None:
                port = 110
            connect = reactor.connectTCP

        factory = POP3GrabberFactory(self)
        if self.debug:
            factory = policies.TrafficLoggingFactory(
                factory,
                'pop3client-%d-%f' % (self.storeID, time.time()))

        self.status.setStatus(u"Connecting to %s:%d..." % (self.domain, port))
        connect(self.domain, port, factory)


    def shouldRetrieve(self, uid):
        return self.store.findUnique(
            POP3UID,
            attributes.AND(POP3UID.grabber == self,
                           POP3UID.value == uid),
            default=None) is None


    def markSuccess(self, uid, msg):
        POP3UID(store=self.store, grabber=self, value=uid)


    def markFailure(self, uid, err):
        POP3UID(store=self.store, grabber=self, value=uid, failed=True)



class POP3GrabberProtocol(pop3.AdvancedPOP3Client):
    def _consumerFactory(self, msg):
        def consume(line):
            msg.lineReceived(line)
        return consume


    def serverGreeting(self, status):
        def ebGrab(err):
            self.factory.grabber.status.setStatus(u"Error: %s" % (err.getErrorMessage(),))
            self.transport.loseConnection()
        return self._grab().addErrback(ebGrab)


    def _grab(self):
        g = self.factory.grabber
        transact = g.store.transact

        d = defer.waitForDeferred(self.login(g.username.encode('ascii'), g.password.encode('ascii')))
        g.status.setStatus(u"Logging in...")
        yield d
        loginResult = d.getResult()

        d = defer.waitForDeferred(self.listUID())
        g.status.setStatus(u"Retrieving message list...")
        yield d
        uidList = d.getResult()

        # XXX This is a bad loop.
        for idx, uid in enumerate(uidList):
            if g.shouldRetrieve(uid):
                rece = g.createMIMEReceiver()
                d = defer.waitForDeferred(self.retrieve(idx, self._consumerFactory(rece)))
                g.status.setStatus(u"Downloading %d of %d" % (idx, len(uidList)))
                yield d
                try:
                    d.getResult()
                    transact(rece.eomReceived)
                except:
                    f = failure.Failure()
                    log.msg("Error retrieving POP message")
                    log.err(f)
                    transact(g.markFailure, uid, f)
                    rece.connectionLost(f)
                else:
                    transact(g.markSuccess, uid, rece.part)

        g.status.setStatus(u"Logging out...")
        d = defer.waitForDeferred(self.quit())
        yield d
        d.getResult()
        g.status.setStatus(u"idle")
        self.transport.loseConnection()
    _grab = defer.deferredGenerator(_grab)


    def connectionLost(self, reason):
        # XXX change status here
        self.factory.grabber.running = False



class POP3GrabberFactory(protocol.ClientFactory):
    protocol = POP3GrabberProtocol

    def __init__(self, grabber):
        self.grabber = grabber


    def clientConnectionFailed(self, connector, reason):
        self.grabber.status.setStatus(u"Connection failed: " + (reason.getErrorMessage(),))
        self.grabber.running = False


    def buildProtocol(self, addr):
        self.grabber.status.setStatus(u"Connection established...")
        return protocol.ClientFactory.buildProtocol(self, addr)



grabberTypes = {
    'POP3': POP3Grabber,
    }


class GrabberConfigFragment(athena.LiveFragment):
    fragmentName = 'grabber-configuration'
    live = 'athena'

    def head(self):
        return ()

    def render_addGrabberForm(self, ctx, data):
        f = liveform.LiveForm(
            self.addGrabber,
            [liveform.Parameter('username',
                                liveform.TEXT_INPUT,
                                unicode,
                                u'The username portion of the address from which to retrieve messages.'),
             liveform.Parameter('password',
                                liveform.PASSWORD_INPUT,
                                unicode,
                                u'The password for the remote account.'),
             liveform.Parameter('domain',
                                liveform.TEXT_INPUT,
                                unicode,
                                u'The domain which hosts the account.'),
#              liveform.Parameter('protocol',
#                                 liveform.Choice(grabberTypes.keys()),
#                                 lambda value: grabberTypes[value],
#                                 u'Super secret computer science stuff',
#                                 'POP3'),
             liveform.Parameter('port',
                                liveform.TEXT_INPUT,
                                int,
                                u'The port number on which the remote server runs.',
                                '110')])
        f.jsClass = u'Quotient.Grabber.AddGrabberFormWidget'
        f.setFragmentParent(self)
        return ctx.tag[f]

    def addGrabber(self, **kwargs):
        self.original.addGrabber(**kwargs)
        return self.configuredGrabbersView.replaceTable()

    def render_POP3Grabbers(self, ctx, data):
        self.configuredGrabbersView = ConfiguredGrabbersView(self.original.store)
        self.configuredGrabbersView.setFragmentParent(self)
        return self.configuredGrabbersView

components.registerAdapter(GrabberConfigFragment, GrabberConfiguration, ixmantissa.INavigableFragment)



class LiveStatusFragment(athena.LiveFragment):
    docFactory = loaders.stan(tags.span(render=tags.directive('liveFragment')))
    jsClass = u'Quotient.Grabber.StatusWidget'

    def __init__(self, status):
        self.status = status


    def _observerError(self, err):
        log.err(err)
        try:
            self.removeObserver()
        except ValueError:
            pass


    def statusChanged(self, newStatus):
        self.callRemote('setStatus', newStatus).addErrback(self._observerError)


    allowedMethods = ['startObserving']
    def startObserving(self):
        self.removeObserver = self.status.addChangeObserver(self.statusChanged)
        return self.status.message



class StatusColumnView(object):
    displayName = attributeID = 'status'
    typeName = typeHint = None

    def __init__(self, fragment):
        self.fragment = fragment


    def stanFromValue(self, idx, item, value):
        f = LiveStatusFragment(item.status)
        f.setFragmentParent(self.fragment)
        return f


    def getWidth(self):
        return ''


    def onclick(self, idx, item, value):
        return None



class RunningColumnView(object):
    displayName = attributeID = 'running'
    typeName = typeHint = None

    def stanFromValue(self, idx, item, value):
        return item.running and 'yes' or 'no'


    def getWidth(self):
        return ''


    def onclick(self, idx, item, value):
        return None



class GrabAction(tdbview.Action):
    def __init__(self, actionID='grab',
                 iconURL='/Quotient/static/images/action-grab.png',
                 description='Retrieve Messages Now',
                 disabledIconURL=None):
        super(GrabAction, self).__init__(actionID, iconURL, description, disabledIconURL)


    def performOn(self, item):
        item.run()


    def actionable(self, item):
        return not item.running



class ConfiguredGrabbersView(tdbview.TabularDataView):
    def __init__(self, store):
        tdm = tdb.TabularDataModel(
            store,
            POP3Grabber,
            [POP3Grabber.username,
             POP3Grabber.domain,
             POP3Grabber.paused,
             POP3Grabber.status])
        tdv = [
            tdbview.ColumnViewBase('username'),
            tdbview.ColumnViewBase('domain'),
            tdbview.ColumnViewBase('paused'),
            StatusColumnView(self),
            RunningColumnView()]
        actions = [
            GrabAction()]

        self.docFactory = webtheme.getLoader(self.fragmentName)
        super(ConfiguredGrabbersView, self).__init__(tdm, tdv, actions)
