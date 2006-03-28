from twisted.python import filepath
from nevow import athena

import xquotient

jsdir = filepath.FilePath(xquotient.__file__).parent().child('static').child('js')

quotient = athena.JSPackage({
    u'Quotient': jsdir.child('quotient.js').path,
    u'Quotient.Common':  jsdir.child('common.js').path,
    u'Quotient.Mailbox': jsdir.child('mailbox.js').path,
    u'Quotient.Compose': jsdir.child('compose.js').path,
    u'Quotient.Gallery': jsdir.child('gallery.js').path,
    u'Quotient.Grabber': jsdir.child('grabber.js').path,
    u'Quotient.Filter': jsdir.child('filter.js').path,

    u'NiftyCorners': jsdir.child('nifty-corners').child('niftycube.js').path,
    u'LightBox': jsdir.child('lightbox.js').path,
})
