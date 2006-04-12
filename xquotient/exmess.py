from os import path
import pytz

from zope.interface import implements
from twisted.python.components import registerAdapter
from twisted.python.util import sibpath

from nevow import rend, inevow, tags, athena

from axiom.tags import Catalog, Tag
from axiom import item, attributes, batch

from xmantissa import ixmantissa, website, people, webapp
from xmantissa.publicresource import getLoader
from xmantissa.fragmentutils import PatternDictionary, dictFillSlots

from xquotient import gallery, equotient, mimeutil
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


class _TrainingInstruction(item.Item):
    """
    Represents a single user-supplied instruction to teach the spam classifier
    something.
    """
    message = attributes.reference()
    spam = attributes.boolean()


_TrainingInstructionSource = batch.processor(_TrainingInstruction)


# The big kahuna.  This, along with some kind of Person object, is the
# core of Quotient.

class Message(item.Item):
    typeName = 'quotient_message'
    schemaVersion = 1

    source = attributes.text(doc="""
    A short string describing the means by which this Message came to exist.
    For example, u'mailto:alice@example.com' or u'pop3://bob@example.net'.
    """)

    sentWhen = attributes.timestamp()
    receivedWhen = attributes.timestamp()

    sender = attributes.text()
    senderDisplay = attributes.text()
    recipient = attributes.text()
    subject = attributes.text()

    attachments = attributes.integer(default=0)

    # flags!
    read = attributes.boolean(default=False)
    archived = attributes.boolean(default=False)
    trash = attributes.boolean(default=False)
    outgoing = attributes.boolean(default=False)
    draft = attributes.boolean(default=False)

    spam = attributes.boolean(doc="""

    Indicates whether this message has been automatically classified as spam.
    This will be None until the message is analyzed by a content-based
    filtering agent; however, application code should always be manipulating
    messages after that step, so it is generally not something you have to deal
    with (you may assume it is True or False).

    """, default=None)

    trained = attributes.boolean(doc="""

    Indicates whether the user has explicitly informed us that this is spam or
    ham.  If True, L{spam} is what the user told us (and so it should never be
    changed automatically).

    """, default=False, allowNone=False)

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


    def train(self, spam):
        if self.trained:
            if self.spam == spam:
                return
            self.spam = spam
        else:
            self.trained = True
            self.spam = spam
        _TrainingInstruction(store=self.store, message=self, spam=spam)



class Correspondent(item.Item):
    typeName = 'quotient_correspondent'
    schemaVersion = 1

    relation = attributes.text(allowNone=False) # sender|recipient|copy|blind-copy
    message = attributes.reference(allowNone=False)
    address = attributes.text(allowNone=False)

class ItemGrabber(rend.Page):
    item = None

    def __init__(self, original):
        self.wt = ixmantissa.IWebTranslator(original.store)
        rend.Page.__init__(self, original)

    def locateChild(self, ctx, segments):
        """
        I understand path segments that are web IDs of items
        in the same store as C{self.original}

        When a child is requested from me, I try to find the
        corresponding item and store it as C{self.item}
        """
        if len(segments) == 1:
            itemWebID = segments[0]
            itemStoreID = self.wt.linkFrom(itemWebID)

            if itemStoreID is not None:
                self.item = self.original.store.getItemByID(itemStoreID)
                return (self, ())
        return rend.NotFound

class PartDisplayer(ItemGrabber):
    filename = None

    def renderHTTP(self, ctx):
        """
        Serve the content of the L{mimestorage.Part} retrieved
        by L{ItemGrabber.locateChild}
        """

        request = inevow.IRequest(ctx)
        part = self.item

        ctype = part.getContentType()
        request.setHeader('content-type', ctype)

        if ctype.startswith('text/'):
            content = part.getUnicodeBody().encode('utf-8')
        else:
            content = part.getBody(decode=True)

        if 'withfilename' in request.args:
            try:
                h = part.getHeader(u'content-disposition').encode('ascii')
            except equotient.NoSuchHeader:
                h = 'filename=No-Name'
            request.setHeader('content-disposition', h)

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

class PrintableMessageResource(ItemGrabber):
    def __init__(self, original):
        ItemGrabber.__init__(self, original)
        self.docFactory = getLoader('printable-shell')

    def renderHTTP(self, ctx):
        """
        @return: a L{webapp.GenericNavigationAthenaPage} that wraps
                 the L{Message} retrieved by L{ItemGrabber.locateChild}.
        """

        privapp = self.original.store.findUnique(webapp.PrivateApplication)

        frag = ixmantissa.INavigableFragment(self.item)
        frag.printing = True

        res = webapp.GenericNavigationAthenaPage(
                    privapp, frag, privapp.getPageComponents())

        res.docFactory = getLoader('printable-shell')
        return res

class PrintableMessageView(item.Item, website.PrefixURLMixin):
    """
    I give C{PrintableMessageResource} a shot at responding
    to requests made at /private/printable-message
    """

    typeName = 'quotient_printable_message_view'
    schemaVersion = 1

    prefixURL = 'private/printable-message'
    installedOn = attributes.reference()

    sessioned = True
    sessionless = False

    def createResource(self):
        return PrintableMessageResource(self)

class MessageDetail(athena.LiveFragment):
    '''i represent the viewable facet of some kind of message'''

    implements(ixmantissa.INavigableFragment)
    fragmentName = 'message-detail'
    live = 'athena'
    jsClass = 'Quotient.Mailbox.MessageDetail'

    iface = allowedMethods = dict(getMessageSource=True,
                                  modifyTags=True)

    printing = False
    _partsByID = None

    def __init__(self, original):
        self.patterns = PatternDictionary(getLoader('message-detail-patterns'))
        athena.LiveFragment.__init__(self, original, getLoader('message-detail'))

        self.messageParts = list(original.walkMessage())
        self.attachmentParts = list(original.walkAttachments())
        self.translator = ixmantissa.IWebTranslator(original.store)
        self.organizer = original.store.findUnique(people.Organizer)

    def head(self):
        return None

    def render_tags(self, ctx, data):
        """
        @return: Sequence of tag names that have been assigned to the
                 message I represent, or "No Tags" if there aren't any
        """
        catalog = self.original.store.findOrCreate(Catalog)
        mtags = list()
        for tag in catalog.tagsOf(self.original):
            mtags.extend((tag, ', '))
        if len(mtags) == 0:
            return 'No Tags'
        else:
            return mtags[:-1]
        return mtags

    def render_messageSourceLink(self, ctx, data):
        if self.printing:
            return ''
        return self.patterns['message-source-link']()

    def render_printableLink(self, ctx, data):
        if self.printing:
            return ''
        printable = self.original.store.findUnique(PrintableMessageView)
        return self.patterns['printable-link'].fillSlots(
                    'link', '/' + printable.prefixURL + '/' + self.translator.toWebID(self.original))

    def render_headerPanel(self, ctx, data):
        p = self.organizer.personByEmailAddress(self.original.sender)
        if p is None:
            personStan = SenderPersonFragment(self.original)
        else:
            personStan = people.PersonFragment(p, self.original.sender)
        personStan.page = self.page

        prefs = ixmantissa.IPreferenceAggregator(self.original.store)
        tzinfo = pytz.timezone(prefs.getPreferenceValue('timezone'))
        sentWhen = self.original.sentWhen.asHumanly(tzinfo)

        try:
            cc = self.original.impl.getHeader(u'cc')
        except equotient.NoSuchHeader:
            cc = ''
        else:
            cc = self.patterns['cc'].fillSlots(
                                'cc', ', '.join(e.anyDisplayName()
                                                    for e in mimeutil.parseEmailAddresses(cc)))

        return dictFillSlots(ctx.tag,
                dict(sender=personStan,
                     recipient=self.original.recipient,
                     cc=cc,
                     subject=self.original.subject,
                     sent=sentWhen))

    def _childLink(self, webItem, item):
        return '/' + webItem.prefixURL + '/' + self.translator.toWebID(item)

    def _partLink(self, part):
        return self._childLink(MessagePartView, part)

    def _thumbnailLink(self, image):
        return self._childLink(gallery.ThumbnailDisplayer, image)

    def render_attachmentPanel(self, ctx, data):
        patterns = list()
        for attachment in self.attachmentParts:
            data = dict(filename=attachment.filename or 'No Name',
                        icon=mimeTypeToIcon(attachment.type))

            if 'generic' in data['icon']:
                ctype = self.patterns['content-type'].fillSlots(
                                            'type', attachment.type)
            else:
                ctype = ''

            data['type'] = ctype

            p = dictFillSlots(self.patterns['attachment'], data)
            location = self._partLink(attachment.part) + '?withfilename=1'
            patterns.append(p.fillSlots('location', str(location)))

        return ctx.tag[patterns]

    def render_imagePanel(self, ctx, data):
        images = self.original.store.query(
                    gallery.Image,
                    gallery.Image.message == self.original)

        for image in images:
            location = self._partLink(image.part) + '?withfilename=1'

            yield dictFillSlots(self.patterns['image-attachment'],
                                {'location': location,
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

    def getMessageSource(self):
        source = self.original.impl.source.getContent()
        charset = self.original.impl.getParam('charset', default='utf-8')

        try:
            return unicode(source, charset, 'replace')
        except LookupError:
            return unicode(source, 'utf-8', 'replace')

    def modifyTags(self, tagsToAdd, tagsToDelete):
        """
        Add/delete tags to/from the message I represent

        @param tagsToAdd: sequence of C{unicode} tags
        @param tagsToDelete: sequence of C{unicode} tags
        """

        c = self.original.store.findOrCreate(Catalog)

        for t in tagsToAdd:
            c.tag(self.original, t)

        for t in tagsToDelete:
            self.original.store.findUnique(Tag,
                                    attributes.AND(
                                        Tag.object == self.original,
                                        Tag.name == t)).deleteFromStore()


registerAdapter(MessageDetail, Message, ixmantissa.INavigableFragment)
