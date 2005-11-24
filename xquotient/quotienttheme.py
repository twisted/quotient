from xmantissa import webtheme
from nevow import tags

class QuotientTheme(webtheme.XHTMLDirectoryTheme):
    def head(self):
        return tags.link(href='/static/quotient/quotient.css',
                         rel='stylesheet', type='text/css')
