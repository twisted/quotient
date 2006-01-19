from twisted.python import filepath
from nevow import athena

import xquotient

jsdir = filepath.FilePath(xquotient.__file__).parent().child('static').child('js')

quotient = athena.JSPackage({
    u'Quotient.Common':  jsdir.child('common.js').path,
    u'Quotient.Mailbox': jsdir.child('quotient.js').path,
    u'Quotient.Compose': jsdir.child('compose.js').path,
    u'Quotient.Gallery': jsdir.child('gallery.js').path,
    u'LightBox': jsdir.child('lightbox.js').path
})
