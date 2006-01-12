from xmantissa import webtheme
from nevow import tags

class QuotientTheme(webtheme.XHTMLDirectoryTheme):
    def head(self):
        return tags.link(href='/Quotient/static/quotient.css',
                         rel='stylesheet', type='text/css')
