# -*- test-case-name: xquotient.test.test_mimepart -*-

from epsilon.extime import Time

from axiom import item, attributes

from xquotient import mimepart, equotient, mimeutil, exmess, extract, iquotient
from xquotient.indexinghelp import SyncIndexer

import quopri, binascii

class Header(item.Item):
    typeName = 'quotient_mime_header'
    schemaVersion = 1

    message = attributes.reference(
        "A reference to the stored top-level L{xquotient.exmess.Message} "
        "object to which this header pertains.")
    part = attributes.reference(
        "A reference to the stored MIME part object to which this header "
        "directly pertains.")

    name = attributes.text(
        "The name of this header.  What it is called.",
        allowNone=False)
    value = attributes.bytes(
        "The encoded value of this header.",
        allowNone=False)
    index = attributes.integer(
        "The position of this header within a part.",
        allowNone=False)

class Part(item.Item):
    typeName = 'quotient_mime_part'
    schemaVersion = 1

    parent = attributes.reference(
        "A reference to another Part object, or None for the top-level part.")
    message = attributes.reference(
        "A reference to the stored top-level L{xquotient.exmess.Message} "
        "object to which this part pertains.")
    partID = attributes.integer(
        "A unique identifier for this Part within the context of its L{message}.")

    source = attributes.path(
        "The file which contains this part, MIME-encoded.")

    headersOffset = attributes.integer(
        "The byte offset within my source file where my headers begin.")
    headersLength = attributes.integer(
        "The length in bytes that all my headers consume within the source file.")
    bodyOffset = attributes.integer(
        "The byte offset within my source file where my body begins (4 bytes "
        "after where my headers end).")
    bodyLength = attributes.integer(
        "The length in bytes that my body consumes within the source file.")


    _partCounter = attributes.inmemory(
        "Temporary Part-ID factory function used to assign IDs to parts "
        "of this message.")
    _headers = attributes.inmemory(
        "Temporary storage for header data before this Part is added to "
        "a database.")
    _children = attributes.inmemory(
        "Temporary storage for child parts before this Part is added to "
        "a database.")

    def addHeader(self, name, value):
        if self.store is not None:
            raise NotImplementedError(
                "Don't add headers to in-database messages - they aren't mutable [yet?]")
        if not hasattr(self, '_headers'):
            self._headers = []
        self._headers.append(Header(name=name.lower().decode('ascii'),
                                    value=value,
                                    part=self,
                                    message=self.message,
                                    index=len(self._headers)))

    def walk(self):
        # this depends on the order the parts are returned by the query
        yield self
        for child in self.store.query(Part, Part.parent == self):
            for grandchild in child.walk():
                yield grandchild

    def getSubPart(self, partID):
        return self.store.findUnique(Part,
                attributes.AND(Part.parent==self,
                               Part.partID==partID))

    def getHeader(self, name):
        for hdr in self.getHeaders(name, _limit=1):
            return hdr.value
        raise equotient.NoSuchHeader(name)

    def getHeaders(self, name, _limit=None):
        name = name.lower()
        if self.store is not None:
            return self.store.query(
                Header,
                attributes.AND(Header.part == self,
                               Header.name == name),
                sort=Header.index.ascending,
                limit=_limit)
        else:
            if not hasattr(self, '_headers'):
                self._headers = []
            return (hdr for hdr in self._headers if hdr.name == name)

    def getAllHeaders(self):
        if self.store is not None:
            return self.store.query(
                Header,
                Header.part == self,
                sort=Header.index.ascending)
        else:
            if hasattr(self, '_headers'):
                return iter(self._headers)
            else:
                return iter(())

    def newChild(self):
        if self.store is not None:
            raise NotImplementedError(
                "Don't add children to in-database messages - they aren't mutable [yet?]")
        if not hasattr(self, '_children'):
            self._children = []
        p = Part(partID=self._partCounter(),
                 source=self.source,
                 _partCounter=self._partCounter)
        self._children.append(p)
        return p


    def _addToStore(self, store, message, sourcepath):
        self.source = sourcepath
        self.message = message
        self.store = store

        if self.parent is None:
            assert self.message.impl is None, "two top-level parts?!"
            self.message.impl = self

        if hasattr(self, '_headers'):
            for hdr in self._headers:
                hdr.part = self
                hdr.message = self.message
                hdr.store = store

        if hasattr(self, '_children'):
            for child in self._children:
                child.parent = self
                child._addToStore(store, message, sourcepath)

        if self.parent is None:
            message.attachments = len(list(self.walkAttachments()))
            extract.extract(message)
            store.findUnique(SyncIndexer).indexMessage(message)

        del self._headers, self._children

    # implementation of IMessageIterator

    def getContentType(self, default=None):
        try:
            value = self.getHeader(u'content-type')
        except equotient.NoSuchHeader:
            return default

        ctype = value.split(';', 1)[0].lower().strip()
        if ctype.count('/') != 1:
            return default
        return ctype

    def getParam(self, param, default=None, header=u'content-type', un_quote=True):
        try:
            h = self.getHeader(header)
        except equotient.NoSuchHeader:
            return default
        param = param.lower()
        for pair in [x.split('=', 1) for x in h.split(';')[1:]]:
            if pair[0].strip().lower() == param:
                r = len(pair) == 2 and pair[1].strip() or ''
                if un_quote:
                    return mimepart.unquote(r)
                return r
        return default

    def getContentTransferEncoding(self, default=None):
        """
        @returns: string like 'base64', 'quoted-printable' or '7bit'
        """
        try:
            ctran = self.getHeader(u'content-transfer-encoding')
        except equotient.NoSuchHeader:
            return default

        if ctran:
            ct = ctran.lower().strip()
            return ct
        return default

    def getBody(self, decode=False):
        f = self.source.open()
        offt = self.bodyOffset
        leng = self.bodyLength
        f.seek(offt)
        data = f.read(leng)
        if decode:
            ct = self.getContentTransferEncoding()
            if ct == 'quoted-printable':
                return quopri.decodestring(data)
            elif ct == 'base64':
                for extraPadding in ('', '=', '=='):
                    try:
                        return (data + extraPadding).decode('base64')
                    except binascii.Error:
                        pass
                return data
            elif ct == '7bit':
                return data
        return data

    def getUnicodeBody(self, default='utf-8'):
        """Get the payload of this part as a unicode object."""
        charset = self.getParam('charset', default=default)
        payload = self.getBody(decode=True)

        try:
            return unicode(payload, charset, 'replace')
        except LookupError:
            return unicode(payload, default, 'replace')

    def getTypedParts(self, *types):
        for part in self.walk():
            if part.getContentType() in types:
                yield part

    def walkMessage(self, prefer): # XXX RENAME ME
        """
        Return an iterator of Paragraph, Extract, and Embedded instances for
        this part of the message.
        """
        ctype = self.getContentType(default='text/plain')
        if ctype.startswith('multipart'):
            args = (prefer,)
        else:
            args = ()

        methodName = 'iterate_'+ctype.replace('/', '_')
        method = getattr(self, methodName, None)
        if method is None:
            assert False, 'no method for content type: %r' % (ctype,)
        else:
            return method(*args)

    def getAttachment(self, partID):
        for part in self.walkAttachments():
            if part.identifier == partID:
                return part

    def walkAttachments(self):
        for part in self.walk():
            try:
                disposition = part.getHeader(u'content-disposition')
            except equotient.NoSuchHeader:
                disposition = ''

            ctyp = part.getContentType()
            if ctyp is not None and (not (ctyp.startswith('text')
                or ctyp.startswith('multipart'))
                    or disposition.startswith('attachment')):

                fname = part.getParam('filename', header=u'content-disposition')
                yield mimepart.AttachmentPart(self.message.storeID,
                                              part.partID, ctyp,
                                              disposition=disposition,
                                              filename=fname,
                                              part=part)
    def iterate_text_plain(self):
        content = self.getUnicodeBody()

        if self.getParam('format') == 'flowed':
            pfactory = mimepart.FlowedParagraph.fromRFC2646
        else:
            pfactory = mimepart.FixedParagraph.fromString

        paragraph = pfactory(content)

        yield mimepart.Part(self.message.storeID, self.partID,
                            self.getContentType(), children=[paragraph],
                            part=self)

    def iterate_text_html(self):
        yield mimepart.HTMLPart(self.message.storeID, self.partID,
                                self.getContentType(),
                                part=self)


    def readableParts(self):
        '''return all parts with a content type of text/*'''
        return (part for part in self.walk()
                    if part.getContentType().startswith('text/'))

    def readablePart(self, prefer):
        '''return one text/* part, preferably of type prefer.  or None'''
        parts = list(self.readableParts())
        if len(parts) == 0:
            return None
        for part in parts:
            if part.getContentType() == prefer:
                return part
        return parts[0]

    def iterate_multipart_alternative(self, prefer):
        part = self.readablePart(prefer)
        if part is not None:
            for child in part.walkMessage(prefer):
                yield child

    def iterate_multipart_mixed(self, prefer):
        # maybe dont shove these all on one page
        for part in self.readableParts():
            for child in part.walkMessage(prefer):
                yield child

class MIMEMessageStorer(mimepart.MIMEMessageReceiver):
    def __init__(self, store, message, *a, **kw):
        super(MIMEMessageStorer, self).__init__(*a, **kw)
        self.store = store
        self.message = message

    def messageDone(self):
        r = super(MIMEMessageStorer, self).messageDone()
        self.message.store = self.store
        self.message.installOn(self.store)
        self.message.received = Time()

        try:
            sent = self.part.getHeader(u'date')
        except equotient.NoSuchHeader:
            sent = None
        else:
            try:
                sent = Time.fromRFC2822(sent)
            except ValueError:
                sent = None
        if sent is None:
            sent = self.message.received
        self.message.sent = sent

        for (attr, headers) in [
            ('recipient', [u'to']),
            ('subject', [u'subject'])]:
            for h in headers:
                try:
                    v = self.part.getHeader(h)
                except equotient.NoSuchHeader:
                    continue
                else:
                    setattr(self.message, attr, mimeutil.headerToUnicode(v))
                    break

        for header in (u'from', u'sender', u'reply-to'):
            try:
                v = self.part.getHeader(header)
            except equotient.NoSuchHeader:
                continue

            email = mimeutil.EmailAddress(v)
            self.message.sender = unicode(email.email)
            self.message.senderDisplay = unicode(email.anyDisplayName())
            break

        for (relation, address) in ((u'sender', self.message.sender),
                                    (u'recipient', self.message.recipient)):

            if address is not None and 0 < len(address):
                exmess.Correspondent(store=self.store,
                                     message=self.message,
                                     relation=relation,
                                     address=address)

        try:
            copied = self.part.getHeader(u'cc')
        except equotient.NoSuchHeader:
            pass
        else:
            for address in mimeutil.parseEmailAddresses(copied):
                exmess.Correspondent(store=self.store,
                                     message=self.message,
                                     relation=u'copy',
                                     address=unicode(address.email))

        self.part._addToStore(self.store, self.message, self.file.finalpath)
        return r

