from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags, livepage

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.slotmachine import hyper as super

from xmantissa import ixmantissa, tdb, tdbview, webnav, prefs
from xmantissa.fragmentutils import PatternDictionary
from xmantissa.publicresource import getLoader

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
    patterns = PatternDictionary(getLoader('message-detail-patterns'))

    def stanFromValue(self, idx, item, value):
        subject = DefaultingColumnView.stanFromValue(self, idx, item, value)
        pname = ('unread-message-link', 'read-message-link')[item.read]
        return self.patterns[pname].fillSlots(
                'subject', subject).fillSlots(
                'onclick', 'loadMessage(%r); return false' % (idx,))

class _PreferredMimeType(prefs.MultipleChoicePreference):
    def __init__(self, value, collection):
        valueToDisplay = {u'text/html':'HTML', u'text/plain':'Text'}
        desc = 'Your preferred format for display of email'

        super(_PreferredMimeType, self).__init__('preferredMimeType',
                                                 value,
                                                 'Preferred Format',
                                                 collection, desc,
                                                 valueToDisplay)

class QuotientPreferenceCollection(Item, InstallableMixin):
    implements(ixmantissa.IPreferenceCollection)

    schemaVersion = 1
    typeName = 'quotient_preference_collection'
    name = 'Email Preferences'

    preferredMimeType = attributes.text(default=u'text/plain')
    installedOn = attributes.reference()
    _cachedPrefs = attributes.inmemory()

    def installOn(self, other):
        super(QuotientPreferenceCollection, self).installOn(other)
        other.powerUp(self, ixmantissa.IPreferenceCollection)

    def activate(self):
        pmt = _PreferredMimeType(self.preferredMimeType, self)
        self._cachedPrefs = dict(preferredMimeType=pmt)

    # IPreferenceCollection
    def getPreferences(self):
        return self._cachedPrefs

    def setPreferenceValue(self, pref, value):
        # this ugliness is short lived
        assert hasattr(self, pref.key)
        setattr(pref, 'value', value)
        self.store.transact(lambda: setattr(self, pref.key, value))

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
    docFactory = getLoader('inbox')

    def __init__(self, original):
        prefs = ixmantissa.IPreferenceAggregator(original.store)

        tdm = tdb.TabularDataModel(
                original.store,
                Message, [Message.sender,
                          Message.subject,
                          Message.received],
                defaultSortColumn='received',
                defaultSortAscending=False,
                itemsPerPage=prefs.getPreferenceValue('itemsPerPage'))

        views = [StoreIDColumnView('storeID'),
                 EmailAddressColumnView('sender', 'No Sender', maxLength=40),
                 MessageLinkColumnView('subject', 'No Subject', maxLength=100),
                 tdbview.DateColumnView('received')]

        tdbview.TabularDataView.__init__(self, tdm, views)

    def handle_loadMessage(self, ctx, targetID):
        modelData = list(self.original.currentPage())
        target = modelData[int(targetID)]['__item__']
        # we are sending too much stuff here - once it becomes apparent
        # that this is a viable way to do things, just fill in slots in
        # the inbox page with the data from the Message
        html = ixmantissa.INavigableFragment(target).rend(ctx, None)
        from nevow.flat import flatten
        return (livepage.set('message-detail', flatten(html)), livepage.eol)

registerAdapter(InboxMessageView, Inbox, ixmantissa.INavigableFragment)

