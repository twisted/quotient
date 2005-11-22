from zope.interface import implements
from twisted.python.components import registerAdapter

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.slotmachine import hyper as super
from xmantissa import ixmantissa, tdb, tdbview, webnav

from xquotient.exmess import Message

class DefaultingColumnView(tdbview.ColumnViewBase):
    def __init__(self, attributeID, default, displayName=None,
                 width=None, typeHint=None):

        self.default = default
        tdbview.ColumnViewBase.__init__(self, attributeID, displayName,
                                        width, typeHint)

    def stanFromValue(self, idx, item, value):
        if value is None:
            return self.default
        return value

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
                Message, [Message.received,
                          Message.sender,
                          Message.subject,
                          Message.recipient],
                itemsPerPage=prefs.getPreferenceValue('itemsPerPage'))

        views = [tdbview.DateColumnView('received'),
                 DefaultingColumnView('sender', 'No Sender'),
                 DefaultingColumnView('subject', 'No Subject'),
                 DefaultingColumnView('recipient', 'No Recipient')]

        tdbview.TabularDataView.__init__(self, tdm, views)

registerAdapter(InboxMessageView,
                Inbox,
                ixmantissa.INavigableFragment)

