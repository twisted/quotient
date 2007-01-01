# -*- test-case-name: xquotient.test.test_mailcmd -*-

"""
$ axiomatic mail
"""

from axiom.plugins.webcmd import decodeCommandLine
from axiom.scripts.axiomatic import AxiomaticCommand
from axiom.errors import ItemNotFound
from axiom.dependency import installOn

from twisted.python.usage import UsageError

from xmantissa.port import TCPPort, SSLPort

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

    optFlags = [
        ('show', None, 'Display information about the current configuration.'),
        ]


    def _changePort(self, factory, type, **kw):
        port = factory.store.findOrCreate(
            type,
            lambda p: installOn(p, p.store),
            factory=factory)
        if kw:
            for k, v in kw.iteritems():
                setattr(port, k, v)
        else:
            port.deleteFromStore()


    def _setPort(self, server, key, type):
        if self[key] is not None:
            if not self[key]:
                self._changePort(server, type)
            else:
                try:
                    port = int(self[key])
                    if port < 0 or port > 65535:
                        raise ValueError
                except ValueError:
                    raise UsageError(
                        "Argument to --" + key + " must be an "
                        "integer between 0 and 65536.")
                self._changePort(server, type, portNumber=port)
            return True
        return False


    def _setPortNumber(self, server):
        return self._setPort(server, 'port', TCPPort)


    def _setSecurePortNumber(self, server):
        return self._setPort(server, 'secure-port', SSLPort)


    def _setCertificate(self, server):
        if self['pem-file'] is not None:
            if self['pem-file']:
                base = server.store.filesdir
                certPath = base.preauthChild(self['pem-file'])
                server.certificateFile = certPath.path
            else:
                certPath = None
                server.certificateFile = None

            for port in server.store.query(SSLPort, SSLPort.factory == server):
                if certPath is None:
                    port.deleteFromStore()
                else:
                    port.certificatePath = certPath
                break

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
            if self['show']:
                didSomething += 1
                for p in store.query(TCPPort, TCPPort.factory == server):
                    print 'Accepting connections on TCP port %d.' % (p.portNumber,)
                for p in store.query(SSLPort, SSLPort.factory == server):
                    print 'Accepting connections on SSL/TCP port %d using certificate .' % (p.portNumber, p.certificatePath.path)
                if server.certificateFile is not None:
                    print 'Using %s for SMTP TLS support.' % (server.certificateFile.path,)
            else:
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
