from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import loaders, tags, athena
from axiom import item, dependency
from xmantissa import ixmantissa, webnav, people

class Console(item.Item):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_console'
    schemaVersion = 1

    powerupInterfaces = (ixmantissa.INavigableElement,)

    organizer = dependency.dependsOn(people.Organizer)

    # INavigableElement
    def getTabs(self):
        return [webnav.Tab('Console', self.storeID, 0)]



class LiveLog(athena.LiveElement):

    jsClass = u'Quotient.Console.LiveLog'

    def __init__(self, console):
        self.console = console


    # INavigableFragment
    docFactory = loaders.stan(
        tags.div(render=tags.directive('liveElement')))

    fragmentName = None   # XXX

    def head(self):
        return None

registerAdapter(LiveLog, Console, ixmantissa.INavigableFragment)
