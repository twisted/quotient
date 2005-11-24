# -*- test-case-name: xquotient.test.test_mimepart -*-

from zope.interface import implements
from epsilon.extime import Time

from axiom import item, attributes

from xquotient import iquotient, mimepart, equotient, mimeutil

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
                child.message = self.message
                child._addToStore(store, message, sourcepath)
        self.source = sourcepath
        del self._headers, self._children


    # implementation of IMessageIterator

    def _getContentType(self):
        # XXX move this
        try:
            ctype = self.getHeader(u'content-type').split(';')[0].lower().strip()
        except equotient.NoSuchHeader:
            ctype = 'text/plain'
        return ctype

    def walkMessage(self): # XXX RENAME ME
        """
        Return an iterator of Paragraph, Extract, and Embedded instances for
        this part of the message.
        """
        ctype = self._getContentType()
        methodName = 'iterate_'+ctype.replace('/', '_')
        method = getattr(self, methodName, None)
        if method is None:
            assert False
            return () # XXX 'UNKNOWN PART' warning?
        else:
            return method()

    def _getBody(self):
        f = self.source.open()
        f.seek(self.bodyOffset)
        body = f.read(self.bodyLength)
        # XXX decode?
        return body
    body = property(_getBody)

    def iterate_text_plain(self):
        return (self.body,)
        #return splitIntoParagraphs(self.body)

    def iterate_text_html(self):
        return (self.body,)

    def iterate_multipart_alternative(self):
        children = self.walk()
        children.next()

        for part in children:
            if part._getContentType() == 'text/plain':
                return part.walkMessage()

    def iterate_multipart_mixed(self):
        pass

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

        for (attr, headers) in [
            ('sender', [u'from', u'sender', u'reply-to']),
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
        self.part._addToStore(self.store, self.message, self.file.finalpath)
        return r
