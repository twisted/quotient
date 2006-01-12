import operator

from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags, inevow, athena
from nevow.flat import flatten

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.tags import Catalog, Tag
from axiom.slotmachine import hyper as super

from xmantissa import ixmantissa, tdb, tdbview, webnav, people
from xmantissa.fragmentutils import PatternDictionary
from xmantissa.publicresource import getLoader

from xquotient.exmess import Message
from xquotient import mimepart, equotient, extract
from xquotient.actions import SenderPersonFragment

def quoteBody(m, maxwidth=78):
    for part in m.walkMessage(preferred='text/plain'):
        if part.type is None or part.type == 'text/plain':
            break
    else:
        return ''

    format = part.part.getParam('format')
    payload = part.part.getUnicodeBody()
    if format == 'flowed':
        para = mimepart.FlowedParagraph.fromRFC2646(payload)
    else:
        para = mimepart.FixedParagraph.fromString(payload)
    newtext = para.asRFC2646(maxwidth-2).split('\r\n')

    if m.sender is not None:
        origfrom = m.sender
    else:
        origfrom = "someone who chose not to be identified"

    if m.sent is not None:
        origdate = m.sent.asHumanly()
    else:
        origdate = "an indeterminate time in the past"

    replyhead = 'On %s, %s wrote:\n>' % (origdate, origfrom.strip())

    newtext = [ '\n>'.join(newtext) ]
    return '\n\n\n' + replyhead + (u'\n> '.join(newtext))

def reSubject(m, pfx='Re: '):
    try:
        newsubject = m.impl.getHeader(u'subject')
    except equotient.NoSuchHeader:
        newsubject = ''

    if not newsubject.lower().startswith(pfx.lower()):
        newsubject = pfx + newsubject
    return newsubject

def replyTo(m):
    try:
        recipient = m.impl.getHeader(u'reply-to')
    except equotient.NoSuchHeader:
        recipient = m.sender
    return recipient

class EmailAddressColumnView(tdbview.ColumnViewBase):
    # there is a lot of optimization here, and it's ugly.  but at 
    # 20 items per page, if the user is sorting on the sender address,
    # there would be a bunch of redundant queries

    _translator = None
    _personActions = None

    def __init__(self, *args, **kwargs):
        tdbview.ColumnViewBase.__init__(self, *args, **kwargs)

        self._cachedPeople = dict()
        self._cachedNotPeople = list()
        self._cachedNames = dict()

    def _personFromAddress(self, message, address):
        # return a people.Person instance if there is one already
        # existing that corresponds to 'address', otherwise None
        person = self._cachedPeople.get(address)
        if person is None and address not in self._cachedNotPeople:
            # at some point differentiate between people belonging to
            # different organizers, or something
            organizer = message.store.findOrCreate(people.Organizer)
            person = organizer.personByEmailAddress(address)

            if person is None:
                self._cachedNotPeople.append(address)
            else:
                self._cachedPeople[address] = person
        return person

    def personAdded(self, person):
        self._cachedPeople[person.name] = person
        if person.name in self._cachedNotPeople:
            self._cachedNotPeople.remove(person.name)

    def stanFromValue(self, idx, msg, value):
        person = self._personFromAddress(msg, msg.sender)
        if person is None:
            display = SenderPersonFragment(msg)
        else:
            display = people.PersonFragment(person)
        display.setFragmentParent(self.fragmentParent)
        return display

class CompoundColumnView(EmailAddressColumnView):
    def __init__(self, *args, **kwargs):
        EmailAddressColumnView.__init__(self, *args, **kwargs)
        self.patterns = PatternDictionary(getLoader('message-detail-patterns'))

    def stanFromValue(self, idx, item, value):
        # FIXME - this & EmailAddressColumnView.stanFromValue should use
        # template patterns
        senderStan = EmailAddressColumnView.stanFromValue(self, idx, item, value)

        subjectStan = item.subject

        if 0 < item.attachments:
            # put a paperclip icon here
            subjectStan = ('(%d) - ' % (item.attachments,), subjectStan)

        className = ('unread-message', 'read-message')[item.read]
        subjectStan = tags.div(style='overflow: hidden')[subjectStan]
        return tags.div(**{'class': className})[(senderStan, subjectStan)]

    def onclick(self, idx, item, value):
        return 'return quotient_loadMessage(event, %r)' % (idx,)

# we want to allow linking to the archive/trash views from outside of the
# inbox page, so we'll make some items with strange adaptors

class Archive(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_archive'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Archive, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('All Mail', self.storeID, 0.3)],
                authoritative=False)]

def archiveScreen(archiveItem):
    inbox = archiveItem.store.findUnique(Inbox)
    inboxScreen = ixmantissa.INavigableFragment(inbox)
    inboxScreen.inArchiveView = True
    return inboxScreen

registerAdapter(archiveScreen, Archive, ixmantissa.INavigableFragment)

class Trash(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_trash'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Trash, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Trash', self.storeID, 0.2)],
                authoritative=False)]

def trashScreen(trashItem):
    inbox = trashItem.store.findUnique(Inbox)
    inboxScreen = ixmantissa.INavigableFragment(inbox)
    inboxScreen.inTrashView = True
    return inboxScreen

registerAdapter(trashScreen, Trash, ixmantissa.INavigableFragment)

class Inbox(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_inbox'
    schemaVersion = 1

    installedOn = attributes.reference()

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Inbox', self.storeID, 0.4)],
                authoritative=True)]

    def installOn(self, other):
        super(Inbox, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

class InboxMessageView(tdbview.TabularDataView):
    def __init__(self, original, baseComparison=None):
        self.prefs = ixmantissa.IPreferenceAggregator(original.store)

        tdm = tdb.TabularDataModel(
                original.store,
                Message, [Message.sent],
                baseComparison=baseComparison,
                defaultSortColumn='sent',
                defaultSortAscending=False,
                itemsPerPage=self.prefs.getPreferenceValue('itemsPerPage'))

        self.emailAddressColumnView = CompoundColumnView('sender',
                                                typeHint='quotient-reader-column')

        views = [self.emailAddressColumnView]
        self.messageDetailPatterns = PatternDictionary(
                                            getLoader('message-detail-patterns'))
        tdbview.TabularDataView.__init__(self, tdm, views, width='340px')

def _fillSlots(tag, slotmap):
    for (k, v) in slotmap.iteritems():
        tag = tag.fillSlots(k, v)
    return tag

class InboxScreen(athena.LiveFragment):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'inbox'
    live = 'athena'
    title = ''
    jsClass = 'Quotient.Mailbox.Controller'

    inArchiveView = False
    inTrashView = False
    viewingByTag = None
    viewingByPerson = None
    currentMessage = None

    translator = None
    _inboxTDB = None

    iface = allowedMethods = dict(
                toggleShowRead=True, newMessage=True,      addTags=True,
                archiveMessage=True, deleteMessage=True,
                archiveView=True,    trashView=True,       inboxView=True,
                viewByTag=True,      viewByAllTags=True,   markCurrentMessageUnread=True,
                viewByPerson=True,   viewByAllPeople=True, nextMessage=True,
                getTags=True,        getMessageContent=True,

                markCurrentMessageRead=True,
                attachPhoneToSender=True,
                incrementItemsPerPage=True,
                archiveCurrentMessage=True,
                deleteCurrentMessage=True,
                replyToCurrentMessage=True)

    def __init__(self, original):
        athena.LiveFragment.__init__(self, original)
        self.prefs = ixmantissa.IPreferenceAggregator(original.store)
        self.organizer = original.store.findOrCreate(people.Organizer)
        self.showRead = self.prefs.getPreferenceValue('showRead')

    def _getInboxTDB(self):
        if self._inboxTDB is None:
            inboxTDB = InboxMessageView(
                    self.original, self._getBaseComparison())
            inboxTDB.docFactory = getLoader(inboxTDB.fragmentName)
            inboxTDB.setFragmentParent(self)
            inboxTDB.emailAddressColumnView.fragmentParent = self
            self._inboxTDB = inboxTDB
        return self._inboxTDB
    inboxTDB = property(_getInboxTDB)

    def locateMethod(self, ctx, method):
        try:
            return athena.LiveFragment.locateMethod(self, ctx, method)
        except AttributeError:
            return self.inboxTDB.locateMethod(ctx, method)

    def incrementItemsPerPage(self, n):
        self.inboxTDB.original.itemsPerPage += int(n)
        self.inboxTDB.original.firstPage()
        self.callRemote('replaceTDB', self.inboxTDB.replaceTable())

    # current message actions
    def markCurrentMessageUnread(self):
        self.currentMessage.read = False
        return self.nextMessage(markUnread=False)

    def markCurrentMessageRead(self):
        self.currentMessage.read = True

    def deleteCurrentMessage(self):
        self.currentMessage.deleted = True
        return self.nextMessage(augmentIndex=-1)

    def archiveCurrentMessage(self):
        self.currentMessage.archived = True
        return self.nextMessage(augmentIndex=-1)

    def replyToCurrentMessage(self):
        assert False, 'dont do this right now'
        composeDialog = self.composePatterns['compose-dialog']
        composeDialog = _fillSlots(composeDialog(),
                            dict(to=replyTo(self.currentMessage),
                                 subject=reSubject(self.currentMessage),
                                 body=quoteBody(self.currentMessage)))
        return unicode(flatten(composeDialog), 'utf-8')

    # other things
    def nextMessage(self, augmentIndex=0, markUnread=True):
        if self._haveNextMessage():
            newOffset = self.currentMessageOffset + 1
            if self.prefs.getPreferenceValue('itemsPerPage') < newOffset:
                newOffset = 0
                self.inboxTDB.original.nextPage()
            else:
                newOffset += augmentIndex

            self.callRemote(
                    'replaceTDB', self.inboxTDB.replaceTable()).addCallback(
                        lambda ign: self.callRemote('prepareForMessage', newOffset))
            return self.getMessageContent(newOffset, markUnread=markUnread)
        else:
            raise ValueError('no next message')

    def newMessage(self):
        pass

    def _changeComparisonReplaceTable(self):
        self.inboxTDB.original.baseComparison = self._getBaseComparison()
        self.inboxTDB.original.firstPage()
        return self.callRemote('replaceTDB', self.inboxTDB.replaceTable())

    def viewByTag(self, tag):
        self.viewingByTag = tag
        self._changeComparisonReplaceTable()

    def viewByPerson(self, person):
        self.viewingByPerson = person
        self._changeComparisonReplaceTable()

    def viewByAllTags(self):
        self.viewingByTag = None
        self._changeComparisonReplaceTable()

    def viewByAllPeople(self):
        self.viewingByPerson = None
        self._changeComparisonReplaceTable()

    def toggleShowRead(self):
        self.showRead = not self.showRead
        self._changeComparisonReplaceTable()
        return unicode(flatten(self._getShowReadPattern()), 'utf-8')

    def archiveMessage(self, index):
        msg = self.inboxTDB.itemFromTargetID(int(index))
        msg.archived = True
        self.callRemote('replaceTDB', self.inboxTDB.replaceTable())

    def deleteMessage(self, index):
        msg = self.inboxTDB.itemFromTargetID(int(index))
        msg.deleted = True
        self.callRemote('replaceTDB', self.inboxTDB.replaceTable())

    def getTags(self):
        return self.original.store.query(Tag).getColumn('name').distinct()

    def addTags(self, tags):
        catalog = self.original.store.findOrCreate(Catalog)
        for tag in tags:
            catalog.tag(self.currentMessage, unicode(tag))
        return unicode(flatten(self.currentMessageDetail.tagsAsStan()), 'utf-8')

    def attachPhoneToSender(self, number):
        person = self.organizer.personByEmailAddress(self.currentMessage.sender)

        people.PhoneNumber(store=person.store,
                           person=person,
                           number=number)


        print 'trying to find an extract with text = %r' % (number,)
        ex = person.store.findUnique(extract.PhoneNumberExtract,
                            attributes.AND(extract.PhoneNumberExtract.message == self.currentMessage,
                                           extract.PhoneNumberExtract.text == number))
        ex.actedUpon = True

    def _getMessageMetadata(self):
        # FIXME this and some other functions need to be commuted
        # to exmess.MessageDetail so the standalone message detail
        # it not entirely broken

        # at some point send extract type names and regular expressions
        # when the page loads

        person = self.organizer.personByEmailAddress(self.currentMessage.sender)
        isPerson = person is not None

        edata = {}
        data  = {u'sender': {u'is-person': isPerson},
                 u'message': {u'extracts': edata,
                              u'read': self.currentMessage.read}}

        for (ename, etype) in extract.extractTypes.iteritems():
            edata[unicode(ename)] = {u'pattern': etype.regex.pattern}
            for ex in self.original.store.query(etype, etype.message==self.currentMessage):
                if ex.actedUpon:
                    v = u'acted-upon'
                elif ex.ignored:
                    v = u'ignored'
                else:
                    v = u'unused'

                edata[ename][ex.text] = v

        return data

    def getMessageContent(self, idx, markUnread=True):
        # i load and display the message at offset 'idx' in the current
        # result set of the underlying tdb model

        message = self.inboxTDB.itemFromTargetID(idx)

        self.currentMessage = message
        self.currentMessageOffset = idx
        self.currentMessageDetail = ixmantissa.INavigableFragment(message)
        self.currentMessageDetail.page = self.page
        return (self._getMessageMetadata(),
                unicode(flatten(self.currentMessageDetail), 'utf-8'))

    def _getBaseComparison(self):
        # the only mutually exclusive views are "show read" and archive/trash,
        # so you could look at all messages in trash, tagged with "boring"
        # sent by the Person with name "Joe" or whatever
        comparison = Message.deleted == self.inTrashView
        if not self.inArchiveView:
            comparison = attributes.AND(comparison, Message.archived == False)

        if self.viewingByTag is not None:
            comparison = attributes.AND(
                Tag.object == Message.storeID,
                Tag.name == self.viewingByTag,
                comparison)

        if self.viewingByPerson is not None:
            comparison = attributes.AND(
                 Message.sender == people.EmailAddress.address,
                 people.EmailAddress.person == people.Person.storeID,
                 people.Person.name == self.viewingByPerson,
                 comparison)

        if not self.showRead and not (self.inArchiveView or self.inTrashView):
            comparison = attributes.AND(comparison,
                                        Message.read == False)
        return comparison

    def render_inboxTDB(self, ctx, data):
        return ctx.tag[self.inboxTDB]

    def render_addPersonFragment(self, ctx, data):
        # the person form is a fair amount of html,
        # so we'll only include it once

        self.addPersonFragment = people.AddPersonFragment(self)
        self.addPersonFragment.setFragmentParent(self)
        self.addPersonFragment.docFactory = getLoader(self.addPersonFragment.fragmentName)
        return self.addPersonFragment

    def _getShowReadPattern(self):
        pname = ['show-read-off', 'show-read-on'][self.showRead]
        return inevow.IQ(self.docFactory).onePattern(pname)

    def render_showRead(self, ctx, data):
        return ctx.tag[self._getShowReadPattern()]

    def _havePrevMessage(self):
        return not (self.currentMessageOffset - 1 < 0
                        and not self.original.hasPrevPage())

    def _haveNextMessage(self):
        return not (self.prefs.getPreferenceValue('itemsPerPage') < self.currentMessageOffset + 1
                        and not self.inboxTDB.original.hasNextPage())

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

    def head(self):
        return tags.link(rel='stylesheet', type='text/css',
                         href='/Quotient/static/reader.css')


registerAdapter(InboxScreen, Inbox, ixmantissa.INavigableFragment)

