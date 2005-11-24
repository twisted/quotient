from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import rend

from axiom.slotmachine import hyper as super;
from axiom import item, attributes

from xmantissa import ixmantissa

# The big kahuna.  This, along with some kind of Person object, is the
# core of Quotient.

class Message(item.Item, item.InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_message'
    schemaVersion = 1

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

class MessageDetail(rend.Fragment):
    '''i represent the viewable facet of some kind of message'''
    implements(ixmantissa.INavigableFragment)

    live = True
    fragmentName = 'message-detail'
    title = ''

    def head(self):
        return None

    def render_headerPanel(self, ctx, data):
        return ctx.tag.fillSlots(
                'sender', self.original.sender).fillSlots(
                        'recipient', self.original.recipient).fillSlots(
                                'subject', self.original.subject)

    def render_messageBody(self, ctx, data):
        (message,) = list(self.original.walkMessage())
        return ctx.tag[message]

registerAdapter(MessageDetail, Message, ixmantissa.INavigableFragment)
