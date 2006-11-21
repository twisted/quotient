from twisted.trial.unittest import TestCase

from epsilon.extime import Time

from axiom.store import Store

from xmantissa.people import Organizer, Person, EmailAddress
from xquotient.qpeople import MessageLister
from xquotient.exmess import Message

class MessageListerTestCase(TestCase):
    def testMostRecentMessages(self):
        s = Store()

        o = Organizer(store=s)
        o.installOn(s)

        def makePerson(name, address):
            return EmailAddress(store=s,
                                address=address,
                                person=Person(store=s,
                                              organizer=o,
                                              name=name)).person

        p11 = makePerson(u'11 Message Person', u'11@person')
        p2  = makePerson(u'2 Message Person', u'2@person')

        def makeMessages(n, email):
            return list(reversed(list(
                        Message(store=s,
                                sender=email,
                                spam=False,
                                receivedWhen=Time()) for i in xrange(n))))

        p11messages = makeMessages(11, u'11@person')
        p2messages  = makeMessages(2, u'2@person')

        lister = MessageLister(store=s)

        getMessages = lambda person, count: list(lister.mostRecentMessages(person, count))

        self.assertEquals(getMessages(p2, 3), p2messages)
        self.assertEquals(getMessages(p2, 2), p2messages)
        self.assertEquals(getMessages(p2, 1), p2messages[:-1])

        self.assertEquals(getMessages(p11, 12), p11messages)
        self.assertEquals(getMessages(p11, 11), p11messages)
        self.assertEquals(getMessages(p11, 10), p11messages[:-1])

        p11messages[0].spam = True

        self.assertEquals(getMessages(p11, 11), p11messages[1:])

        p11messages[1].draft = True

        self.assertEquals(getMessages(p11, 11), p11messages[2:])

        p11messages[2].trash = True

        self.assertEquals(getMessages(p11, 11), p11messages[3:])
