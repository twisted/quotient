"""
Some basic Ur-Quotient items.
"""

from itertools import chain

from zope.interface import implements

from axiom import attributes
from axiom.batch import processor
from axiom.errors import ItemNotFound
from axiom.item import Item
from axiom.iaxiom import IReliableListener

from xmantissa.people import EmailAddress, Organizer, Person

from xquotient import exmess


def _dict(items):
    """
    Like dict(items), but list all values.
    """
    from collections import defaultdict
    d = defaultdict(list)
    for k, v in items:
        d[k].append(v)
    return d



class Correspondence(Item):
    """
    Person C{source} corresponded with Person C{target} through C{via}.
    """

    source = attributes.reference(allowNone=False,
                                  whenDeleted=attributes.reference.CASCADE,
                                  reftype=Person)

    target = attributes.reference(allowNone=False,
                                  whenDeleted=attributes.reference.CASCADE,
                                  reftype=Person)

    via = attributes.reference(whenDeleted=attributes.reference.CASCADE,
                               reftype=exmess.Message)


    @staticmethod
    def onMessage(message):
        """
        Create Correspondences for the given message.
        """
        from xquotient import console
        # Extract the sender / recipients
        (sender, recipients) = _sender_recipients(message)
        # mimeutil.EmailAddress -> EmailAddress, creating if necessary
        _item = lambda a: _itemForEmailAddress(message.store, a)
        (sender, recipients) = (_item(sender),
                                map(_item, recipients))
        for recipient in recipients:
            message.store.findOrCreate(Correspondence,
                                       lambda c: console.LogEntry(store=message.store,
                                                                  subject=c),
                                       source=sender.person,
                                       target=recipient.person)



class Coordinator(Item):
    """
    """

    implements(IReliableListener)

    dispatchCount = attributes.integer(default=0)

    _dispatchTable = attributes.inmemory(doc='{type(item): [handler]}')


    def activate(self):
        """
        """
        # XXX temporarily hardcoded
        from xquotient import console
        self._dispatchTable = {
            exmess.Message: [Correspondence.onMessage],
            console.LogEntry: [console.ConsoleView.newEntry],
        }
        # Make sure we're registered for each type
        for itemType in self._dispatchTable:
            self.store.findOrCreate(processor(itemType)).addReliableListener(self)


    #def monitor(self, itemtype, callback):
    #    self._dispatchTable[itemtype].append(callback)


    #def unmonitor(self, itemtype, callback):
    #    self._dispatchTable[itemtype].remove(callback)


    # IReliableListener
    def processItem(self, item):
        """
        Dispatch C{item} to to the appropriate monitor.
        """
        #print 'XXX Coordinator processing', item
        try:
            callbacks = self._dispatchTable[type(item)]
        except KeyError:
            raise TypeError(type(item))
        else:
            for callback in callbacks:
                callback(item)
            self.dispatchCount += 1



# Helpers

def _sender_recipients(message):
    """
    Helper: Get the effective sender and recipients of a message.

    @type message: L{exmess.Message}
    @return: (sender, [recipients]) of L{xquotient.mimestorage.EmailAddress}
    """
    # Extract the addresses via IMessageData
    addrs = _dict(message.impl.relatedAddresses())
    # If it's a resend, return the forwarding sender/recipients instead of the
    # original sender/recipients
    if exmess.RESENT_FROM_RELATION in addrs:
        (sender,) = addrs[exmess.RESENT_FROM_RELATION]
        recipients = addrs[exmess.RESENT_TO_RELATION]
    elif exmess.SENDER_RELATION in addrs:
        (sender,) = addrs[exmess.SENDER_RELATION]
        recipients = chain(addrs[exmess.RECIPIENT_RELATION],
                            addrs[exmess.COPY_RELATION],
                            addrs[exmess.BLIND_COPY_RELATION])
    else:
        raise AssertionError('no senders in %r' % (addrs,))
    return sender, recipients



def _itemForEmailAddress(store, addr):
    """
    Helper: Get or create an L{EmailAddress} item for the given address.

    @param addr: L{quotient.mimeutil.EmailAddress}
    @rtype: L{EmailAddress}
    """
    # Try to find an existing EmailAddress
    try:
        a = store.findUnique(EmailAddress, EmailAddress.address == addr.email)
        if not addr.display == a.person.name:
            print 'XXX TODO: display name mismatch for %r: received %r' % (a.person, addr)
        return a
    except ItemNotFound:
        # Create a new EmailAddress, using the display name for the Person
        p = store.findOrCreate(Person,
                               name=(addr.display if addr.display
                                     else addr.localpart),
                               organizer=store.findFirst(Organizer))    # XXX random
        return EmailAddress(store=store, address=addr.email, person=p)

__all__ = 'Correspondence Coordinator'.split()
