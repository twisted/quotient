# -*- test-case-name: xmantissa.test.test_signup -*-

from axiom import iaxiom, scheduler, userbase

from xmantissa import website, offering, provisioning

from xquotient.quotientapp import QuotientBenefactor
from xquotient import mail, publicpage

quotientBenefactorFactory = provisioning.BenefactorFactory(
    name = u'quotient',
    description = u'a whole bunch of things related to messaging',
    benefactorClass = QuotientBenefactor)

plugin = offering.Offering(
    name = u'Quotient',

    description = u'''
    Quotient is really great, you should install it
    ''',

    siteRequirements = (
        (iaxiom.IScheduler, scheduler.Scheduler),
        (userbase.IRealm, userbase.LoginSystem),
        (None, website.WebSite),
        (None, mail.MailTransferAgent)),

    appPowerups = (publicpage.QuotientPublicPage,),

    benefactorFactories = (quotientBenefactorFactory,))

