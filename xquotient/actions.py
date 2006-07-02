from nevow import athena

from xmantissa.fragmentutils import dictFillSlots
from xmantissa.webtheme import getLoader

class SenderPersonFragment(athena.LiveFragment):
    jsClass = 'Quotient.Common.SenderPerson'

    def __init__(self, message):
        self.message = message
        athena.LiveFragment.__init__(self, message,
                                     getLoader('sender-person'))

    def render_senderPerson(self, ctx, data):
        return dictFillSlots(ctx.tag, dict(name=self.message.senderDisplay,
                                           identifier=self.message.sender))

