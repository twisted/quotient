# -*- test-case-name: xquotient.test.test_inbox -*-
from datetime import timedelta
from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags, inevow, athena
from nevow.flat import flatten

from epsilon.extime import Time

from axiom.item import Item, InstallableMixin
from axiom.tags import Tag
from axiom import attributes

from xmantissa import ixmantissa, webnav, people
from xmantissa.fragmentutils import dictFillSlots
from xmantissa.publicresource import getLoader
from xmantissa.scrolltable import ScrollingFragment

from xquotient.exmess import Message
from xquotient import mimepart, equotient, compose

#_entityReference = re.compile('&([a-z]+);', re.I)

def quoteBody(m, maxwidth=78):
    for part in m.walkMessage(prefer='text/plain'):
        if part.type is None or part.type == 'text/plain':
            break
    else:
        return ''

    format = part.part.getParam('format')
    payload = part.part.getUnicodeBody()
    if format == 'flowed':
        para = mimepart.FlowedParagraph.fromRFC2646(payload)
    else:
        para = mimepart.FixedParagraph.fromString(payload)
    newtext = para.asRFC2646(maxwidth-2).split('\r\n')

    return [ '\n>'.join(newtext) ]

def reSubject(m, pfx='Re: '):
    newsubject = m.subject
    if not newsubject.lower().startswith(pfx.lower()):
        newsubject = pfx + newsubject
    return newsubject

def replyTo(m):
    try:
        recipient = m.impl.getHeader(u'reply-to')
    except equotient.NoSuchHeader:
        recipient = m.sender
    return recipient

class AddPersonFragment(people.AddPersonFragment):
    jsClass = 'Quotient.Common.AddPerson'

    iface = allowedMethods = dict(getPersonHTML=True)
    lastPerson = None

    def makePerson(self, nickname):
        person = super(AddPersonFragment, self).makePerson(nickname)
        self.lastPerson = person
        return person

    def getPersonHTML(self):
        # come up with a better way to identify people.
        # i kind of hate that we have to do this at all, it's really, really ugly.
        # once we have some kind of history thing set up, we should just
        # reload the page instead of dousing ourselves with petrol
        # and jumping through flaming hoops
        assert self.lastPerson is not None
        personFrag = people.PersonFragment(self.lastPerson)
        return unicode(flatten(personFrag), 'utf-8')

class Archive(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_archive'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Archive, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('All Mail', self.storeID, 0.3)],
                authoritative=False)]

def archiveScreen(archiveItem):
    inbox = archiveItem.store.findUnique(Inbox)
    inboxScreen = ixmantissa.INavigableFragment(inbox)
    inboxScreen.inArchiveView = True
    return inboxScreen

registerAdapter(archiveScreen, Archive, ixmantissa.INavigableFragment)

class SentMail(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_sent_mail'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(SentMail, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Sent Mail', self.storeID, 0.15)],
                authoritative=False)]

def sentMailScreen(sentMailItem):
    inbox = sentMailItem.store.findUnique(Inbox)
    inboxScreen = ixmantissa.INavigableFragment(inbox)
    inboxScreen.inSentMailView = True
    return inboxScreen

registerAdapter(sentMailScreen, SentMail, ixmantissa.INavigableFragment)

class Trash(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_trash'
    schemaVersion = 1

    installedOn = attributes.reference()

    def installOn(self, other):
        super(Trash, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Trash', self.storeID, 0.2)],
                authoritative=False)]

def trashScreen(trashItem):
    inbox = trashItem.store.findUnique(Inbox)
    inboxScreen = ixmantissa.INavigableFragment(inbox)
    inboxScreen.inTrashView = True
    return inboxScreen

registerAdapter(trashScreen, Trash, ixmantissa.INavigableFragment)

class Inbox(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_inbox'
    schemaVersion = 1

    installedOn = attributes.reference()

    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.6, children=
                    [webnav.Tab('Inbox', self.storeID, 0.4)],
                authoritative=True)]

    def installOn(self, other):
        super(Inbox, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

class InboxScreen(athena.LiveFragment):
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'inbox'
    live = 'athena'
    title = ''
    jsClass = 'Quotient.Mailbox.Controller'

    inArchiveView = False
    inTrashView = False
    inSentMailView = False
    currentMessage = None

    viewingByTag = None
    viewingByAccount = None

    translator = None

    iface = allowedMethods = dict(deleteCurrentMessage=True,
                                  archiveCurrentMessage=True,
                                  deferCurrentMessage=True,
                                  replyToCurrentMessage=True,
                                  forwardCurrentMessage=True,
                                  getMessageCount=True,

                                  fastForward=True,

                                  viewByTag=True,
                                  viewByPerson=True)

    def __init__(self, original):
        athena.LiveFragment.__init__(self, original)
        self.prefs = ixmantissa.IPreferenceAggregator(original.store)
        self.showRead = self.prefs.getPreferenceValue('showRead')
        self.translator = ixmantissa.IWebTranslator(original.store)

        self._resetCurrentMessage()

    def _resetCurrentMessage(self):
        self.currentMessage = self._getNextMessage()
        if self.currentMessage is not None:
            self.currentMessage.read = True
            self.nextMessage = self._getNextMessage(self.currentMessage.receivedWhen)
        else:
            self.nextMessage = None

    def _getNextMessage(self, after=None, before=None):
        comparison = self._getBaseComparison()
        sort = Message.receivedWhen.desc
        if after is not None:
            comparison = attributes.AND(comparison, Message.receivedWhen < after)
        if before is not None:
            comparison = attributes.AND(comparison, before < Message.receivedWhen)
            sort = Message.receivedWhen.asc

        return self.original.store.findFirst(Message,
                                             comparison,
                                             default=None,
                                             sort=sort)

    def _currentAsFragment(self):
        if self.currentMessage is None:
            return ''
        f = ixmantissa.INavigableFragment(self.currentMessage)
        f.setFragmentParent(self)
        self.currentMessageDetail = f
        return f

    def render_messageDetail(self, ctx, data):
        return self._currentAsFragment()

    def render_addPersonFragment(self, ctx, data):
        # the person form is a fair amount of html,
        # so we'll only include it once

        self.addPersonFragment = AddPersonFragment(self.original)
        self.addPersonFragment.setFragmentParent(self)
        self.addPersonFragment.docFactory = getLoader(self.addPersonFragment.fragmentName)
        return self.addPersonFragment

    def render_scroller(self, ctx, data):
        f = ScrollingFragment(self.original.store,
                              Message,
                              self._getBaseComparison(),
                              [u'senderDisplay', u'subject', u'receivedWhen', u'read', u'sentWhen'],
                              defaultSortColumn=Message.receivedWhen)
        f.resort('receivedWhen')
        f.jsClass = 'Quotient.Mailbox.ScrollingWidget'
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        self.scrollingFragment = f
        return f

    def getTags(self):
        tags = self.original.store.query(Tag,
                            attributes.AND(Tag.object == Message.storeID,
                                           self._getBaseComparison()))
        return list(tags.getColumn('name').distinct())

    def render_tagChooser(self, ctx, data):
        select = inevow.IQ(self.docFactory).onePattern('tagChooser')
        option = inevow.IQ(select).patternGenerator('tagChoice')
        for tag in [None] + self.getTags():
            opt = option().fillSlots('tagName', tag or 'All')
            if tag == self.viewingByTag:
                opt(selected="selected")
            select[opt]
        return select

    def _accountNames(self):
        return self.original.store.query(Message).getColumn("source").distinct()

    def render_accountChooser(self, ctx, data):
        select = inevow.IQ(self.docFactory).onePattern('accountChooser')
        option = inevow.IQ(select).patternGenerator('accountChoice')
        for acc in [None] + list(self._accountNames()):
            opt = option().fillSlots('accountName', acc or 'All')
            if acc == self.viewingByAccount:
                opt(selected="selected")
            select[opt]
        return select

    def _nextMessagePreview(self):
        if self.currentMessage is None:
            return u'No more messages'
        onePattern = inevow.IQ(self.docFactory).onePattern
        if self.nextMessage is None:
            return onePattern('last-message')
        m = self.nextMessage
        return dictFillSlots(onePattern('next-message'),
                             dict(sender=m.senderDisplay,
                                  subject=m.subject,
                                  date=m.sentWhen.asHumanly()))

    def render_nextMessagePreview(self, ctx, data):
        return self._nextMessagePreview()

    def head(self):
        return tags.link(rel='stylesheet', type='text/css',
                         href='/Quotient/static/reader.css')

    # remote methods

    def fastForward(self, webID):
        self.currentMessage = self.translator.fromWebID(webID)
        self.currentMessage.read = True
        self.nextMessage = self._getNextMessage(self.currentMessage.receivedWhen)
        return self._current()

    def _resetScrollQuery(self):
        self.scrollingFragment.baseConstraint = self._getBaseComparison()

    def viewByTag(self, tag):
        self.viewingByTag = tag
        self._resetCurrentMessage()
        self._resetScrollQuery()
        return (self.getMessageCount(), self._current())

    def viewByAccount(self, account):
        self.viewingByAccount = account
        self._resetCurrentMessage()
        self._resetScrollQuery()
        return (self.getMessageCount(), self._current())

    def getMessageCount(self):
        return self.original.store.count(Message, self._getBaseComparison())

    def _squish(self, thing):
        # replacing &nbsp with &#160 in webmail.SpacePreservingStringRenderer
        # fixed all issues with calling setNodeContent on flattened message
        # details for all messages in the test pool.  but there might be
        # other things that will break also.

        #for eref in set(_entityReference.findall(text)):
        #    entity = getattr(entities, eref, None)
        #    if entity is not None:
        #        text = text.replace('&' + eref + ';', '&#' + entity.num + ';')
        return unicode(flatten(thing), 'utf-8')

    def _current(self):
        return (self._squish(self._nextMessagePreview()),
                self._squish(self._currentAsFragment()))

    def _moveToNextMessage(self):
        previousMessage = self.currentMessage
        self.currentMessage = self.nextMessage

        if self.currentMessage is not None:
            self.currentMessage.read = True
            self.nextMessage = self._getNextMessage(self.currentMessage.receivedWhen)
        else:
            self.currentMessage = self._getNextMessage(before=previousMessage.receivedWhen)
            self.nextMessage = None

    def deleteCurrentMessage(self):
        self.currentMessage.deleted = True
        self._moveToNextMessage()
        return self._current()

    def archiveCurrentMessage(self):
        self.currentMessage.archived = True
        self._moveToNextMessage()
        return self._current()

    def deferCurrentMessage(self, days, hours, minutes):
        self.currentMessage.receivedWhen = Time() + timedelta(days=days,
                                                              hours=hours,
                                                              minutes=minutes)
        self.currentMessage.read = False
        self._moveToNextMessage()
        return self._current()

    def _composeSomething(self, toAddress, subject, messageBody, attachments=()):
        composer = self.original.store.findUnique(compose.Composer)
        cf = compose.ComposeFragment(composer,
                                     toAddress=toAddress,
                                     subject=subject,
                                     messageBody=messageBody,
                                     attachments=attachments)
        cf.setFragmentParent(self)
        cf.docFactory = getLoader(cf.fragmentName)

        return (None, unicode(flatten(cf), 'utf-8'))

    def replyToCurrentMessage(self):
        curmsg = self.currentMessage

        if curmsg.sender is not None:
            origfrom = curmsg.sender
        else:
            origfrom = "someone who chose not to be identified"

        if curmsg.sentWhen is not None:
            origdate = curmsg.sentWhen.asHumanly()
        else:
            origdate = "an indeterminate time in the past"

        replyhead = 'On %s, %s wrote:\n>' % (origdate, origfrom.strip())

        return self._composeSomething(replyTo(curmsg),
                                      reSubject(curmsg),
                                      '\n\n\n' + replyhead + '\n> '.join(quoteBody(curmsg)))

    def forwardCurrentMessage(self):
        curmsg = self.currentMessage

        reply = ['\nBegin forwarded message:\n']
        for hdr in u'From Date To Subject Reply-to'.split():
            try:
                val = curmsg.impl.getHeader(hdr)
            except equotient.NoSuchHeader:
                continue
            reply.append('%s: %s' % (hdr, val))
        reply.append('')
        reply.extend(quoteBody(curmsg))

        return self._composeSomething('',
                                      reSubject(curmsg, 'Fwd: '),
                                      '\n\n' + '\n> '.join(reply),
                                      self.currentMessageDetail.attachmentParts)

    def _getBaseComparison(self):
        # the only mutually exclusive views are "show read" and archive/trash,
        # so you could look at all messages in trash, tagged with "boring"
        # sent by the Person with name "Joe" or whatever
        comparison = attributes.AND(Message.deleted == self.inTrashView,
                                    Message.outgoing == self.inSentMailView,
                                    Message.receivedWhen < Time(),
                                    Message.draft == False)
        if not self.inArchiveView:
            comparison = attributes.AND(comparison, Message.archived == False)

        if self.viewingByTag is not None:
            comparison = attributes.AND(
                Tag.object == Message.storeID,
                Tag.name == self.viewingByTag,
                comparison)

        if self.viewingByAccount is not None:
            comparison = attributes.AND(
                Message.source == self.viewingByAccount,
                comparison)

        if not self.showRead and not (self.inArchiveView or self.inTrashView):
            comparison = attributes.AND(comparison,
                                        Message.read == False)
        return comparison

registerAdapter(InboxScreen, Inbox, ixmantissa.INavigableFragment)

