from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import rend, inevow

from axiom.slotmachine import hyper as super
from axiom import item, attributes

from xquotient import webmail
from xmantissa import ixmantissa, webapp, webnav
from xmantissa.publicresource import getLoader
from xmantissa.myaccount import MyAccount

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
    impl = attributes.reference()

    def installOn(self, other):
        super(Message, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return ()

    def walkMessage(self):
        return self.impl.walkMessage()

    def getSubPart(self, partID):
        return self.impl.getSubPart(partID)

class MessageDetail(webapp.NavMixin, rend.Page):
    '''i represent the viewable facet of some kind of message'''

    docFactory = getLoader('shell')
    contentFragment = getLoader('message-detail')

    def __init__(self, original):
        rend.Page.__init__(self, original)
        webapp.NavMixin.__init__(self,
            original.store.findUnique(webapp.PrivateApplication),
            self._getPageComponents())

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

    def render_content(self, ctx, data):
        return ctx.tag[self.contentFragment]

    def render_headerPanel(self, ctx, data):
        return ctx.tag.fillSlots(
                'sender', self.original.sender).fillSlots(
                        'recipient', self.original.recipient).fillSlots(
                                'subject', self.original.subject)

    def render_messageBody(self, ctx, data):
        paragraphs = list()
        for part in self.original.walkMessage():
            for child in part.children:
                child = inevow.IRenderer(child)
                paragraphs.append(child)
        return ctx.tag.fillSlots('paragraphs', paragraphs)

registerAdapter(MessageDetail, Message, inevow.IResource)
