
import os

from twisted.trial import unittest
from twisted.python import filepath

from epsilon import extime

from axiom import store, scheduler

from xquotient import mail, mimepart, mimestorage

def msg(s):
    return '\r\n'.join(s.splitlines())

class MessageTestMixin:
    trivialMessage = msg("""\
From: alice@example.com
To: bob@example.com
Subject: a test message, comma separated
Date: Tue, 11 Oct 2005 14:25:12 GMT
Junk\xa0Header: value
References: <one@domain>\t<two@domain>\x20
\t<three@domain>

Hello Bob,
  How are you?
-A
""")

    def assertHeadersEqual(self, a, b):
        self.assertEquals(a.name, b.name)
        self.assertEquals(a.value, b.value)

    def assertTrivialMessageStructure(self, msg):
        map(self.assertHeadersEqual,
            list(msg.getAllHeaders())[:-1],
            [mimepart.Header(u"from", "alice@example.com"),
             mimepart.Header(u"to", "bob@example.com"),
             mimepart.Header(u"subject", "a test message, comma separated"),
             mimepart.Header(u"date", "Tue, 11 Oct 2005 14:25:12 GMT"),
             mimepart.Header(u"junkheader", "value"),
             mimepart.Header(u"references", "<one@domain>"),
             mimepart.Header(u"references", "<two@domain>"),
             mimepart.Header(u"references", "<three@domain>")])

        self.assertEquals(msg.getHeader(u"from"), "alice@example.com")
        self.assertEquals(msg.getHeader(u"to"), "bob@example.com")
        self.assertEquals(msg.getHeader(u"subject"), "a test message, comma separated")
        self.assertEquals(msg.getHeader(u"date"), 'Tue, 11 Oct 2005 14:25:12 GMT')
        self.assertEquals(msg.getHeader(u"junkheader"), "value")
        self.assertEquals([hdr.value for hdr in msg.getHeaders(u"references")],
                          [u"<one@domain>", u"<two@domain>", u"<three@domain>"])

    def testTrivialMessage(self):
        self._messageTest(self.trivialMessage, self.assertTrivialMessageStructure)


    messageWithUnicode = msg("""\
From: =?utf-8?b?VMOpc3Qgx5NzZXIgPHRlc3R1c2VyQGV4YW1wbGUuY29tPg==?=

Body.
""")


    def assertUnicodeHeaderValues(self, msg):
        self.assertEquals(
            msg.getHeader(u"from"),
            u"T\N{LATIN SMALL LETTER E WITH ACUTE}st "
            u"\N{LATIN CAPITAL LETTER U WITH CARON}ser "
            u"<testuser@example.com>")


    def testUnicodeHeaderValues(self):
        """
        MIME Headers may be encoded in various ways.  Assert that none of these
        encoding details make it into the resulting Header objects and that the
        non-ASCII payload is correctly interpreted.
        """
        self._messageTest(self.messageWithUnicode, self.assertUnicodeHeaderValues)


    multipartMessage = msg("""\
Envelope-to: test@domain.tld
Received: from pool-138-88-80-171.res.east.verizon.net
	([138.88.80.171] helo=meson.dyndns.org ident=69gnV1Y3MozcsVOT)
	by pyramid.twistedmatrix.com with esmtp (Exim 3.35 #1 (Debian))
	id 181WHR-0002Rq-00
	for <test@domain.tld>; Tue, 15 Oct 2002 13:18:57 -0500
Received: by meson.dyndns.org (Postfix, from userid 1000)
	id 34DEB13E95; Tue, 15 Oct 2002 14:20:18 -0400 (EDT)
Date: Tue, 15 Oct 2002 14:20:18 -0400
From: Jp Calderone <exarkun@blargchoo.choo.choo.dyndns.org>
To: test@domain.tld
Subject: [user@address: My Cool Apartment!]
Message-ID: <20021015182018.GA11673@unique.oh.yea>
Mime-Version: 1.0
Content-Type: multipart/signed; micalg=x-unknown;
	protocol="application/pgp-signature"; boundary="24zk1gE8NUlDmwG9"
Content-Disposition: inline
User-Agent: Mutt/1.3.25i
Content-Length: 2003
Lines: 72
Status: RO
x-pop3-uid: 3dbf299600000017 twistedmatrix.com


--24zk1gE8NUlDmwG9
Content-Type: multipart/mixed; boundary="h31gzZEtNLTqOjlF"
Content-Disposition: inline


--h31gzZEtNLTqOjlF
Content-Type: text/plain; charset=us-ascii
Content-Disposition: inline
Content-Transfer-Encoding: quoted-printable


--=20
   Know what I pray for? The strength to change what I can, the inability to
accept what I can't and the incapacity to tell the difference.    -- Calvin
--
 2:00pm up 147 days, 14:57, 4 users, load average: 0.00, 0.02, 0.00

--h31gzZEtNLTqOjlF
Content-Type: message/rfc822
Content-Disposition: inline

Return-Path: <dynamox@springstreet.com>
Delivered-To: thisuser@guy.wherever
Received: from mx1.springstreet.com (unknown [206.131.172.28])
	by meson.dyndns.org (Postfix) with ESMTP id E027314187
	for <exarkun@choo.choo.choo.dyndns.org>; Wed, 18 Sep 2002 00:27:14 -0400 (EDT)
Received: from app2.springstreet.com (app2.admin.springstreet.com
	[10.0.149.2])
	by mx1.springstreet.com (8.11.6/8.11.6) with ESMTP id g8I4RUe47820
	for <exarkun@xxxx.org>; Tue, 17 Sep 2002 21:27:30 -0700 (PDT)
	(envelope-from dynamox@springstreet.com)
Received: (from dynamox@localhost)
	by app2.springstreet.com (8.10.2+Sun/8.10.2) id g8I4RUb22565;
	Tue, 17 Sep 2002 21:27:30 -0700 (PDT)
Date: Tue, 17 Sep 2002 21:27:30 -0700 (PDT)
Message-Id: <200209180427.g8I4RUb22565@app2.springstreet.com>
To: this.field.is.for@the.user.it.is.for
From: someuser@anotherdomain.com
SUBJECT: My Cool Apartment!

jp,

Hey! Check out this great apartment I found at Homestore.com apartments &
rentals! You can visit it here:
http://www.springstreet.com/propid/246774?source=1xxctb079


cathedral ceilings



<message id:1032323249933719>

--h31gzZEtNLTqOjlF--

--24zk1gE8NUlDmwG9
Content-Type: application/pgp-signature
Content-Disposition: inline

-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA1


-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1.0.7 (GNU/Linux)

iD8DBQE9rFxhedcO2BJA+4YRAjZqAKC6jZcmEZu0tInRreBjTbFcIh7rfACdEDhZ
oTZw+Ovl1BvLcE+pK9VFxxY=
=Uds2
-----END PGP SIGNATURE-----

--24zk1gE8NUlDmwG9--
""")

    def assertMultipartMessageStructure(self, msg):
        pass

    def testMultipartMessage(self):
        self._messageTest(self.multipartMessage, self.assertMultipartMessageStructure)


class ParsingTestCase(unittest.TestCase, MessageTestMixin):
    def _messageTest(self, source, assertMethod):
        deliveryDir = self.mktemp()
        os.makedirs(deliveryDir)
        f = store.AtomicFile(
            filepath.FilePath(deliveryDir).child('tmp.eml').path,
            filepath.FilePath(deliveryDir).child('message.eml'))
        mr = mimepart.MIMEMessageReceiver(f)
        msg = mr.feedStringNow(source)
        assertMethod(msg)



class PersistenceTestCase(unittest.TestCase, MessageTestMixin):
    def setUpMailStuff(self):
        dbdir = self.mktemp()
        s = store.Store(dbdir)
        scheduler.Scheduler(store=s).installOn(s)
        da = mail.DeliveryAgent(store=s)
        da.installOn(s)
        return da.createMIMEReceiver(u"test://" + dbdir)

    def _messageTest(self, source, assertMethod):
        mr = self.setUpMailStuff()
        msg = mr.feedStringNow(source)
        assertMethod(msg)

    def testPartIDs(self):
        mr = self.setUpMailStuff()
        part = mr.feedStringNow(self.multipartMessage)
        self.assertEquals(part.partID, 0)
        partIDs = list(part.store.query(
                            mimestorage.Part, sort=mimestorage.Part.partID).getColumn('partID'))
        self.assertEquals(partIDs, range(len(partIDs)))


    typelessMessage = msg("""\
To: you
From: nobody

haha
""")

    def testContentTypeNotNone(self):
        self._messageTest(self.typelessMessage,
                          lambda part: self.assertEquals(part.getContentType(),
                                                         'text/plain'))

    datelessMessage = msg("""\
Received: Wed, 15 Feb 2006 03:58:50 GMT

Some body
""")

    def testSentWhen(self):
        def assertSentWhen(part):
            self.assertEquals(
                part.message.sentWhen,
                extime.Time.fromRFC2822("Wed, 15 Feb 2006 03:58:50 GMT"))

        self._messageTest(self.datelessMessage, assertSentWhen)
