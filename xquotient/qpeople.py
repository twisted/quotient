import urllib
from zope.interface import implements

from nevow import tags, rend, athena

from axiom.item import Item, InstallableMixin
from axiom import attributes

from xmantissa import tdb, tdbview, ixmantissa, people
from xmantissa.webtheme import getLoader
from xmantissa.fragmentutils import PatternDictionary, dictFillSlots

from xquotient import gallery, extract, compose
from xquotient.exmess import Message

class EmailActions(Item, InstallableMixin):
    implements(ixmantissa.IPersonAction)

    typeName = 'quotient_email_actions'
    schemaVersion = 1

    installedOn = attributes.reference()
    translator = attributes.inmemory()

    def installOn(self, other):
        super(EmailActions, self).installOn(other)
        other.powerUp(self, ixmantissa.IPersonAction)

    def activate(self):
        self.translator = None

    def toLinkStan(self):
        if self.translator is None:
            self.translator = ixmantissa.IWebTranslator(self.store)

        def linkTo(typeClass):
            return self.translator.linkTo(self.store.findUnique(typeClass).storeID)

        sendMailLink = tags.a(href='%s?recipient=%s' % (linkTo(compose.Composer),
                                                        urllib.quote(self.installedOn.getEmailAddress())))
        return sendMailLink['Send an email!']

class LinkToColumnView(tdbview.ColumnViewBase):
    translator = None
    def stanFromValue(self, idx, item, value):
        if self.translator is None:
            self.translator = ixmantissa.IWebTranslator(item.store)
        return tags.a(href=self.translator.linkTo(item.storeID))[value]

class ExtractSubjectColumnView(LinkToColumnView):
    def stanFromValue(self, idx, item, value):
        return LinkToColumnView.stanFromValue(self, idx, item.message,
                                              item.message.subject)


def striptime(time):
    '''move this into extime.Time maybe.  it is not a replacement
       for asHumanly(), it does something pretty different.

       12 Dec 1990, 12:15 pm -> Dec 12 1990
       06:45pm -> 6:45pm'''

    h = time.asHumanly()
    if ',' in h:
            h = h.split(',')[0]
            parts = h.split()
            (parts[1], parts[0]) = (parts[0], parts[1])
            h = ' '.join(parts)
    else:
            h = h.lstrip('0')
    return h

class StripTimeColumnView(tdbview.ColumnViewBase):
    def stanFromValue(self, idx, item, value):
        return striptime(value)

class ExcerptColumnView(tdbview.ColumnViewBase):
    def stanFromValue(self, idx, item, value):
        return item.inContext()

class PersonFragmentColumnView(people.PersonFragmentColumnView):
    person = None

    def stanFromValue(self, idx, item, value):
        return people.PersonFragmentColumnView.stanFromValue(
                                        self, idx, self.person, value)

class MessageList(tdbview.TabularDataView):
    implements(ixmantissa.IPersonFragment)
    title = 'Messages'

    def __init__(self, person):
        self.prefs = ixmantissa.IPreferenceAggregator(person.store)

        comparison = attributes.AND(
                Message.sender == people.EmailAddress.address,
                people.EmailAddress.person == person)

        tdm = tdb.TabularDataModel(
                person.store,
                Message, (Message.sender,
                          Message.subject,
                          Message.sent),
                baseComparison=comparison,
                defaultSortColumn='sent',
                defaultSortAscending=False,
                itemsPerPage=self.prefs.getPreferenceValue('itemsPerPage'))

        self.personFragmentColumnView = PersonFragmentColumnView('sender')
        self.personFragmentColumnView.person = person

        views = (self.personFragmentColumnView,
                 LinkToColumnView('subject'),
                 StripTimeColumnView('sent'))

        tdbview.TabularDataView.__init__(self, tdm, views)
        self.docFactory = getLoader(self.fragmentName)

    def setFragmentParent(self, parent):
        self.personFragmentColumnView.page = parent
        super(MessageList, self).setFragmentParent(parent)

class ImageList(gallery.GalleryScreen):
    implements(ixmantissa.IPersonFragment)
    title = 'Images'

    def __init__(self, person):
        self.person = person
        gallery.GalleryScreen.__init__(self, person)
        self.docFactory = self.translator.getDocFactory(self.fragmentName)

    def _getComparison(self):
        return attributes.AND(
                gallery.Image.message == Message.storeID,
                Message.sender == people.EmailAddress.address,
                people.EmailAddress.person == self.person)

class ExtractViewer(tdbview.TabularDataView):

    def __init__(self, *a, **k):
        super(ExtractViewer, self).__init__(*a, **k)
        self.extractViewerPatterns = PatternDictionary(getLoader('extract-viewer'))

        for cview in self.columnViews:
            if cview.attributeID == 'excerpt':
                self.excerptColumn = cview
                self.columnViews.remove(cview)
                break

    def constructRows(self, modelData):
        excerptRowPattern = self.extractViewerPatterns['excerpt-row']
        columnRowPattern = self.patterns['row']
        cellPattern = self.patterns['cell']

        for (idx, row) in enumerate(modelData):
            cells = []
            for cview in self.columnViews:
                if cview.attributeID == 'excerpt':
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

            yield excerptRowPattern.fillSlots('col-value',
                    self.excerptColumn.stanFromValue(
                        idx, row['__item__'], row.get('excerpt')))

class ExtractList(athena.LiveFragment):
    implements(ixmantissa.IPersonFragment)
    title = 'Extracts'
    jsClass = u'Quotient.Common.CollapsiblePane'
    live = 'athena'

    def __init__(self, person):
        self.person = person
        rend.Fragment.__init__(self, person)
        self.docFactory = getLoader('extracts')

        self.prefs = ixmantissa.IPreferenceAggregator(person.store)

    def _getComparison(self, extractType):
        # this could be optimized
        return attributes.AND(
                  extractType.message == Message.storeID,
                  Message.sender == people.EmailAddress.address,
                  people.EmailAddress.person == self.person)

    def _makeExtractTDB(self, extractType, itemsCalled):
        comparison = self._getComparison(extractType)

        tdm = tdb.TabularDataModel(
                self.person.store,
                extractType, (extractType.timestamp,),
                baseComparison=comparison,
                defaultSortColumn='timestamp',
                defaultSortAscending=False,
                itemsPerPage=self.prefs.getPreferenceValue('itemsPerPage'))

        views = (ExtractSubjectColumnView('subject'),
                 StripTimeColumnView('timestamp'),
                 ExcerptColumnView('excerpt'))

        return ExtractViewer(tdm, views, itemsCalled=itemsCalled)

    def _countExtracts(self, extractType):
        return self.person.store.count(extractType, self._getComparison(extractType))

    def render_extractPanes(self, ctx, data):
        etypes = (('URLs', extract.URLExtract),
                  ('Phone Numbers', extract.PhoneNumberExtract),
                  ('Email Addresses', extract.EmailAddressExtract))

        patterns = PatternDictionary(self.docFactory)

        stan = list()
        for (title, etype) in etypes:
            tdb = self._makeExtractTDB(etype, title)
            tdb.docFactory = getLoader(tdb.fragmentName)
            tdb.setFragmentParent(self.page)
            count = self._countExtracts(etype)
            stan.append(dictFillSlots(patterns['horizontal-pane'],
                            dict(title=title + ' (%s)' % (count,),
                                 body=tdb)))

        return stan


class MessageLister(Item, InstallableMixin):
    implements(ixmantissa.IOrganizerPlugin)

    typeName = 'quotient_message_lister_plugin'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(MessageLister, self).installOn(other)
        other.powerUp(self, ixmantissa.IOrganizerPlugin)

    def personalize(self, person):
        return MessageList(person)

class ImageLister(Item, InstallableMixin):
    implements(ixmantissa.IOrganizerPlugin)

    typeName = 'quotient_image_lister_plugin'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(ImageLister, self).installOn(other)
        other.powerUp(self, ixmantissa.IOrganizerPlugin)

    def personalize(self, person):
        return ImageList(person)

class ExtractLister(Item, InstallableMixin):
    implements(ixmantissa.IOrganizerPlugin)

    typeName = 'quotient_extract_lister_plugin'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(ExtractLister, self).installOn(other)
        other.powerUp(self, ixmantissa.IOrganizerPlugin)

    def personalize(self, person):
        return ExtractList(person)

