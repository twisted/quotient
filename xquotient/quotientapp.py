from zope.interface import implements

from axiom.item import Item, InstallableMixin, declareLegacyItem
from axiom import attributes, scheduler
from axiom.upgrade import (registerAttributeCopyingUpgrader,
                           registerUpgrader)

from xmantissa import website, webapp, ixmantissa, people, prefs, webnav, fulltext

from xquotient import inbox, mail, gallery, qpeople, extract, spam, _mailsearchui
from xquotient.exmess import MessageDisplayPreferenceCollection
from xquotient.grabber import GrabberConfiguration


INDEXER_TYPE = fulltext.PyLuceneIndexer


class MessageSearchProvider(Item, InstallableMixin):
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


    def search(self, *a, **k):
        if 'sortAscending' not in k:
            k['sortAscending'] = False
        d = self.indexer.search(*a, **k)
        d.addCallback(_mailsearchui.SearchAggregatorFragment, self.store)
        return d



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
        avatar.findOrCreate(MessageDisplayPreferenceCollection).installOn(avatar)

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



class QuotientPreferenceCollection(Item, InstallableMixin, prefs.PreferenceCollectionMixin):
    """
    The core Quotient L{xmantissa.ixmantissa.IPreferenceCollection}.  Doesn't
    collect any preferences, but groups some quotient settings related fragments
    """
    implements(ixmantissa.IPreferenceCollection)

    typeName = 'quotient_preference_collection'
    schemaVersion = 3

    installedOn = attributes.reference()

    def installOn(self, other):
        super(QuotientPreferenceCollection, self).installOn(other)
        other.powerUp(self, ixmantissa.IPreferenceCollection)

    def getPreferenceParameters(self):
        return ()

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

    def getTabs(self):
        return (webnav.Tab('Mail', self.storeID, 0.0),)

registerAttributeCopyingUpgrader(QuotientPreferenceCollection, 1, 2)

declareLegacyItem(QuotientPreferenceCollection.typeName, 2,
                  dict(installedOn=attributes.reference(),
                       preferredMimeType=attributes.text(),
                       preferredMessageDisplay=attributes.text(),
                       showRead=attributes.boolean(),
                       showMoreDetail=attributes.boolean()))

def quotientPreferenceCollection2To3(old):
    """
    Remove the preference attributes of
    L{xquotient.quotientapp.QuotientPreferenceCollection}, and install
    a L{xquotient.exmess.MessageDisplayPreferenceCollection}, because
    the attributes have either been moved there, or removed entirely
    """
    MessageDisplayPreferenceCollection(
        store=old.store,
        preferredFormat=old.preferredMimeType).installOn(old.store)

    return old.upgradeVersion('quotient_preference_collection', 2, 3,
                              installedOn=old.installedOn)

registerUpgrader(quotientPreferenceCollection2To3, 'quotient_preference_collection', 2, 3)
