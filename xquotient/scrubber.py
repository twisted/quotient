# Copyright 2005 Divmod, Inc.  See LICENSE file for details

"""
Code which can take an incoming DOM tree and \"scrub\" it clean,
removing all tag attributes which could potentially be harmful, and
turning potentially harmful tags such as script and style tags into
div tags.
"""

from twisted.web.microdom import lmx
from twisted.web.microdom import Element, Comment, Text
from twisted.web import domhelpers


# GAWD this is cheap
# remind me to put it in a new release of Twisted at some point

def setTagName(self, tagName):
    self.endTagName = self.nodeName = self.tagName = tagName

Element.setTagName = setTagName


class Scrubber(object):
    _alwaysSafeAttributes = ['class', 'id', 'style']

    _goodHtml = {
        'html': [],
        'head': [],
        'title': [],
        'body': ['bgcolor'],
        'style': ['type'],
        'a': ['href'],
        'b': [],
        'div': [],
        'i': [],
        'u': [],
        'blockquote': [],
        'strong': [],
        'em': [],
        'hr': [],
        'font': ['size', 'face', 'style', 'color'],
        'br': [],
        'ul': [],
        'li': [],
        'p': ['align'],
        'table': ['width', 'height', 'cellpadding', 'cellspacing', 'border', 'bgcolor', 'valign'],
        'tr': ['bgcolor', 'valign', 'height'],
        'td': ['width', 'height', 'valign', 'align', 'nowrap', 'bgcolor'],
        'img': ['width', 'height', 'src'],
        'form': ['action', 'method'],
        'input': ['type', 'name', 'value'],
        'label': []
        }


    def iternode(self, n):
        """
        Iterate a node using a pre-order traversal, yielding every
        Element instance.
        """
        if getattr(n, 'clean', None):
            return
        if isinstance(n, Element):
            yield n
        newChildNodes = None
        for c in n.childNodes:
            if isinstance(c, Comment):
                if not newChildNodes:
                    newChildNodes = n.childNodes[:]
            else:
                for x in self.iternode(c):
                    yield x
        if newChildNodes:
            n.childNodes = newChildNodes


    def spanify(self, node):
        node.attributes = {}
        node.childNodes = []
        node.endTagName = node.nodeName = node.tagName = 'span'
        lnew = lmx(node).span()
        lnew.node.clean = True
        return lnew

    def _handle_img(self, node):
        ## TODO: Pass some sort of context object so we can know whether the user
        ## wants to display images for this message or not
        # del node.attributes['src'] #  = '/images/missing.png'
        oldSrc = node.attributes.get('src', '')
        l = self.spanify(node)
        l['class'] = 'blocked-image'
        a = l.a(href=oldSrc)
        img = a.img(src="/images/bumnail.png", style="height: 25px; width: 25px")
        img.clean = True
        return node


    def scrub(self, node):
        """
        Remove all potentially harmful elements from the node and
        return a wrapper node.

        For reasons (perhaps dubious) of performance, this mutates its
        input.
        """
        if node.nodeName == 'html':
            filler = body = lmx().div(_class="message-html")
            for c in node.childNodes:
                if c.nodeName == 'head':
                    for hc in c.childNodes:
                        if hc.nodeName == 'title':
                            body.div(_class="message-title").text(domhelpers.gatherTextNodes(hc))
                            break
                elif c.nodeName == 'body':
                    filler = body.div(_class='message-body')
                    break
        else:
            filler = body = lmx().div(_class="message-nohtml")
        for e in self.iternode(node):
            if getattr(e, 'clean', False):
                # If I have manually exploded this node, just forget about it.
                continue
            ennl = e.nodeName.lower()
            if ennl in self._goodHtml:
                handler = getattr(self, '_handle_' + ennl, None)
                if handler is not None:
                    e = handler(e)
                newAttributes = {}
                oldAttributes = e.attributes
                e.attributes = newAttributes
                goodAttributes = self._goodHtml[ennl] + self._alwaysSafeAttributes
                for attr in goodAttributes:
                    if attr in oldAttributes:
                        newAttributes[attr] = oldAttributes[attr]
            else:
                e.attributes.clear()
                e.setTagName("div")
                e.setAttribute("class", "message-html-unknown")
                e.setAttribute("style", "display: none")
                div = Element('div')
                div.setAttribute('class', 'message-html-unknown-tag')
                div.appendChild(Text("Untrusted %s tag" % (ennl, )))
                e.childNodes.insert(0, div)
        filler.node.appendChild(node)
        return body.node

scrub = Scrubber().scrub
