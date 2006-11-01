# Copyright 2005 Divmod, Inc.  See LICENSE file for details

from twisted.trial import unittest

from xquotient import mimeutil

class MIMEUtilTests(unittest.TestCase):

    def testheaderToUnicode(self):
        expected = [('=?ISO-8859-1?Q?C=E9sar?=', u'C\u00e9sar', ()),
                    ('=?ISO-8859-1?Q?C=E9sar?= fu bar', u'C\u00e9sar fu bar', ()),
                    ('=?ISO-FUBAR1?Q?C=E9sar?= fu bar', u'C\ufffdr fu bar', ()),
                    ('=?ISO-FUBAR1?Q?C=E9sar?= fu bar', u'C\u00e9sar fu bar', ('iso-8859-1',))]

        for source, expected, args in expected:
            result = mimeutil.headerToUnicode(source, *args)
            self.failUnless(isinstance(result, unicode))
            self.assertEquals(result, expected, "from %r got %r, expected %r" % (source, result, expected))

    dates = [
        ("Wed, 08 Dec 2004 16:44:11 -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("08 Dec 2004 16:44:11 -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("8 Dec 2004 16:44:11 -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("8 Dec 04 16:44:11 -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("  Wed,    08     Dec    2004      16:44:11     -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("Wed,08 Dec 2004 16:44:11 -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        # implementation doesn't handle comments correctly, but they are now obsoleted
        #("Wed,08 Dec 2004 16(rfc2822 allows):44: (comments all over here)  11 -0500", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("08 Dec 2004 16:44 -0500", (2004, 12, 8, 21, 44, 0, 2, 343, 0)),
        ("08 Dec 2004 15:44:11 -0600", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("08 Dec 2004 21:44:11 -0000", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("08 Dec 2004 21:44:11 +0000", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("Wed, 08 Dec 2004 16:44:11 EST", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        # implementation says it handles military style timezones, but it
        # doesn't. They are obsolete now anyway, and because rfc822 got the
        # sign on them backwards, rfc2822 suggests they all be considered
        # -0000. Whatever.
        #("Wed, 08 Dec 2004 16:44:11 R", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ("Wednesday, 08 Dec 2004 16:44:11 EST", (2004, 12, 8, 21, 44, 11, 2, 343, 0)),
        ]

    def test_formatdate(self):
        for formatted, tuple in self.dates:
            self.assertEquals(mimeutil.parsedate(mimeutil.formatdate(tuple)), tuple)

    def test_parsedate(self):
        for formatted, tuple in self.dates:
            self.assertEquals(mimeutil.parsedate(formatted), tuple)

    def test_parseBadDate(self):
        """Invalid dates return None"""
        self.failUnless(mimeutil.parsedate('invalid date') is None, 'parsedate("invalid date") did not return None')


class EmailAddressTests(unittest.TestCase):
    def test_cmp(self):
        self.assertEquals(mimeutil.EmailAddress('    '), mimeutil.EmailAddress(''))
        self.assertEquals(mimeutil.EmailAddress('Fu@bAr'), mimeutil.EmailAddress('  fu  @ bar  '))
        self.assertEquals(mimeutil.EmailAddress('bleh <Fu@bAr>'), mimeutil.EmailAddress(('  bleh  ', '  fu  @ bar  ')))
        self.assertNotEquals(mimeutil.EmailAddress('bleh <Fu@bAr>'), mimeutil.EmailAddress('  fu  @ bar  '))

    def test_parsing(self):
        e = mimeutil.EmailAddress(' SoMe  NaMe   <SoMeNaMe@example.com>')
        self.assertEquals(e.display, 'SoMe NaMe')
        self.assertEquals(e.email, 'somename@example.com')
        self.assertEquals(e.anyDisplayName(), 'SoMe NaMe')
        self.assertEquals(e.pseudoFormat(), 'SoMe NaMe <somename@example.com>')
        self.assertEquals(e.localpart, 'somename')
        self.assertEquals(e.domain, 'example.com')

        e = mimeutil.EmailAddress(('  SoMe  NaMe  ', 'SoMeNaMe@example.com'))
        self.assertEquals(e.display, 'SoMe NaMe')
        self.assertEquals(e.email, 'somename@example.com')
        self.assertEquals(e.anyDisplayName(), 'SoMe NaMe')
        self.assertEquals(e.pseudoFormat(), 'SoMe NaMe <somename@example.com>')
        self.assertEquals(e.localpart, 'somename')
        self.assertEquals(e.domain, 'example.com')

        e = mimeutil.EmailAddress(' n o  name  @ examplE.com  ')
        self.assertEquals(e.display, '')
        self.assertEquals(e.email, 'noname@example.com')
        self.assertEquals(e.anyDisplayName(), 'noname@example.com')
        self.assertEquals(e.pseudoFormat(), 'noname@example.com')
        self.assertEquals(e.localpart, 'noname')
        self.assertEquals(e.domain, 'example.com')

        e = mimeutil.EmailAddress('    ')
        self.assertEquals(e.display, '')
        self.assertEquals(e.email, '')
        self.assertEquals(e.anyDisplayName(), 'Nobody')
        self.assertEquals(e.pseudoFormat(), '')
        self.assertEquals(e.localpart, '')
        self.assertEquals(e.domain, '')

        e = mimeutil.EmailAddress('  =?ISO-8859-1?Q?C=E9sar______?= fu   bar  <cesarfubar@example.com>')
        self.assertEquals(e.display, u'C\u00e9sar fu bar')
        self.assertEquals(e.email, 'cesarfubar@example.com')
        self.assertEquals(e.anyDisplayName(), u'C\u00e9sar fu bar')
        self.assertEquals(e.pseudoFormat(), u'C\u00e9sar fu bar <cesarfubar@example.com>')
        self.assertEquals(e.localpart, 'cesarfubar')
        self.assertEquals(e.domain, 'example.com')

    def test_parseEmailAddresses(self):
        self.assertEquals(
            mimeutil.parseEmailAddresses('  one@t  wo , three <four@five>  '),
            map(mimeutil.EmailAddress, ['one@two', 'three <four@five>']))

    def test_flattenEmailAddresses(self):
        """
        Test that L{xquotient.mimeutil.flattenEmailAddresses} works as
        expected
        """
        self.assertEquals(
            mimeutil.flattenEmailAddresses(
                (mimeutil.EmailAddress('One <one@two>'),
                 mimeutil.EmailAddress('two@three'))),
            'One <one@two>, two@three')

    def test_makeHeader(self):
        e = mimeutil.EmailAddress('  =?ISO-8859-1?Q?C=E9sar______?= fu   bar  <cesarfubar@example.com>')
        header = e.makeHeader('To')
        e2 = mimeutil.EmailAddress(header.encode())
        self.assertEquals(e, e2)

    def test_ListHeader(self):
        emails = []
        emails.append(mimeutil.EmailAddress('  =?ISO-8859-1?Q?C=E9sar______?= fu   bar  <cesarfubar@example.com>'))
        emails.append(mimeutil.EmailAddress(' n o  name  @ examplE.com  '))
        header = mimeutil.makeEmailListHeader(emails, 'To')
        parsed = mimeutil.parseEmailAddresses(header.encode())
        self.assertEquals(emails, parsed)

    def test_nonzero(self):
        self.failIf(mimeutil.EmailAddress(''))
        self.failUnless(mimeutil.EmailAddress('foo@bar'))
        self.failUnless(mimeutil.EmailAddress('baz <foo@bar>'))
        self.failUnless(mimeutil.EmailAddress('baz <>'))
