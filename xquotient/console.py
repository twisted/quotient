from zope.interface import implements
from twisted.python.components import registerAdapter

from epsilon import extime

from axiom import attributes
from axiom.dependency import dependsOn
from axiom.item import Item

from nevow import athena, flat, loaders, tags
from xmantissa import ixmantissa, webnav

from xquotient import exmess
from xquotient import urquotient   # XXX



class Console(Item):
    """
    The console tab.
    """

    implements(ixmantissa.INavigableElement)

    powerupInterfaces = (ixmantissa.INavigableElement,)

    coordinator = dependsOn(urquotient.Coordinator)

    #_observers = attributes.inmemory()

    #def activate(self):
    #    self._observers = set()


    #def addObserver(self, observer):
    #    self._observers.add(observer)


    #def removeObserver(self, observer):
    #    self._observers.remove(observer)


    #def newExtract(self, _extract):
    #    for observer in self._observers:
    #        observer.newExtract(_extract)


    # INavigableElement
    def getTabs(self):
        return [webnav.Tab('Console', self.storeID, 0)]



class LogEntry(Item):
    """
    """

    timestamp = attributes.timestamp(allowNone=False,
                                     defaultFactory=extime.Time)

    subject = attributes.reference(allowNone=False,
                                   whenDeleted=attributes.reference.CASCADE,
                                   reftype=exmess.Message)  # XXX


    def _toStan(self):
        assert isinstance(self.subject, urquotient.Correspondence)
        _person = lambda p: tags.b[
            tags.a(href=p.organizer.linkToPerson(p))[
                p.name]
        ]
        return tags.div(style='margin: 1em')[
            'Found new correspondence: ',
            _person(self.subject.source),
            ' to ', _person(self.subject.target)
        ]


    #def rend(...):
    #    if isinstance(insight.subject, extract.Extract):
    #        before, _, after = _extract.inContext()
    #    return tags.div(style='margin: 1em')[
    #        'Found ', {extract.URLExtract: 'URL',
    #                   extract.EmailAddressExtract: 'email address',
    #                   extract.PhoneNumberExtract: 'phone number',
    #                  }[type(self.extract)],
    #        ': ...', inevow.IRenderer(self.extract),
    #        #entry['before'],
    #        #tags.b()[tags.a(href=entry['href'])[entry['text']]
    #        #         if 'href' in entry
    #        #         else entry['text']],
    #        #entry['after'],
    #        '...']
# Magic
from axiom.batch import processor; processor(LogEntry)



class ConsoleView(athena.LiveElement):
    """
    A console page.

    @ivar _active_instances:  keep track of views ready to receive entries
    """

    jsClass = u'Quotient.Console.ConsoleView'

    _active_instances = set()

    def __init__(self, console):
        self.console = console


    @classmethod
    def newEntry(cls, entry):
        """
        @type entry: L{LogEntry}
        """
        print 'XXX log entry:', entry
        string = xhtmlFlatten(entry._toStan()).decode('utf-8')
        for self in cls._active_instances:
            self.callRemote('newEntry', string)


    @athena.expose
    def clientLoaded(self):
        self._retrigger()

        #from axiom import iaxiom
        #print 'XXX triggering scheduler?'
        #s = iaxiom.IScheduler(self.console.store)
        #s._transientSchedule(s.now(), s.now())

        type(self)._active_instances.add(self)
        self.page.notifyOnDisconnect().addBoth(lambda _: type(self)._active_instances.remove(self))
        #c.monitor(LogEntry, self.newEntry)
        #self.page.notifyOnDisconnect().addBoth(lambda _: c.unmonitor(LogEntry, self.newEntry))


    #@athena.expose
    def _retrigger(self):
        # HACK
        from axiom import batch

        #s = self.console.store
        #for l in self.console.store.query(batch._ReliableListener,
        #                                  batch._ReliableListener.listener == c):
        #    print 'XXX manually running', l
        #    l.processor.run()

        #p = self.console.store.findUnique(batch.processor(exmess.Message))
        p = self.console.store.findUnique(batch.processor(LogEntry))
        c = self.console.coordinator
        p.removeReliableListener(c)
        p.addReliableListener(c)
        #p.itemAdded()

        #p = self.console.store.findUnique(batch.processor(exmess.Message))
        #e = self.console.store.findUnique(extract.ExtractPowerup)
        #p.removeReliableListener(e)
        #p.addReliableListener(e)

        #print 'XXX retriggered Coordinator'


    # INavigableFragment
    docFactory = loaders.stan(tags.div(render=tags.directive('liveElement')))

    # XXX
    fragmentName = None   

    def head(self):
        return None

registerAdapter(ConsoleView, Console, ixmantissa.INavigableFragment)



# Helpers

def xhtmlFlatten(tag, XHTMLNS='http://www.w3.org/1999/xhtml'):
    """
    Flatten the given stan tag, making sure the XHTML namespace is declared.
    """
    return flat.flatten(tag(xmlns=XHTMLNS))
