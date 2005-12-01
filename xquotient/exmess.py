from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import rend, inevow, tags
from nevow.url import URL

from axiom.tags import Catalog
from axiom import item, attributes

from xmantissa import ixmantissa, website
from xmantissa.publicresource import getLoader
from xmantissa.fragmentutils import PatternDictionary

# The big kahuna.  This, along with some kind of Person object, is the
# core of Quotient.

class Message(item.Item, item.InstallableMixin):
    typeName = 'quotient_message'
    schemaVersion = 1

    installedOn = attributes.reference()

    received = attributes.timestamp()
    sender = attributes.text()
    recipient = attributes.text()
    subject = attributes.text()
    read = attributes.boolean(default=False)
    archived = attributes.boolean(default=False)
    impl = attributes.reference()

    _prefs = attributes.inmemory()

    def activate(self):
        self._prefs = None

    def walkMessage(self):
        if self._prefs is None:
            self._prefs = ixmantissa.IPreferenceAggregator(self.store)
        preferred = self._prefs.getPreferenceValue('preferredMimeType')
        return self.impl.walkMessage(prefer=preferred)

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

# on a scale of 1 to 10, how bad is this
class PartDisplayer(rend.Page):
    message = None
    part = None

    def locateChild(self, ctx, segments):
        if len(segments) in (2, 3):
            (messageID, partID) = map(int, segments[:2])
            self.message = self.original.store.getItemByID(int(messageID))
            self.part = self.message.getPart(int(partID))
            segments = segments[2:]
            if len(segments) == 1:
                self.filename = segments[0]
            return self, ()
        return rend.NotFound

    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)
        # we can do this because no multipart part would make
        # sense to display stand-alone.  this is weird though,
        # we should ideally be able to do IDisplayable(part)
        # or whatever to get a mimepart.Container subclass

        if self.part.getContentType() == 'text/html':
            (part,) = list(self.part.walkMessage(None))
        else:
            part = self.message.getAttachment(self.part.partID)

        request.setHeader('content-type', part.type)

        if hasattr(part, 'disposition'):
            request.setHeader('content-disposition',
                              part.disposition)

        if part.type.startswith('text/'):
            # FIXME weird to decode here.
            # alse replace original.part with the Container.children idiom
            # from mimepart.
            content = part.part.getUnicodeBody().encode('utf-8')
        else:
            content = part.part.getBody(decode=True)

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

    _partsByID = None

    def __init__(self, original):
        self.patterns = PatternDictionary(getLoader('message-detail-patterns'))
        rend.Fragment.__init__(self, original, getLoader('message-detail'))

        if not original.read:
            original.read = True

        self.messageParts = list(original.walkMessage())
        self.attachmentParts = list(original.walkAttachments())
        self.translator = ixmantissa.IWebTranslator(original.store)

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
        return ctx.tag.fillSlots(
                'sender', self.original.sender).fillSlots(
                        'recipient', self.original.recipient).fillSlots(
                                'subject', self.original.subject).fillSlots(
                                        'tags', self.tagsAsStan())

    def render_attachmentPanel(self, ctx, data):
        requestURL = URL.fromContext(ctx)

        patterns = list()
        for attachment in self.attachmentParts:
            if attachment.type.startswith('image/'):
                pname = 'image-attachment'
            else:
                pname = 'attachment'

            p = self.patterns[pname].fillSlots('filename', attachment.filename)
            location = requestURL.child(attachment.identifier)
            location = '/private/message-parts/%d/%d' % (self.original.storeID,
                                                         attachment.identifier)
            if attachment.filename is not None:
                location += '/' + attachment.filename
            patterns.append(p.fillSlots('location', str(location)))

        return ctx.tag[patterns]

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
