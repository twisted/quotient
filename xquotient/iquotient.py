# -*- test-case-name: xquotient.test -*-

from zope.interface import Interface, Attribute

class IMIMEDelivery(Interface):
    def createMIMEReceiver(source):
        """Create an object to accept a MIME message.

        @type source: C{unicode}
        @param source: A short string describing the means by which this
        Message came to exist. For example, u'mailto:alice@example.com' or
        u'pop3://bob@example.net'.

        @rtype: L{twisted.mail.smtp.IMessage}
        """
