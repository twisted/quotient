
from zope.interface import implements

from nevow.page import renderer

from xmantissa import ixmantissa, scrolltable, webtheme

from xquotient import exmess


class SearchAggregatorFragment(webtheme.ThemedElement):
    implements(ixmantissa.INavigableFragment)

    jsClass = u'Mantissa.Search.Search'

    fragmentName = 'search'


    def __init__(self, searchResults, store):
        super(SearchAggregatorFragment, self).__init__()
        self.searchResults = searchResults
        self.store = store


    def head(self):
        return None


    def search(self, ctx, data):
        f = scrolltable.StoreIDSequenceScrollingFragment(
            self.store,
            self.searchResults,
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
