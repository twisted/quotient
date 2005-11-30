import operator

from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags, livepage, json
from nevow.flat import flatten

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.tags import Catalog, Tag
from axiom.slotmachine import hyper as super

from xmantissa import ixmantissa, tdb, tdbview, webnav, prefs
from xmantissa.fragmentutils import PatternDictionary
from xmantissa.publicresource import getLoader

from xquotient.exmess import Message
from xquotient.mimeutil import EmailAddress

class DefaultingColumnView(tdbview.ColumnViewBase):
    def __init__(self, attributeID, default, displayName=None,
                 width=None, typeHint='tdb-mail-column', maxLength=None):

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
    patterns = None

    def stanFromValue(self, idx, item, value):
        if self.patterns is None:
            self.patterns = PatternDictionary(getLoader('message-detail-patterns'))

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
                 MessageLinkColumnView('subject', 'No Subject',
                                       maxLength=100, width='100%'),
                 tdbview.DateColumnView('received')]

        self.docFactory = getLoader('inbox')
        self.messageDetailPatterns = PatternDictionary(
                                            getLoader('message-detail-patterns'))

        tdbview.TabularDataView.__init__(self, tdm, views)

    def _adjacentMessage(self, prev, baseComparison=None):
        # i dont know if this is worse or better than getting the
        # adjacent values from the tdb.  on the edges, we'd have
        # to call nextPage or prevPage and do fiddly things.
        # but its not so great reimplementing part of it here.

        switch = prev ^ self.original.isAscending
        sortColumn = self.original.currentSortColumn
        sortableColumn = sortColumn.sortAttribute()

        if switch:
            op = operator.lt
            sortableColumn = sortableColumn.ascending
        else:
            op = operator.gt
            sortableColumn = sortableColumn.descending

        comparison = op(sortColumn.extractValue(None, self.currentMessage),
                        sortColumn.sortAttribute())

        if baseComparison is not None:
            comparison = attributes.AND(comparison, baseComparison)

        q = self.original.store.query(Message, comparison,
                                      limit=1, sort=sortableColumn)
        try:
            return iter(q).next()
        except StopIteration:
            return None

    def goingLive(self, ctx, client):
        tdbview.TabularDataView.goingLive(self, ctx, client)
        tags = self.original.store.query(Tag).getColumn('name').distinct()
        client.call('setTags', json.serialize(list(tags)))

    def handle_prevMessage(self, ctx):
        return self.loadMessage(ctx, self._adjacentMessage(prev=True))

    def handle_nextMessage(self, ctx):
        return self.loadMessage(ctx, self._adjacentMessage(prev=False))

    def handle_nextUnreadMessage(self, ctx):
        return self.loadMessage(ctx, self._adjacentMessage(prev=False,
                                        baseComparison=Message.read == False))

    def handle_loadMessage(self, ctx, targetID):
        modelData = list(self.original.currentPage())
        return self.loadMessage(ctx, self.itemFromTargetID(int(targetID)))

    def handle_addTag(self, ctx, tag):
        catalog = self.original.store.findOrCreate(Catalog)
        catalog.tag(self.currentMessage, unicode(tag))
        return livepage.set('message-tags', flatten(self.currentMessageDetail.tagsAsStan()))

    def replaceTable(self):
        yield tdbview.TabularDataView.replaceTable(self)
        yield (livepage.js.fitMessageDetailToPage(), livepage.eol)

    def loadMessage(self, ctx, message):
        self.currentMessage = message
        self.currentMessageDetail = ixmantissa.INavigableFragment(message)
        html = self.currentMessageDetail.rend(ctx, None)
        return (livepage.set('message-detail', flatten(html)), livepage.eol)


registerAdapter(InboxMessageView, Inbox, ixmantissa.INavigableFragment)

