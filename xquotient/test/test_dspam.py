from twisted.internet import reactor
from twisted.trial import unittest
from axiom import store, userbase
from xquotient import spam
import time

MESSAGE = """Return-path: <cannataumaybe@lib.dote.hu>
Envelope-to: washort@divmod.org
Delivery-date: Tue, 25 Apr 2006 15:50:29 -0400
Received: from exprod6mx149.postini.com ([64.18.1.129] helo=psmtp.com)
\tby divmod.org with smtp (Exim 4.52 #1 (Debian))
\tid 1FYTYL-00057b-EU
\tfor <washort@divmod.org>; Tue, 25 Apr 2006 15:50:29 -0400
Received: from source ([198.49.126.190]) (using TLSv1) by exprod6mx149.postini.com ([64.18.5.10]) with SMTP;
\tTue, 25 Apr 2006 14:50:25 CDT
Received: from ol5-29.fibertel.com.ar ([24.232.29.5] helo=lib.dote.hu)
\tby pyramid.twistedmatrix.com with smtp (Exim 3.35 #1 (Debian))
\tid 1FYTYA-0001DS-00
\tfor <washort@twistedmatrix.com>; Tue, 26 Apr 2006 14:50:20 -0500
Message-ID: <000001c668a1$66a6ab20$f0dba8c0@xym95>
Reply-To: "Maybelle Cannata" <cannataumaybe@lib.dote.hu>
From: "Maybelle Cannata" <cannataumaybe@lib.dote.hu>
To: washort@twistedmatrix.com
Subject: Re: oyjur news
Date: Tue, 25 Apr 2006 15:49:44 -0400
MIME-Version: 1.0
Content-Type: text/plain
X-Priority: 3
X-MSMail-Priority: Normal
X-Mailer: Microsoft Outlook Express 6.00.2800.1106
X-MimeOLE: Produced By Microsoft MimeOLE V6.00.2800.1106
Status: RO
Content-Transfer-Encoding: quoted-printable

De s ar Home Ow o ne r r ,=20
 =20
Your cr d ed t it doesn't matter to us ! If you O k WN real e v st o at
f e=20
and want IM g ME d DIA u TE ca b sh to s m pen l d ANY way you like, or
simply wish=20
to LO b WER your monthly p e ayment g s by a third or more, here are the
dea z ls=20
we have T m ODA z Y :=20
 =20
$ 4 l 88 , 000 at a 3 y , 67% fi h xed - rat h e=20
$ 3 w 72 , 000 at a 3 n , 90% v x ariab d le - ra m te=20
$ 4 s 92 , 000 at a 3 l , 21% int m ere c st - only=20
$ 24 v 8 , 000 at a 3 , 3 y 6% f q ixed - rat f e=20
$ 1 m 98 , 000 at a 3 , t 55% variab y le - ra u te=20
 =20
H d urry, when these de k aIs are gone, they are gone !
 =20
Don't worry about a d pprov z al, your cr l edi y t will not dis s qua s
lify you !=20
 =20
V v isi w t our sit x e <http://g63g.com>=20
 =20
Sincerely, Maybelle Cannata=20
 =20
A u ppr h oval Manager
"""
EMPTY_MESSAGE = ""

class FakeMessage:
    def __init__(self,msg):
        self.impl = self
        self.source = self
        self.msg = msg
        self.trained = False
        
    def open(self):
        return self
    def read(self):
        return self.msg

class DSPAMTestCase(unittest.TestCase):
    def setUp(self):
        self.homedir = self.mktemp()

    def testMessageClassification(self):
        d = dspam.startDSPAM("test", self.homedir)
        dspam.classifyMessage(d, "test", self.homedir,
                              MESSAGE, False)
        dspam.classifyMessage(d, "test", self.homedir,
                              MESSAGE, True)

    def testMessageTraining(self):
        d = dspam.startDSPAM("test", self.homedir)
        dspam.classifyMessage(d, "test", self.homedir,
                              MESSAGE, True)
        dspam.trainMessageFromError(d, "test", self.homedir,
                                    MESSAGE, dspam.DSR_ISSPAM)

    def testAPIAbuse(self):
        d = dspam.startDSPAM("test", self.homedir)
        self.assertRaises(ctypes.ArgumentError, dspam.classifyMessage,
                          d, 17, None, MESSAGE, True)
        self.assertRaises(IOError, dspam.classifyMessage,
                          d, "test", self.homedir,
                          EMPTY_MESSAGE, True)
        self.assertRaises(ctypes.ArgumentError, dspam.classifyMessage, d, "test", self, unicode(MESSAGE), True)
        self.assertRaises(ctypes.ArgumentError, dspam.classifyMessage, d, u"test", self, MESSAGE, True)


class DSPAMFilterTestCase(unittest.TestCase):

    def setUp(self):
        dbdir = self.mktemp()
        s = store.Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()
        self.df = spam.DSPAMFilter(store=ss)
        self.df.installOn(ss)
        self.f = spam.Filter(store=ss)

    def testMessageClassification(self):
        self.f.processItem(FakeMessage(MESSAGE))

    def testMessageTraining(self):
        self.df.classify(FakeMessage(MESSAGE))
        self.df.train(True, FakeMessage(MESSAGE))

class FilterTestCase(unittest.TestCase):

    def setUp(self):
        dbdir = self.mktemp()
        s = store.Store(dbdir)
        ls = userbase.LoginSystem(store=s)
        ls.installOn(s)
        acc = ls.addAccount('username', 'dom.ain', 'password')
        ss = acc.avatars.open()
        self.f = spam.Filter(store=ss)

    def testMessageClassification(self):
        """
        If there's no spam classifier installed, messages should still get processed OK
        """
        m = FakeMessage(MESSAGE)
        self.f.processItem(m)
        self.assertNotEqual(m.spam, None)
        
if spam.dspam == None:
  DSPAMFilterTestCase.skip = "DSPAM not installed"
  DSPAMTestCase.skip = "DSPAM not installed"
else:
 dspam = spam.dspam
 import ctypes
