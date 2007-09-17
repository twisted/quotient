# -*- test-case-name: xquotient.test.test_theme -*-

from nevow import tags

from xmantissa import webtheme

class QuotientTheme(webtheme.XHTMLDirectoryTheme):
    def head(self, request, website):
        root = website.rootURL(request)
        static = root.child('Quotient').child('static')
        return tags.link(
            rel='stylesheet',
            type='text/css',
            href=static.child('quotient.css'))
