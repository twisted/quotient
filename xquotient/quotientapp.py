from zope.interface import implements

from nevow import tags

from axiom.item import Item, InstallableMixin
from axiom import attributes, scheduler

from xmantissa import website, webapp, ixmantissa, people, prefs, search

from xquotient import inbox, exmess, mail, gallery, qpeople, extract, spam
from xquotient.grabber import GrabberConfiguration
from xquotient.indexinghelp import SyncIndexer

class QuotientSearchProvider(Item, InstallableMixin):
    implements(ixmantissa.ISearchProvider)

    typeName = 'quotient_search_provider'
    schemaVersion = 1

    installedOn = attributes.reference()
    _indexer = attributes.inmemory()

    def installOn(self, other):
        super(QuotientSearchProvider, self).installOn(other)
        other.powerUp(self, ixmantissa.ISearchProvider)


    def activate(self):
        self._indexer = None


    def _getIndexer(self):
        if self._indexer is None:
            self._indexer = self.store.findUnique(SyncIndexer)
        return self._indexer
    indexer = property(_getIndexer)


    def count(self, term):
        return self.indexer.search(term).addCallback(len)


    def search(self, term, count, offset):
        translator = ixmantissa.IWebTranslator(self.store)
        def searchCompleted(results):
            for (i, document) in enumerate(results):
                msg = self.store.getItemByID(long(document['@uri']))
                yield search.SearchResult(description=msg.subject,
                                          url=translator.linkTo(msg.storeID),
                                          summary=document.text[:200],
                                          timestamp=msg.sentWhen,
                                          score=0)
        return self.indexer.search(term, count, offset).addCallback(searchCompleted)



class StaticShellContent(Item, InstallableMixin):
    implements(ixmantissa.IStaticShellContent)

    schemaVersion = 2
    typeName = 'quotient_static_shell_content'

    installedOn = attributes.reference()

    def installOn(self, other):
        super(StaticShellContent, self).installOn(other)
        other.powerUp(self, ixmantissa.IStaticShellContent)

    def getHeader(self):
        return tags.img(src='/Quotient/static/images/logo.png',
                        style='margin: 2px')

    def getFooter(self):
        return None


class QuotientBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    typeName = 'quotient_benefactor'
    schemaVersion = 1

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(scheduler.SubScheduler).installOn(avatar)
        avatar.findOrCreate(website.WebSite).installOn(avatar)
        avatar.findOrCreate(webapp.PrivateApplication).installOn(avatar)

        avatar.findOrCreate(mail.DeliveryAgent).installOn(avatar)
        avatar.findOrCreate(mail.MailTransferAgent).installOn(avatar)

        avatar.findOrCreate(spam.Filter).installOn(avatar)

        avatar.findOrCreate(QuotientPreferenceCollection).installOn(avatar)

        avatar.findOrCreate(inbox.Inbox).installOn(avatar)
        avatar.findOrCreate(inbox.Archive).installOn(avatar)
        avatar.findOrCreate(inbox.Trash).installOn(avatar)
        avatar.findOrCreate(inbox.SentMail).installOn(avatar)

        avatar.findOrCreate(exmess.ZippedAttachments).installOn(avatar)

        avatar.findOrCreate(StaticShellContent).installOn(avatar)


class ExtractBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)


    def endow(self, ticket, avatar):
        avatar.findOrCreate(extract.ExtractPowerup).installOn(avatar)
        avatar.findOrCreate(gallery.Gallery).installOn(avatar)
        avatar.findOrCreate(gallery.ThumbnailDisplayer).installOn(avatar)


    def revoke(self, ticket, avatar):
        avatar.findUnique(extract.ExtractPowerup).deleteFromStore()
        avatar.findUnique(gallery.Gallery).deleteFromStore()
        avatar.findUnique(gallery.ThumbnailDisplayer).deleteFromStore()

class QuotientPeopleBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)

    def endow(self, ticket, avatar):
        organizer = avatar.findOrCreate(people.Organizer)
        organizer.installOn(avatar)

        avatar.findOrCreate(qpeople.MessageLister).installOn(organizer)
        avatar.findOrCreate(qpeople.ExtractLister).installOn(organizer)
        avatar.findOrCreate(qpeople.ImageLister).installOn(organizer)

class IndexingBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)


    def endow(self, ticket, avatar):
        avatar.findOrCreate(SyncIndexer).installOn(avatar)
        avatar.findOrCreate(QuotientSearchProvider).installOn(avatar)


    def revoke(self, ticket, avatar):
        avatar.findUnique(SyncIndexer).deleteFromStore()
        avatar.findUnique(QuotientSearchProvider).deleteFromStore()


class _PreferredMimeType(prefs.MultipleChoicePreference):
    def __init__(self, value, collection):
        valueToDisplay = {u'text/html':'HTML', u'text/plain':'Text'}
        desc = 'Your preferred format for display of email'

        super(_PreferredMimeType, self).__init__('preferredMimeType',
                                                 value,
                                                 'Preferred Format',
                                                 collection, desc,
                                                 valueToDisplay)

class _PreferredMessageDisplay(prefs.MultipleChoicePreference):
    def __init__(self, value, collection):
        valueToDisplay = {u'split':'Split Screen',u'full':'Full Screen'}
        desc = 'Your preferred message detail value'

        super(_PreferredMessageDisplay, self).__init__('preferredMessageDisplay',
                                                       value,
                                                       'Preferred Message Display',
                                                       collection, desc,
                                                       valueToDisplay)

class _ShowReadPreference(prefs.MultipleChoicePreference):
    def __init__(self, value, collection):
        valueToDisplay = {True:'Yes', False:'No'}
        desc = 'Show Read messages by default in Inbox View'

        super(_ShowReadPreference, self).__init__('showRead',
                                                  value,
                                                  'Show Read Messages',
                                                  collection, desc,
                                                  valueToDisplay)

class QuotientPreferenceCollection(Item, InstallableMixin):
    implements(ixmantissa.IPreferenceCollection)

    typeName = 'quotient_preference_collection'
    schemaVersion = 1

    installedOn = attributes.reference()

    preferredMimeType = attributes.text(default=u'text/plain')
    preferredMessageDisplay = attributes.text(default=u'split')
    showRead = attributes.boolean(default=True)

    _cachedPrefs = attributes.inmemory()

    applicationName = 'Mail'

    def installOn(self, other):
        super(QuotientPreferenceCollection, self).installOn(other)
        other.powerUp(self, ixmantissa.IPreferenceCollection)

    def activate(self):
        pmt = _PreferredMimeType(self.preferredMimeType, self)
        pmd = _PreferredMessageDisplay(self.preferredMessageDisplay, self)
        showRead = _ShowReadPreference(self.showRead, self)

        self._cachedPrefs = dict(preferredMimeType=pmt,
                                 preferredMessageDisplay=pmd,
                                 showRead=showRead)

    # IPreferenceCollection
    def getPreferences(self):
        return self._cachedPrefs

    def setPreferenceValue(self, pref, value):
        # this ugliness is short lived
        assert hasattr(self, pref.key)
        setattr(pref, 'value', value)
        setattr(self, pref.key, value)

    def getSections(self):
        # XXX This is wrong because it is backwards.  This class cannot be
        # responsible for looking for every item that might exist in the
        # database and want to provide configuration, because plugins make it
        # impossible for this class to ever have a complete list of such items.
        # Instead, items need to act as plugins for something so that there
        # mere existence in the database causes them to show up for
        # configuration.
        sections = []
        for cls in GrabberConfiguration, spam.Filter:
            item = self.store.findUnique(cls, default=None)
            if item is not None:
                sections.append(item)
        if sections:
            return sections
        return None
