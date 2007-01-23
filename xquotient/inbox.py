# -*- test-case-name: xquotient.test.test_inbox -*-
import itertools

from datetime import timedelta
from zope.interface import implements
from twisted.python.components import registerAdapter
from twisted.internet import defer

from nevow import tags as T, inevow, athena
from nevow.page import renderer
from nevow.athena import expose, LiveElement
from epsilon import cooperator

from axiom.item import Item, transacted, declareLegacyItem
from axiom import tags
from axiom import attributes
from axiom.upgrade import registerUpgrader, registerAttributeCopyingUpgrader
from axiom.dependency import dependsOn, installOn, installedOn, _DependencyConnector
from axiom.scheduler import SubScheduler

from xmantissa import ixmantissa, webnav, people, webtheme
from xmantissa.webapp import PrivateApplication

from xmantissa.fragmentutils import dictFillSlots
from xmantissa.publicresource import getLoader
from xmantissa.scrolltable import Scrollable, ScrollableView

from xquotient import mimepart, equotient, compose, renderers, mimeutil, smtpout, spam
from xquotient.filter import Focus
from xquotient.exmess import Message, getMessageSources, MailboxSelector
from xquotient.exmess import (READ_STATUS, UNREAD_STATUS, CLEAN_STATUS,
                              INBOX_STATUS, ARCHIVE_STATUS, DEFERRED_STATUS,
                              OUTBOX_STATUS, BOUNCED_STATUS, SENT_STATUS,
                              SPAM_STATUS, TRASH_STATUS, SENDER_RELATION,
                              COPY_RELATION, BLIND_COPY_RELATION, DRAFT_STATUS,
                              FOCUS_STATUS)

from xquotient.mail import MessageSource, DeliveryAgent
from xquotient.quotientapp import QuotientPreferenceCollection, MessageDisplayPreferenceCollection

# Views that the user may select.
VIEWS = [FOCUS_STATUS, INBOX_STATUS, ARCHIVE_STATUS, u'all', DEFERRED_STATUS,
         DRAFT_STATUS, OUTBOX_STATUS, BOUNCED_STATUS, SENT_STATUS, SPAM_STATUS,
         TRASH_STATUS]
# The subset of all views that should use 'touch-once' message order; oldest
# messages first
TOUCH_ONCE_VIEWS = [INBOX_STATUS, FOCUS_STATUS]



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
    newtext = renderers.replaceIllegalChars(para.asRFC2646(maxwidth-2))

    return [ '\n>'.join(newtext.split('\r\n')) ]


def reSubject(m, pfx='Re: '):
    newsubject = m.subject
    if not newsubject.lower().startswith(pfx.lower()):
        newsubject = pfx + newsubject
    return newsubject


def replyTo(m):
    """
    Figure out the address(es) that a reply to the message C{m} should be sent to.

    @type m: L{xquotient.exmess.Message}
    @rtype: sequence of L{xquotient.mimeutil.EmailAddress}
    """
    # FIXME this should be a method on Message or something
    try:
        recipient = m.impl.getHeader(u'reply-to')
    except equotient.NoSuchHeader:
        recipient = m.sender
    return mimeutil.parseEmailAddresses(recipient, mimeEncoded=False)


def replyToAll(m):
    """
    Figure out the address(es) that a reply to all people involved in message
    C{m} should be sent to.

    @type m: L{xquotient.exmess.Message}
    @return: Mapping of header names to sequences of
    L{xquotient.mimeutil.EmailAddress} instances.  Keys are 'to', 'cc' and
    'bcc'.
    @rtype: C{dict}
    """
    fromAddrs = list(m.store.query(smtpout.FromAddress))
    fromAddrs = set(a.address for a in fromAddrs)

    relToKey = {SENDER_RELATION: 'to',
                COPY_RELATION: 'cc',
                BLIND_COPY_RELATION: 'bcc'}
    addrs = {}

    for (rel, addr) in m.impl.relatedAddresses():
        if rel not in relToKey or addr.email in fromAddrs:
            continue
        addrs.setdefault(relToKey[rel], []).append(addr)
    return addrs


def _viewSelectionToMailboxSelector(store, viewSelection):
    """
    Convert a 'view selection' object, sent from the client, into a MailboxSelector
    object which will be used to view the mailbox.

    @param store: an L{axiom.store.Store} that contains some messages.

    @param viewSelection: a dictionary with 4 keys: 'view', 'tag', 'person',
    'account'.  This dictionary represents the selections that users have
    made in the 4-section 'complexity 3' filtering UI.  Each key may have a
    string value, or None.  If the value is None, the user has selected
    'All' for that key in the UI; if the value is a string, the user has
    selected that string.

    @return: a L{MailboxSelector} object.
    """
    view, tag, personWebID, account = map(
        viewSelection.__getitem__,
        [u"view", u"tag", u"person", u"account"])

    sq = MailboxSelector(store)
    sq.setLimit(None)
    if view in TOUCH_ONCE_VIEWS:
        sq.setOldestFirst()
    else:
        sq.setNewestFirst()
    if view == u'all':
        view = CLEAN_STATUS

    sq.refineByStatus(view) # 'view' is really a status!  and the names
                            # even line up!
    if tag is not None:
        sq.refineByTag(tag)
    if account is not None:
        sq.refineBySource(account)
    if personWebID is not None:
        person = ixmantissa.IWebTranslator(store).fromWebID(personWebID)
        sq.refineByPerson(person)
    return sq


class Inbox(Item):
    implements(ixmantissa.INavigableElement)

    typeName = 'quotient_inbox'
    schemaVersion = 5

    powerupInterfaces = (ixmantissa.INavigableElement,)

    privateApplication = dependsOn(PrivateApplication)
    scheduler = dependsOn(SubScheduler)
    messageSource = dependsOn(MessageSource)
    quotientPrefs = dependsOn(QuotientPreferenceCollection)
    deliveryAgent = dependsOn(DeliveryAgent)
    messageDisplayPrefs = dependsOn(MessageDisplayPreferenceCollection)
    filter = dependsOn(spam.Filter)
    focus = dependsOn(Focus)

    # uiComplexity should be an integer between 1 and 3, where 1 is the least
    # complex and 3 is the most complex.  the value of this attribute
    # determines what portions of the inbox UI will be visible each time it is
    # loaded (and so should be updated each time the user changes the setting)
    uiComplexity = attributes.integer(default=1)

    # showMoreDetail is a boolean which indicates whether messages should be
    # loaded with the "More Detail" pane expanded.
    showMoreDetail = attributes.boolean(default=False)

    def __init__(self, **kw):
        super(Inbox, self).__init__(**kw)


    def getTabs(self):
        return [webnav.Tab('Mail', self.storeID, 0.75, children=
                    [webnav.Tab('Inbox', self.storeID, 0.4)],
                authoritative=True)]




    def getBaseComparison(self, viewSelection):
        """
        Return an IComparison to be used as the basic restriction for a view
        onto the mailbox with the given parameters.

        @param viewSelection: a dictionary with 4 keys: 'view', 'tag', person',
        'account'.  This dictionary represents the selections that users have
        made in the 4-section 'complexity 3' filtering UI.  Each key may have a
        string value, or None.  If the value is None, the user has selected
        'All' for that key in the UI; if the value is a string, the user has
        selected that string.

        @return: an IComparison which can be used to generate a query for
        messages matching the selection represented by the viewSelection
        criterea.
        """
        return _viewSelectionToMailboxSelector(self.store,
                                               viewSelection)._getComparison()


    def getComparisonForBatchType(self, batchType, viewSelection):
        """
        Return an IComparison to be used as the restriction for a particular
        batch of messages from a view onto the mailbox with the given
        parameters.
        """
        sq = _viewSelectionToMailboxSelector(self.store, viewSelection)
        if batchType in (UNREAD_STATUS, READ_STATUS):
            sq.refineByStatus(batchType)
        return sq._getComparison()


    def messagesForBatchType(self, batchType, viewSelection, exclude=()):
        """
        Return an iterable of L{exmess.Message} items which belong to the
        specified batch.

        @param batchType: A string defining a particular batch.  For example,
        C{"read"} or C{"unread"}.

        @param exclude: messages to exclude from the batch selection.
        defaults to no messages.
        @type exclude: iterable of L{xquotient.exmess.Message}

        @rtype: iterable
        """
        it = self.store.query(
            Message,
            self.getComparisonForBatchType(
                batchType, viewSelection)).paginate()

        exclude = set(m.storeID for m in exclude)
        return itertools.ifilter(lambda m: m.storeID not in exclude, it)


    def action_archive(self, message):
        """
        Move the given message to the archive.
        """
        message.archive()


    def action_unarchive(self, message):
        """
        Move the given message out of the archive.
        """
        message.unarchive()


    def action_delete(self, message):
        """
        Move the given message to the trash.
        """
        message.moveToTrash()


    def action_undelete(self, message):
        """
        Move the given message out of the trash.
        """
        message.removeFromTrash()


    def action_defer(self, message, days, hours, minutes):
        """
        Change the state of the given message to Deferred and schedule it to
        be changed back after the given interval has elapsed.
        """
        return message.deferFor(timedelta(days=days, hours=hours, minutes=minutes))

    def action_trainSpam(self, message):
        """
        Train the message filter using the given message as an example of
        spam.
        """
        message.trainSpam()


    def action_trainHam(self, message):
        """
        Train the message filter using the given message as an example of
        ham.
        """
        message.trainClean()


    def _getActionMethod(self, actionName):
        return getattr(self, 'action_' + actionName)


    def _performManyAct(self, action, args, messages, D):
        """
        Call C{action} on each message in C{messages}, passing the keyword
        arguments C{args}, and calling back the deferred C{D} with the number
        of read and unread messages when done

        @param action: the action to call
        @type action: function

        @param args: extra arguments to pass to the action
        @type args: C{dict}

        @param messages: the messages to act on
        @type messages: iterable of L{xquotient.exmess.Message}

        @param D: the deferred to call when we're done
        @type D: L{twisted.internet.defer.Deferred}

        @return: deferred firing with pair of (read count, unread count)
        @type: L{twisted.internet.defer.Deferred}
        """
        readCount = 0
        i = -1

        for message in messages:
            if message.read:
                readCount += 1
            yield action(message, **args)
            i += 1
        D.callback((readCount, i+1-readCount))


    def performMany(self, actionName, messages, args=None,
                    scheduler=cooperator.iterateInReactor):
        """
        Perform the action with name C{actionName} on the messages in
        C{messages}, passing C{args} as extra arguments to the action method

        @param actionName: name of an action, e.g. "archive".
        @type actionName: C{str}

        @param messages: the messages to act on
        @type messages: iterable of L{xquotient.exmess.Message}

        @param args: extra arguments to pass to the action method
        @type args: None or a C{dict}

        @param scheduler: callable which takes an iterator of deferreds and
        consumes them appropriately.  expected to return a deferred.  defaults
        to L{epsilon.cooperator.iterateInReactor}
        @type scheduler: callable

        @return: the number of affected messages which have been read and the
        number of affected messages which haven't
        @rtype: pair
        """
        if args is None:
            args = {}

        action = self._getActionMethod(actionName)
        D = defer.Deferred()

        coopDeferred = scheduler(self._performManyAct(action, args, messages, D))
        coopDeferred.addErrback(D.errback)

        return D



def upgradeInbox1to2(oldInbox):
    """
    Create the extra state tracking items necessary for efficiently determining
    distinct source addresses.
    """
    s = oldInbox.store
    newInbox = oldInbox.upgradeVersion(
        'quotient_inbox', 1, 2,
        installedOn=oldInbox.installedOn,
        uiComplexity=oldInbox.uiComplexity)
    return newInbox
registerUpgrader(upgradeInbox1to2, 'quotient_inbox', 1, 2)

declareLegacyItem(Inbox.typeName, 2,
                  dict(installedOn=attributes.reference(),
                       uiComplexity=attributes.integer(),
                       catalog=attributes.reference()))

registerAttributeCopyingUpgrader(Inbox, 2, 3)

declareLegacyItem(Inbox.typeName, 3,
                  dict(installedOn=attributes.reference(),
                       catalog=attributes.reference(),
                       uiComplexity=attributes.integer(),
                       showMoreDetail=attributes.boolean()))

def inbox3to4(old):
    """
    Copy over all attributes except for 'installedOn' and 'catalog', which
    have been deleted.

    To avoid triggering an Axiom bug where installOn will load the Inbox
    instance being upgraded and re-entrantly run its remaining upgraders,
    rely on inbox4to5 to set the 'filter' attribute which was added in this
    version of the schema either to a L{xquotient.spam.Filter} that exists
    in the store, or to a new one.
    """
    new = old.upgradeVersion(
        Inbox.typeName, 3, 4,
        privateApplication=old.store.findOrCreate(PrivateApplication),
        scheduler=old.store.findOrCreate(SubScheduler),
        messageSource=old.store.findOrCreate(MessageSource),
        quotientPrefs=old.store.findOrCreate(QuotientPreferenceCollection),
        deliveryAgent=old.store.findOrCreate(DeliveryAgent),
        messageDisplayPrefs=old.store.findOrCreate(MessageDisplayPreferenceCollection),
        uiComplexity=old.uiComplexity,
        showMoreDetail=old.showMoreDetail)

    return new
registerUpgrader(inbox3to4, Inbox.typeName, 3, 4)

declareLegacyItem(Inbox.typeName, 4,
                  dict(privateApplication=attributes.reference(),
                       scheduler=attributes.reference(),
                       messageSource=attributes.reference(),
                       quotientPrefs=attributes.reference(),
                       deliveryAgent=attributes.reference(),
                       messageDisplayPrefs=attributes.reference(),
                       uiComplexity=attributes.integer(),
                       showMoreDetail=attributes.boolean(),
                       filter=attributes.reference()))

def inbox4to5(old):
    """
    Copy over all attributes and add a reference to a newly created Focus item.
    Focus did not exist prior to the addition of this dependency, so there is
    no way one could exist in the store of an existing Inbox.

    Additionally, find or create a spam.Filter.  See inbox3to4.
    """
    focus = Focus(store=old.store)

    new = old.upgradeVersion(
        Inbox.typeName, 4, 5,
        privateApplication=old.privateApplication,
        scheduler=old.scheduler,
        messageSource=old.messageSource,
        quotientPrefs=old.quotientPrefs,
        deliveryAgent=old.deliveryAgent,
        messageDisplayPrefs=old.messageDisplayPrefs,
        uiComplexity=old.uiComplexity,
        showMoreDetail=old.showMoreDetail)

    src = old.store.findUnique(MessageSource)
    if installedOn(src) is None:
        #MessageSource was created in pre-dependency-system days
        _DependencyConnector(installee=src, target=old.store,
                             explicitlyInstalled=True,
                             store=old.store)
    # Cannot do either of these before the upgradeVersion call: while
    # examining dependencies, it is likely that the Inbox being upgraded
    # will be encountered, causing this upgrade function to run again. 
    # Repeat until the stack is full, then explode. -exarkun
    filter = new.store.findFirst(spam.Filter, default=None)
    if filter is None:
        filter = spam.Filter(store=new.store)
        installOn(filter, new.store)
    new.filter = filter

    installOn(focus, old.store)
    new.focus = focus
    return new
registerUpgrader(inbox4to5, Inbox.typeName, 4, 5)


class MailboxScrollingFragment(Scrollable, ScrollableView, LiveElement):
    """
    Specialized ScrollingFragment which supports client-side requests to alter
    the query constraints.
    """
    jsClass = u'Quotient.Mailbox.ScrollingWidget'

    def __init__(self, store):
        Scrollable.__init__(self, ixmantissa.IWebTranslator(store, None),
                            columns=(Message.sender,
                                     Message.senderDisplay,
                                     Message.recipient,
                                     Message.subject,
                                     Message.receivedWhen,
                                     Message.read,
                                     Message.sentWhen,
                                     Message.attachments,
                                     Message.everDeferred),
                            defaultSortColumn=Message.receivedWhen,
                            defaultSortAscending=False)
        LiveElement.__init__(self)
        self.store = store
        self.setViewSelection({u"view": "inbox", u"tag": None, u"person": None, u"account": None})


    def getInitialArguments(self):
        return [self.getTableMetadata(self.viewSelection)]


    def setViewSelection(self, viewSelection):
        self.viewSelection = dict(
            (k.encode('ascii'), v)
            for (k, v)
            in viewSelection.iteritems())
        self.statusQuery = _viewSelectionToMailboxSelector(
            self.store, viewSelection)


    def getTableMetadata(self, viewSelection):
        self.setViewSelection(viewSelection)
        return super(MailboxScrollingFragment, self).getTableMetadata()
    expose(getTableMetadata)


    def performQuery(self, rangeBegin, rangeEnd):
        """
        This scrolling fragment should perform queries using MailboxSelector, not
        the normal store query machinery, because it is more efficient.

        @param rangeBegin: an integer, the start of the range to retrieve.

        @param rangeEnd: an integer, the end of the range to retrieve.
        """
        return self.statusQuery.offsetQuery(rangeBegin, rangeEnd-rangeBegin)


    def performCount(self):
        """
        This scrolling fragment should perform counts using MailboxSelector, not the
        normal store query machinery, because it is more efficient.

        NB: it isn't actually more efficient.  But it could at least be changed
        to be.
        """
        return self.statusQuery.count()


    def requestRowRange(self, viewSelection, firstRow, lastRow):
        self.setViewSelection(viewSelection)
        return super(MailboxScrollingFragment, self).requestRowRange(
            firstRow, lastRow)
    expose(requestRowRange)


    def requestCurrentSize(self, viewSelection=None):
        if viewSelection is not None:
            self.setViewSelection(viewSelection)
        return super(MailboxScrollingFragment, self).requestCurrentSize()
    expose(requestCurrentSize)



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
    jsClass = u'Quotient.Mailbox.Controller'

    translator = None


    # A dictionary mapping view parameters to their current state.  Valid keys
    # in this dictionary are:
    #
    #   view - mapped to one of "all", "trash", "sent", "spam", "deferred", or "inbox"
    #   tag - mapped to a tag name or None
    #   person - mapped to a person name or None
    #   account - mapped to an account name or None
    viewSelection = None


    def __init__(self, inbox):
        athena.LiveElement.__init__(self)
        self.translator = ixmantissa.IWebTranslator(inbox.store)
        self.store = inbox.store
        self.inbox = inbox

        self.viewSelection = {
            "view": "inbox",
            "tag": None,
            "person": None,
            "account": None}

        self.scrollingFragment = self._createScrollingFragment()
        self.scrollingFragment.setFragmentParent(self)

        messages = self.scrollingFragment.performQuery(0, 2)
        while len(messages) < 2:
            messages.append(None)
        self._currentMessageAtRenderTime = messages[0]
        self._nextMessageAtRenderTime = messages[1]
        if self._currentMessageAtRenderTime is not None:
            self._currentMessageAtRenderTime.markRead()


    def _createScrollingFragment(self):
        """
        Create a Fragment which will display a mailbox.
        """
        f = MailboxScrollingFragment(self.store)
        f.docFactory = getLoader(f.fragmentName)
        return f


    def getInitialArguments(self):
        """
        Return the initial view complexity for the mailbox.
        """
        return (self.inbox.uiComplexity,)


    def _messageFragment(self, message):
        f = ixmantissa.INavigableFragment(message)
        f.setFragmentParent(self)
        return f


    def _currentAsFragment(self, currentMessage):
        if currentMessage is None:
            return ''
        return self._messageFragment(currentMessage)


    def messageDetail(self, request, tag):
        return self._currentAsFragment(self._currentMessageAtRenderTime)
    renderer(messageDetail)


    def scroller(self, request, tag):
        return self.scrollingFragment
    renderer(scroller)


    def getUserTagNames(self):
        """
        Return a list of unique tag names as unicode strings.
        """
        return list(self.inbox.store.findOrCreate(tags.Catalog).tagNames())


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
            if person == self.viewSelection["person"]:
                p = selectedOption
            else:
                p = option

            if person:
                name = person.getDisplayName()
                key = self.translator.toWebID(person)
            else:
                name = key = 'all'

            opt = p().fillSlots(
                    'personName', name).fillSlots(
                    'personKey', key)

            select[opt]
        return select
    renderer(personChooser)

    # This is the largest unread count allowed.  Counts larger than this will
    # not be reported, to save on database work.  This is, I hope, a temporary
    # feature which will be replaced once counts can be done truly efficiently,
    # by saving the intended results in the DB.
    countLimit = 1000

    def getUnreadMessageCount(self, viewSelection):
        """
        @return: number of unread messages in current view
        """
        sq = _viewSelectionToMailboxSelector(self.inbox.store, viewSelection)
        sq.refineByStatus(UNREAD_STATUS)
        sq.setLimit(self.countLimit)
        lsq = sq.count()
        return lsq

    def mailViewChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('mailViewChooser')
        option = inevow.IQ(select).patternGenerator('mailViewChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedMailViewChoice')

        counts = self.mailViewCounts()
        counts = sorted(counts.iteritems(), key=lambda (v, c): VIEWS.index(v))

        curview = self.viewSelection["view"]
        for (view, count) in counts:
            if view == curview:
                p = selectedOption
            else:
                p = option

            select[p().fillSlots(
                        'mailViewName', view.title()).fillSlots(
                        'count', count)]
        return select
    renderer(mailViewChooser)


    def tagChooser(self, request, tag):
        select = inevow.IQ(self.docFactory).onePattern('tagChooser')
        option = inevow.IQ(select).patternGenerator('tagChoice')
        selectedOption = inevow.IQ(select).patternGenerator('selectedTagChoice')
        for tag in [None] + self.getUserTagNames():
            if tag == self.viewSelection["tag"]:
                p = selectedOption
            else:
                p = option
            opt = p().fillSlots('tagName', tag or 'all')
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
            if acc == self.viewSelection["account"]:
                p = selectedOption
            else:
                p = option
            opt = p().fillSlots('accountName', acc or 'all')
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

    def fastForward(self, viewSelection, webID):
        """
        Retrieve message detail information for the specified message as well
        as look-ahead information for the next message.  Mark the specified
        message as read.
        """
        currentMessage = self.translator.fromWebID(webID)
        currentMessage.markRead()
        return self._messageFragment(currentMessage)
    expose(fastForward)

    fastForward = transacted(fastForward)

    def mailViewCounts(self):
        counts = {}
        viewSelection = dict(self.viewSelection)
        for v in VIEWS:
            viewSelection["view"] = v
            counts[v] = self.getUnreadMessageCount(viewSelection)
        return counts


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
        msgs = map(self.translator.fromWebID, messageIdentifiers)

        if extraArguments is not None:
            extraArguments = dict((k.encode('ascii'), v)
                                    for (k, v) in extraArguments.iteritems())
        return self.inbox.performMany(action, msgs, args=extraArguments)
    expose(actOnMessageIdentifierList)


    def actOnMessageBatch(self, action, viewSelection, batchType, include,
                          exclude, extraArguments=None):
        """
        Perform an action on a set of messages defined by a common
        characteristic or which are specifically included but not specifically
        excluded.
        """
        msgs = self.inbox.messagesForBatchType(
            batchType, viewSelection,
            exclude=[self.translator.fromWebID(webID)
                        for webID in exclude])

        msgs = itertools.chain(
            msgs,
            (self.translator.fromWebID(webID) for webID in include))

        if extraArguments is not None:
            extraArguments = dict((k.encode('ascii'), v)
                                    for (k, v) in extraArguments.iteritems())

        return self.inbox.performMany(action, msgs, args=extraArguments)
    expose(actOnMessageBatch)


    composeFragmentFactory = compose.ComposeFragment

    def _composeSomething(self, recipients=None, subject=u'', messageBody=u'', attachments=()):
        composer = self.inbox.store.findUnique(compose.Composer)
        cf = self.composeFragmentFactory(composer,
                                         recipients=recipients,
                                         subject=subject,
                                         messageBody=messageBody,
                                         attachments=attachments,
                                         inline=True)
        cf.setFragmentParent(self)
        cf.docFactory = getLoader(cf.fragmentName)
        return cf


    def getComposer(self):
        """
        Return an inline L{xquotient.compose.ComposeFragment} instance with
        empty to address, subject, message body and attacments
        """
        return self._composeSomething()
    expose(getComposer)

    def _getBodyForReply(self, msg):
        """
        Figure out helpful default body text for a reply to C{msg}

        @type msg: L{xquotient.exmess.Message}
        @rtype: C{unicode}
        """
        # XXX this method probably doesn't belong on InboxScreen
        if msg.sender is not None:
            origfrom = msg.sender
        else:
            origfrom = "someone who chose not to be identified"

        if msg.sentWhen is not None:
            origdate = msg.sentWhen.asHumanly()
        else:
            origdate = "an indeterminate time in the past"

        replyhead = 'On %s, %s wrote:\n>' % (origdate, origfrom.strip())

        return '\n\n\n' + replyhead + '\n> '.join(quoteBody(msg))

    def replyToMessage(self, messageIdentifier):
        curmsg = self.translator.fromWebID(messageIdentifier)
        return self._composeSomething({'to': replyTo(curmsg)},
                                      reSubject(curmsg),
                                      self._getBodyForReply(curmsg))
    expose(replyToMessage)


    def replyAllToMessage(self, messageIdentifier):
        """
        Return a L{xquotient.compose.ComposeFragment} loaded with presets that
        might be useful for sending a reply to the message identified by
        C{messageIdentifier} to all of the people involved in it

        @param messageIdentifier: web ID
        @type messageIdentifier: C{unicode}

        @rtype: L{xquotient.compose.ComposeFragment}
        """
        curmsg = self.translator.fromWebID(messageIdentifier)
        return self._composeSomething(replyToAll(curmsg),
                                      reSubject(curmsg),
                                      self._getBodyForReply(curmsg))
    expose(replyAllToMessage)


    def redirectMessage(self, messageIdentifier):
        msg = self.translator.fromWebID(messageIdentifier)

        composer = self.inbox.store.findUnique(compose.Composer)

        redirect = compose.RedirectingComposeFragment(composer, msg)
        redirect.setFragmentParent(self)
        redirect.docFactory = getLoader(redirect.fragmentName)
        return redirect
    expose(redirectMessage)


    def forwardMessage(self, messageIdentifier):
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

        currentMessageDetail = self._messageFragment(curmsg)

        return self._composeSomething(
            subject=reSubject(curmsg, 'Fwd: '),
            messageBody='\n\n' + '\n> '.join(reply),
            attachments=currentMessageDetail.attachmentParts)
    expose(forwardMessage)

registerAdapter(InboxScreen, Inbox, ixmantissa.INavigableFragment)
