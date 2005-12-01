import operator

from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import livepage, json
from nevow.flat import flatten

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.tags import Catalog, Tag
from axiom.slotmachine import hyper as super
from axiom.upgrade import registerUpgrader

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
                'onclick', 'loadMessage(this, %r); return false' % (idx,))

class ArchiveAction(tdbview.Action):
    def __init__(self):
        tdbview.Action.__init__(self, 'archive',
                                '/static/quotient/images/archive.png',
                                'Archive this message')

    def performOn(self, message):
        message.archived = True
        return 'Archived message successfully'

    def actionable(self, message):
        return True


class _PreferredMimeType(prefs.MultipleChoicePreference):
    def __init__(self, value, collection):
        valueToDisplay = {u'text/html':'HTML', u'text/plain':'Text'}
        desc = 'Your preferred format for display of email'

        super(_PreferredMimeType, self).__init__('preferredMimeType',
                                                 value,
                                                 'Preferred Format',
                                                 collection, desc,
                                                 valueToDisplay)

class _PreferredMessageDisplay(prefs.MultipleChoicePreference):
    def __init__(self, value, collection):
        valueToDisplay = {u'split':'Split Screen',u'full':'Full Screen'}
        desc = 'Your preferred message detail value'

        super(_PreferredMessageDisplay, self).__init__('preferredMessageDisplay',
                                                       value,
                                                       'Preferred Message Display',
                                                       collection, desc,
                                                       valueToDisplay)

class QuotientPreferenceCollection(Item, InstallableMixin):
    implements(ixmantissa.IPreferenceCollection)

    schemaVersion = 2
    typeName = 'quotient_preference_collection'
    name = 'Email Preferences'

    preferredMimeType = attributes.text(default=u'text/plain')
    preferredMessageDisplay = attributes.text(default=u'split')

    installedOn = attributes.reference()
    _cachedPrefs = attributes.inmemory()

    def installOn(self, other):
        super(QuotientPreferenceCollection, self).installOn(other)
        other.powerUp(self, ixmantissa.IPreferenceCollection)

    def activate(self):
        pmt = _PreferredMimeType(self.preferredMimeType, self)
        pmd = _PreferredMessageDisplay(self.preferredMessageDisplay, self)

        self._cachedPrefs = dict(preferredMimeType=pmt,
                                 preferredMessageDisplay=pmd)

    # IPreferenceCollection
    def getPreferences(self):
        return self._cachedPrefs

    def setPreferenceValue(self, pref, value):
        # this ugliness is short lived
        assert hasattr(self, pref.key)
        setattr(pref, 'value', value)
        self.store.transact(lambda: setattr(self, pref.key, value))

def preferenceCollection1To2(old):
    return old.upgradeVersion('quotient_preference_collection', 1, 2,
                              preferredMimeType=old.preferredMimeType,
                              preferredMessageDisplay=u'split',
                              installedOn=old.installedOn)

registerUpgrader(preferenceCollection1To2,
                 'quotient_preference_collection',
                 1, 2)

class Inbox(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_inbox'
    schemaVersion = 1

    installedOn = attributes.reference()

    def getTabs(self):
        return [webnav.Tab('Inbox', self.storeID, 0.6)]

    def installOn(self, other):
        super(Inbox, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

class InboxMessageView(tdbview.TabularDataView):
    def __init__(self, original):
        self.prefs = ixmantissa.IPreferenceAggregator(original.store)

        tdm = tdb.TabularDataModel(
                original.store,
                Message, [Message.sender,
                          Message.subject,
                          Message.received],
                baseComparison=Message.archived == False,
                defaultSortColumn='received',
                defaultSortAscending=False,
                itemsPerPage=self.prefs.getPreferenceValue('itemsPerPage'))

        views = [StoreIDColumnView('storeID'),
                 EmailAddressColumnView('sender', 'No Sender', maxLength=40),
                 MessageLinkColumnView('subject', 'No Subject',
                                       maxLength=100, width='100%'),
                 tdbview.DateColumnView('received')]

        self.messageDetailPatterns = PatternDictionary(
                                            getLoader('message-detail-patterns'))

        tdbview.TabularDataView.__init__(self, tdm, views, (ArchiveAction(),))
        self.docFactory = getLoader('inbox')

    def goingLive(self, ctx, client):
        tdbview.TabularDataView.goingLive(self, ctx, client)
        tags = self.original.store.query(Tag).getColumn('name').distinct()
        client.call('setTags', json.serialize(list(tags)))

    def handle_prevMessage(self, ctx):
        assert self._havePrevMessage(), 'there isnt a prev message'

        if self.currentMessageOffset == 0:
            newOffset = self.original.itemsPerPage - 1
            self.original.prevPage()
            yield self.replaceTable()
        else:
            newOffset = self.currentMessageOffset - 1

        yield self.loadMessage(ctx, newOffset)

    def handle_nextMessage(self, ctx):
        assert self._haveNextMessage(), 'there isnt a next message'

        if self.currentMessageOffset == self.original.itemsPerPage - 1:
            newOffset = 0
            self.original.nextPage()
            yield self.replaceTable()
        else:
            newOffset = self.currentMessageOffset + 1

        yield self.loadMessage(ctx, newOffset)

    def handle_nextUnreadMessage(self, ctx):
        return self.loadMessage(ctx, self._adjacentMessage(prev=False,
                                        baseComparison=Message.read == False))

    def _havePrevMessage(self):
        return not (self.currentMessageOffset - 1 < 0
                        and not self.original.hasPrevPage())

    def _haveNextMessage(self):
        return not (self.original.itemsPerPage < self.currentMessageOffset + 1
                        and not self.original.hasNextPage())

    def _haveNextUnreadMessage(self):
        return self._haveNextMessage() and self._findNextUnread() is not None

    def _findNextUnread(self, prev=False):
        switch = prev ^ self.original.isAscending
        sortColumn = self.original.currentSortColumn
        sortableColumn = sortColumn.sortAttribute()

        if switch:
            op = operator.lt
            sortableColumn = sortableColumn.ascending
        else:
            op = operator.gt
            sortableColumn = sortableColumn.descending

        currentPivot = sortColumn.extractValue(None, self.currentMessage)
        offsetComparison = op(currentPivot, sortColumn.sortAttribute())

        comparison = attributes.AND(offsetComparison,
                                    self.original.baseComparison,
                                    Message.read == False)

        q = self.original.store.query(Message, comparison,
                                      limit=1, sort=sortableColumn)
        try:
            return iter(q).next()
        except StopIteration:
            return None

    def handle_loadMessage(self, ctx, targetID):
        #if not self._havePrevMessage():
        #   yield (livepage.js.disablePrevMessage(), livepage.eol)
        #if not self._haveNextMessage():
        #    yield (livepage.js.disableNextMessage(), livepage.eol)
        #elif not self._haveNextUnreadMessage():
        #    yield (livepage.js.disableNextUnreadMessage(), livepage.eol)
        yield self.loadMessage(ctx, int(targetID))

    def handle_addTag(self, ctx, tag):
        catalog = self.original.store.findOrCreate(Catalog)
        catalog.tag(self.currentMessage, unicode(tag))
        return livepage.set('message-tags', flatten(self.currentMessageDetail.tagsAsStan()))

    def replaceTable(self):
        # override TabularDataView.replaceTable in order to
        # resize the message view in the case that there are
        # less items on the new page.
        yield tdbview.TabularDataView.replaceTable(self)
        yield (livepage.js.fitMessageDetailToPage(), livepage.eol)

    def loadMessage(self, ctx, idx):
        # i load and display the message at offset 'idx' in the current
        # result set of the underlying tdb model

        message = self.itemFromTargetID(idx)

        self.currentMessage = message
        self.currentMessageOffset = idx
        self.currentMessageDetail = ixmantissa.INavigableFragment(message)

        html = self.currentMessageDetail.rend(ctx, None)
        view = self.prefs.getPreferenceValue('preferredMessageDisplay')

        yield (livepage.js.highlightMessageAtOffset(idx), livepage.eol)
        yield (livepage.set('%s-message-detail' % (view,), flatten(html)), livepage.eol)


registerAdapter(InboxMessageView, Inbox, ixmantissa.INavigableFragment)

