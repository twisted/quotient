from cStringIO import StringIO
from email import Generator as G, MIMEMultipart as MMP, MIMEText as MT, MIMEImage as MI

from axiom import store
from axiom.userbase import LoginSystem

from xmantissa.offering import installOffering

from xmantissa.plugins.mailoff import (
    plugin as quotientOffering, quotientBenefactorFactory)

from xquotient.quotientapp import QuotientBenefactor
from xquotient.mail import DeliveryAgent

class PartMaker:
    """
    Convenience class for assembling and serializing
    hierarchies of mime parts.
    """

    parent = None

    def __init__(self, ctype, body, *children):
        """
        @param ctype: content-type of this part.
        @param body: the string body of this part.
        @param children: arbitrary number of PartMaker instances
                         representing children of this part.
        """

        self.ctype = ctype
        self.body = body
        for c in children:
            assert c.parent is None
            c.parent = self
        self.children = children

    def _make(self):
        (major, minor) = self.ctype.split('/')

        if major == 'multipart':
            p = MMP.MIMEMultipart(minor,
                                  None,
                                  list(c._make() for c in self.children))
        elif major == 'text':
            p = MT.MIMEText(self.body, minor)
        elif major == 'image':
            p = MI.MIMEImage(self.body, minor)
        else:
            assert False

        return p

    def make(self):
        """
        Serialize this part using the stdlib L{email} package.
        @return: string
        """
        s = StringIO()
        G.Generator(s).flatten(self._make())
        s.seek(0)
        return s.read()


class MIMEReceiverMixin:
    def createMIMEReceiver(self):
        return self.deliveryAgent.createMIMEReceiver(u'test://' + self.dbdir)

    def setUpMailStuff(self):
        sitedir = self.mktemp()
        s = store.Store(sitedir)
        loginSystem = LoginSystem(store=s)
        loginSystem.installOn(s)

        account = loginSystem.addAccount(u'testuser', u'example.com', None)
        substore = account.avatars.open()
        self.dbdir = substore.dbdir.path

        installOffering(s, quotientOffering, {})
        benefactor = quotientBenefactorFactory.instantiate()
        benefactor.endow(None, substore)

        self.deliveryAgent = substore.findUnique(DeliveryAgent)
        return self.createMIMEReceiver()
