# -*- test-case-name: quotient.test.test_mimeutil -*-

# Copyright 2005 Divmod, Inc.  See LICENSE file for details

"""Misc. tool for manipulating email and MIME stuffs.

This module must not depend on anything but the stdlib.
"""

from email import Header
import email.Utils, time, rfc822

def headerToUnicode(header, fallbackEncoding='utf-8'):
    """Decode a MIME encoded header and return a unicode object.

    @param header: a MIME encoded header to decode
    @param fallbackEncoding: the encoding to use if an unknown encoding is encountered
    """
    segments = []
    for segment, charset in Header.decode_header(header):
        try:
            segments.append(segment.decode(charset or 'ascii', 'replace'))
        except LookupError:
            segments.append(segment.decode(fallbackEncoding, 'replace'))
    return u' '.join(segments)


class EmailAddress(object):
    """An email address, and maybe an associated display name.

    @ivar email: just the address part, like 'fu@example.com'. Always lowercase
    and stripped.

    @ivar localpart: Just the part of C{email} before the '@', or all of
    C{email} if it does not contain an '@'.

    @ivar domain: Just the part of C{email} after '@', or '' if C{email}
    does not contain an '@'.

    @ivar display: the display name part, like u'John Smith'. Always a unicode
    string and stripped, with whitespace normalized to one space.

    @ivar person: the Person instance coresponding to this address. This
    attribute is None until findInAddressbook is called.

    A flattener is registered for this class which will render the address and
    display name prettily. It will also call the 'findInAddressbook' method,
    which might set self.person.

    It is unwise to set attributes of an EmailAddress directly since this
    circumvents the whitespace normalization that normally takes place in
    __init__, and might introduce inconsistencies when findInAddressbook has
    been used. Instead, create a new instance with an (displayName, email) and
    mimeEncoded=False.
    """

    person = None

    def __init__(self, address, mimeEncoded=True):
        """
        @param address: an rfc822 formatted address or a (displayname, address)
        pair. If mimeEncoded is True, any strings in `address` are first
        decoded as specified by MIME for headers. Otherwise, any strings must
        be ascii or unicode objects.
        """

        if isinstance(address, tuple):
            display = address[0]
            emailaddress = email.Utils.parseaddr(address[1])[1]
        else:
            display, emailaddress = email.Utils.parseaddr(address)

        if mimeEncoded:
            decode = headerToUnicode
        else:
            decode = lambda h: h

        self.display = ' '.join(decode(display).split())
        self.email = emailaddress.lower()

        # This could be smarter (also, correct, perhaps) someday.
        if '@' in self.email:
            self.localpart, self.domain = self.email.split('@', 1)
        else:
            self.localpart, self.domain = self.email, ''


    def anyDisplayName(self):
        """Return some sort of display name, in any case.

        - if self.person is set (see findInAddressbook method), return self.person.name.
        - try to return the display name provided in the address, a unicode string
        - if there is no display name, return the email address, a string
        - if there is no email address, return 'Nobody'
        """
        return (self.person and self.person.name) or self.display or self.email or 'Nobody'

    def pseudoFormat(self):
        """Return an rfc-822ish format of self.

        The returned (possibly unicode) string is an rfc-822 header except that
        it is not MIME encoded.
        """
        return email.Utils.formataddr((self.display, self.email))

    __str__ = pseudoFormat

    def makeHeader(self, header_name):
        """Convert self to an email.Header

        @param header_name: passed to Header.__init__

        @return an email.Header.Header instance with self as the content.
        """
        header = Header.Header(header_name=header_name)
        self.appendToHeader(header)
        return header

    def appendToHeader(self, header):
        """Append self to an email.Header.

        Note that this won't add a comma between multiple addresses; it simply
        appends the address. See appendToHeaderWithComma and
        makeEmailListHeader for that.
        """
        if self.display:
            header.append(self.display)
            header.append('<%s>' % (self.email,))
        else:
            header.append(self.email)

    def appendToHeaderWithComma(self, header):
        """Append self to an email.Header, followed by a comma.

        This is used for constructing headers like To and Cc that are comma
        delimited lists of addresses. See the module function
        makeEmailListHeader for the common case.
        """
        if self.display:
            header.append(self.display)
            header.append('<%s>,' % (self.email,))
        else:
            header.append(self.email+',')

    def __cmp__(self, other):
        if not isinstance(other, EmailAddress):
            return cmp(self.__class__, getattr(other, '__class__', type(other)))
        return cmp((self.email, self.display), (other.email, other.display))

    def findInAddressbook(self, addressbook):
        """Look for a person matching this address in an addressbook.

        If this person is not in the addressbook, KeyError is raised.
        Otherwise, self.person will be set to the person instance.
        """
        from quotient.addressbook import EmailIndex
        self.person = addressbook.addressPool.getIndexItem(EmailIndex, self.email)
        return self.person

    def __nonzero__(self):
        return bool(self.display or self.email)


def makeEmailListHeader(emails, header_name):
    """Return an email.Header instance that is a comma separated list of EmailAddress.

    @param emails: a sequence of EmailAddress instances
    @param header_name: the name of the header, passed to Header.__init__.
    """
    header = Header.Header(header_name=header_name)
    for email in emails[:-1]:
        email.appendToHeaderWithComma(header)
    if emails:
        emails[-1].appendToHeader(header)
    return header


def parseEmailAddresses(addresses, mimeEncoded=True):
    """Parse a list of comma separated addresses and might be found in an email header.

    @param mimeEncoded: as parameter by same name to EmailAddress.__init__
    @return a list of EmailAddress instances.
    """
    return [EmailAddress(address, mimeEncoded=mimeEncoded) for address in rfc822.AddressList(addresses)]


def formatdate(utctuple):
    """Convert a UTC 9-tuple to an RFC 2822 date.

    Note that the RFC says the Date header should reflect the local timezone,
    but this always produces -0000.
    """
    assert len(utctuple) == 9
    return email.Utils.formatdate(email.Utils.mktime_tz(utctuple[:6] + (0,0,0,0)))

def parsedate(rfc822string):
    """Convert an RFC 2822 date to a UTC 9-tuple.

    Returns None if the date can not be parsed.
    """
    date = email.Utils.parsedate_tz(rfc822string)
    if date is None:
        return None
    return time.gmtime(email.Utils.mktime_tz(date))
