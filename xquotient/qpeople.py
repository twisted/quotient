from zope.interface import implements

from nevow.flat import flatten
from nevow.athena import expose
from nevow import athena, stan, inevow, tags, rend

from axiom.item import Item, InstallableMixin
from axiom import attributes, scheduler
from axiom.upgrade import registerUpgrader

from xmantissa import ixmantissa, people
from xmantissa.webtheme import getLoader
from xmantissa.tdb import TabularDataModel
from xmantissa.tdbview import TabularDataView, ColumnViewBase, DateColumnView
from xmantissa import tdb, tdbview
from xmantissa.fragmentutils import dictFillSlots, PatternDictionary

from xquotient import extract, mail, exmess, equotient, mimeutil, gallery
from xquotient.rss import Feed, FeedItem

from xmantissa.scrolltable import UnsortableColumn, AttributeColumn, TYPE_FRAGMENT

class FeedBenefactor(Item):
    implements(ixmantissa.IBenefactor)
    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(FeedLister).installOn(avatar.findOrCreate(people.Organizer))
        avatar.findOrCreate(scheduler.SubScheduler).installOn(avatar)
        self.endowed += 1

    def deprive(self, ticket, avatar):
        feedLister = avatar.findUnique(FeedLister)
        avatar.findUnique(people.Organizer).powerDown(
                                            feedLister, ixmantissa.IOrganizerPlugin)
        feedLister.deleteFromStore()

        self.endowed -= 1

def makePersonExtracts(store, person):
    def queryMessageSenderPerson(typ):
        # having Message.person might speed this up, but it would
        # need some kind of notification thing that fires each time
        # an email address is associated with a Person item so we
        # can update the attribute

        return store.query(typ, attributes.AND(
                                    typ.message == exmess.Message.storeID,
                                    exmess.Message.sender == people.EmailAddress.address,
                                    people.EmailAddress.person == person))

    for (etypename, etyp) in extract.extractTypes.iteritems():
        for e in queryMessageSenderPerson(etyp):
            person.registerExtract(e, etypename)
            e.person = person

    for imageSet in queryMessageSenderPerson(gallery.ImageSet):
        person.registerExtract(imageSet, u'Images')
        imageSet.person = person

class AddPersonFragment(people.AddPersonFragment):
    jsClass = 'Quotient.Common.AddPerson'

    lastPerson = None

    def makePerson(self, nickname):
        person = super(AddPersonFragment, self).makePerson(nickname)
        self.lastPerson = person
        return person

    def addPerson(self, *a, **k):
        result = super(AddPersonFragment, self).addPerson(*a, **k)
        makePersonExtracts(self.original.store, self.lastPerson)
        return result

    def getPersonHTML(self):
        # come up with a better way to identify people.
        # i kind of hate that we have to do this at all,
        # it's really, really ugly.  once we have some
        # kind of history thing set up, we should just
        # reload the page.
        assert self.lastPerson is not None
        return people.PersonFragment(self.lastPerson)
    expose(getPersonHTML)


class CorrespondentExtractor(Item, InstallableMixin):
    """
    Creates items based on the people involved with particular messages.
    """
    installedOn = attributes.reference()

    def installOn(self, other):
        super(CorrespondentExtractor, self).installOn(other)
        self.store.findUnique(mail.MessageSource).addReliableListener(self)


    def processItem(self, item):
        for (relation, address) in ((u'sender', item.sender),
                                    (u'recipient', item.recipient)):

            if address:
                exmess.Correspondent(store=self.store,
                                     message=item,
                                     relation=relation,
                                     address=address)

        try:
            copied = item.impl.getHeader(u'cc')
        except equotient.NoSuchHeader:
            pass
        else:
            for address in mimeutil.parseEmailAddresses(copied, mimeEncoded=False):
                exmess.Correspondent(store=self.store,
                                     message=item,
                                     relation=u'copy',
                                     address=address.email)

class PersonFragmentColumn(UnsortableColumn):
    person = None

    def extractValue(self, model, item):
        # XXX BAD
        f = people.PersonFragment(self.person)
        return unicode(flatten(f), 'utf-8')

    def getType(self):
        return TYPE_FRAGMENT


class MessageList(TabularDataView):
    implements(ixmantissa.IPersonFragment)
    title = 'Messages'

    def __init__(self, messageLister, person):
        tdm = TabularDataModel(
                person.store,
                exmess.Message,
                (exmess.Message.subject, exmess.Message.sentWhen),
                attributes.AND(
                    exmess.Message.sender == people.EmailAddress.address,
                    people.EmailAddress.person == person),
                itemsPerPage=5,
                defaultSortColumn='sentWhen',
                defaultSortAscending=False)

        wt = ixmantissa.IWebTranslator(person.store)

        subjectCol = ColumnViewBase('subject')
        dateCol = DateColumnView('sentWhen', displayName='Date')

        def onclick(idx, item, value):
            return 'document.location = %r' % (wt.linkTo(item.storeID))

        subjectCol.onclick = dateCol.onclick = onclick

        TabularDataView.__init__(self, tdm, (subjectCol, dateCol))
        self.docFactory = getLoader(self.fragmentName)

class ExcerptColumn(AttributeColumn):
    def extractValue(self, model, item):
        return unicode(flatten(item.inContext()), 'utf-8')

    def getType(self):
        return TYPE_FRAGMENT

class DescriptionColumnView(tdbview.ColumnViewBase):
    def stanFromValue(self, idx, item, value):
        return stan.xml(item.description)

class SubjectColumnView(tdbview.ColumnViewBase):
    togglePattern = None
    def stanFromValue(self, idx, item, value):
        if self.togglePattern is None:
            self.togglePattern = inevow.IQ(getLoader('feed-viewer')).patternGenerator('toggle-desc')
        return tags.b[self.togglePattern(), stan.xml(value)]

class DoubleRowTabularDataView(tdbview.TabularDataView):
    """
    alternate TDB view that places a specified column
    on it's own row (giving two rows to each item in the
    result set)
    """
    splitAttributeID = None
    altRowPattern = None

    def __init__(self, *a, **k):
        super(DoubleRowTabularDataView, self).__init__(*a, **k)

        for cview in self.columnViews:
            if cview.attributeID == self.splitAttributeID:
                self.splitColumn = cview
                self.columnViews.remove(cview)
                break

    def constructRows(self, modelData):
        columnRowPattern = self.patterns['row']
        cellPattern = self.patterns['cell']

        for (idx, row) in enumerate(modelData):
            cells = []
            for cview in self.columnViews:
                if cview.attributeID == self.splitAttributeID:
                    continue
                value = row.get(cview.attributeID)
                cellContents = cview.stanFromValue(
                                idx, row['__item__'], value)
                handler = cview.onclick(idx, row['__item__'], value)
                cellStan = dictFillSlots(cellPattern,
                                         {'value': cellContents,
                                          'onclick': handler,
                                          'class': cview.typeHint})
                cells.append(cellStan)

            yield dictFillSlots(columnRowPattern,
                                {'cells': cells,
                                 'class': 'tdb-row-%s' % (idx,)})

            yield self.altRowPattern.fillSlots('col-value',
                    self.splitColumn.stanFromValue(
                        idx, row['__item__'], row.get(self.splitAttributeID)))

class FeedViewer(DoubleRowTabularDataView):
    def __init__(self, *a, **k):
        self.altRowPattern = inevow.IQ(getLoader(
                                'feed-viewer')).patternGenerator('body-row')
        self.splitAttributeID = 'description'
        super(FeedViewer, self).__init__(*a, **k)

class FeedTitleColumnView(tdbview.ColumnViewBase):
    def stanFromValue(self, idx, item, value):
        return tags.a(href=item.feed.url)[item.feed.title]
class SubjectColumn(AttributeColumn):
    def extractValue(self, model, item):
        return item.message.subject


class FeedList(athena.LiveFragment):
    implements(ixmantissa.IPersonFragment)
    title = 'Feeds'
    live = 'athena'
    jsClass = 'Quotient.Common.Feeds'

    def __init__(self, person):
        self.person = person
        rend.Fragment.__init__(self, person)
        self.docFactory = getLoader('feeds')

    def addFeed(self, url):
        s = self.person.store
        if s.findFirst(Feed,
                       attributes.AND(
                           Feed.author == self.person,
                           Feed.url == url),
                       default=None) is None:

            f = Feed(store=s,
                     author=self.person,
                     url=url)

            def doneFetching(n):
                f # we want the feed to stay in memory
                  # so it doesn't forget about us
                if 0 < n:
                    return self.tdv.replaceTable()

            return f.notifyAfterFetch().addCallback(doneFetching)
    expose(addFeed)

    def render_feedTDBs(self, ctx, data):
        patterns = PatternDictionary(self.docFactory)

        tdm = tdb.TabularDataModel(
                self.person.store,
                FeedItem,
                (FeedItem.subject, FeedItem.timestamp),
                defaultSortAscending=False,
                defaultSortColumn='timestamp',
                itemsPerPage=5)

        views = (FeedTitleColumnView('feed'),
                 SubjectColumnView('subject'),
                 tdbview.DateColumnView('timestamp'),
                 DescriptionColumnView('description'))

        tdv = FeedViewer(tdm, views)
        tdv.setFragmentParent(self.page)
        tdv.jsClass = 'Quotient.Common.FeedList'
        tdv.docFactory = getLoader(tdv.fragmentName)
        self.tdv = tdv

        return tdv


class MessageLister(Item, InstallableMixin):
    implements(ixmantissa.IOrganizerPlugin)

    typeName = 'quotient_message_lister_plugin'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(MessageLister, self).installOn(other)
        other.powerUp(self, ixmantissa.IOrganizerPlugin)

    def personalize(self, person):
        return MessageList(self, person)

    def mostRecentMessages(self, person, n=5):
        """
        @param person: L{xmantissa.people.Person}
        @return: sequence of C{n} L{xquotient.exmess.Message} instances,
                 each one a message either to or from C{person}, ordered
                 descendingly by received date.
        """
        # probably the slowest query in the world.
        return self.store.query(exmess.Message,
                                attributes.AND(
                                    attributes.OR(
                                        exmess.Message.sender == people.EmailAddress.address,
                                        exmess.Message.recipient == people.EmailAddress.address),
                                    people.EmailAddress.person == person,
                                    exmess.Message.trash == False,
                                    exmess.Message.draft == False,
                                    exmess.Message.spam == False),
                                sort=exmess.Message.receivedWhen.desc,
                                limit=n)

# this is a waste of an item
class FeedLister(Item, InstallableMixin):
    implements(ixmantissa.IOrganizerPlugin)

    typeName = 'quotient_rss_lister_plugin'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(FeedLister, self).installOn(other)
        other.powerUp(self, ixmantissa.IOrganizerPlugin)

    def personalize(self, person):
        return FeedList(person)

class ImageLister(Item):
    typeName = 'quotient_image_lister_plugin'
    schemaVersion = 2
    z = attributes.integer()

class ExtractLister(Item):
    typeName = 'quotient_extract_lister_plugin'
    schemaVersion = 2
    z = attributes.integer()

def anyLister1to2(old):
    new = old.upgradeVersion(old.typeName, 1, 2)
    new.store.findUnique(people.Organizer).powerDown(new, ixmantissa.IOrganizerPlugin)
    new.deleteFromStore()

registerUpgrader(anyLister1to2, ImageLister.typeName, 1, 2)
registerUpgrader(anyLister1to2, ExtractLister.typeName, 1, 2)
