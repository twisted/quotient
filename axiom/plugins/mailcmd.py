
from zope.interface import classProvides

from twisted.python import usage
from twisted.python.util import sibpath
from twisted import plugin

from axiom import iaxiom, errors as eaxiom
from xmantissa import website

from xquotient import mail, inbox

class MailConfiguration(usage.Options):
    classProvides(plugin.IPlugin, iaxiom.IAxiomaticCommand)

    name = 'mail'
    description = 'Accept SMTP connections'

    optParameters = [
        ('port', 'p', None, 'TCP port over which to serve SMTP'),
        ('secure-port', 's', None, 'TCP port over which to server SMTP/SSL'),
        ('pem-file', 'f', None, 'Filename containing PEM-format private key and certificate'),
        ('domain', 'd', None, 'Canonical domain name of this server'),
        ]

    optFlags = [
        ('mailbox', 'm', 'Install a mailbox viewer'),
        ]

    didSomething = False

    def opt_show(self):
        """Display current configuration
        """
        self.didSomething = True
        s = self.parent.getStore()
        try:
            mta = s.findUnique(mail.MailTransferAgent)
        except eaxiom.ItemNotFound:
            print 'MailTransferAgent is not installed on this store.'
        else:
            if mta.portNumber is not None:
                print 'SMTP Port:', mta.portNumber
            if mta.securePortNumber is not None:
                print 'SMTP/SSL Port:', mta.securePortNumber
            if mta.certificateFile is not None:
                print 'Certificate:', mta.certificateFile

    def postOptions(self):
        s = self.parent.getStore()

        def _():

            mta = s.findOrCreate(mail.MailTransferAgent, lambda newItem: newItem.installOn(s))
            if self['mailbox']:
                s.findOrCreate(inbox.Inbox).installOn(s)
                s.findOrCreate(website.StaticSite,
                               prefixURL=u'static/quotient',
                               staticContentPath=sibpath(mail.__file__, u'static')).installOn(s)
                s.findOrCreate(inbox.QuotientPreferenceCollection).installOn(s)

                self.didSomething = True

            if self['port'] is not None:
                mta.portNumber = int(self['port'])
                self.didSomething = True

            if (self['secure-port'] is None) != (self['pem-file'] is None):
                raise MailConfigurationError("Supply both or neither of secure-port and pem-file")
            elif self['secure-port']:
                mta.securePortNumber = int(self['secure-port'])
                mta.certificateFile = self['pem-file']
                self.didSomething = True

        s.transact(_)
        if not self.didSomething:
            self.opt_help()
