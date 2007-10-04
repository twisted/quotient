from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import loaders, tags, athena
from axiom import item, dependency, attributes
from xmantissa import ixmantissa, webnav, people
from xquotient import extract

class Console(item.Item):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_console'
    schemaVersion = 1

    powerupInterfaces = (ixmantissa.INavigableElement,)

    organizer = dependency.dependsOn(people.Organizer)

    _observers = attributes.inmemory()

    def activate(self):
        self._observers = set()


    def addObserver(self, observer):
        self._observers.add(observer)


    def removeObserver(self, observer):
        self._observers.remove(observer)


    def newExtract(self, _extract):
        for observer in self._observers:
            observer.newExtract(_extract)


    # INavigableElement
    def getTabs(self):
        return [webnav.Tab('Console', self.storeID, 0)]



class LiveLog(athena.LiveElement):

    jsClass = u'Quotient.Console.LiveLog'

    def __init__(self, console):
        self.console = console


    @athena.expose
    def clientLoaded(self):
        self.console.addObserver(self)
        self.page.notifyOnDisconnect().addBoth(
            lambda _: self.console.removeObserver(self))


    def newExtract(self, _extract):
        before, _, after = _extract.inContext()
        entry = {
            u'type': {
                extract.URLExtract: 'URL',
                extract.EmailAddressExtract: 'email address',
                extract.PhoneNumberExtract: 'phone number',
            }[type(_extract)].decode('ascii'),
            #message=_extract.message,
            #part=_extract.part,
            u'timestamp_iso': _extract.timestamp.asISO8601TimeAndDate().decode('ascii'),
            u'timestamp_humanly': _extract.timestamp.asHumanly().decode('ascii'),
            u'before': before,
            u'text': _extract.text,
            u'after': after,
        }
        if isinstance(_extract, extract.URLExtract):
            entry[u'href'] = _extract.text
        self.callRemote('newEntry', entry)


    # INavigableFragment
    docFactory = loaders.stan(
        tags.div(render=tags.directive('liveElement')))

    fragmentName = None   # XXX

    def head(self):
        return None

registerAdapter(LiveLog, Console, ixmantissa.INavigableFragment)
