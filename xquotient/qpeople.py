# -*- test-case-name: xquotient.test.test_qpeople -*-

from zope.interface import implements

from nevow import rend, inevow, tags
from nevow.flat import flatten
from nevow.athena import expose

from axiom.item import Item, InstallableMixin
from axiom import attributes
from axiom.upgrade import registerUpgrader

from xmantissa import ixmantissa, people
from xmantissa.webtheme import getLoader
from xmantissa.fragmentutils import dictFillSlots

from xquotient import extract, mail, exmess, gallery

from xmantissa.scrolltable import UnsortableColumn, AttributeColumn, TYPE_FRAGMENT

from xquotient.exmess import MailboxSelector, CLEAN_STATUS

def makePersonExtracts(store, person):
    def queryMessageSenderPerson(typ):
        # having Message.person might speed this up, but it would
        # need some kind of notification thing that fires each time
        # an email address is associated with a Person item so we
        # can update the attribute
        sq = MailboxSelector(store)
        sq.refineByPerson(person)
        return store.query(typ, attributes.AND(
                typ.message == exmess.Message.storeID,
                sq._getComparison()))

    for etyp in extract.extractTypes.itervalues():
        for e in queryMessageSenderPerson(etyp):
            person.registerExtract(e)
            e.person = person

    for imageSet in queryMessageSenderPerson(gallery.ImageSet):
        person.registerExtract(imageSet)
        imageSet.person = person

class AddPersonFragment(people.AddPersonFragment):
    jsClass = u'Quotient.Common.AddPerson'

    lastPerson = None

    def makePerson(self, nickname):
        person = super(AddPersonFragment, self).makePerson(nickname)
        makePersonExtracts(self.original.store, person)
        self.lastPerson = person
        return person

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
        """
        This was dead code.  It has been deleted.  (This is only here to avoid
        breaking old databases.)
        """

class PersonFragmentColumn(UnsortableColumn):
    person = None

    def extractValue(self, model, item):
        # XXX BAD
        f = people.PersonFragment(self.person)
        return unicode(flatten(f), 'utf-8')

    def getType(self):
        return TYPE_FRAGMENT

class MessageList(rend.Fragment):
    implements(ixmantissa.IPersonFragment)
    title = 'Messages'

    def __init__(self, messageLister, person):
        self.messageLister = messageLister
        self.person = person
        rend.Fragment.__init__(self, docFactory=getLoader('person-messages'))

    def render_messages(self, *junk):
        iq = inevow.IQ(self.docFactory)
        msgpatt = iq.patternGenerator('message')
        newpatt = iq.patternGenerator('unread-message')
        content = []
        addresses = set(self.person.store.query(
                            people.EmailAddress,
                            people.EmailAddress.person == self.person).getColumn('address'))

        wt = ixmantissa.IWebTranslator(self.person.store)
        link = lambda href, text: tags.a(href=href, style='display: block')[text]

        displayName = self.person.getDisplayName()
        for m in self.messageLister.mostRecentMessages(self.person):
            if m.sender in addresses:
                sender = displayName
            else:
                sender = 'Me'
            if m.read:
                patt = msgpatt
            else:
                patt = newpatt
            if not m.subject or m.subject.isspace():
                subject = '<no subject>'
            else:
                subject = m.subject

            url = wt.linkTo(m.storeID)
            content.append(dictFillSlots(patt,
                                         dict(sender=link(url, sender),
                                              subject=link(url, subject),
                                              date=link(url, m.receivedWhen.asHumanly()))))

        if 0 < len(content):
            return iq.onePattern('messages').fillSlots('messages', content)
        return iq.onePattern('no-messages')

class ExcerptColumn(AttributeColumn):
    def extractValue(self, model, item):
        return unicode(flatten(item.inContext()), 'utf-8')

    def getType(self):
        return TYPE_FRAGMENT

class SubjectColumn(AttributeColumn):
    def extractValue(self, model, item):
        return item.message.subject


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

        sq = MailboxSelector(self.store)
        sq.refineByStatus(CLEAN_STATUS)
        sq.refineByPerson(person)
        sq.setLimit(n)
        sq.setNewestFirst()
        return list(sq)

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
