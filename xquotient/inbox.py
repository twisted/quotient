from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.slotmachine import hyper as super
from xmantissa import ixmantissa, tdb, tdbview, webnav

from xquotient.exmess import Message
from xquotient.mimeutil import EmailAddress

class DefaultingColumnView(tdbview.ColumnViewBase):
    def __init__(self, attributeID, default, displayName=None,
                 width=None, typeHint=None, maxLength=None):

        self.default = default
        self.maxLength = maxLength
        tdbview.ColumnViewBase.__init__(self, attributeID, displayName,
                                        width, typeHint)

    def stanFromValue(self, idx, item, value):
        if value is None:
            return self.default

        if self.maxLength is not None and self.maxLength < len(value):
            value = value[:self.maxLength-3] + '...'
        return value

class StoreIDColumnView(tdbview.ColumnViewBase):
    def stanFromValue(self, idx, item, value):
        return str(item.storeID)

class EmailAddressColumnView(DefaultingColumnView):
    def stanFromValue(self, idx, item, value):
        if value is not None:
            value = EmailAddress(value, mimeEncoded=False).anyDisplayName()

        return DefaultingColumnView.stanFromValue(self, idx, item, value)

class MessageLinkColumnView(DefaultingColumnView):
    translator = None

    def stanFromValue(self, idx, item, value):
        if self.translator is None:
            self.translator = ixmantissa.IWebTranslator(item.store)
        linktext = DefaultingColumnView.stanFromValue(self, idx, item, value)
        return tags.a(href=self.translator.linkTo(item.storeID))[linktext]

class Inbox(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_inbox'
    schemaVersion = 1

    installedOn = attributes.reference()

    def getTabs(self):
        return [webnav.Tab('Inbox', self.storeID, 0.0)]

    def installOn(self, other):
        super(Inbox, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

class InboxMessageView(tdbview.TabularDataView):

    def __init__(self, original):
        prefs = ixmantissa.IPreferenceAggregator(original.store)

        tdm = tdb.TabularDataModel(
                original.store,
                Message, [Message.sender,
                          Message.subject,
                          Message.received],
                itemsPerPage=prefs.getPreferenceValue('itemsPerPage'))

        views = [StoreIDColumnView('storeID'),
                 EmailAddressColumnView('sender', 'No Sender', maxLength=40),
                 MessageLinkColumnView('subject', 'No Subject', maxLength=100),
                 tdbview.DateColumnView('received')]

        tdbview.TabularDataView.__init__(self, tdm, views)

registerAdapter(InboxMessageView,
                Inbox,
                ixmantissa.INavigableFragment)

