import re

from zope.interface import implements

from nevow import tags

from epsilon.extime import Time

from axiom.item import Item, InstallableMixin
from axiom import attributes

from xquotient import iquotient
from xquotient.gallery import Image, makeThumbnail
from xquotient.exmess import Message

def extractImages(message):
    for attachment in message.walkAttachments():
        if attachment.type.startswith('image/'):
            thumbdir = message.store.newDirectory('thumbnails')
            if not thumbdir.exists():
                thumbdir.makedirs()

            basename = (str(attachment.messageID)
                            + '-' + str(attachment.identifier))

            # TODO pass attachment.part.source to image magick
            imgdata = attachment.part.getBody(decode=True)
            thumbf = thumbdir.child(basename)
            makeThumbnail(imgdata, thumbf.path)

            Image(part=attachment.part,
                  thumbnailPath=thumbf,
                  message=message,
                  mimeType=unicode(attachment.type),
                  store=message.store)

# the idea with extraction is that we only store an extract
# once per sender.  so if you import the last 5 years worth
# of bugtraq daily message digests, and each one ends with a
# long sig listing a bunch of email addresses, we we will
# only store each unique address once so they at least show up in
# the extracts-per-person view.  highlighting the extracts
# per message will be done by client-side code.

class SimpleExtractMixin(object):

    def installOn(self, other):
        super(SimpleExtractMixin, self).installOn(other)
        other.powerUp(self, iquotient.IExtract)

    # a lot of class methods. though it is less weird this way i think

    def findExisting(cls, message, extractedText):
        return message.store.findUnique(cls,
                        attributes.AND(cls.text == extractedText,
                                       cls.message == Message.storeID,
                                       Message.sender == message.sender),
                        default=None)

    findExisting = classmethod(findExisting)

    def worthStoring(message, extractedText):
        return True

    worthStoring = staticmethod(worthStoring)

    def extract(cls, message):
        for part in message.impl.getTypedParts('text/plain'):
            for match in cls.regex.finditer(part.getUnicodeBody()):
                (start, end) = match.span()
                extractedText = match.group()

                if cls.worthStoring(message, extractedText):
                    existing = cls.findExisting(message, extractedText)
                    if existing is not None:
                        existing.installedOn.powerDown(existing, iquotient.IExtract)
                        existing.deleteFromStore()

                    cls(message=message,
                        timestamp=Time(),
                        text=extractedText,
                        start=start,
                        end=end,
                        store=message.store).installOn(part)

    extract = classmethod(extract)

    def inContext(self, chars=30):
        text = self.installedOn.getUnicodeBody()
        (start, end) = (self.start, self.end)

        return (text[start-chars:start],
                self.asStan(),
                text[end:end+chars])

class URLExtract(SimpleExtractMixin, Item, InstallableMixin):
    implements(iquotient.IExtract)

    typeName = 'quotient_url_extract'
    schemaVersion = 1

    start = attributes.integer()
    end = attributes.integer()
    text = attributes.text()

    message = attributes.reference()
    timestamp = attributes.timestamp()

    installedOn = attributes.reference()

    actedUpon = attributes.boolean(default=False)
    ignored = attributes.boolean(default=False)

    regex = re.compile(ur'(?:\w+:\/\/|www\.)[^\s\<\>\'\(\)\"]+[^\s\<\>\(\)\'\"\?\.]',
                       re.UNICODE | re.IGNORECASE)

    def asStan(self):
        return tags.a(href=self.text)[self.text]


class PhoneNumberExtract(SimpleExtractMixin, Item, InstallableMixin):
    implements(iquotient.IExtract)

    typeName = 'quotient_phone_number_extract'
    schemaVersion = 1

    start = attributes.integer()
    end = attributes.integer()
    text = attributes.text()

    message = attributes.reference()
    timestamp = attributes.timestamp()

    installedOn = attributes.reference()

    actedUpon = attributes.boolean(default=False)
    ignored = attributes.boolean(default=False)

    regex = re.compile(ur'%(area)s%(body)s%(extn)s' % dict(area=r'(?:(?:\(?\d{3}\)?[-.\s]?|\d{3}[-.\s]))?',
                                                         body=r'\d{3}[-.\s]\d{4}',
                                                         extn=r'(?:\s?(?:ext\.?|\#)\s?\d+)?'),
                       re.UNICODE | re.IGNORECASE)

    def asStan(self):
        return tags.b[self.text]

class EmailAddressExtract(SimpleExtractMixin, Item, InstallableMixin):
    implements(iquotient.IExtract)

    typeName = 'quotient_email_address_extract'
    schemaVersion = 1

    start = attributes.integer()
    end = attributes.integer()
    text = attributes.text()

    message = attributes.reference()
    timestamp = attributes.timestamp()

    installedOn = attributes.reference()

    actedUpon = attributes.boolean(default=False)
    ignored = attributes.boolean(default=False)

    regex = re.compile(ur'[\w\-\.]+@(?:[a-z0-9-]+\.)+[a-z]+',
                       re.UNICODE | re.IGNORECASE)

    def worthStoring(message, extractedText):
        return not message.sender == extractedText

    worthStoring = staticmethod(worthStoring)

    def asStan(self):
        return tags.b[self.text]

extractTypes = {'url': URLExtract,
                'phone number': PhoneNumberExtract,
                'email address': EmailAddressExtract}

def extract(message):
    extractImages(message)

    for et in extractTypes.itervalues():
        et.extract(message)
