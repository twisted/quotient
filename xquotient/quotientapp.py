from zope.interface import implements

from axiom.item import Item, InstallableMixin
from axiom import iaxiom, attributes, scheduler

from xmantissa import website, webapp, ixmantissa, people, prefs
from xmantissa import fulltext, search

from xquotient import inbox, mail, gallery, qpeople, extract, spam, _mailsearchui
from xquotient.grabber import GrabberConfiguration


INDEXER_TYPE = fulltext.PyLuceneIndexer


class MessageSearchProvider(Item, InstallableMixin, search.SearchProviderMixin):
    """
    Wrapper around an ISearchProvider which will hand back search results
    wrapped in a fragment that knows about Messages.
    """
    installedOn = attributes.reference()

    indexer = attributes.reference(doc="""
    The actual fulltext indexing implementation object which will perform
    searches.  The results it returns will be wrapped up in a fragment which
    knows how to display L{exmess.Message} instances.
    """, allowNone=False)


    def installOn(self, other):
        super(MessageSearchProvider, self).installOn(other)
        other.powerUp(self, ixmantissa.ISearchProvider)


    def count(self, term):
        raise NotImplementedError("No one should ever call count, I think.")


    def wrapSearchResults(self, searchIdentifier):
        return _mailsearchui.SearchAggregatorFragment(searchIdentifier, self.store)




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

        avatar.findOrCreate(mail.MessageSource)

        avatar.findOrCreate(spam.Filter).installOn(avatar)

        avatar.findOrCreate(QuotientPreferenceCollection).installOn(avatar)

        avatar.findOrCreate(inbox.Inbox).installOn(avatar)


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



class IndexingBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)


    def endow(self, ticket, avatar):
        messageSource = avatar.findUnique(mail.MessageSource)
        indexer = avatar.findOrCreate(INDEXER_TYPE)
        indexer.addSource(messageSource)
        searcher = MessageSearchProvider(store=avatar, indexer=indexer)
        searcher.installOn(avatar)


    def revoke(self, ticket, avatar):
        avatar.findUnique(MessageSearchProvider).deleteFromStore()



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
