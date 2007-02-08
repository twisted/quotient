# -*- test-case-name: xquotient.test.test_compose -*-
"""
A collection of functions for getting mail from the UI into the
database and sent via SMTP.
"""
from email import (Parser as P, Generator as G, MIMEMultipart as MMP,
                   MIMEText as MT, MIMEBase as MB,
                   Header as MH, Charset as MC, Utils as EU, Encoders as EE)
import StringIO as S
from xquotient.mimestorage import Part
from twisted.mail import smtp

from xquotient import renderers, mimeutil


def _fileItemToEmailPart(fileItem):
    """
    Convert a L{File} item into an appropriate MIME part object
    understandable by the stdlib's C{email} package
    """
    (majorType, minorType) = fileItem.type.split('/')
    if majorType == 'multipart':
        part = P.Parser().parse(fileItem.body.open())
    else:
        part = MB.MIMEBase(majorType, minorType)
        if majorType == 'message':
            part.set_payload([P.Parser().parse(fileItem.body.open())])
        else:
            part.set_payload(fileItem.body.getContent())
            if majorType == 'text':
                EE.encode_quopri(part)
            else:
                EE.encode_base64(part)
    part.add_header('content-disposition', 'attachment', filename=fileItem.name)
    return part


def createMessage(composer, cabinet, msgRepliedTo, fromAddress,
                  toAddresses, subject, messageBody, cc, bcc, files):
    """
    Create an outgoing message, format the body into MIME parts, and
    populate its headers.
    """
    MC.add_charset('utf-8', None, MC.QP, 'utf-8')

    encode = lambda s: MH.Header(s).encode()

    s = S.StringIO()
    m = MMP.MIMEMultipart(
        'alternative',
        None,
        [MT.MIMEText(messageBody, 'plain', 'utf-8'),
         MT.MIMEText(renderers.textToRudimentaryHTML(messageBody), 'html', 'utf-8')])

    fileItems = []
    if files:
        attachmentParts = []
        for storeID in files:
            a = composer.store.getItemByID(long(storeID))
            if isinstance(a, Part):
                a = cabinet.createFileItem(
                        a.getParam('filename',
                                   default=u'',
                                   header=u'content-disposition'),
                        unicode(a.getContentType()),
                        a.getBody(decode=True))
            fileItems.append(a)
            attachmentParts.append(
                _fileItemToEmailPart(a))

        m = MMP.MIMEMultipart('mixed', None, [m] + attachmentParts)

    m['From'] = encode(fromAddress.address)
    m['To'] = encode(mimeutil.flattenEmailAddresses(toAddresses))
    m['Subject'] = encode(subject)
    m['Date'] = EU.formatdate()
    m['Message-ID'] = smtp.messageid('divmod.xquotient')

    if cc:
        m['Cc'] = encode(mimeutil.flattenEmailAddresses(cc))
    if msgRepliedTo is not None:
        #our parser does not remove continuation whitespace, so to
        #avoid duplicating it --
        refs = [hdr.value for hdr in
                msgRepliedTo.impl.getHeaders("References")]
        if len(refs) == 0:
            irt = [hdr.value for hdr in
                   msgRepliedTo.impl.getHeaders("In-Reply-To")]
            if len(irt) == 1:
                refs = irt
            else:
                refs = []
        msgid = msgRepliedTo.impl.getHeader("Message-ID")
        refs.append(msgid)
        m['References'] = u'\n\t'.join(refs)
        m['In-Reply-To'] = msgid
    G.Generator(s).flatten(m)
    s.seek(0)

    msg = composer.createMessageAndQueueIt(fromAddress.address, s, True)

    # there is probably a better way than this, but there
    # isn't a way to associate the same file item with multiple
    # messages anyway, so there isn't a need to reflect that here
    for fileItem in fileItems:
        fileItem.message = msg
    return msg


def sendMail(_savedDraft, composer, cabinet, parentMessage,
             fromAddress, toAddresses, subject, messageBody, cc, bcc,
             files):
    """
    Construct and send a message over SMTP.
    """
    # overwrite the previous draft of this message with another draft
    _savedDraft = saveDraft(_savedDraft, composer, cabinet,
                      parentMessage, fromAddress, toAddresses,
                      subject, messageBody, cc, bcc, files)

    addresses = [addr.pseudoFormat() for addr in toAddresses + cc + bcc]

    # except we are going to send this draft
    composer.sendMessage(fromAddress, addresses, _savedDraft.message)

    # once the user has sent a message, we'll consider all subsequent
    # drafts in the lifetime of this fragment as being drafts of a
    # different message
    _savedDraft.deleteFromStore()
    return _savedDraft


def saveDraft(_savedDraft, composer, cabinet, parentMessage,
               fromAddress, toAddresses, subject, messageBody, cc,
               bcc, files):
    """
    Construct a message and save it in the database.
    """
    msg = createMessage(composer, cabinet, parentMessage, fromAddress,
                        toAddresses, subject, messageBody, cc, bcc,
                        files)

    if _savedDraft is not None:
        oldmsg = _savedDraft.message
        oldmsg.deleteFromStore()
        _savedDraft.message = msg
        return _savedDraft
    else:
        from xquotient.compose import Draft
        return Draft(store=composer.store, message=msg)

