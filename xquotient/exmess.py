
from axiom import item, attributes

# The big kahuna.  This, along with some kind of Person object, is the
# core of Quotient.
class Message(item.Item):
    typeName = 'quotient_message'
    schemaVersion = 1

    received = attributes.timestamp()
    sender = attributes.text()
    recipient = attributes.text()
    subject = attributes.text()
