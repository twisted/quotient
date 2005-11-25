from xmantissa import webtheme
from nevow import tags

class QuotientTheme(webtheme.XHTMLDirectoryTheme):
    def head(self):
        yield tags.link(href='/static/quotient/quotient.css',
                        rel='stylesheet', type='text/css')
        yield tags.script(src='/static/quotient/quotient.js',
                          type='text/javascript')
