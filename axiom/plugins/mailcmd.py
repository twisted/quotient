# -*- test-case-name: xquotient.test.test_mailcmd -*-

"""
$ axiomatic mail
"""

from axiom.plugins.webcmd import decodeCommandLine
from axiom.scripts.axiomatic import AxiomaticCommand
from axiom.errors import ItemNotFound

from twisted.python.usage import UsageError

from xquotient.mail import MailTransferAgent
from xquotient.popout import POP3Listener


class _PortConfigurationMixin:
    optParameters = [
        ('port', 'p', None,
         'TCP port over which to serve plaintext connections '
         '(empty string to disable)'),
        ('secure-port', 's', None,
         'TCP port over which to server SSL connections '
         '(empty string to disable)'),
        ('pem-file', 'f', None,
         'Filename containing PEM-format private key and certificate '
         '(empty string to disable; ignored if --secure-port is not '
         'specified)'),
        ]


    def _setPortNumber(self, server, key='port', attr='portNumber'):
        if self[key] is not None:
            if not self[key]:
                port = None
            else:
                try:
                    port = int(self[key])
                    if port < 1 or port > 65535:
                        raise ValueError
                except ValueError:
                    raise UsageError(
                        "Argument to --" + key + " must be an "
                        "integer between 0 and 65536.")
            setattr(server, attr, port)
            return True
        return False


    def _setSecurePortNumber(self, server):
        return self._setPortNumber(server, 'secure-port', 'securePortNumber')


    def _setCertificate(self, server):
        if self['pem-file'] is not None:
            if not self['pem-file']:
                certificateFile = None
            else:
                certificateFile = self['pem-file']
            server.certificateFile = certificateFile
            return True
        return False


    def postOptions(self):
        store = self.parent.getStore()
        def reconfigure():
            didSomething = False
            try:
                server = store.findUnique(self.serverType)
            except ItemNotFound:
                raise UsageError("No %s server installed on this store." % (self.name,))
            for f in [self._setPortNumber,
                      self._setSecurePortNumber,
                      self._setCertificate]:
                didSomething += f(server)
            return didSomething
        if not store.transact(reconfigure):
            self.opt_help()



class POPConfiguration(_PortConfigurationMixin, AxiomaticCommand):
    """
    Subcommand for configuring and introspecting a POP3 server installed on an
    Axiom database.
    """
    name = 'pop3'
    description = 'POP3 configuration and introspection'
    serverType = POP3Listener



class SMTPConfiguration(_PortConfigurationMixin, AxiomaticCommand):
    """
    Subcommand for configuring and introspecting an MTA installed on an Axiom
    database.
    """
    name = 'smtp'
    description = 'SMTP configuration and introspection'
    serverType = MailTransferAgent


del AxiomaticCommand
