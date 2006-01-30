# -*- test-case-name: xmantissa.test.test_signup -*-

from axiom import iaxiom, scheduler, userbase

from xmantissa import website, offering, provisioning

from xquotient.quotientapp import QuotientBenefactor
from xquotient import mail, grabber, compose, publicpage

quotientBenefactorFactory = provisioning.BenefactorFactory(
    name = u'quotient',
    description = u'Incoming SMTP, Gallery, Address Book, Thumbnailer, Fulltext Indexer, Extracts',
    benefactorClass = QuotientBenefactor)

grabberBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Grabbers',
    description = u'Remote message retrieval',
    benefactorClass = grabber.GrabberBenefactor)

composeBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Sending Mail',
    description = u'Allows message transmission',
    benefactorClass = compose.ComposeBenefactor)

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

    benefactorFactories = [quotientBenefactorFactory,
                           grabberBenefactorFactory,
                           composeBenefactorFactory])
