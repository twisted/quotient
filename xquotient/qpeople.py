from zope.interface import implements

from nevow import rend, athena
from nevow.flat import flatten

from axiom.item import Item, InstallableMixin
from axiom import attributes

from xmantissa import ixmantissa, people
from xmantissa.webtheme import getLoader
from xmantissa.fragmentutils import PatternDictionary, dictFillSlots

from xquotient import gallery, extract, mail, exmess, equotient, mimeutil

from xmantissa.scrolltable import ScrollingFragment, UnsortableColumn, AttributeColumn, TYPE_FRAGMENT

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

class MessageList(ScrollingFragment):
    implements(ixmantissa.IPersonFragment)
    title = 'Messages'

    def __init__(self, person):
        self.prefs = ixmantissa.IPreferenceAggregator(person.store)

        comparison = attributes.AND(
                exmess.Message.sender == people.EmailAddress.address,
                people.EmailAddress.person == person)

        pfc = PersonFragmentColumn(None, 'sender')
        pfc.person = person

        ScrollingFragment.__init__(
                self, person.store,
                exmess.Message,
                comparison,
                (pfc, exmess.Message.subject, exmess.Message.sentWhen),
                defaultSortColumn=exmess.Message.sentWhen,
                defaultSortAscending=False)

        self.docFactory = getLoader(self.fragmentName)

class ImageList(gallery.GalleryScreen):
    implements(ixmantissa.IPersonFragment)
    title = 'Images'

    def __init__(self, person):
        self.person = person
        gallery.GalleryScreen.__init__(self, person)
        self.docFactory = self.translator.getDocFactory(self.fragmentName)

    def _getComparison(self):
        return attributes.AND(
                gallery.Image.message == exmess.Message.storeID,
                exmess.Message.sender == people.EmailAddress.address,
                people.EmailAddress.person == self.person)


class ExcerptColumn(AttributeColumn):
    def extractValue(self, model, item):
        return unicode(flatten(item.inContext()), 'utf-8')

    def getType(self):
        return TYPE_FRAGMENT

class SubjectColumn(AttributeColumn):
    def extractValue(self, model, item):
        return item.message.subject

class ExtractScrollingFragment(ScrollingFragment):
    def constructRows(self, items):
        rows = ScrollingFragment.constructRows(self, items)
        for (item, row) in zip(items, rows):
            row['__id__'] = unicode(self.wt.linkTo(item.message.storeID), 'ascii')
        return rows

class ExtractList(athena.LiveFragment):
    implements(ixmantissa.IPersonFragment)
    title = 'Extracts'
    live = 'athena'

    def __init__(self, person):
        self.person = person
        rend.Fragment.__init__(self, person)
        self.docFactory = getLoader('extracts')

        self.prefs = ixmantissa.IPreferenceAggregator(person.store)

    def _getComparison(self, extractType):
        # this could be optimized
        return attributes.AND(
                  extractType.message == exmess.Message.storeID,
                  exmess.Message.sender == people.EmailAddress.address,
                  people.EmailAddress.person == self.person)

    def _makeExtractScrollTable(self, extractType):
        comparison = self._getComparison(extractType)

        return ExtractScrollingFragment(
                    self.person.store,
                    extractType,
                    comparison,
                    (extractType.timestamp,
                        SubjectColumn(None, 'subject'),
                        ExcerptColumn(None, 'excerpt')),
                    defaultSortColumn=extractType.timestamp,
                    defaultSortAscending=False)

    def _countExtracts(self, extractType):
        return self.person.store.count(extractType, self._getComparison(extractType))

    def render_extractPanes(self, ctx, data):
        etypes = (('URLs', extract.URLExtract),
                  ('Phone Numbers', extract.PhoneNumberExtract),
                  ('Email Addresses', extract.EmailAddressExtract))

        patterns = PatternDictionary(self.docFactory)

        for (title, etype) in etypes:
            sf = self._makeExtractScrollTable(etype)
            sf.jsClass = 'Quotient.Extracts.ScrollingWidget'
            sf.docFactory = getLoader(sf.fragmentName)
            sf.setFragmentParent(self.page)
            count = self._countExtracts(etype)
            yield dictFillSlots(patterns['horizontal-pane'],
                                dict(title=title + ' (%s)' % (count,), body=sf))


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

