import operator

from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import rend, inevow
from nevow.url import URL

from axiom.slotmachine import hyper as super
from axiom import item, attributes

from xmantissa import ixmantissa, webapp, webnav, webtheme
from xmantissa.publicresource import getLoader
from xmantissa.myaccount import MyAccount
from xmantissa.fragmentutils import PatternDictionary

# The big kahuna.  This, along with some kind of Person object, is the
# core of Quotient.

class Message(item.Item, item.InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_message'
    schemaVersion = 1

    # add installedOn
    received = attributes.timestamp()
    sender = attributes.text()
    recipient = attributes.text()
    subject = attributes.text()
    read = attributes.boolean(default=False)

    impl = attributes.reference()

    _prefs = attributes.inmemory()

    def installOn(self, other):
        super(Message, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def activate(self):
        self._prefs = None

    def getTabs(self):
        return ()

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

class PartDisplayer(rend.Page):
    def locateChild(self, ctx, segments):
        fname = getattr(self.original, 'filename', None)
        if len(segments) == 1 and segments[0] == fname:
            return self, ()
        return rend.NotFound

    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)
        request.setHeader('content-type', self.original.type)

        if hasattr(self.original, 'disposition'):
            request.setHeader('content-disposition',
                              self.original.disposition)

        if self.original.type.startswith('text/'):
            # FIXME weird to decode here.
            # alse replace original.part with the Container.children idiom
            # from mimepart.
            content = self.original.part.getUnicodeBody().encode('utf-8')
        else:
            content = self.original.part.getBody(decode=True)

        return content

class MessageDetail(webapp.NavMixin, rend.Page):
    '''i represent the viewable facet of some kind of message'''

    docFactory = getLoader('shell')
    contentFragment = getLoader('message-detail')
    patterns = PatternDictionary(getLoader('message-detail-patterns'))
    _partsByID = None

    def __init__(self, original):
        rend.Page.__init__(self, original)
        webapp.NavMixin.__init__(self,
            original.store.findUnique(webapp.PrivateApplication),
            self._getPageComponents())

        if not original.read:
            original.read = True

        self.messageParts = list(original.walkMessage())
        self.attachmentParts = list(original.walkAttachments())
        self.translator = ixmantissa.IWebTranslator(original.store)

    def _getPageComponents(self):
        # this is not nice.  it doesn't really make sense for webapp
        # to pass _PageComponents to IResource implementors, but there
        # is stuff in there that we need if we are going to convincingly
        # pretend to be an INavigableFragment, so we'll get the stuff
        # ourselves.  think about making this a function in webapp or a
        # PageComponents.fromAvatar class method rather than something
        # that happens in PrivateApplication.createResource

        s = self.original.store
        navigation = webnav.getTabs(s.powerupsFor(ixmantissa.INavigableElement))
        searchAggregator = ixmantissa.ISearchAggregator(s, None)
        staticShellContent = ixmantissa.IStaticShellContent(s, None)

        return webapp._PageComponents(navigation,
                                      searchAggregator,
                                      staticShellContent,
                                      s.findFirst(MyAccount))

    def locateChild(self, ctx, segments):
        if self._partsByID is None:
            byid = lambda i: dict((p.identifier, p) for p in i)
            self._partsByID = byid(self.messageParts)
            self._partsByID.update(byid(self.attachmentParts))

        try:
            partID = int(segments[0])
        except ValueError:
            return rend.NotFound

        part = self._partsByID.get(partID)
        if part is None or part.alwaysInline:
            return rend.NotFound

        return (PartDisplayer(part), segments[1:])

    def render_content(self, ctx, data):
        return ctx.tag[self.contentFragment]

    def render_headerPanel(self, ctx, data):
        return ctx.tag.fillSlots(
                'sender', self.original.sender).fillSlots(
                        'recipient', self.original.recipient).fillSlots(
                                'subject', self.original.subject)

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
            if attachment.filename is not None:
                location = location.child(attachment.filename)
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

    def _adjacentMessage(self, ctx, prev, baseComparison=None):
        # prev is a boolean
        args = inevow.IRequest(ctx).args
        (column,) = args['sort']
        (ascending,) = args['asc']
        switch = prev ^ int(ascending)
        sortColumn = getattr(Message, column)

        if switch:
            op = operator.lt
        else:
            op = operator.gt

        comparison = op(getattr(self.original, column), sortColumn)

        if switch:
            sortColumn = sortColumn.ascending
        else:
            sortColumn = sortColumn.descending

        if baseComparison is not None:
            comparison = attributes.AND(comparison, baseComparison)

        try:
            return iter(self.original.store.query(Message,
                            comparison, limit=1,
                            sort=sortColumn)).next()
        except StopIteration:
            return None

    def _makeMessageLink(self, ctx, item):
        args = inevow.IRequest(ctx).args
        return (self.translator.linkTo(item.storeID) +
                '?sort=%s&asc=%s' % (args['sort'][0], args['asc'][0]))

    def render_nextMessageLink(self, ctx, data):
        next = self._adjacentMessage(ctx, prev=False)
        if next is None:
            return self.patterns['no-next-message']()

        return self.patterns['next-message-link'].fillSlots(
                    'location', self._makeMessageLink(ctx, next))

    def render_prevMessageLink(self, ctx, data):
        prev = self._adjacentMessage(ctx, prev=True)
        if prev is None:
            return self.patterns['no-prev-message']()

        return self.patterns['prev-message-link'].fillSlots(
                'location', self._makeMessageLink(ctx, prev))

    def render_nextUnreadMessageLink(self, ctx, data):
        next = self._adjacentMessage(ctx, prev=False,
                                     baseComparison=Message.read == False)
        if next is None:
            return self.patterns['no-next-unread-message']()

        return self.patterns['next-unread-message-link'].fillSlots(
                'location', self._makeMessageLink(ctx, next))

    def render_head(self, ctx, data):
        content = []
        for theme in webtheme.getAllThemes():
            extra = theme.head()
            if extra is not None:
                content.append(extra)

        return ctx.tag[content]


registerAdapter(MessageDetail, Message, inevow.IResource)
