# -*- test-case-name: xquotient.test -*-

from zope.interface import Interface, Attribute

class IMIMEDelivery(Interface):
    def createMIMEReceiver():
        """Create an object to accept a MIME message.

        @rtype: L{twisted.mail.smtp.IMessage}
        """

class IExtract(Interface):
    start = Attribute("the character offset where this extract starts")
    end = Attribute("the character offset where this extract ends")

    def extract(message):
        """Create an extract item for each matching
           substring in the body of C{message}
        """

    def stanFromExcerpt(excerpt):
        """Wrap C{excerpt} in a useful stan expression"""
