# -*- test-case-name: xquotient.test.test_grabber -*-

import time, datetime

from twisted.mail import pop3, pop3client
from twisted.internet import protocol, defer, ssl
from twisted.python import log, components, failure
from twisted.protocols import policies

from nevow import loaders, tags, athena
from nevow.flat import flatten

from epsilon import descriptor, extime

from axiom import item, attributes, scheduler, iaxiom

from xmantissa import ixmantissa, webapp, webtheme, liveform, tdb, tdbview
from xmantissa.stats import BandwidthMeasuringFactory

from xquotient import mail


PROTOCOL_LOGGING = True


class Status(item.Item):
    """
    Represents the latest status of a particular grabber.
    """

    when = attributes.timestamp(doc="""
    Time at which this status was set.
    """)

    message = attributes.text(doc="""
    A short string describing the current state of the grabber.
    """)

    success = attributes.boolean(doc="""
    Flag indicating whether this status indicates a successful action
    or not.
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


    def setStatus(self, message, success=True):
        self.when = extime.Time()
        self.message = message
        self.success = success
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
        for cls in (scheduler.SubScheduler, webapp.PrivateApplication,
                    mail.DeliveryAgent, GrabberConfiguration):
            avatar.findOrCreate(cls).installOn(avatar)


    def deprive(self, ticket, avatar):
        avatar.findUnique(GrabberConfiguration, GrabberConfiguration.installedOn == avatar).deleteFromStore()



class GrabberConfiguration(item.Item, item.InstallableMixin):
    """
    Manages the creation, operation, and destruction of grabbers
    (items which retrieve information from remote sources).
    """

    paused = attributes.boolean(doc="""
    Flag indicating whether grabbers created by this Item will be
    allowed to run.
    """, default=False)

    installedOn = attributes.reference(doc="""
    A reference to the avatar which has been powered up by this item.
    """)

    def addGrabber(self, username, password, domain, ssl):
        # DO IT
        if ssl:
            port = 995
        else:
            port = 110

        pg = POP3Grabber(
            store=self.store,
            username=username,
            password=password,
            domain=domain,
            port=port,
            config=self,
            ssl=ssl)
        # DO IT *NOW*
        scheduler.IScheduler(self.store).schedule(pg, extime.Time())
        # OR MAYBE A LITTLE LATER


class POP3UID(item.Item):
    grabberID = attributes.text(doc="""
    A string identifying the email-address/port parts of a
    configured grabber
    """)

    value = attributes.bytes(doc="""
    A POP3 UID which has already been retrieved.
    """, indexed=True)

    failed = attributes.boolean(doc="""
    When set, indicates that an attempt was made to retrieve this UID,
    but for some reason was unsuccessful.
    """, indexed=True, default=False)



class POP3Grabber(item.Item):
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

    protocol = attributes.inmemory(doc="""
    While self.running=True this attribute will point to the
    ControlledPOP3GrabberProtocol that is grabbing stuff
    for me""")

    scheduled = attributes.timestamp(doc="""
    When this grabber is next scheduled to run.
    """)

    debug = attributes.boolean(doc="""
    Flag indicating whether to log traffic from this grabber or not.
    """, default=False)

    created = attributes.timestamp(doc="""
    Creation time of this grabber.  Used when deciding whether a grabbed
    message is old enough to automatically archive.
    """)


    class installedOn(descriptor.attribute):
        def get(self):
            return self.config.installedOn


    def __init__(self, **kw):
        if 'created' not in kw:
            kw['created'] = extime.Time()
        return super(POP3Grabber, self).__init__(**kw)


    def activate(self):
        self.running = False
        self.protocol = None
        if self.status is None:
            self.status = Status(store=self.store, message=u'idle')


    def grab(self):
        # Don't run concurrently, ever.
        if self.running:
            return
        self.running = True

        from twisted.internet import reactor

        port = self.port
        if self.ssl:
            if port is None:
                port = 995
            connect = lambda h, p, f: reactor.connectSSL(h, p, f, ssl.ClientContextFactory())
        else:
            if port is None:
                port = 110
            connect = reactor.connectTCP

        factory = POP3GrabberFactory(self, self.ssl)
        if self.debug:
            factory = policies.TrafficLoggingFactory(
                factory,
                'pop3client-%d-%f' % (self.storeID, time.time()))

        self.status.setStatus(u"Connecting to %s:%d..." % (self.domain, port))
        connect(self.domain, port, BandwidthMeasuringFactory(factory, 'pop3-grabber'))


    def run(self):
        """
        Retrieve some messages from the account associated with this
        grabber.
        """
        try:
            if not self.paused:
                try:
                    self.grab()
                except:
                    log.err()
        finally:
            # XXX This is not a good way for things to work.  Different, later.
            delay = datetime.timedelta(seconds=300)
            self.scheduled = extime.Time() + delay
            return self.scheduled


    def _grabberID(self):
        if self.ssl and self.port == 995 or not self.ssl and self.port == 110:
            port = 'default'
        else:
            port = self.port

        return '%s@%s:%s' % (self.username, self.domain, port)
    grabberID = property(_grabberID)


    def shouldRetrieve(self, uidList):
        d = {}
        for (idx, uid) in uidList:
            d[uid] = (idx, uid)
        for uid in self.store.query(
            POP3UID,
            attributes.AND(POP3UID.grabberID == self.grabberID,
                           POP3UID.value.oneOf(d.keys()))).getColumn('value'):
            del d[uid]
        return d.values()


    def markSuccess(self, uid, msg):
        if msg.sentWhen + datetime.timedelta(days=1) < self.created:
            msg.archived = True
        log.msg(interface=iaxiom.IStatEvent, stat_messages_grabbed=1)
        POP3UID(store=self.store, grabberID=self.grabberID, value=uid)


    def markFailure(self, uid, err):
        POP3UID(store=self.store, grabberID=self.grabberID, value=uid, failed=True)



class POP3GrabberProtocol(pop3.AdvancedPOP3Client):
    _rate = 50
    _delay = 2.0


    def setCredentials(self, username, password):
        self._username = username
        self._password = password


    def _consumerFactory(self, msg):
        def consume(line):
            msg.lineReceived(line)
        return consume


    def serverGreeting(self, status):
        def ebGrab(err):
            log.err(err)
            self.setStatus(u'Internal error: ' + unicode(err.getErrorMessage()))
            self.transport.loseConnection()
        return self._grab().addErrback(ebGrab)


    def _grab(self):
        source = self.getSource()

        d = defer.waitForDeferred(self.login(self._username, self._password))
        self.setStatus(u"Logging in...")
        yield d
        try:
            loginResult = d.getResult()
        except:
            f = failure.Failure()
            if not f.check(pop3client.ServerErrorResponse):
                log.err(f)
            self.setStatus(u'Login failed: ' + unicode(f.getErrorMessage(), 'ascii'), False)
            self.transport.loseConnection()
            yield None                  # defgen error handling work-around.
            return


        N = 100

        # Up to N (index, uid) pairs which have been received but not
        # checked against shouldRetrieve
        uidWorkingSet = []

        # All the (index, uid) pairs which should be retrieved
        uidList = []

        # Consumer for listUID - adds to the working set and processes
        # a batch if appropriate.
        def consumeUIDLine(ent):
            uidWorkingSet.append(ent)
            if len(uidWorkingSet) >= N:
                processBatch()

        def processBatch():
            L = self.shouldRetrieve(uidWorkingSet)
            L.sort()
            uidList.extend(L)
            del uidWorkingSet[:]


        d = defer.waitForDeferred(self.listUID(consumeUIDLine))
        self.setStatus(u"Retrieving message list...")
        yield d
        try:
            d.getResult()
        except:
            f = failure.Failure()
            log.err(f)
            self.setStatus(unicode(f.getErrorMessage()), False)
            self.transport.loseConnection()
            return

        # Clean up any stragglers.
        if uidWorkingSet:
            processBatch()

        # XXX This is a bad loop.
        for idx, uid in uidList:
            if self.stopped:
                return
            if self.paused():
                break

            rece = self.createMIMEReceiver(source)
            if rece is None:
                return # ONO
            d = defer.waitForDeferred(self.retrieve(idx, self._consumerFactory(rece)))
            self.setStatus(u"Downloading %d of %d" % (idx, uidList[-1][0]))
            yield d
            try:
                d.getResult()
                 
            except:
                f = failure.Failure()
                rece.connectionLost(f)
                self.markFailure(uid, f)
                if f.check(pop3client.LineTooLong):
                    # reschedule, the connection has dropped
                    self.transientFailure(f)
                    break
                else:
                    log.err(f)
            else:
                try:
                    rece.eomReceived()
                except:
                    # message could not be delivered.
                    f = failure.Failure()
                    log.err(f)
                    self.markFailure(uid, f)
                else:
                    self.markSuccess(uid, rece.message)

        self.setStatus(u"Logging out...")
        d = defer.waitForDeferred(self.quit())
        yield d
        try:
            d.getResult()
        except:
            f = failure.Failure()
            log.err(f)
            self.setStatus(unicode(f.getErrorMessage()), False)
        else:
            self.setStatus(u"idle")
        self.transport.loseConnection()
    _grab = defer.deferredGenerator(_grab)


    def connectionLost(self, reason):
        # XXX change status here - maybe?
        self.stoppedRunning()

    stopped = False

    def stop(self):
        self.stopped = True





class ControlledPOP3GrabberProtocol(POP3GrabberProtocol):
    def _transact(self, *a, **kw):
        return self.grabber.store.transact(*a, **kw)


    def getSource(self):
        return u'pop3://' + self.grabber.grabberID


    def setStatus(self, msg, success=True):
        self._transact(self.grabber.status.setStatus, msg, success)


    def shouldRetrieve(self, uidList):
        if self.grabber is not None:
            return self._transact(self.grabber.shouldRetrieve, uidList)


    def createMIMEReceiver(self, source):
        if self.grabber is not None:
            def createIt():
                agent = self.grabber.store.findUnique(mail.DeliveryAgent)
                return agent.createMIMEReceiver(source)
            return self._transact(createIt)


    def markSuccess(self, uid, msg):
        if self.grabber is not None:
            return self._transact(self.grabber.markSuccess, uid, msg)


    def markFailure(self, uid, reason):
        if self.grabber is not None:
            return self._transact(self.grabber.markFailure, uid, reason)


    def paused(self):
        if self.grabber is not None:
            return self.grabber.paused


    _transient = False
    def transientFailure(self, f):
        self._transient = True


    def stoppedRunning(self):
        if self.grabber is None:
            return
        self.grabber.running = False
        if self._transient:
            scheduler.IScheduler(self.grabber.store).reschedule(
                self.grabber,
                self.grabber.scheduled,
                extime.Time())



class POP3GrabberFactory(protocol.ClientFactory):
    protocol = ControlledPOP3GrabberProtocol

    def __init__(self, grabber, ssl):
        self.grabber = grabber
        self.ssl = ssl


    def clientConnectionFailed(self, connector, reason):
        self.grabber.status.setStatus(u"Connection failed: " + reason.getErrorMessage())
        self.grabber.running = False
        self.grabber.protocol = None


    def buildProtocol(self, addr):
        self.grabber.status.setStatus(u"Connection established...")
        p = protocol.ClientFactory.buildProtocol(self, addr)
        if self.ssl:
            p.allowInsecureLogin = True
        p.setCredentials(
            self.grabber.username.encode('ascii'),
            self.grabber.password.encode('ascii'))
        p.grabber = self.grabber
        self.grabber.protocol = p
        return p



grabberTypes = {
    'POP3': POP3Grabber,
    }


class GrabberConfigFragment(athena.LiveFragment):
    fragmentName = 'grabber-configuration'
    live = 'athena'
    iface = allowedMethods = dict(getEditGrabberForm=True)
    jsClass = u'Quotient.Grabber.Controller'
    title = 'External Accounts'

    def head(self):
        return ()

    def render_addGrabberForm(self, ctx, data):
        f = liveform.LiveForm(
            self.addGrabber,
            [liveform.Parameter('domain',
                                liveform.TEXT_INPUT,
                                unicode,
                                u'The domain which hosts the account.'),
             liveform.Parameter('username',
                                liveform.TEXT_INPUT,
                                unicode,
                                u'The username portion of the address from which to retrieve messages.'),
             liveform.Parameter('password1',
                                liveform.PASSWORD_INPUT,
                                unicode,
                                u'The password for the remote account.'),
             liveform.Parameter('password2',
                                liveform.PASSWORD_INPUT,
                                unicode,
                                u'Repeat password'),
#              liveform.Parameter('protocol',
#                                 liveform.Choice(grabberTypes.keys()),
#                                 lambda value: grabberTypes[value],
#                                 u'Super secret computer science stuff',
#                                 'POP3'),
             liveform.Parameter('ssl',
                                liveform.CHECKBOX_INPUT,
                                bool,
                                u'Use SSL to fetch messages')],
             description='Add Grabber')
        f.jsClass = u'Quotient.Grabber.AddGrabberFormWidget'
        f.setFragmentParent(self)
        return ctx.tag[f]

    def getEditGrabberForm(self, targetID):
        grabber = self.configuredGrabbersView.itemFromTargetID(targetID)

        f = liveform.LiveForm(
                lambda **kwargs: self.editGrabber(grabber, **kwargs),
                (liveform.Parameter('password1',
                                    liveform.PASSWORD_INPUT,
                                    unicode,
                                    u'New Password'),
                liveform.Parameter('password2',
                                   liveform.PASSWORD_INPUT,
                                   unicode,
                                   u'Repeat Password'),
                liveform.Parameter('ssl',
                                   liveform.CHECKBOX_INPUT,
                                   bool,
                                   'Use SSL',
                                   default=grabber.ssl)),
                description='Edit Grabber')

        grabber.grab()
        f.setFragmentParent(self)
        return unicode(flatten(f), 'utf-8')

    def editGrabber(self, grabber, password1, password2, ssl):
        if password1 != password2:
            raise ValueError("Passwords don't match")

        if ssl != grabber.ssl:
            if ssl:
                port = 995
            else:
                port = 110
            grabber.port = port
            grabber.ssl = ssl

        if password1 and password2:
            grabber.password = password1

        self.callRemote('hideEditForm')
        return u'Well Done'

    def addGrabber(self, domain, username, password1, password2, ssl):
        if password1 != password2:
            raise ValueError("Passwords don't match")
        self.original.addGrabber(username, password1, domain, ssl)
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
    attributeID = 'status'
    displayName = 'Status'
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



class DeleteAction(tdbview.Action):
    def __init__(self, actionID='delete',
                 iconURL='/Mantissa/images/delete.png',
                 description='Delete',
                 disabledIconURL=None):
        super(DeleteAction, self).__init__(actionID, iconURL, description, disabledIconURL)

    def performOn(self, grabber):
        scheduler.IScheduler(grabber.store).unscheduleAll(grabber)
        if grabber.running:
            grabber.protocol.stop()
            grabber.protocol.grabber = None
        grabber.deleteFromStore()

    def actionable(self, item):
        return True

class EditAction(tdbview.Action):
    def __init__(self, actionID='edit',
                 iconURL=None,
                 description='Edit',
                 disabledIconURL=None):
        super(EditAction, self).__init__(actionID, iconURL, description, disabledIconURL)

    def performOn(self, item):
        raise NotImplementedError()

    def actionable(self, item):
        return True

    def toLinkStan(self, idx, item):
        handler = 'Nevow.Athena.Widget.get(this).widgetParent.loadEditForm(%r)' % (idx,)
        return tags.a(href='#', onclick=handler + ';return false')['Edit']

class PauseAction(tdbview.Action):
    def __init__(self, actionID='pause',
                 iconURL='/Quotient/static/images/action-pause.png',
                 description='Pause',
                 disabledIconURL=None):
        super(PauseAction, self).__init__(actionID, iconURL, description, disabledIconURL)


    def performOn(self, item):
        item.paused = True


    def actionable(self, item):
        return not item.paused



class ResumeAction(tdbview.Action):
    def __init__(self, actionID='resume',
                 iconURL='/Quotient/static/images/action-resume.png',
                 description='Resume',
                 disabledIconURL=None):
        super(ResumeAction, self).__init__(actionID, iconURL, description, disabledIconURL)


    def performOn(self, item):
        item.paused = False


    def actionable(self, item):
        return item.paused



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
            StatusColumnView(self)]
        actions = [
            PauseAction(),
            ResumeAction(),
            DeleteAction(),
            EditAction()]

        self.docFactory = webtheme.getLoader(self.fragmentName)
        super(ConfiguredGrabbersView, self).__init__(tdm, tdv, actions, itemsCalled='Grabbers')
