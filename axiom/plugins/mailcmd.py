# -*- test-case-name: xquotient.test.test_mailcmd -*-

"""
$ axiomatic mail
"""

from axiom.plugins.webcmd import decodeCommandLine
from axiom.scripts.axiomatic import AxiomaticCommand

from twisted.python.usage import UsageError

from xquotient.mail import MailTransferAgent

class SMTPConfiguration(AxiomaticCommand):
    """
    Subcommand for configuring and introspecting an MTA installed on an Axiom
    database.
    """
    name = 'mail'
    description = 'SMTP configuration and introspection'

    optParameters = [
        ('port', 'p', None,
         'TCP port over which to serve SMTP (empty string to disable)'),
        ('secure-port', 's', None,
         'TCP port over which to server SMTP/SSL (empty string to disable)'),
        ('pem-file', 'f', None,
         'Filename containing PEM-format private key and certificate '
         '(empty string to disable; ignored if --secure-port is not '
         'specified)'),
        ]


    def _setPortNumber(self, mta, key='port', attr='portNumber'):
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
            setattr(mta, attr, port)
            return True
        return False


    def _setSecurePortNumber(self, mta):
        return self._setPortNumber(mta, 'secure-port', 'securePortNumber')


    def _setCertificate(self, mta):
        if self['pem-file'] is not None:
            if not self['pem-file']:
                certificateFile = None
            else:
                certificateFile = self['pem-file']
            mta.certificateFile = certificateFile
            return True
        return False


    def postOptions(self):
        store = self.parent.getStore()
        def reconfigure():
            didSomething = False
            try:
                mta = store.findUnique(MailTransferAgent)
            except ItemNotFound:
                raise UsageError("No MTA installed on this store.")
            for f in [self._setPortNumber,
                      self._setSecurePortNumber,
                      self._setCertificate]:
                didSomething += f(mta)
            return didSomething
        if not store.transact(reconfigure):
            self.opt_help()


del AxiomaticCommand
