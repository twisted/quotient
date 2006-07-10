
from zope.interface import implements

from nevow import inevow
from nevow.page import renderer

from axiom import attributes

from xmantissa import ixmantissa, scrolltable, search, webtheme

from xquotient import exmess


class SearchAggregatorFragment(webtheme.ThemedElement):
    implements(ixmantissa.INavigableFragment)

    jsClass = u'Mantissa.Search.Search'

    fragmentName = 'search'
    title = ''

    def __init__(self, searchIdentifier, store):
        super(SearchAggregatorFragment, self).__init__()
        self.store = store
        self.searchIdentifier = searchIdentifier


    def head(self):
        return None


    def search(self, ctx, data):
        f = scrolltable.ScrollingFragment(
            self.store,
            exmess.Message,
            attributes.AND(
                search.SearchResult.identifier == self.searchIdentifier,
                search.SearchResult.indexedItem == exmess.Message.storeID),
            (exmess.Message.senderDisplay,
             exmess.Message.subject,
             exmess.Message.receivedWhen,
             exmess.Message.read),
            defaultSortColumn=exmess.Message.receivedWhen,
            defaultSortAscending=False)
        f.jsClass = u'Quotient.Search.SearchResults'
        f.setFragmentParent(self)
        f.docFactory = webtheme.getLoader(f.fragmentName)
        return f
    renderer(search)
