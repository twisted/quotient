# -*- test-case-name: xquotient.test.test_inbox -*-
import re

from datetime import timedelta
from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags as T, inevow, athena
from nevow.flat import flatten
from nevow.page import renderer
from nevow.athena import expose

from epsilon.extime import Time

from axiom.item import Item, InstallableMixin, transacted
from axiom import attributes, tags, iaxiom

from xmantissa import ixmantissa, webnav, people
from xmantissa.fragmentutils import dictFillSlots
from xmantissa.publicresource import getLoader
from xmantissa.scrolltable import ScrollingFragment

from xquotient.exmess import Message
from xquotient import mimepart, equotient, compose, renderers
from xquotient.qpeople import AddPersonFragment

#_entityReference = re.compile('&([a-z]+);', re.I)

# C0 control set (0x01-0x1F), minus CR (0x0D), LF (0x0A) & HT (0x09)
# These can't appear in XML or XHTML (apparently they can be escaped in XML 1.1)
# See: http://lists.w3.org/Archives/Public/public-i18n-geo/2003May/att-0030/W3C_I18N_Q_A_C0_Range.htm

_UNSUPPORTED_C0_CHARS = re.compile(ur'[\x01-\x08\x0B\x0C\x0E-\x1F]')
replaceControlChars = lambda s: _UNSUPPORTED_C0_CHARS.sub('', s)

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

def makeBatchAction(actionName):
    def batchAction(self, batchType, include=(), exclude=(), *args):
        return self._performBatchAction(actionName,
                                        self._messagesForBatchType(batchType, include, exclude),
                                        args)
    return transacted(batchAction)

def makeGroupAction(actionName):
    def groupAction(self, advance, nextMessageWebID, webIDs, *args):
        return self._performGroupAction(actionName,
                                        advance, nextMessageWebID, webIDs, args)
    return transacted(groupAction)

def makeSingleAction(actionName):
    def singleAction(self, advance, *args):
        return self._performSingleAction(actionName, advance, args)

    return transacted(singleAction)

class UndeferTask(Item):
    """
    Created when a message is deferred.  When run, I undefer
    the message, mark it as unread, and delete myself from the
    database
    """
    message = attributes.reference(reftype=Message,
                                   whenDeleted=attributes.reference.CASCADE,
                                   allowNone=False)
    deferredUntil = attributes.timestamp(allowNone=False)

    def run(self):
        self.message.deferred = False
        if not self.message.everDeferred:
            self.message.everDeferred = True
        self.message.read = False
        self.deleteFromStore()

class Inbox(Item, InstallableMixin):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_inbox'
    schemaVersion = 1

    installedOn = attributes.reference()

    # uiComplexity should be an integer between 1 and 3, where 1 is the least
    # complex and 3 is the most complex.  the value of this attribute
    # determines what portions of the inbox UI will be visible each time it is
    # loaded (and so should be updated each time the user changes the setting)
    uiComplexity = attributes.integer(default=1)


    catalog = attributes.reference(doc="""
    A reference to an L{axiom.tags.Catalog} Item.  This will be used to
    determine which tags should be displayed to the user and to create new
    tags.  If no catalog is specified at creation time, one will be found in
    the database or created if none exists at all.
    """)

    def __init__(self, **kw):
        super(Inbox, self).__init__(**kw)
        if self.catalog is None:
            self.catalog = self.store.findOrCreate(tags.Catalog)


    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.75, children=
                    [webnav.Tab('Inbox', self.storeID, 0.4)],
                authoritative=True)]

    def installOn(self, other):
        super(Inbox, self).installOn(other)
        other.powerUp(self, ixmantissa.INavigableElement)

    def action_archive(self, message):
        message.archived = True

    def action_delete(self, message):
        message.trash = True

    def action_defer(self, message, days, hours, minutes):
        message.deferred = True
        task = UndeferTask(store=self.store,
                           message=message,
                           deferredUntil=Time() + timedelta(days=days,
                                                            hours=hours,
                                                            minutes=minutes))
        iaxiom.IScheduler(self.store).schedule(task, task.deferredUntil)
        return task

    def action_train(self, message, spam):
        message.train(spam)

class InboxScreen(athena.LiveElement, renderers.ButtonRenderingMixin):
    """
    Renderer for boxes for of email.

    @ivar store: The L{axiom.store.Store} containing the state this instance
    renders.

    @ivar inbox: The L{Inbox} which serves as the model for this view.
    """
    implements(ixmantissa.INavigableFragment)

    fragmentName = 'inbox'
    live = 'athena'
    title = ''
    jsClass = 'Quotient.Mailbox.Controller'

    inAllView = False
    inTrashView = False
    inSentView = False
    inSpamView = False
    inDeferredView = False
    currentMessage = None

    viewingByTag = None
    viewingByAccount = None
    viewingByPerson = None

    translator = None

    def __init__(self, inbox):
        athena.LiveElement.__init__(self)
        self.translator = ixmantissa.IWebTranslator(inbox.store)
        self.store = inbox.store
        self.inbox = inbox

        self._resetCurrentMessage()

    def getInitialArguments(self):
        return (self.getMessageCount(), self.inbox.uiComplexity)

    def _resetCurrentMessage(self):
        self.currentMessage = self.getLastMessage()
        if self.currentMessage is not None:
            self.currentMessage.read = True
            self.nextMessage = self.getMessageBefore(self.currentMessage)
        else:
            self.nextMessage = None


    def getFirstMessage(self):
        """
        Retrieve the message which was received before all other messages.
        """
        return self.inbox.store.findFirst(
            Message,
            self._getBaseComparison(),
            sort=Message.receivedWhen.ascending)


    def getLastMessage(self):
        """
        Retrieve the message which was received after all other messages.
        """
        return self.inbox.store.findFirst(
            Message,
            self._getBaseComparison(),
            sort=Message.receivedWhen.descending)


    def getMessageBefore(self, whichMessage):
        """
        Retrieve the first message which was received before the given time.

        @type whichMessage: L{exmess.Message}
        """
        sort = Message.receivedWhen.desc
        comparison = attributes.AND(self._getBaseComparison(),
                                    Message.receivedWhen < whichMessage.receivedWhen)
        return self.inbox.store.findFirst(Message,
                                          comparison,
                                          default=None,
                                          sort=sort)


    def getMessageAfter(self, whichMessage):
        """
        Retrieve the first message which was received after the given time.

        @type whichMessage: L{exmess.Message}
        """
        sort = Message.receivedWhen.asc
        comparison = attributes.AND(self._getBaseComparison(),
                                    Message.receivedWhen > whichMessage.receivedWhen)
        return self.inbox.store.findFirst(Message,
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


    def _currentMessageData(self):
        if self.currentMessage is not None:
            return {
                u'spam': self.currentMessage.spam,
                u'trained': self.currentMessage.trained,
                }
        return {}

    def messageDetail(self, request, tag):
        return self._currentAsFragment()
    renderer(messageDetail)


    def composeLink(self, ctx, data):
        """
        If L{compose.Composer} is installed in our store,
        then render a link to it, otherwise don't
        """
        composer = self.store.findUnique(compose.Composer, default=None)
        if composer is not None:
            return inevow.IQ(self.docFactory).onePattern(
                        'compose-link').fillSlots(
                            'href', self.translator.linkTo(composer.storeID))
        return ''
    renderer(composeLink)


    def spamState(self, request, tag):
        if self.currentMessage is None:
            return tag['????']
        if self.currentMessage.trained:
            confidence = 'definitely'
        else:
            confidence = 'probably'
        if self.currentMessage.spam:
            modifier = ''
        else:
            modifier = 'not'
        return tag[confidence + ' ' + modifier]
    renderer(spamState)


    def addPersonFragment(self, request, tag):
        # the person form is a fair amount of html,
        # so we'll only include it once

        self.addPersonFragment = AddPersonFragment(self.inbox)
        self.addPersonFragment.setFragmentParent(self)
        self.addPersonFragment.docFactory = getLoader(self.addPersonFragment.fragmentName)
        return self.addPersonFragment
    renderer(addPersonFragment)

    def _getScrolltableComparison(self):
        if self.currentMessage is not None:
            beforeTime = self.currentMessage.receivedWhen
        else:
            beforeTime = None

        return self._getBaseComparison(beforeTime)

    def scroller(self, request, tag):
        f = ScrollingFragment(self.inbox.store,
                              Message,
                              self._getScrolltableComparison(),
                              (Message.senderDisplay,
                               Message.subject,
                               Message.receivedWhen,
                               Message.read,
                               Message.sentWhen,
                               Message.attachments,
                               Message.everDeferred),
                              defaultSortColumn=Message.receivedWhen,
                              defaultSortAscending=False)

        f.jsClass = 'Quotient.Mailbox.ScrollingWidget'
        f.setFragmentParent(self)
        f.docFactory = getLoader(f.fragmentName)
        self.scrollingFragment = f
        return f
    renderer(scroller)


    def getTags(self):
        """
        Return a list of unique tag names as unicode strings.
        """
        return list(self.inbox.catalog.tagNames())


    def viewPane(self, request, tag):
        attrs = tag.attributes
        return dictFillSlots(inevow.IQ(self.docFactory).onePattern('view-pane'),
                             {'name': attrs['name'],
                              'renderer': T.directive(attrs['renderer'])})
    renderer(viewPane)

    def personChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('personChooser')
        option = inevow.IQ(select).patternGenerator('personChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedPersonChoice')

        for person in [None] + list(self.inbox.store.query(people.Person)):
            if person == self.viewingByPerson:
                p = selectedOption
            else:
                p = option

            if person:
                name = person.getDisplayName()
                key = self.translator.toWebID(person)
            else:
                name = key = 'All'

            opt = p().fillSlots(
                    'personName', name).fillSlots(
                    'personKey', key)

            select[opt]
        return select
    renderer(personChooser)

    def getUnreadMessageCount(self):
        """
        @return: number of unread messages in current view
        """
        return self.inbox.store.count(Message,
                                      attributes.AND(self._getBaseComparison(),
                                                     Message.read == False))

    def mailViewChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('mailViewChooser')
        option = inevow.IQ(select).patternGenerator('mailViewChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedMailViewChoice')

        views = ['All', 'Trash', 'Sent', 'Spam', 'Deferred', 'Inbox']
        counts = self.mailViewCounts()
        counts = sorted(counts.iteritems(), key=lambda (v, c): views.index(v))

        curview = self.getCurrentViewName()
        for (view, count) in counts:
            if view == curview:
                p = selectedOption
            else:
                p = option

            select[p().fillSlots(
                        'mailViewName', view).fillSlots(
                        'count', count)]
        return select
    renderer(mailViewChooser)


    def tagChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('tagChooser')
        option = inevow.IQ(select).patternGenerator('tagChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedTagChoice')
        for tag in [None] + self.getTags():
            if tag == self.viewingByTag:
                p = selectedOption
            else:
                p = option
            opt = p().fillSlots('tagName', tag or 'All')
            select[opt]
        return select
    renderer(tagChooser)


    def _accountNames(self):
        return self.inbox.store.query(Message).getColumn("source").distinct()

    def accountChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('accountChooser')
        option = inevow.IQ(select).patternGenerator('accountChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedAccountChoice')
        for acc in [None] + list(self._accountNames()):
            if acc == self.viewingByAccount:
                p = selectedOption
            else:
                p = option
            opt = p().fillSlots('accountName', acc or 'All')
            select[opt]
        return select
    renderer(accountChooser)


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

    def nextMessagePreview(self, request, tag):
        return self._nextMessagePreview()
    renderer(nextMessagePreview)


    def head(self):
        return None

    # remote methods

    def setComplexity(self, n):
        self.inbox.uiComplexity = n
    expose(setComplexity)

    setComplexity = transacted(setComplexity)

    def selectMessage(self, message):
        """
        Set C{message} as the current message.  Also cache the message that
        will be displayed next, which is going to be the message received
        immediately before C{message}.
        """
        self.currentMessage = message
        message.read = True
        next = self.getMessageBefore(message)
        if next is None:
            next = self.getMessageAfter(message)
        self.nextMessage = next

    def fastForward(self, webID):
        self.selectMessage(self.translator.fromWebID(webID))
        return self._current()
    expose(fastForward)

    fastForward = transacted(fastForward)

    def _resetScrollQuery(self):
        self.scrollingFragment.baseConstraint = self._getScrolltableComparison()

    def mailViewCounts(self):
        counts = {}
        curview = self.getCurrentViewName()
        for v in (u'Trash', u'Sent', u'Spam', u'All', u'Deferred', u'Inbox'):
            self.changeView(v)
            counts[v] = self.getUnreadMessageCount()
        self.changeView(curview)
        return counts

    def getCurrentViewName(self):
        for (truth, name) in ((self.inAllView, 'All'),
                              (self.inTrashView, 'Trash'),
                              (self.inSentView, 'Sent'),
                              (self.inSpamView, 'Spam'),
                              (self.inDeferredView, 'Deferred'),
                              (True, 'Inbox')):
            if truth:
                return name

    def viewByPerson(self, webID):
        if webID is None:
            self.viewingByPerson = None
        else:
            self.viewingByPerson = self.translator.fromWebID(webID)

        self._resetCurrentMessage()
        self._resetScrollQuery()
        return (self.getMessageCount(), self._current(), self.mailViewCounts())
    expose(viewByPerson)

    viewByPerson = transacted(viewByPerson)

    def viewByTag(self, tag):
        self.viewingByTag = tag
        self._resetCurrentMessage()
        self._resetScrollQuery()
        return (self.getMessageCount(), self._current(), self.mailViewCounts())
    expose(viewByTag)

    viewByTag = transacted(viewByTag)

    def viewByAccount(self, account):
        self.viewingByAccount = account
        self._resetCurrentMessage()
        self._resetScrollQuery()
        return (self.getMessageCount(), self._current(), self.mailViewCounts())
    expose(viewByAccount)

    viewByAccount = transacted(viewByAccount)

    def changeView(self, typ):
        self.inAllView = self.inTrashView = self.inSentView = self.inSpamView = self.inDeferredView = False
        attr = 'in' + typ + 'View'
        if hasattr(self, attr):
            setattr(self, attr, True)

    def viewByMailType(self, typ):
        self.changeView(typ)
        self._resetCurrentMessage()
        self._resetScrollQuery()
        return (self.getMessageCount(), self._current(), self.mailViewCounts())
    expose(viewByMailType)

    viewByMailType = transacted(viewByMailType)

    def getMessageCount(self):
        return self.inbox.store.count(Message, self._getBaseComparison())
    expose(getMessageCount)

    def getMessages(self, **k):
        return self.inbox.store.query(Message, self._getBaseComparison(), **k)

    def _squish(self, thing):
        # replacing &nbsp with &#160 in renderers.SpacePreservingStringRenderer
        # fixed all issues with calling setNodeContent on flattened message
        # details for all messages in the test pool.  but there might be
        # other things that will break also.

        #for eref in set(_entityReference.findall(text)):
        #    entity = getattr(entities, eref, None)
        #    if entity is not None:
        #        text = text.replace('&' + eref + ';', '&#' + entity.num + ';')
        return replaceControlChars(unicode(flatten(thing), 'utf-8'))

    def _current(self):
        return (self._squish(self._nextMessagePreview()),
                self._squish(self._currentAsFragment()),
                self._currentMessageData())

    def _moveToNextMessage(self):
        previousMessage = self.currentMessage
        currentMessage = self.nextMessage

        if currentMessage is not None:
            self.selectMessage(currentMessage)
        else:
            self.currentMessage = self.getMessageBefore(previousMessage)
            self.nextMessage = None

    def _progressOrDont(self, advance):
        if advance:
            self._moveToNextMessage()
        return self._current()

    def _getActionMethod(self, actionName):
        return getattr(self.inbox, 'action_' + actionName)

    def _performMany(self, actionName, messages=(), webIDs=(), args=()):
        action = self._getActionMethod(actionName)
        for message in messages:
            action(message, *args)
        for webID in webIDs:
            action(self.translator.fromWebID(webID), *args)

    archiveCurrentMessage = expose(makeSingleAction('archive'))
    deleteCurrentMessage  = expose(makeSingleAction('delete'))
    deferCurrentMessage   = expose(makeSingleAction('defer'))
    trainCurrentMessage   = expose(makeSingleAction('train'))

    archiveMessageGroup = expose(makeGroupAction('archive'))
    deleteMessageGroup  = expose(makeGroupAction('delete'))
    trainMessageGroup   = expose(makeGroupAction('train'))

    archiveMessageBatch = expose(makeBatchAction('archive'))
    deleteMessageBatch  = expose(makeBatchAction('delete'))
    trainMessageBatch   = expose(makeBatchAction('train'))

    def _getComparisonForBatchType(self, batchType):
        comp = self._getBaseComparison()
        if batchType in ("read", "unread"):
            comp = attributes.AND(comp, Message.read == (batchType == "read"))
        return comp

    def _performBatchAction(self, actionName, messages, args):
        self._performMany(actionName, messages, args=args)

        # this could probably be more fine-grained
        if self.currentMessage in messages or self.nextMessage in messages:
            self._resetCurrentMessage()

        return (self._current(), len(messages), sum(1 for m in messages if not m.read))

    def _performGroupAction(self, actionName, advance, nextMessageWebID, webIDs, args):
        self._performMany(actionName, webIDs=webIDs, args=args)

        if advance:
            if nextMessageWebID is not None:
                self.nextMessage = self.translator.fromWebID(nextMessageWebID)
            return self._progressOrDont(advance)

    def _performSingleAction(self, actionName, advance, args):
        action = self._getActionMethod(actionName)
        action(self.currentMessage, *args)

        return self._progressOrDont(advance)

    def _messagesForBatchType(self, batchType, include, exclude):
        comp = attributes.AND(
                Message.storeID.notOneOf(
                    self.translator.linkFrom(wid) for wid in exclude),
                self._getComparisonForBatchType(batchType))

        comp = attributes.OR(
                Message.storeID.oneOf(
                    self.translator.linkFrom(wid) for wid in include),
                comp)

        return list(self.store.query(Message, comp))

    def _composeSomething(self, toAddress, subject, messageBody, attachments=()):
        composer = self.inbox.store.findUnique(compose.Composer)
        cf = compose.ComposeFragment(composer,
                                     toAddress=toAddress,
                                     subject=subject,
                                     messageBody=messageBody,
                                     attachments=attachments,
                                     inline=True)
        cf.setFragmentParent(self)
        cf.docFactory = getLoader(cf.fragmentName)

        return unicode(flatten(cf), 'utf-8')

    def replyToCurrentMessage(self, advance):
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
    expose(replyToCurrentMessage)

    def forwardCurrentMessage(self, advance):
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
    expose(forwardCurrentMessage)

    def _getBaseComparison(self, beforeTime=None):
        if beforeTime is None:
            beforeTime = Time()

        comparison = [
            Message.trash == self.inTrashView,
            Message.draft == False,
            Message.deferred == self.inDeferredView]

        if not self.inTrashView:
            comparison.append(Message.outgoing == self.inSentView)

        if not (self.inAllView or self.inTrashView or self.inSpamView):
            comparison.append(Message.archived == False)

        if not (self.inSentView or self.inTrashView):
            # Note - Message.spam defaults to None, and inSpamView will
            # always be either True or False.  This means messages which
            # haven't been processed by the spam filtering system will never
            # show up in any query!  Is this a problem?  It depends how
            # responsive the spam filtering system ends up being, I suppose.
            # Currently, it should be fast enough so as not to make much of
            # a difference, but that may not always be the case.  However,
            # ultimately we are going to need to support updating messages
            # views without doing a complete page re-load, at which point
            # delivered but unfiltered messages will just show up on the
            # page, which should result in this minor inequity being more or
            # less irrelevant.
            comparison.append(Message.spam == self.inSpamView)


        if self.viewingByTag is not None:
            comparison.extend((
                tags.Tag.object == Message.storeID,
                tags.Tag.name == self.viewingByTag))

        if self.viewingByAccount is not None:
            comparison.append(Message.source == self.viewingByAccount)

        if self.viewingByPerson is not None:
            comparison.extend((
                Message.sender == people.EmailAddress.address,
                people.EmailAddress.person == people.Person.storeID,
                people.Person.storeID == self.viewingByPerson.storeID))

        return attributes.AND(*comparison)

registerAdapter(InboxScreen, Inbox, ixmantissa.INavigableFragment)

