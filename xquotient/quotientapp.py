from zope.interface import implements

from axiom.item import Item, InstallableMixin
from axiom import attributes

from xmantissa import website, webapp, ixmantissa, people, prefs, search

from xquotient import inbox, exmess, mail, gallery, compose, qpeople
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
        return len(self.indexer.search(term))

    def search(self, term, count, offset):
        translator = ixmantissa.IWebTranslator(self.store)
        for (i, document) in enumerate(self.indexer.search(term, count, offset)):
            msg = self.store.getItemByID(long(document['@uri']))

            yield search.SearchResult(description=msg.subject,
                                      url=translator.linkTo(msg.storeID),
                                      summary=document.text[:200],
                                      timestamp=msg.sent,
                                      score=0)
class QuotientBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    typeName = 'quotient_benefactor'
    schemaVersion = 1

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)

    def endow(self, ticket, avatar):
        avatar.findOrCreate(website.WebSite).installOn(avatar)
        avatar.findOrCreate(webapp.PrivateApplication).installOn(avatar)
        avatar.findOrCreate(mail.MailTransferAgent).installOn(avatar)
        avatar.findOrCreate(QuotientPreferenceCollection).installOn(avatar)

        avatar.findOrCreate(people.AddPerson).installOn(avatar)

        organizer = avatar.findOrCreate(people.Organizer)
        organizer.installOn(avatar)

        avatar.findOrCreate(qpeople.MessageLister).installOn(organizer)
        avatar.findOrCreate(qpeople.ImageLister).installOn(organizer)
        avatar.findOrCreate(qpeople.ExtractLister).installOn(organizer)

        avatar.findOrCreate(inbox.Inbox).installOn(avatar)
        avatar.findOrCreate(inbox.Archive).installOn(avatar)
        avatar.findOrCreate(inbox.Trash).installOn(avatar)

        avatar.findOrCreate(gallery.Gallery).installOn(avatar)
        avatar.findOrCreate(gallery.ThumbnailDisplayer).installOn(avatar)

        avatar.findOrCreate(compose.Composer).installOn(avatar)

        avatar.findOrCreate(exmess.MessagePartView).installOn(avatar)

        avatar.findOrCreate(SyncIndexer)
        avatar.findOrCreate(QuotientSearchProvider).installOn(avatar)

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

    schemaVersion = 1
    typeName = 'quotient_preference_collection'

    name = 'Email Preferences'

    preferredMimeType = attributes.text(default=u'text/plain')
    preferredMessageDisplay = attributes.text(default=u'split')
    showRead = attributes.boolean(default=True)

    installedOn = attributes.reference()
    _cachedPrefs = attributes.inmemory()

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

