# -*- test-case-name: xmantissa.test.test_signup -*-

from axiom import iaxiom, scheduler, userbase

from xmantissa import website, offering, provisioning

from xquotient.quotientapp import (QuotientBenefactor,
                                   ExtractBenefactor,
                                   IndexingBenefactor,
                                   QuotientPeopleBenefactor)

from xquotient.quotienttheme import QuotientTheme
from xquotient import mail, grabber, compose, popout, publicpage, filter

quotientBenefactorFactory = provisioning.BenefactorFactory(
    name = u'quotient',
    description = u'Incoming SMTP, Address Book',
    benefactorClass = QuotientBenefactor)

extractBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Extracts',
    description = u'Data-driven feature discovery, extraction, and presentation',
    benefactorClass = ExtractBenefactor,
    dependencies = [quotientBenefactorFactory])

indexingBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Indexing',
    description = u'Full-text email (and other stuff) indexing',
    benefactorClass = IndexingBenefactor,
    dependencies = [quotientBenefactorFactory])

grabberBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Grabbers',
    description = u'Remote message retrieval',
    benefactorClass = grabber.GrabberBenefactor)

composeBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Sending Mail',
    description = u'Allows message transmission',
    benefactorClass = compose.ComposeBenefactor)

popAccessBenefactorFactory = provisioning.BenefactorFactory(
    name = u'POP Server',
    description = u'Access to mail via POP3',
    benefactorClass = popout.POP3Benefactor)

ruleBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Filtering',
    description = u'Pre-configured and user-customizable filtering of messages based on headers and such.',
    benefactorClass = filter.FilterBenefactor,
    dependencies = [quotientBenefactorFactory])

quotientPeopleBenefactorFactory = provisioning.BenefactorFactory(
    name = u'Quotient People Plugins',
    description = u'Per-person Image/Extract/Picture lists',
    benefactorClass = QuotientPeopleBenefactor)

plugin = offering.Offering(
    name = u'Quotient',

    description = u'''
    Quotient is really great, you should install it
    ''',

    siteRequirements = (
        (iaxiom.IScheduler, scheduler.Scheduler),
        (userbase.IRealm, userbase.LoginSystem),
        (None, website.WebSite),
        (None, popout.POP3Listener),
        (None, mail.MailTransferAgent)),

    appPowerups = (publicpage.QuotientPublicPage,),

    benefactorFactories = [quotientBenefactorFactory,
                           extractBenefactorFactory,
                           indexingBenefactorFactory,
                           grabberBenefactorFactory,
                           composeBenefactorFactory,
                           popAccessBenefactorFactory,
                           ruleBenefactorFactory,
                           quotientPeopleBenefactorFactory],
    themes = [QuotientTheme('base', 0)])
