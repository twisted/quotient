import re

from datetime import timedelta

from epsilon.extime import Time

from twisted.internet.defer import Deferred
from twisted.python import log
from twisted.web import microdom, domhelpers
from twisted.web.client import getPage

from axiom.item import Item
from axiom import attributes
from axiom.scheduler import IScheduler

from nevow import entities

_entityReference = re.compile('&([a-z]+);', re.I)

class BadFeed(Exception):
    """
    The feed is either seriously malformed, or we don't support the format
    """
    pass

class FeedItem(Item):
    typeName = 'rss_feed_item'
    schemaVersion = 1

    subject = attributes.text()
    description = attributes.text()
    timestamp = attributes.timestamp()
    guid = attributes.text()
    feed = attributes.reference()

class Feed(Item):
    typeName = 'rss_feed'
    schemaVersion = 1

    url = attributes.text()
    author = attributes.reference() # Person item
    title = attributes.text()

    working = attributes.inmemory()
    listeners = attributes.inmemory()

    def __init__(self, *a, **k):
        super(Feed, self).__init__(*a, **k)
        IScheduler(self.store).schedule(self, Time())

    def run(self):
        # maybe do something better
        if not self.working:
            self.working = True

            D = getPage(str(self.url))
            D.addCallback(self._cbRan)
            D.addErrback(self._ebRan)

            def stopWorking():
                self.working = False

            D.addCallback(lambda ign: stopWorking())

        return Time() + timedelta(seconds=600)

    def activate(self):
        self.working = False
        self.listeners = []

    def notifyAfterFetch(self):
        d = Deferred()
        self.listeners.append(d)
        return d

    def _cbRan(self, page):
        doc = microdom.parseString(page)
        i = 0
        for item in self._rssItems(doc):
            i += 1
            (subj, descr, when, link, guid) = item
            descr = self._cleanDescription(descr)

            if link is not None:
                descr += '<br /><br /><a href="%s">Original Article</a>' % (link,)

            if guid is not None:
                existing = self.store.findUnique(FeedItem,
                                                 FeedItem.guid == guid,
                                                 default=None)
                if existing is not None:
                    continue
            else:
                duplicate = False
                for item in self.store.query(FeedItem, FeedItem.timestamp == when):
                    if item.description == descr:
                        duplicate = True
                        break
                if duplicate:
                    continue

            FeedItem(store=self.store,
                     subject=subj,
                     description=descr,
                     timestamp=when,
                     guid=guid,
                     feed=self)

        while 0 < len(self.listeners):
            self.listeners.pop().callback(i+1)

    def _ebRan(self, err):
        while 0 < len(self.listeners):
            self.listeners.pop().errback(err)

        # if we're bad feed with no items, delete ourselves
        if (err.check(BadFeed) and
                self.store.findFirst(
                    FeedItem, FeedItem.feed == self, default=None) is None):
            self.deleteFromStore()

    def _cleanDescription(self, desc):
        desc = desc.replace('&quot;', '"').replace('&#34;', '"')
        for eref in set(_entityReference.findall(desc)):
            entity = getattr(entities, eref, None)
            if entity is not None:
                desc = desc.replace('&' + eref + ';', '&#' + entity.num + ';')
        return desc

    def _rssItems(self, doc):
        # Make sure it is RSS 2.0
        ele = doc.childNodes[0]
        if ele.tagName == 'rss':
            if ele.getAttribute('version') in ('0.91', '2.0'):
                return self._rss2Items(ele)
            else:
                raise BadFeed("Unsupported feed: only RSS 0.91 and 2.0 are supported")
        elif ele.tagName == 'feed':
            if ele.getAttribute('version') in ('0.3',):
                return self._atom3Items(ele)
            else:
                raise BadFeed("Unsupported feed: only Atom 0.3 is supported")
        else:
            raise BadFeed("Unsupported feed: Cannot determine type")

    def _rss2Items(self, ele):
        # Wade through the channel mode
        ele = ele.childNodes[0]
        if ele.tagName != 'channel':
            raise BadFeed("Malformed RSS 2.0, giving up parsing")

        for node in ele.childNodes:
            if node.tagName == 'item':
                yield self._rss2MIME(node)
            elif node.tagName == 'title':
                title = self._text(node)
                if title != self.title:
                    self.title = title

    def _atom3Items(self, ele):
        for node in ele.childNodes:
            if node.tagName == 'entry':
                yield self._atom3MIME(node)
            elif node.tagName == 'title':
                title = self._text(node)
                if title != self.title:
                    self.title = title

    def _rss2MIME(self, item):
        parts = {}
        for node in item.childNodes:
            parts[node.tagName] = node
        try:
            subj = self._text(parts['title'])
        except KeyError:
            subj = u'No Subject'

        descr = self._text(parts['description'])

        for key in ('pubdate', 'dc:date'):
            try:
                pub = parts['pubdate']
            except KeyError:
                pass
            else:
                when = Time.fromRFC2822(self._text(pub))
                break
        else:
            when = Time.fromPOSIXTimestamp(0)

        if 'link' in parts:
            link = self._text(parts['link'])
        else:
            link = None

        if 'guid' in parts:
            guid = self._text(parts['guid'])
        else:
            guid = None

        return subj, descr, when, link, guid

    def _atom3MIME(self, item):
        parts = {}
        for node in item.childNodes:
            parts[node.tagName] = node

        try:
            subj = self._text(parts['title'])
        except KeyError:
            subj = u'No Subject'

        descr = self._text(parts['content'])
        when = Time.fromISO8601TimeAndDate(self._text(parts['issued']))
        link = parts['link'].getAttribute("href")
        guid = self._text(parts['id'])

        return subj, descr, when, link, guid

    def _text(self, node):
        return unicode(domhelpers.gatherTextNodes(node, dounescape=True), 'utf-8', 'replace')

