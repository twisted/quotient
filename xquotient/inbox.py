import operator

from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import livepage, json, tags
from nevow.flat import flatten

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.tags import Catalog, Tag
from axiom.slotmachine import hyper as super
from axiom.upgrade import registerUpgrader

from xmantissa import ixmantissa, tdb, tdbview, webnav, prefs, people
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

class EmailAddressColumnView(tdbview.ColumnViewBase):
    # there is a lot of optimization here, and it's ugly.  but at 
    # 20 items per page, if the user is sorting on the sender address,
    # there would be a bunch of redundant queries

    _translator = None

    def __init__(self, *args, **kwargs):
        tdbview.ColumnViewBase.__init__(self, *args, **kwargs)

        self._cachedPeople = dict()
        self._cachedNotPeople = list()
        self._cachedNames = dict()

    def _personFromAddress(self, message, address):
        # return a people.Person instance if there is one already
        # existing that corresponds to 'address', otherwise None
        person = self._cachedPeople.get(address.email)
        if person is None and address.email not in self._cachedNotPeople:
            # at some point differentiate between people belonging to
            # different organizers, or something
            person = message.store.findUnique(people.Person,
                        people.Person.name == address.email,
                        default=None)
            if person is None:
                self._cachedNotPeople.append(address.email)
            else:
                self._cachedPeople[address.email] = person
        return person

    def personAdded(self, person):
        self._cachedPeople[person.name] = person
        if person.name in self._cachedNotPeople:
            self._cachedNotPeople.remove(person.name)

    def _realNameFromPerson(self, person):
        if person.name not in self._cachedNames:
            rn = person.store.findUnique(people.RealName,
                                         people.RealName.person==person,
                                         default=None)
            self._cachedNames[person.name] = rn
        return self._cachedNames[person.name]

    def stanFromValue(self, idx, item, value):
        address = EmailAddress(value, mimeEncoded=False)
        person = self._personFromAddress(item, address)

        if person is not None:
            if self._translator is None:
                self._translator = ixmantissa.IWebTranslator(item.store)

            personLink = tags.a(href=self._translator.linkTo(person.storeID))
            realName = self._realNameFromPerson(person)
            if realName is None:
                personLink[person.name]
            else:
                if realName.last is None:
                    last = ''
                else:
                    last = ' ' + realName.last
                personLink[realName.first + last]
            icon = tags.img(src='/static/quotient/images/person.png',
                            style='padding: 2px;')
            personStan = (icon, personLink)
        else:
            link = tags.a(href='#', onclick='addPerson(this, %r); return false' % (idx,))
            icon = tags.img(src='/static/quotient/images/add-person.png',
                            border=0, style='padding: 2px')
            personStan = (link[icon], address.anyDisplayName())

        return personStan

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

class MarkUnreadAction(tdbview.Action):
    def __init__(self):
        tdbview.Action.__init__(self, 'mark-unread',
                                '/static/quotient/images/mark-unread.png',
                                'Mark this message as unread',
                                '/static/quotient/images/mark-unread-disabled.png')

    def performOn(self, message):
        message.read = False
        return 'Marked Message: Unread'

    def actionable(self, message):
        return message.read

class MarkReadAction(tdbview.Action):
    def __init__(self):
        tdbview.Action.__init__(self, 'mark-read',
                                '/static/quotient/images/mark-read.png',
                                'Mark this message as read',
                                '/static/quotient/images/mark-read-disabled.png')

    def performOn(self, message):
        message.read = True
        return 'Marked Message: Read'

    def actionable(self, message):
        return not message.read

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

        self.emailAddressColumnView = EmailAddressColumnView('sender', 'No Sender')

        views = [StoreIDColumnView('storeID'),
                 self.emailAddressColumnView,
                 MessageLinkColumnView('subject', 'No Subject',
                                       maxLength=100, width='100%'),
                 tdbview.DateColumnView('received')]

        self.messageDetailPatterns = PatternDictionary(
                                            getLoader('message-detail-patterns'))

        tdbview.TabularDataView.__init__(self, tdm, views, (ArchiveAction(),
                                                            MarkReadAction(),
                                                            MarkUnreadAction()))
        self.docFactory = getLoader('inbox')

    def goingLive(self, ctx, client):
        tdbview.TabularDataView.goingLive(self, ctx, client)
        tags = self.original.store.query(Tag).getColumn('name').distinct()
        client.call('setTags', json.serialize(list(tags)))

    def handle_addPerson(self, ctx, targetID):
        message = self.itemFromTargetID(int(targetID))
        address = EmailAddress(message.sender)
        organizer = self.original.store.findOrCreate(people.Organizer)
        person = organizer.personByName(address.email)
        self.emailAddressColumnView.personAdded(person)

        # mimeutil.EmailAddress hadssome integration with the quotient
        # addressbook, that might be something we want to revamp for this,
        # thought this doesn't seem bad for now

        realName = self.original.store.findOrCreate(people.RealName, person=person)

        if ' ' in address.display:
            (realName.first, realName.last) = address.display.split(' ', 1)
        elif 0 < len(address.display):
            realName.first = address.display
        else:
            realName.first = address.email

        return self.replaceTable()

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
        assert self._haveNextUnreadMessage(), 'there arent any more unread messages'
        next = self._findNextUnread()

        newOffset = None
        while newOffset is None:
            curpage = self.original.currentPage()
            for (i, row) in enumerate(curpage):
                if row['__item__'].storeID == next.storeID:
                    newOffset = i
                    break
            else:
                assert self.original.hasNextPage(), 'something went horribly wrong'
                self.original.nextPage()

        yield self.replaceTable()
        yield self.loadMessage(ctx, newOffset)

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

