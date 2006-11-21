# -*- test-case-name: xquotient.test.test_theme -*-
from xmantissa import webtheme
from nevow import tags

class QuotientTheme(webtheme.XHTMLDirectoryTheme):
    def head(self, req, website):
        root = website.encryptedRoot(req.getHeader('host'))
        static = root.child('Quotient').child('static')
        return tags.link(
            rel='stylesheet',
            type='text/css',
            href=static.child('quotient.css'))
