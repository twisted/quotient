// import Quotient.Common
// import Mantissa.People

function _quotient_getTDBController() {
    return Mantissa.TDB.Controller.get(
        Nevow.Athena.NodeByAttribute(
            document.documentElement, "athena:class", "Mantissa.TDB.Controller"
        ));
}

function _quotient_getMailboxController() {
    return Quotient.Mailbox.Controller.get(
        Nevow.Athena.NodeByAttribute(
            document.documentElement, "athena:class", "Quotient.Mailbox.Controller"
        ));
}

var mailboxController = null;
var tdbController = null;

MochiKit.DOM.addLoadEvent(function() { mailboxController = _quotient_getMailboxController();
                                       tdbController = _quotient_getTDBController(); });

if(typeof(Quotient) == "undefined") {
    Quotient = {};
}

if(typeof(Quotient.Mailbox) == "undefined") {
    Quotient.Mailbox = { selectedMessageColor : "#FFFF00" };
}

function mailboxFeedback(message) {
    log(message);
}

function log(msg) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(msg));
    document.getElementById("mailbox-log").appendChild(d);
}

Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass();

Quotient.Mailbox.Controller.method("loaded",
    function(self) {
        var tdbContainer = self.nodeByAttribute("class", "inbox-tdb-container");
        var tdbNode = Nevow.Athena.NodeByAttribute(tdbContainer,
                                                   "athena:class",
                                                   "Mantissa.TDB.Controller");

        self.inboxTDB = Mantissa.TDB.Controller.get(tdbNode);
        
        self.allTags   = new Array();
        self.selectedRow = null;
        self.selectedRowOffset = null;

        self.callRemote("getTags").addCallback(
            function(tags) {
                self.allTags = self.allTags.concat(tags).sort();
                self.stuffTagsInDropdown();
            });

    });

function quotient_addPerson(targetID) {
    mailboxController.callRemote("addPerson", targetID);
}

function _quotient_replaceWithDialog(index, dialog) {
    var row = document.getElementById("tdb-row-" + index);
    mailboxController.setChildBGColors(row, "");
    var cell = row.getElementsByTagName("td")[0];
    MochiKit.DOM.replaceChildNodes(cell,
        MochiKit.DOM.DIV({"class":"embedded-action-dialog"}, dialog));
}

function quotient_archiveMessage(index) {
    mailboxController.callRemote("archiveMessage", index);
}

function quotient_deleteMessage(index) {
    _quotient_replaceWithDialog(index, "Deleting...");
    mailboxController.callRemote("deleteMessage", index);
}

/*
Quotient.Mailbox.Controller.method("checkTDBSize", function() {
    var row = document.getElementById("tdb-item-1");
    if(!row) {
        var outerself = self;
        return setTimeout(function() { outerself.checkTDBSize() }, 100);
    }

    self.loadMessageStart = null;
    self.loadMessageEnd = null;
    self.replaceMessageDOMStart = null;
    self.replaceMessageDOMEnd = null;
    self.extractStart = null;
    self.extractEnd = null;
    self.everythingStart = null;
    self.everythingEnd = null;

    var tdb = Nevow.Athena.NodeByAttribute(
        document.getElementById("tdb-container"), "athena:class", "Mantissa.TDB.Controller"
    );
    var tdbEnd = quotient_findPosY(tdb) + tdb.clientHeight;
    var viewOpts = document.getElementById("view-options");
    tdbEnd += viewOpts.clientHeight;
    // + 15 because of padding and whatever
    var moreRows = Math.floor((document.documentElement.clientHeight - tdbEnd) / (row.clientHeight + 15)) - 1;
    self.callRemote('incrementItemsPerPage', moreRows).addCallback(
        function() {
            MochiKit.DOM.hideElement("loading-dialog");
            document.getElementById("mailbox-meat").style.visibility = 'visible' });
}
*/

Quotient.Mailbox.Controller.method("nextPage",
    function(self) {
        self.inboxTDB.nextPage();
    });

Quotient.Mailbox.Controller.method("prevPage",
    function(self) {
        self.inboxTDB.prevPage();
    });

Quotient.Mailbox.Controller.method("stuffTagsInDropdown",
    function(self) {
        var select = document.getElementById("tag-select");
        MochiKit.DOM.replaceChildNodes(select);
        select.appendChild(MochiKit.DOM.createDOM("OPTION", {"value":"--all--"}, "--all--"));

        for(i = 0; i < self.allTags.length; i++)
            select.appendChild(
                MochiKit.DOM.createDOM("OPTION", {"value":self.allTags[i]}, self.allTags[i]));
    });

Quotient.Mailbox.Controller.method("viewChanged",
    function(self) {
        var vselect = document.getElementById("more-views-select");
        for(var i = 0; i < vselect.childNodes.length; i++) {
            var subvselect = document.getElementById(vselect.childNodes[i].value + "-select");
            subvselect.style.display = (i == vselect.selectedIndex) ?  "" : "none";
        }
    });

Quotient.Mailbox.Controller.method("viewByTagChanged",
    function(self, select) {
        var options = 0; var selectedValue = null;
        for(var i = 0; i < select.childNodes.length; i++) {
            if(options == select.selectedIndex) {
                selectedValue = select.childNodes[i].value;
                break;
            }
            if(select.childNodes[i].tagName)
                options++;
        }
        if(selectedValue == select.firstChild.value) {
            self.callRemote("viewByAllTags");
        } else {
            self.callRemote("viewByTag", selectedValue);
        }
    });

Quotient.Mailbox.Controller.method("viewByPersonChanged",
    function(self, select) {
        var options = 0; var selectedValue = null;
        for(var i = 0; i < select.childNodes.length; i++) {
            if(options == select.selectedIndex) {
                selectedValue = select.childNodes[i].value;
                break;
            }
            if(select.childNodes[i].tagName)
                options++;
        }
        if(selectedValue == select.firstChild.value) {
            self.callRemote("viewByAllPeople");
        } else {
            self.callRemote("viewByPerson", selectedValue).addErrback(mailboxFeedback);
        }
    });


Quotient.Mailbox.Controller.method("replaceTDB",
    function(self, data) {
        tdbController._setTableContent(data[0]);
    });

Quotient.Mailbox.Controller.method("replaceSender",
    function(self, data) {
        document.getElementById("message-detail-sender").innerHTML = data;
    });

Quotient.Mailbox.Controller.method("toggleShowRead",
    function(self) {
        self.callRemote("toggleShowRead").addCallback(
            function(linkHTML) { self.setShowReadLinks(linkHTML) });
    });

Quotient.Mailbox.Controller.method("_changeView",
    function(self, viewName) {
        self.callRemote(viewname).addCallback(
            function(linkHTML) { self.setViewLinks(linkHTML) }).addCallback(
                function(ign) { self.hideShowReadLinks() });
    });

Quotient.Mailbox.Controller.method("trashView",
    function(self) { self._changeView("trashView") });

Quotient.Mailbox.Controller.method("archiveView",
    function(self) { self._changeView("archiveView") });

Quotient.Mailbox.Controller.method("inboxView",
    function(self) { self._changeView("inboxView") });

Quotient.Mailbox.Controller.method("setViewLinks",
    function(self, html) {
        document.getElementById("view-container").innerHTML = html;
    });

Quotient.Mailbox.Controller.method("showShowReadLinks",
    function(self) {
        MochiKit.DOM.setDisplayForElement("", "show-read-outer-container");
    });

Quotient.Mailbox.Controller.method("hideShowReadLinks",
    function(self) {
        MochiKit.DOM.hideElement("show-read-outer-container");
    });

Quotient.Mailbox.Controller.method("setShowReadLinks",
    function(self, html) {
        document.getElementById("show-read-container").innerHTML = html;
    });

Quotient.Mailbox.Controller.method("loadMessage",
    function(self, index) {
        var md = document.getElementById("message-detail");
        md.style.opacity = '.3';
        md.style.backgroundColor = '#CACACA';

        self.everythingStart = self.loadMessageStart = new Date();
        self.showThrobber();
        self.prepareForMessage(index);
        self.callRemote("getMessageContent", index).addCallback(
            function(data) { self.setMessageContent(data) });
    });

Quotient.Mailbox.Controller.method("applyToChildren", 
    function(self, f, parent) {
        MochiKit.Base.map(function(e) { if(e.tagName) { f(e) }}, parent.childNodes);
    });

Quotient.Mailbox.Controller.method("setChildBGColors",
    function(self, parent, color) {
        self.applyToChildren(function(e) { e.style.backgroundColor = color }, parent);
    });

Quotient.Mailbox.Controller.method("setChildBorders",
    function(self, parent, style) {
        self.applyToChildren(function(e) { e.style.border = style }, parent);
    });

Quotient.Mailbox.Controller.method("showThrobber",
    function(self) {
        document.getElementById("throbber").style.visibility = "visible";
    });

Quotient.Mailbox.Controller.method("hideThrobber",
    function(self) {
        document.getElementById("throbber").style.visibility = "hidden";
    });

Quotient.Mailbox.Controller.method("reselectMessage",
    function(self) {
        self.prepareForMessage(self.selectedRowOffset);
    });

Quotient.Mailbox.Controller.method("prepareForMessage",
    function(self, offset) {
        /* if we are selecting a message, and there was a message selected before self */
        if(self.selectedRow) {
            /* and it hadn't been read before */
            if(self.messageMetadata && !self.messageMetadata["message"]["read"]) {
                /* mark it read */
                self.callRemote('markCurrentMessageRead');
                /* and make it look like it has been read */
                try {
                    var node = Nevow.Athena.NodeByAttribute(self.selectedRow, 'class', 'unread-message');
                    if(node) {
                        node.className = 'read-message';
                    }
                } catch(e) {}
            }
        }

        self.selectedRowOffset = offset;
        var newlySelectedRow = tdbController.nodeByAttribute('class', 'tdb-row-' + offset);

        if(self.selectedRow != null && self.selectedRow != newlySelectedRow)
            self.setChildBGColors(self.selectedRow, "");

        self.setChildBGColors(newlySelectedRow, Quotient.Mailbox.selectedMessageColor);
        self.setChildBorders(newlySelectedRow, "");
        self.selectedRow = newlySelectedRow;
    });

Quotient.Mailbox.Controller.method("newMessage",
    function(self) {
        if(self.selectedRow)
            self.setChildBGColors(self.selectedRow, "");
        self.callRemote("newMessage").addCallback(
            function(data) { self.setMessageContent(data) }).addCallback(
                function(ign) { self.fitMessageBodyToPage() });
    });

Quotient.Mailbox.Controller.method("fitMessageBodyToPage",
    function(self) {
        var e = document.getElementById("message-body");
        e.style.height = document.documentElement.clientHeight - Quotient.Common.Util.findPosY(e) - 35 + "px";
    });

function quotient_intermingle(string, regex, transformation) {
    var lpiece = null;
    var mpiece = null;
    var rpiece = null;
    var piece  = null;
    var match  = null;
    var matches = null;

    var pieces = [string];

    while(true) {
        piece = pieces[pieces.length-1];
        match = regex.exec(piece);
        if(match) {
            matches++;
            lpiece = piece.slice(0, match.index);
            mpiece = match[0];
            rpiece = piece.slice(match.index+mpiece.length, piece.length);
            pieces.pop();
            pieces = pieces.concat([lpiece, transformation(mpiece), rpiece]);
        } else { break }
    }
    if(matches) {
        return pieces;
    }
    return null;
}

Quotient.Mailbox.Controller.method("attachPhoneToSender",
    function(self, number, node) {
        function swapImages(ign) {
            var newimg = MochiKit.DOM.IMG({"src": "/Quotient/static/images/attach-data-disabled.png"});
            node.parentNode.insertBefore(newimg, node);
            node.parentNode.removeChild(node);
            self._setExtractState("phone number", number, "acted-upon");
        }
        self.callRemote('attachPhoneToSender', number).addCallback(swapImages);
    });

Quotient.Mailbox.Controller.method("transformURL",
    function(self, s) {
        var target = s
        if(Quotient.Common.Util.startswith('www', s)) {
            target = 'http://' + target;
        }
        return MochiKit.DOM.A({"href":target}, s);
    });

Quotient.Mailbox.Controller.method("_setExtractState",
    function(self, etype, extract, state) {
        self.messageMetadata["message"]["extracts"][type][extract] = state;
    });

Quotient.Mailbox.Controller.method("_lookupExtractState",
    function(self, etype, extract) {
        return self.messageMetadata["message"]["extracts"][etype][extract];
    });

Quotient.Mailbox.Controller.method("transformPhoneNumber",
    function(self, s) {
        var enabled = self.messageMetadata["sender"]["is-person"] &&
                            self._lookupExtractState("phone number", s) == "unused";
        var icon = null;

        if(enabled) {
            var handler = "Quotient.Mailbox.Controller.get(this).attachPhoneToSender";
            handler += "('" + s + "', this); return false";
            var link = MochiKit.DOM.A({"href": "#","onclick": handler},
                            MochiKit.DOM.IMG({"src": "/Quotient/static/images/attach-data.png",
                                            "border": "0"}));
            icon = link;
        } else {
            icon = MochiKit.DOM.IMG(
                        {"src": "/Quotient/static/images/attach-data-disabled.png"});
        }

        return MochiKit.DOM.SPAN({}, [s, icon]);
    });

Quotient.Mailbox.Controller.method("transformEmailAddress",
    function(self, s) {
        return MochiKit.DOM.A({"href":"mailto:" + s}, s);
    });

Quotient.Mailbox.Controller.method("getTransformationForExtractType",
    function(self, etype) {
        var f = null;

        if(etype == "url") {
            f = self.transformURL;
        } else if(etype == "phone number") {
            f = self.transformPhoneNumber;
        } else if(etype == "email address") {
            f = self.transformEmailAddress;
        }

        return f;
    });

Quotient.Mailbox.Controller.method("highlightExtracts",
    function(self, outerp) {
        var body = document.getElementById("message-body");
        var replacements = null;
        var replacement = null;

        var j = null;
        var i = null;
        var elem = null;
        var regex = null;
        var etypes = self.messageMetadata["message"]["extracts"];

        for(var k in etypes) {
            etype = etypes[k];

            i = 0;

            while(true) {
                elem = body.childNodes[i];

                if(!elem) { break };
                if(elem.tagName) { i++; continue };

                replacements = quotient_intermingle(
                                    elem.nodeValue, etype["pattern"], self.getTransformationForExtractType(k));

                if(!replacements) { i++; continue };

                for(j = 0; j < replacements.length; j++) {
                    replacement = replacements[j];
                    if(!replacement.tagName) {
                        replacement = document.createTextNode(replacement);
                    }
                    body.insertBefore(replacement, elem);
                }
                body.removeChild(elem);
                i += j;
            }
        }
    });

Quotient.Mailbox.Controller.method("setMessageContent",
    function(self, data) {
        self.messageMetadata = data[0];
        var extractDict = self.messageMetadata["message"]["extracts"];
        for(var etypename in extractDict) {
            extractDict[etypename]["pattern"] = new RegExp().compile(
                                                        extractDict[etypename]["pattern"], "i");
        }
        self.loadMessageEnd = new Date();
        var md = document.getElementById("message-detail");
        md.style.opacity = '';
        md.style.backgroundColor = '';
        self.replaceMessageDOMStart = new Date();
        md.innerHTML = data[1];
        self.replaceMessageDOMEnd = new Date();
        var iframe = document.getElementById("content-iframe");
        if(iframe) {
            Quotient.Common.Util.resizeIFrame(iframe);
        }
        self.hideThrobber();
        self.extractStart = new Date();
        self.highlightExtracts();
        self.extractEnd = new Date();
        self.reportTimes();
    });

Quotient.Mailbox.Controller.method("reportTimes",
    function(self) {
        self.everythingEnd = new Date();
        function deltaInMsecs(first, last) {
            return last.getTime() - first.getTime();
        }
        var report =  "Load Message: " + deltaInMsecs(self.loadMessageStart, self.loadMessageEnd) + " ms | ";
        report += "Replace Message Detail DOM: " + deltaInMsecs(self.replaceMessageDOMStart,
                                                                self.replaceMessageDOMEnd) + " ms | ";
        report += "Extracts: " + deltaInMsecs(self.extractStart, self.extractEnd) + " ms | ";
        report += "Everything (not a total): " + deltaInMsecs(self.everythingStart,
                                                            self.everythingEnd) + " ms";
        var trb = document.getElementById("time-report-box");
        if(!trb.childNodes.length) {
            trb.appendChild(document.createTextNode(""));
        }

        trb.firstChild.nodeValue = report;
    });

Quotient.Mailbox.Controller.method("showTagEntry",
    function(self) {
        with(MochiKit.DOM) {
            hideElement("tags-plus");
            setDisplayForElement("", "tags-minus");
            setDisplayForElement("", "add-tags-dialog");
            getElement("add-tags-dialog-text-input").focus();
        }
    });

Quotient.Mailbox.Controller.method("hideTagEntry",
    function(self) {
        with(MochiKit.DOM) {
            setDisplayForElement("", "tags-plus");
            hideElement("tags-minus");
            hideElement("add-tags-dialog");
        }
    });

Quotient.Mailbox.Controller.method("dontBubbleEvent",
    function(self, event) {
        event.cancel = true;
        event.returnValue = false;
        event.preventDefault();
        return false;
    });

Quotient.Mailbox.Controller.method("tagAutocompleteKeyDown",
    function(self, event) {
        var TAB = 9;
        var DEL = 8;

        if(event.keyCode == TAB) {
            var completions = document.getElementById("tag-completions");
            if(0 < completions.childNodes.length) {
                self.appendTagCompletionToEntry(
                    completions.firstChild.firstChild.nodeValue);
                MochiKit.DOM.replaceChildNodes(completions);
            }
            return self.dontBubbleEvent(event);
        } else if(event.keyCode == DEL) {
            var tags = event.originalTarget.value;
            if(0 < tags.length)
                tags = tags.slice(0, tags.length-1);
            self.completeCurrentTag(tags);
        }
        return true;
    });

Quotient.Mailbox.Controller.method("completeCurrentTag",
    function(self, tags) {
        tags = tags.split(/,/);
        var last = Quotient.Common.Util.normalizeTag(tags[tags.length - 1]);

        var completionContainer = document.getElementById("tag-completions");
        MochiKit.DOM.replaceChildNodes(completionContainer);

        if(last.length == 0)
            return;

        var completions = MochiKit.Base.filter(
                MochiKit.Base.partial(Quotient.Common.Util.startswith, last),
                self.allTags);

        var handler = "Quotient.Mailbox.Controller.get(this)";
        handler += ".appendTagCompletionToEntry(this.firstChild.nodeValue)";

        var attrs = null;

        for(i = 0; i < completions.length; i++) {
            attrs = {"href":"#", "onclick":handler+";return false"};
            if(i == 0)
                attrs["style"] = "font-weight: bold";

            completionContainer.appendChild(
                MochiKit.DOM.A(attrs, completions[i]));

            if(i < completions.length-1)
                completionContainer.appendChild(
                    document.createTextNode(", "));
        }
    });

Quotient.Mailbox.Controller.method("appendTagCompletionToEntry",
    function(self, completion) {
        var input = document.getElementById("add-tags-dialog-text-input");
        var tags = input.value.split(/,/);
        var last = Quotient.Common.Util.normalizeTag(tags[tags.length-1]);
        input.value += completion.slice(last.length, completion.length) + ", ";
        MochiKit.DOM.replaceChildNodes("tag-completions");
        input.focus();
    });

Quotient.Mailbox.Controller.method("gotUpdatedTagList",
    function(self, html) {
        document.getElementById("message-tags").innerHTML = html;
    });

Quotient.Mailbox.Controller.method("addTags",
    function(self, form) {
        var mtags = document.getElementById("message-tags");
        MochiKit.DOM.replaceChildNodes(mtags);
        mtags.appendChild(document.createTextNode("Loading..."));

        var tag  = form.tag.value;
        var tags = tag.match(/,/) ? tag.split(/,/) : [tag];
        tags = MochiKit.Base.filter(function(s) { return 0 < s.length },
                                    MochiKit.Base.map(Quotient.Common.Util.normalizeTag, tags));

        var newTags = 0;
        var i = 0;
        var j = 0;

        var allTagsContains = function(tag) {
            for(j = 0; j < self.allTags.length; j++) {
                if(self.allTags[j] == tag) {
                    return true;
                }
            }
            return false;
        }

        for(i = 0; i < tags.length; i++) {
            if(!allTagsContains(tags[i])) {
                newTags++;
                self.allTags.push(tags[i]);
            }
        }

        if(0 < newTags) { /* at least pretend to be doing self efficiently */
            self.allTags = self.allTags.sort();
            self.stuffTagsInDropdown();
        }
        form.tag.value = ""; form.tag.focus();
        self.hideTagEntry();
        MochiKit.DOM.replaceChildNodes("tag-completions");
        self.callRemote("addTags", tags).addCallback(
            function(tl) { self.gotUpdatedTagList(tl) }).addErrback(
                function(err) { mailboxFeedback(err) });
    });

Quotient.Mailbox.Controller.method("_makeHandler",
    function(self, fdesc) {
        return "Quotient.Mailbox.Controller.get(self)." + fdesc + ";return false";

    });

Quotient.Mailbox.Controller.method("setAttachment",
    function(self, input) {
        MochiKit.DOM.hideElement(input);
        MochiKit.DOM.appendChildNodes(input.parentNode,
            MochiKit.DOM.SPAN({"style":"font-weight: bold"}, input.value + " | "),
            MochiKit.DOM.A({"href":"#",
                "onclick":self._makeHandler("removeAttachment(this)")}, "remove"),
            MochiKit.DOM.BR(),
            MochiKit.DOM.A({"href":"#",
                "onclick":self._makeHandler("addAttachment(this)")}, "Attach another file"));
    });

Quotient.Mailbox.Controller.method("removeAttachment",
    function(self, link) {
        var parent = link.parentNode;
        parent.removeChild(link.previousSibling);
        parent.removeChild(link.nextSibling);
        parent.removeChild(link);
    });

Quotient.Mailbox.Controller.method("addAttachment",
    function(self, link) {
        var parent = link.parentNode;
        parent.removeChild(link);
        parent.appendChild(MochiKit.DOM.INPUT(
            {"type":"file", "style":"display: block",
            "onchange":self._makeHandler("setAttachment(self)")}));
    });

/* message actions - each of these asks the server to modify
   the current message somehow, and expects to receive the 
   content of the next message as a result, or a ValueError
   if there is no next message */

Quotient.Mailbox.Controller.method("markThisUnread",
    function(self) {
        _quotient_replaceWithDialog(self.selectedRowOffset, "Marking Unread...");
        self.callRemote('markCurrentMessageUnread').addCallback(
            function(data) { self.setMessageContent(data) });
    });

Quotient.Mailbox.Controller.method("archiveThis",
    function(self) {
        _quotient_replaceWithDialog(self.selectedRowOffset, "Archiving...");
        self.callRemote('archiveCurrentMessage').addCallback(
            function(data) { self.setMessageContent(data) });
    });

Quotient.Mailbox.Controller.method("deleteThis",
    function(self) {
        _quotient_replaceWithDialog(self.selectedRowOffset, "Deleting...");
        self.callRemote('deleteCurrentMessage').addCallback(
            function(data) { self.setMessageContent(data) });
    });

Quotient.Mailbox.Controller.method("replyToThis",
    function(self) {
        if(self.selectedRow)
            self.setChildBGColors(self.selectedRow, "");
        self.callRemote("replyToCurrentMessage").addCallback(
            function(data) { self.setMessageContent(data) }).addCallback(
                function(ign) { self.fitMessageBodyToPage() }).addErrback(
                    mailboxFeedback);
    });
