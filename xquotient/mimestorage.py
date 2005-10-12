
from axiom import item, attributes

class Header(item.Item):
    typeName = 'quotient_mime_header'
    schemaVersion = 1

    message = attributes.reference(
        "A reference to the stored top-level L{xquotient.exmess.Message} "
        "object to which this header pertains.",
        allowNone=False)
    part = attributes.reference(
        "A reference to the stored MIME part object to which this header "
        "directly pertains.",
        allowNone=False)
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

    headerOffset = attributes.integer(
        "The byte offset within my source file where my headers begin.")
    bodyOffset = attributes.integer(
        "The byte offset within my source file where my body begins (4 bytes "
        "after where my headers end).")
    bodyLength = attributes.integer(
        "The length in bytes that my body consumes within the source file.")


    _headers = attributes.inmemory(
        "Temporary storage for header data before this Part is added to "
        "a database.")

    def addHeader(self, name, value):
        if self.store is not None:
            raise NotImplementedError(
                "Don't add headers to in-database messages - they aren't mutable [yet?]")
        if not hasattr(self, '_headers'):
            self._headers = []
        self._headers.append(Header(name=name.lower(),
                                    value=value,
                                    part=self,
                                    message=self.message,
                                    index=len(self._headers)))

    def getHeader(self, name):
        name = name.lower()
        if self.store is None:
            for hdr in self._headers:
                if hdr.name == name:
                    return hdr.value
            raise equotient.NoSuchHeader(
