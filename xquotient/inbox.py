# -*- test-case-name: xquotient.test.test_inbox -*-
import re
from itertools import chain, imap

from datetime import timedelta
from zope.interface import implements
from twisted.python.components import registerAdapter

from nevow import tags as T, inevow, athena
from nevow.flat import flatten
from nevow.page import renderer
from nevow.athena import expose

from epsilon.extime import Time

from axiom.item import Item, InstallableMixin, transacted, declareLegacyItem
from axiom import attributes, tags, iaxiom
from axiom.upgrade import registerUpgrader, registerAttributeCopyingUpgrader

from xmantissa import ixmantissa, webnav, people, webtheme
from xmantissa.fragmentutils import dictFillSlots
from xmantissa.publicresource import getLoader
from xmantissa.scrolltable import ScrollingFragment

from xquotient.exmess import Message, getMessageSources, addMessageSource
from xquotient import mimepart, equotient, compose, renderers

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
    schemaVersion = 3

    installedOn = attributes.reference()

    # uiComplexity should be an integer between 1 and 3, where 1 is the least
    # complex and 3 is the most complex.  the value of this attribute
    # determines what portions of the inbox UI will be visible each time it is
    # loaded (and so should be updated each time the user changes the setting)
    uiComplexity = attributes.integer(default=1)

    # showMoreDetail is a boolean which indicates whether messages should be
    # loaded with the "More Detail" pane expanded.
    showMoreDetail = attributes.boolean(default=False)

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


    def getBaseComparison(self,
                          view,
                          viewingByTag=None,
                          viewingByPerson=None,
                          viewingByAccount=None):
        """
        Return an IComparison to be used as the basic restriction for a view
        onto the mailbox with the given parameters.
        """

        inTrashView = view == 'Trash'
        inDeferredView = view == 'Deferred'
        inSentView = view == 'Sent'
        inAllView = view == 'All'
        inSpamView = view == 'Spam'

        comparison = [
            Message.trash == inTrashView,
            Message.draft == False,
            Message.deferred == inDeferredView]

        if not inTrashView:
            comparison.append(Message.outgoing == inSentView)

        if not (inAllView or inTrashView or inSpamView):
            comparison.append(Message.archived == False)

        if not (inSentView or inTrashView):
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
            comparison.append(Message.spam == inSpamView)


        if viewingByTag is not None:
            comparison.extend((
                tags.Tag.object == Message.storeID,
                tags.Tag.name == viewingByTag))

        if viewingByAccount is not None:
            comparison.append(Message.source == viewingByAccount)

        if viewingByPerson is not None:
            comparison.extend((
                Message.sender == people.EmailAddress.address,
                people.EmailAddress.person == people.Person.storeID,
                people.Person.storeID == viewingByPerson.storeID))

        return attributes.AND(*comparison)


    def getComparisonForBatchType(self,
                                  batchType,
                                  view,
                                  viewingByTag=None,
                                  viewingByPerson=None,
                                  viewingByAccount=None):
        """
        Return an IComparison to be used as the restriction for a particular
        batch of messages from a view onto the mailbox with the given
        parameters.
        """
        comp = self.getBaseComparison(view, viewingByTag, viewingByPerson, viewingByAccount)
        if batchType in ("read", "unread"):
            comp = attributes.AND(comp, Message.read == (batchType == "read"))
        return comp


    def messagesForBatchType(self,
                             batchType,
                             view,
                             viewingByTag=None,
                             viewingByPerson=None,
                             viewingByAccount=None):
        """
        Return a list of L{exmess.Message} instances which belong to the
        specified batch.

        @param batchType: A string defining a particular batch.  For example,
        C{"read"} or C{"unread"}.

        @rtype: C{list}
        """
        return self.store.query(
                Message,
                self.getComparisonForBatchType(
                    batchType, view, viewingByTag,
                    viewingByPerson, viewingByAccount))


    def action_archive(self, message):
        """
        Move the given message to the archive.
        """
        message.archived = True


    def action_delete(self, message):
        """
        Move the given message to the trash.
        """
        message.trash = True


    def action_defer(self, message, days=0, hours=0, minutes=0):
        """
        Change the state of the given message to Deferred and schedule it to
        be changed back after the given interval has elapsed.
        """
        message.deferred = True
        task = UndeferTask(store=self.store,
                           message=message,
                           deferredUntil=Time() + timedelta(days=days,
                                                            hours=hours,
                                                            minutes=minutes))
        iaxiom.IScheduler(self.store).schedule(task, task.deferredUntil)
        return task


    def action_trainSpam(self, message):
        """
        Train the message filter using the given message as an example of
        spam.
        """
        message.train(True)


    def action_trainHam(self, message):
        """
        Train the message filter using the given message as an example of
        ham.
        """
        message.train(False)



def upgradeInbox1to2(oldInbox):
    """
    Create the extra state tracking items necessary for efficiently determining
    distinct source addresses.
    """
    s = oldInbox.store
    newInbox = oldInbox.upgradeVersion(
        'quotient_inbox', 1, 2,
        installedOn=oldInbox.installedOn,
        uiComplexity=oldInbox.uiComplexity,
        catalog=oldInbox.catalog)

    for source in s.query(Message).getColumn("source").distinct():
        addMessageSource(s, source)
    return newInbox
registerUpgrader(upgradeInbox1to2, 'quotient_inbox', 1, 2)

declareLegacyItem(Inbox.typeName, 2,
                  dict(installedOn=attributes.reference(),
                       uiComplexity=attributes.integer(),
                       catalog=attributes.reference()))

registerAttributeCopyingUpgrader(Inbox, 2, 3)


class InboxScreen(webtheme.ThemedElement, renderers.ButtonRenderingMixin):
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

    viewingByTag = None
    viewingByAccount = None
    viewingByPerson = None

    translator = None

    def __init__(self, inbox):
        athena.LiveElement.__init__(self)
        self.translator = ixmantissa.IWebTranslator(inbox.store)
        self.store = inbox.store
        self.inbox = inbox

        currentMessage, nextMessage = self._resetCurrentMessage()
        self._currentMessageAtRenderTime = currentMessage
        self._nextMessageAtRenderTime = nextMessage


    def getInitialArguments(self):
        if self._currentMessageAtRenderTime is not None:
            msgid = self.translator.toWebID(self._currentMessageAtRenderTime).decode('ascii')
        else:
            msgid = None
        return (self.getMessageCount(), msgid, self.inbox.uiComplexity)


    def _resetCurrentMessage(self):
        currentMessage = self.getLastMessage()
        if currentMessage is not None:
            currentMessage.read = True
            nextMessage = self.getMessageBefore(currentMessage)
        else:
            nextMessage = None
        return currentMessage, nextMessage


    def getLastMessage(self):
        """
        Retrieve the message which was received after all other messages.
        """
        return self.inbox.store.findFirst(
            Message,
            self.inbox.getBaseComparison(self.getCurrentViewName(),
                                         self.viewingByTag,
                                         self.viewingByPerson,
                                         self.viewingByAccount),
            sort=Message.receivedWhen.descending)


    def getMessageBefore(self, whichMessage):
        """
        Retrieve the first message which was received before the given time.

        @type whichMessage: L{exmess.Message}
        """
        sort = Message.receivedWhen.desc
        comparison = attributes.AND(self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                                 self.viewingByTag,
                                                                 self.viewingByPerson,
                                                                 self.viewingByAccount),
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
        comparison = attributes.AND(self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                                 self.viewingByTag,
                                                                 self.viewingByPerson,
                                                                 self.viewingByAccount),
                                    Message.receivedWhen > whichMessage.receivedWhen)
        return self.inbox.store.findFirst(Message,
                                          comparison,
                                          default=None,
                                          sort=sort)


    def _messageFragment(self, message):
        f = ixmantissa.INavigableFragment(message)
        f.setFragmentParent(self)
        return f


    def _currentAsFragment(self, currentMessage):
        if currentMessage is None:
            return ''
        f = self._messageFragment(currentMessage)
        self.currentMessageDetail = f
        return f


    def _currentMessageData(self, currentMessage):
        if currentMessage is not None:
            return {
                u'identifier': self.translator.toWebID(currentMessage).decode('ascii'),
                u'spam': currentMessage.spam,
                u'trained': currentMessage.trained,
                }
        return {}

    def messageDetail(self, request, tag):
        return self._currentAsFragment(self._currentMessageAtRenderTime)
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
        currentMessage = self._currentMessageAtRenderTime

        if currentMessage is None:
            return tag['????']
        if currentMessage.trained:
            confidence = 'definitely'
        else:
            confidence = 'probably'
        if currentMessage.spam:
            modifier = ''
        else:
            modifier = 'not'
        return tag[confidence + ' ' + modifier]
    renderer(spamState)


    def scroller(self, request, tag):
        currentMessage = self._currentMessageAtRenderTime

        f = ScrollingFragment(self.inbox.store,
                              Message,
                              self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                           self.viewingByTag,
                                                           self.viewingByPerson,
                                                           self.viewingByAccount),
                              (Message.sender,
                               Message.senderDisplay,
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

        iq = inevow.IQ(self.docFactory)
        if 'open' in attrs:
            paneBodyPattern = 'open-pane-body'
        else:
            paneBodyPattern = 'pane-body'
        paneBodyPattern = iq.onePattern(paneBodyPattern)

        return dictFillSlots(iq.onePattern('view-pane'),
                             {'name': attrs['name'],
                              'pane-body': paneBodyPattern.fillSlots(
                                             'renderer', T.directive(attrs['renderer']))})
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
                                      attributes.AND(self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                                                  self.viewingByTag,
                                                                                  self.viewingByPerson,
                                                                                  self.viewingByAccount),
                                                     Message.read == False))

    def mailViewChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('mailViewChooser')
        option = inevow.IQ(select).patternGenerator('mailViewChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedMailViewChoice')

        views = ['Inbox', 'All', 'Deferred', 'Sent', 'Spam', 'Trash']
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
        return getMessageSources(self.inbox.store)

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


    def _nextMessagePreview(self, currentMessage, nextMessage):
        if currentMessage is None:
            return u'No more messages'
        onePattern = inevow.IQ(self.docFactory).onePattern
        if nextMessage is None:
            return onePattern('last-message')
        m = nextMessage
        return dictFillSlots(onePattern('next-message'),
                             dict(sender=m.senderDisplay,
                                  subject=m.subject,
                                  date=m.sentWhen.asHumanly()))

    def nextMessagePreview(self, request, tag):
        currentMessage = self._currentMessageAtRenderTime
        nextMessage = self._nextMessageAtRenderTime
        return self._nextMessagePreview(currentMessage, nextMessage)
    renderer(nextMessagePreview)


    def head(self):
        return None

    # remote methods

    def setComplexity(self, n):
        self.inbox.uiComplexity = n
    expose(setComplexity)

    setComplexity = transacted(setComplexity)

    def fastForward(self, webID):
        """
        Retrieve message detail information for the specified message as well
        as look-ahead information for the next message.  Mark the specified
        message as read.
        """
        currentMessage = self.translator.fromWebID(webID)
        nextMessage = self.getMessageAfter(currentMessage)

        currentMessage.read = True

        return [
            self._messagePreview(nextMessage),
            self._messageFragment(currentMessage),
            self._messageData(currentMessage),
            ]
    expose(fastForward)

    fastForward = transacted(fastForward)

    def _resetScrollQuery(self, currentMessage):
        self.scrollingFragment.baseConstraint = self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                                             self.viewingByTag,
                                                                             self.viewingByPerson,
                                                                             self.viewingByAccount)

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


    def _updatedViewState(self, currentMessage, nextMessage):
        """
        Retrieve state relevant to the view: the number of messages in the
        current view, the current message body, and the number of messages in
        the other views.  This is returned as a three-tuple.

        The first two elements are always present but the third element may be
        None.  This will be the case when it would be too expensive to compute.
        """
        return (self.getMessageCount(),
                self._current(currentMessage, nextMessage),
                None) # self.mailViewCounts()


    def viewByPerson(self, webID):
        if webID is None:
            self.viewingByPerson = None
        else:
            self.viewingByPerson = self.translator.fromWebID(webID)

        currentMessage, nextMessage = self._resetCurrentMessage()
        self._resetScrollQuery(currentMessage)
        return self._updatedViewState(currentMessage, nextMessage)
    expose(viewByPerson)
    viewByPerson = transacted(viewByPerson)


    def viewByTag(self, tag):
        self.viewingByTag = tag
        currentMessage, nextMessage = self._resetCurrentMessage()
        self._resetScrollQuery(currentMessage)
        return self._updatedViewState(currentMessage, nextMessage)
    expose(viewByTag)
    viewByTag = transacted(viewByTag)


    def viewByAccount(self, account):
        self.viewingByAccount = account
        currentMessage, nextMessage = self._resetCurrentMessage()
        self._resetScrollQuery(currentMessage)
        return self._updatedViewState(currentMessage, nextMessage)
    expose(viewByAccount)
    viewByAccount = transacted(viewByAccount)


    def changeView(self, typ):
        self.inAllView = self.inTrashView = self.inSentView = self.inSpamView = self.inDeferredView = False
        attr = 'in' + typ + 'View'
        if hasattr(self, attr):
            setattr(self, attr, True)

    def viewByMailType(self, typ):
        self.changeView(typ)
        currentMessage, nextMessage = self._resetCurrentMessage()
        self._resetScrollQuery(currentMessage)
        return self._updatedViewState(currentMessage, nextMessage)
    expose(viewByMailType)

    viewByMailType = transacted(viewByMailType)

    def getMessageCount(self):
        return self.inbox.store.count(Message, self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                                            self.viewingByTag,
                                                                            self.viewingByPerson,
                                                                            self.viewingByAccount))
    expose(getMessageCount)

    def getMessages(self, **k):
        return self.inbox.store.query(Message, self.inbox.getBaseComparison(self.getCurrentViewName(),
                                                                            self.viewingByTag,
                                                                            self.viewingByPerson,
                                                                            self.viewingByAccount), **k)

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

    def _current(self, currentMessage, nextMessage):
        return (self._squish(self._nextMessagePreview(currentMessage, nextMessage)),
                self._squish(self._currentAsFragment(currentMessage)),
                self._currentMessageData(currentMessage))

    def _getActionMethod(self, actionName):
        return getattr(self.inbox, 'action_' + actionName)

    def _performMany(self, actionName, messages=(), webIDs=(), args=()):
        readCount = 0
        unreadCount = 0
        action = self._getActionMethod(actionName)
        for message in chain(messages, imap(self.translator.fromWebID, webIDs)):
            if message.read:
                readCount += 1
            else:
                unreadCount += 1
            action(message, *args)
        return readCount, unreadCount


    def _messageData(self, msg):
        if msg is not None:
            return {
                u'identifier': self.translator.toWebID(msg).decode('ascii'),
                u'trained': msg.trained,
                u'spam': msg.spam,
                }
        return None


    def _messagePreview(self, msg):
        if msg is not None:
            return {
                u'subject': msg.subject}
        return None


    def actOnMessageIdentifierList(self, action, messageIdentifiers, extraArguments=None):
        """
        Perform an action on list of messages specified by their web
        identifier.

        @type action: C{unicode}
        @param action: The name of the action to perform.  This may be any
        string which can be prepended with C{'action_'} to name a method
        defined on this class.

        @type currentMessageIdentifier: C{unicode}
        @param currentMessageIdentifier: The web ID for the message which is
        currently being displayed on the client.

        @type messageIdentifiers: C{list} of C{unicode}
        @param messageIdentifiers: A list of web IDs for messages on which to act.

        @type extraArguments: C{None} or C{dict}
        @param extraArguments: Additional keyword arguments to pass on to the
        action handler.
        """
        messages = map(self.translator.fromWebID, messageIdentifiers)
        return self._performMany(action, messages, **(extraArguments or {}))
    expose(actOnMessageIdentifierList)


    def actOnMessageBatch(self, action, batchType, include, exclude, extraArguments=None):
        """
        Perform an action on a set of messages defined by a common
        characteristic or which are specifically included but not specifically
        excluded.
        """
        view = self.getCurrentViewName()
        messages = set(self.inbox.messagesForBatchType(
                batchType, view, self.viewingByTag,
                self.viewingByPerson, self.viewingByAccount))
        more = set(map(self.translator.fromWebID, include))
        less = set(map(self.translator.fromWebID, exclude))

        targets = (messages | more) - less
        return self._performMany(action, targets, **(extraArguments or {}))
    expose(actOnMessageBatch)


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


    def replyToMessage(self, messageIdentifier, advance):
        curmsg = self.translator.fromWebID(messageIdentifier)

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
    expose(replyToMessage)


    def forwardMessage(self, messageIdentifier, advance):
        curmsg = self.translator.fromWebID(messageIdentifier)

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
    expose(forwardMessage)

registerAdapter(InboxScreen, Inbox, ixmantissa.INavigableFragment)

