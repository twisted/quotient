from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import athena, tags, inevow

from axiom.item import Item, InstallableMixin
from axiom import attributes

from xmantissa.fragmentutils import dictFillSlots
from xmantissa import webnav, ixmantissa, people

class Composer(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_composer'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Composer, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Compose', self.storeID, 0.1)],
                authoritative=False)]

class ComposeFragment(athena.LiveFragment):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'compose'
    live = 'athena'
    jsClass = 'Quotient.Compose.Controller'
    title = ''

    iface = allowedMethods = dict(getPeople=True)

    def getPeople(self):
        peeps = []
        for person in self.original.store.query(people.Person):
            peeps.append((person.name, person.getEmailAddress()))
        return peeps

    def render_compose(self, ctx, data):
        to = ','.join(inevow.IRequest(ctx).args.get('recipient', ()))
        return dictFillSlots(ctx.tag, dict(to=to, subject='', body=''))

    def head(self):
        yield tags.script(type='text/javascript',
                          src='/Quotient/static/js/tiny_mce/tiny_mce.js')
        yield tags.link(rel='stylesheet', type='text/css',
                        href='/Quotient/static/reader.css')

registerAdapter(ComposeFragment, Composer, ixmantissa.INavigableFragment)

