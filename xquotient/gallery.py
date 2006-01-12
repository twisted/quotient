import itertools

from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import rend, static, tags, flat, athena

from axiom.item import Item, InstallableMixin
from axiom import attributes

from xmantissa import ixmantissa, webnav, website, people, tdb
from xmantissa.fragmentutils import dictFillSlots, PatternDictionary

from xquotient.actions import SenderPersonFragment

from PIL import Image as PilImage
from cStringIO import StringIO

class CannotThumbnail(Exception):
    pass

def makeThumbnail(data, outpath, thumbSize=135):
    try:
        # i since noticed that PIL.Image has a thumbnail method, maybe use
        # that instead
        image = PilImage.open(StringIO(data))
        # Calculate scale
        (width, height) = image.size
        biggest = max(width, height)
        scale = float(thumbSize) / max(biggest, thumbSize)
        # Do the thumbnailing
        image.resize((int(width * scale), int(height * scale)), True).save(outpath, 'jpeg')
    except IOError:
        raise CannotThumbnail()

class Image(Item):
    typeName = 'quotient_image'
    schemaVersion = 1

    part = attributes.reference()
    thumbnailPath = attributes.path()
    mimeType = attributes.text()

    message = attributes.reference()

class ThumbnailDisplay(rend.Page):

    def locateChild(self, ctx, segments):
        try:
            (storeID,) = segments
            image = self.original.store.getItemByID(long(storeID))
        except (ValueError, KeyError):
            return rend.NotFound

        return (static.File(image.thumbnailPath.path), ())

class ThumbnailDisplayer(Item, website.PrefixURLMixin):
    typeName = 'quotient_thumbnail_displayer'
    schemaVersion = 1

    prefixURL = 'private/thumbnails'
    installedOn = attributes.reference()

    sessioned = True
    sessionless = False

    def createResource(self):
        return ThumbnailDisplay(self)

class Gallery(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_gallery'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Gallery, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Gallery', self.storeID, 0.0)],
                authoritative=False)]

class GalleryScreen(athena.LiveFragment):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'gallery'
    live = 'athena'
    title = ''
    jsClass = 'Quotient.Gallery.Controller'

    organizer = None

    iface = allowedMethods = dict(nextPage=True, prevPage=True, addPerson=True)

    itemsPerRow = 5
    rowsPerPage = 4

    def __init__(self, original):
        athena.LiveFragment.__init__(self, original)
        self.organizer = original.store.findOrCreate(people.Organizer)
        self.translator = ixmantissa.IWebTranslator(original.store)

        self.tdm = tdb.TabularDataModel(original.store, Image, (Image.message,),
                                        baseComparison=self._getComparison(),
                                        defaultSortColumn='message',
                                        itemsPerPage=self.itemsPerRow * self.rowsPerPage)
    def _getComparison(self):
        return None

    def _currentPage(self):
        patterns = PatternDictionary(self.docFactory)
        self.items = list(d['__item__'] for d in self.tdm.currentPage())
        lastMessageID = None
        imageClasses = itertools.cycle(('gallery-image', 'gallery-image-alt'))
        placedImages = 0

        for (i, image) in enumerate(self.items):
            if 0 < i and i % self.itemsPerRow == 0:
                yield patterns['row-separator']()

            message = image.message
            if message.storeID != lastMessageID:
                imageClass = imageClasses.next()
                lastMessageID = message.storeID

            imageURL = '/private/message-parts/%s/%s' % (message.storeID,
                                                            image.part.partID)
            thumbURL = '/private/thumbnails/' + str(image.storeID)

            person = self.organizer.personByEmailAddress(message.sender)
            if person is None:
                personStan = SenderPersonFragment(message)
            else:
                personStan = people.PersonFragment(person)
            personStan.page = self.page

            yield dictFillSlots(patterns['image'],
                                    {'image-url': imageURL,
                                     'thumb-url': thumbURL,
                                     'message-url': self.translator.linkTo(message.storeID),
                                     'message-subject': message.subject,
                                     'sender-stan': personStan,
                                     'class': imageClass})

    def render_images(self, ctx, data):
        return ctx.tag[self._currentPage()]

    def _paginationLinks(self):
        patterns = PatternDictionary(self.docFactory)
        if self.tdm.hasPrevPage():
            pp = patterns['prev-page']()
        else:
            pp = ''
        if self.tdm.hasNextPage():
            np = patterns['next-page']()
        else:
            np = ''
        return (pp, np)

    def render_paginationLinks(self, ctx, data):
        return ctx.tag[self._paginationLinks()]

    def _flatten(self, thing):
        return unicode(flat.flatten(thing), 'utf-8')

    def nextPage(self):
        self.tdm.nextPage()
        return map(self._flatten, (self._currentPage(), self._paginationLinks()))

    def prevPage(self):
        self.tdm.prevPage()
        return map(self._flatten, (self._currentPage(), self._paginationLinks()))

    def head(self):
        return None

registerAdapter(GalleryScreen, Gallery, ixmantissa.INavigableFragment)
