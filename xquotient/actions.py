from nevow import tags, athena, flat

from xmantissa.fragmentutils import PatternDictionary, dictFillSlots
from xmantissa import ixmantissa, people
from xmantissa.webtheme import getLoader

from xquotient import compose

class SenderPersonFragment(athena.LiveFragment):
    jsClass = 'Quotient.Common.SenderPerson'
    iface = allowedMethods = dict(addPerson=True)

    def __init__(self, message):
        self.message = message
        athena.LiveFragment.__init__(self, message,
                                     getLoader('sender-person'))

    def render_senderPerson(self, ctx, data):
        return dictFillSlots(ctx.tag, dict(name=self.message.senderDisplay,
                                           identifier=self.message.sender))

    def addPerson(self):
        from xquotient import qpeople
        store = self.message.store
        organizer = store.findOrCreate(people.Organizer)
        person = organizer.personByName(self.message.senderDisplay)
        qpeople.EmailActions(store=store).installOn(person)

        emailAddress = store.store.findOrCreate(
                            people.EmailAddress, person=person,
                            address=self.message.sender)

        realName = store.findOrCreate(
                            people.RealName, person=person)

        if ' ' in self.message.senderDisplay:
            (realName.first, realName.last) = self.message.senderDisplay.split(' ', 1)
        else:
            realName.last = self.message.senderDisplay

        pf = people.PersonFragment(person, self.message.sender)
        pf.setFragmentParent(self)
        return unicode(flat.flatten(pf), 'utf-8')

class PersonActions(object):
    def __init__(self, store):
        self.store = store
        self.translator = ixmantissa.IWebTranslator(store)
        self.composeLink = self.translator.linkTo(
                            store.findUnique(compose.Composer).storeID)
        self.organizer = store.findFirst(people.Organizer)
        self.patterns = PatternDictionary(getLoader('action-patterns'))

    def _getAddress(self, person):
        # TODO : find default email address
        email = self.store.findFirst(people.EmailAddress,
                                     people.EmailAddress.person == person,
                                     default=None)
        if email is not None:
            return email.address

    def actionsForPerson(self, person):
        personURL = self.translator.linkTo(person.storeID)

        actions = list()

        addr = self._getAddress(person) # TODO real icon
        link = tags.a(href=self.composeLink + '?recipient=' + addr)
        img = tags.img(src='/Quotient/static/images/mark-unread.png', border=0)

        actions.append(dictFillSlots(self.patterns['action'],
                                        {'icon-link': link[img],
                                         'description': 'Send an email'}))

        return dictFillSlots(self.patterns['person'],
                             dict(name=person.getDisplayName(),
                                  location=personURL,
                                  actions=actions))

    def anonymousActions(self, address, identifier):
        return (address, tags.a(href='#',
            onclick='quotient_addPerson(%r); return false' % (identifier))['add person!'])

    def actionsFromEmailAddress(self, address, display, identifier):
        person = self.organizer.personByEmailAddress(address)
        if person is None:
            return self.anonymousActions(display, identifier)
        return self.actionsForPerson(person)

    def actionsFromMessage(self, message, identifier):
        return self.actionsFromEmailAddress(
                message.sender, message.senderDisplay, identifier)

