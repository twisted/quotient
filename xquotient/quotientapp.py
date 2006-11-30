from zope.interface import implements

from axiom.item import Item, declareLegacyItem
from axiom import attributes, scheduler
from axiom.upgrade import (registerAttributeCopyingUpgrader,
                           registerUpgrader)
from axiom.dependency import dependsOn

from xmantissa import website, webapp, ixmantissa, people, prefs, webnav, fulltext

from xquotient import mail, gallery, qpeople, extract, spam, _mailsearchui
from xquotient.exmess import MessageDisplayPreferenceCollection
from xquotient.grabber import GrabberConfiguration


class MessageSearchProvider(Item):
    """
    Wrapper around an ISearchProvider which will hand back search results
    wrapped in a fragment that knows about Messages.
    """
    installedOn = attributes.reference()

    indexer = dependsOn(fulltext.PyLuceneIndexer, doc="""
    The actual fulltext indexing implementation object which will perform
    searches.  The results it returns will be wrapped up in a fragment which
    knows how to display L{exmess.Message} instances.
    """)

    messageSource = dependsOn(mail.MessageSource)
    powerupInterfaces = (ixmantissa.ISearchProvider)

    def installed(self):
        self.indexer.addSource(self.messageSource)
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


class ExtractBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)

    def installOn(self, other):
        other.powerUp(self, ixmantissa.IBenefactor)

class QuotientPeopleBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)

class IndexingBenefactor(Item):
    implements(ixmantissa.IBenefactor)

    endowed = attributes.integer(default=0)



class QuotientPreferenceCollection(Item, prefs.PreferenceCollectionMixin):
    """
    The core Quotient L{xmantissa.ixmantissa.IPreferenceCollection}.  Doesn't
    collect any preferences, but groups some quotient settings related fragments
    """
    implements(ixmantissa.IPreferenceCollection)

    typeName = 'quotient_preference_collection'
    schemaVersion = 3

    installedOn = attributes.reference()

    powerupInterfaces = (ixmantissa.IPreferenceCollection)

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

