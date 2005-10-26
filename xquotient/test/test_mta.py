
from twisted.trial import unittest
from twisted.application import service
from twisted.mail import smtp

from vertex.scripts import certcreate

from axiom import store, userbase

from xquotient import mail, mimestorage

class MailTests(unittest.TestCase):
    def setUp(self):
        self.dbdir = self.mktemp()
        self.store = store.Store(self.dbdir)
        self.login = userbase.LoginSystem(store=self.store)
        self.login.installOn(self.store)

        svc = service.IService(self.store)
        svc.privilegedStartService()
        svc.startService()

    def tearDown(self):
        svc = service.IService(self.store)
        return svc.stopService()

    def testLateInstallation(self):
        mta = mail.MailTransferAgent(store=self.store)
        mta.installOn(self.store)
        self.failUnless(mta.running)

    def testSMTP(self):
        mta = mail.MailTransferAgent(store=self.store)
        mta.installOn(self.store)

        self.failIfEqual(mta.port, None)
        self.assertEquals(mta.securePort, None)

    def testSMTPS(self):
        certfile = self.mktemp()
        certcreate.main(['--filename', certfile])

        mta = mail.MailTransferAgent(store=self.store,
                                     portNumber=None,
                                     securePortNumber=0,
                                     certificateFile=certfile)
        mta.installOn(self.store)

        self.assertEqual(mta.port, None)
        self.failIfEqual(mta.securePort, None)

    def testMessageDeliveryObjects(self):
        mta = mail.MailTransferAgent(store=self.store)
        mta.installOn(self.store)
        factory = smtp.IMessageDeliveryFactory(self.store)
        delivery = factory.getMessageDelivery()
        self.failUnless(smtp.IMessageDelivery.providedBy(delivery))

    def testValidateTo(self):
        mta = mail.MailTransferAgent(store=self.store)
        mta.installOn(self.store)
        factory = smtp.IMessageDeliveryFactory(self.store)
        delivery = factory.getMessageDelivery()

        account = self.login.addAccount('testuser', 'example.com', None)
        subStore = account.avatars.open()
        mail.MailTransferAgent(store=subStore).installOn(subStore)

        d = delivery.validateTo(
            smtp.User(smtp.Address('testuser@example.com'),
                      None, None, None))

        def cbValidated(messageCallable):
            msg = messageCallable()
            self.failUnless(smtp.IMessage.providedBy(msg))

        d.addCallback(cbValidated)
        return d
