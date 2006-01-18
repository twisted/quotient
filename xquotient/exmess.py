from os import path

from zope.interface import implements
from twisted.python.components import registerAdapter
from twisted.python.util import sibpath

from nevow import rend, inevow, tags

from axiom.tags import Catalog
from axiom import item, attributes

from xmantissa import ixmantissa, website, people
from xmantissa.publicresource import getLoader
from xmantissa.fragmentutils import PatternDictionary, dictFillSlots

from xquotient import gallery
from xquotient.actions import SenderPersonFragment

LOCAL_ICON_PATH = sibpath(__file__, path.join('static', 'images', 'attachment-types'))

def mimeTypeToIcon(mtype,
                   webIconPath='/Quotient/static/images/attachment-types',
                   localIconPath=LOCAL_ICON_PATH,
                   extension='png',
                   defaultIconPath='/Quotient/static/images/attachment-types/generic.png'):

    lastpart = mtype.replace('/', '-') + '.' + extension
    localpath = path.join(localIconPath, lastpart)
    if path.exists(localpath):
        return webIconPath + '/' + lastpart
    return defaultIconPath

# The big kahuna.  This, along with some kind of Person object, is the
# core of Quotient.

class Message(item.Item, item.InstallableMixin):
    typeName = 'quotient_message'
    schemaVersion = 1

    installedOn = attributes.reference()

    sent = attributes.timestamp()
    received = attributes.timestamp()
    sender = attributes.text()
    senderDisplay = attributes.text()
    recipient = attributes.text()
    subject = attributes.text()

    attachments = attributes.integer(default=0)

    read = attributes.boolean(default=False)
    archived = attributes.boolean(default=False)
    deleted = attributes.boolean(default=False)
    impl = attributes.reference()

    _prefs = attributes.inmemory()

    def activate(self):
        self._prefs = None

    def walkMessage(self, prefer=None):
        if prefer is None:
            if self._prefs is None:
                self._prefs = ixmantissa.IPreferenceAggregator(self.store)
            prefer = self._prefs.getPreferenceValue('preferredMimeType')
        return self.impl.walkMessage(prefer)

    def getSubPart(self, partID):
        return self.impl.getSubPart(partID)

    def getPart(self, partID):
        if self.impl.partID == partID:
            return self.impl
        return self.getSubPart(partID)

    def walkAttachments(self):
        '''"attachments" are message parts that are not readable'''
        return self.impl.walkAttachments()

    def getAttachment(self, partID):
        return self.impl.getAttachment(partID)

class Correspondent(item.Item):
    typeName = 'quotient_correspondent'
    schemaVersion = 1

    relation = attributes.text(allowNone=False) # sender|recipient|copy|blind-copy
    message = attributes.reference(allowNone=False)
    address = attributes.text(allowNone=False)

class PartDisplayer(rend.Page):
    part = None
    filename = None

    def __init__(self, original):
        self.translator = ixmantissa.IWebTranslator(original.store)
        rend.Page.__init__(self, original)

    def locateChild(self, ctx, segments):
        if len(segments) in (1, 2):

            partWebID = segments[0]
            partStoreID = self.translator.linkFrom(partWebID)

            if partStoreID is not None:
                self.part = self.original.store.getItemByID(partStoreID)
                segments = segments[1:]
                if segments:
                    self.filename = segments[0]
                return (self, ())

        return rend.NotFound

    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)

        ctype = self.part.getContentType()
        request.setHeader('content-type', ctype)

        if ctype.startswith('text/'):
            content = self.part.getUnicodeBody().encode('utf-8')
        else:
            content = self.part.getBody(decode=True)

        return content

# somewhere there needs to be an IResource that can display
# the standalone parts of a given message, like images,
# scrubbed text/html parts and such.  this is that thing.

class MessagePartView(item.Item, website.PrefixURLMixin):
    typeName = 'quotient_message_part_view'
    schemaVersion = 1

    prefixURL = 'private/message-parts'
    installedOn = attributes.reference()

    sessioned = True
    sessionless = False

    def createResource(self):
        return PartDisplayer(self)

class MessageDetail(rend.Fragment):
    '''i represent the viewable facet of some kind of message'''
    implements(ixmantissa.INavigableFragment)
    fragmentName = 'message-detail'
    live = False

    _partsByID = None

    def __init__(self, original):
        self.patterns = PatternDictionary(getLoader('message-detail-patterns'))
        rend.Fragment.__init__(self, original, getLoader('message-detail'))

        self.messageParts = list(original.walkMessage())
        self.attachmentParts = list(original.walkAttachments())
        self.translator = ixmantissa.IWebTranslator(original.store)
        self.organizer = original.store.findUnique(people.Organizer)

    def head(self):
        return tags.script(type='text/javascript',
                           src='/Mantissa/js/people.js')

    def tagsAsStan(self):
        catalog = self.original.store.findOrCreate(Catalog)
        mtags = list()
        for tag in catalog.tagsOf(self.original):
            mtags.extend((tags.a(href='')[tag], ', '))
        if len(mtags) == 0:
            mtags = ['No Tags']
        else:
            mtags = mtags[:-1]
        return mtags

    def render_headerPanel(self, ctx, data):
        p = self.organizer.personByEmailAddress(self.original.sender)
        if p is None:
            personStan = SenderPersonFragment(self.original)
        else:
            personStan = people.PersonFragment(p, self.original.sender)
        personStan.page = self.page

        return dictFillSlots(ctx.tag,
                dict(sender=personStan,
                     recipient=self.original.recipient,
                     subject=self.original.subject,
                     tags=self.tagsAsStan()))

    def _childLink(self, webItem, item):
        return '/' + webItem.prefixURL + self.translator.linkTo(item.storeID)[len('/private'):]

    def _partLink(self, part):
        return self._childLink(MessagePartView, part)

    def _thumbnailLink(self, image):
        return self._childLink(gallery.ThumbnailDisplayer, image)

    def render_attachmentPanel(self, ctx, data):
        patterns = list()
        for attachment in self.attachmentParts:
            if not attachment.type.startswith('image/'):
                p = dictFillSlots(self.patterns['attachment'],
                                            dict(filename=attachment.filename,
                                                 icon=mimeTypeToIcon(attachment.type)))

                location = self._partLink(attachment.part)
                if attachment.filename is not None:
                    location += '/' + attachment.filename
                patterns.append(p.fillSlots('location', str(location)))

        return ctx.tag[patterns]

    def render_imagePanel(self, ctx, data):
        images = self.original.store.query(
                    gallery.Image,
                    gallery.Image.message == self.original)

        for image in images:
            location = self._partLink(image.part)
            yield dictFillSlots(self.patterns['image-attachment'],
                                {'location': self._partLink(image.part),
                                 'thumbnail-location': self._thumbnailLink(image)})

    def render_messageBody(self, ctx, data):
        paragraphs = list()
        for part in self.messageParts:
            renderable = inevow.IRenderer(part, None)
            if renderable is None:
                for child in part.children:
                    child = inevow.IRenderer(child)
                    paragraphs.append(child)
            else:
                paragraphs.append(renderable)

        return ctx.tag.fillSlots('paragraphs', paragraphs)


registerAdapter(MessageDetail, Message, ixmantissa.INavigableFragment)
