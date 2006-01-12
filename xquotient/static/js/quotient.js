// import Quotient.Common
// import Mantissa.People


/* these quotient_* functions are necessary because we are supplying
   alternative TDB navigation buttons that are outside the jurisdiction
   of the TDB's containing node */

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
/*
Array.prototype.contains = function(e) {
    for(var i = 0; i < this.length; i++)
        if(this[i] == e)
            return true;
    return false;
}
*/

function mailboxFeedback(message) {
    log(message);
}

function log(msg) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(msg));
    document.getElementById("mailbox-log").appendChild(d);
}

Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass();

Quotient.Mailbox.Controller.prototype.loaded = function() {
    var outerthis = this;

    window.onresize = function() { outerthis.checkTDBSize() }
    //setTimeout(function() { outerthis.checkTDBSize() }, 100);
    this.allTags   = new Array();
    this.selectedRow = null;
    this.selectedRowOffset = null;

    this.callRemote("getTags").addCallback(
        function(tags) {
            outerthis.allTags = outerthis.allTags.concat(tags).sort();
            outerthis.stuffTagsInDropdown();
        });

}

function quotient_prevPage() {
    tdbController.prevPage();
}

function quotient_nextPage() {
    tdbController.nextPage();
}

function quotient_addPerson(targetID) {
    mailboxController.callRemote("addPerson", targetID);
}

function _quotient_replaceWithDialog(index, dialog) {
    var row = MochiKit.DOM.getElement("tdb-row-" + index);
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

function quotient_loadMessage(event, idx) {
    if(event.originalTarget.tagName == "A")
        return;
    mailboxController.loadMessage(idx);
}

Quotient.Mailbox.Controller.prototype.checkTDBSize = function() {
    var row = MochiKit.DOM.getElement("tdb-item-1");
    if(!row) {
        var outerthis = this;
        return setTimeout(function() { outerthis.checkTDBSize() }, 100);
    }

    this.loadMessageStart = null;
    this.loadMessageEnd = null;
    this.replaceMessageDOMStart = null;
    this.replaceMessageDOMEnd = null;
    this.extractStart = null;
    this.extractEnd = null;
    this.everythingStart = null;
    this.everythingEnd = null;

    var tdb = Nevow.Athena.NodeByAttribute(
        MochiKit.DOM.getElement("tdb-container"), "athena:class", "Mantissa.TDB.Controller"
    );
    var tdbEnd = quotient_findPosY(tdb) + tdb.clientHeight;
    var viewOpts = MochiKit.DOM.getElement("view-options");
    tdbEnd += viewOpts.clientHeight;
    // + 15 because of padding and whatever
    var moreRows = Math.floor((document.documentElement.clientHeight - tdbEnd) / (row.clientHeight + 15)) - 1;
    this.callRemote('incrementItemsPerPage', moreRows).addCallback(
        function() {
            MochiKit.DOM.hideElement("loading-dialog");
            MochiKit.DOM.getElement("mailbox-meat").style.visibility = 'visible' });
}

Quotient.Mailbox.Controller.prototype.stuffTagsInDropdown = function() {
    var select = MochiKit.DOM.getElement("tag-select");
    MochiKit.DOM.replaceChildNodes(select);
    select.appendChild(MochiKit.DOM.createDOM("OPTION", {"value":"--all--"}, "--all--"));

    for(i = 0; i < this.allTags.length; i++)
        select.appendChild(
            MochiKit.DOM.createDOM("OPTION", {"value":this.allTags[i]}, this.allTags[i]));
}

Quotient.Mailbox.Controller.prototype.viewChanged = function() {
    var vselect = MochiKit.DOM.getElement("more-views-select");
    for(var i = 0; i < vselect.childNodes.length; i++) {
        var subvselect = MochiKit.DOM.getElement(vselect.childNodes[i].value + "-select");
        subvselect.style.display = (i == vselect.selectedIndex) ?  "" : "none";
    }
}

Quotient.Mailbox.Controller.prototype.viewByTagChanged = function(select) {
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
        this.callRemote("viewByAllTags");
    } else {
        this.callRemote("viewByTag", selectedValue);
    }
}

Quotient.Mailbox.Controller.prototype.viewByPersonChanged = function(select) {
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
        this.callRemote("viewByAllPeople");
    } else {
        this.callRemote("viewByPerson", selectedValue).addErrback(mailboxFeedback);
    }
}


Quotient.Mailbox.Controller.prototype.replaceTDB = function(data) {
    tdbController._setTableContent(data[0]);
}

Quotient.Mailbox.Controller.prototype.replaceSender = function(data) {
    MochiKit.DOM.getElement("message-detail-sender").innerHTML = data;
}

Quotient.Mailbox.Controller.prototype.toggleShowRead = function() {
    this.callRemote("toggleShowRead").addCallback(MochiKit.Base.bind(this.setShowReadLinks, this));
}

Quotient.Mailbox.Controller.prototype.trashView = function() {
    this.callRemote("trashView").addCallback(MochiKit.Base.bind(this.setViewLinks, this)).addCallback(
        MochiKit.Base.bind(function(ign) { this.hideShowReadLinks() }, this));
}

Quotient.Mailbox.Controller.prototype.archiveView = function() {
    this.callRemote("archiveView").addCallback(MochiKit.Base.bind(this.setViewLinks, this)).addCallback(
        MochiKit.Base.bind(function(ign) { this.hideShowReadLinks() }, this));
}

Quotient.Mailbox.Controller.prototype.inboxView = function() {
    this.callRemote("inboxView").addCallback(MochiKit.Base.bind(this.setViewLinks, this)).addCallback(
        MochiKit.Base.bind(function(ign) { this.showShowReadLinks() }, this));
}

Quotient.Mailbox.Controller.prototype.setViewLinks = function(html) {
    MochiKit.DOM.getElement("view-container").innerHTML = html;
}

Quotient.Mailbox.Controller.prototype.showShowReadLinks = function() {
    MochiKit.DOM.setDisplayForElement("", "show-read-outer-container");
}

Quotient.Mailbox.Controller.prototype.hideShowReadLinks = function() {
    MochiKit.DOM.hideElement("show-read-outer-container");
}

Quotient.Mailbox.Controller.prototype.setShowReadLinks = function(html) {
    MochiKit.DOM.getElement("show-read-container").innerHTML = html;
}

Quotient.Mailbox.Controller.prototype.loadMessage = function(idx) {
    var md = MochiKit.DOM.getElement("message-detail")
    md.style.opacity = '.3';
    md.style.backgroundColor = '#CACACA';

    this.everythingStart = this.loadMessageStart = new Date();
    this.showThrobber();
    this.prepareForMessage(idx);
    this.callRemote("getMessageContent", idx).addCallback(
                                    MochiKit.Base.bind(this.setMessageContent, this));
}

Quotient.Mailbox.Controller.prototype.applyToChildren = function(f, parent) {
    MochiKit.Base.map(function(e) { if(e.tagName) { f(e) }}, parent.childNodes);
}

Quotient.Mailbox.Controller.prototype.setChildBGColors = function(parent, color) {
    this.applyToChildren(function(e) { e.style.backgroundColor = color }, parent);
}

Quotient.Mailbox.Controller.prototype.setChildBorders = function(parent, style) {
    this.applyToChildren(function(e) { e.style.border = style }, parent);
}

Quotient.Mailbox.Controller.prototype.showThrobber = function() {
    MochiKit.DOM.getElement("throbber").style.visibility = "visible";
}
Quotient.Mailbox.Controller.prototype.hideThrobber = function() {
    MochiKit.DOM.getElement("throbber").style.visibility = "hidden";
}

Quotient.Mailbox.Controller.prototype.reselectMessage = function() {
    this.prepareForMessage(this.selectedRowOffset);
}

Quotient.Mailbox.Controller.prototype.prepareForMessage = function(offset) {
    /* if we are selecting a message, and there was a message selected before this */
    if(this.selectedRow) {
        /* and it hadn't been read before */
        if(this.messageMetadata && !this.messageMetadata["message"]["read"]) {
            /* mark it read */
            this.callRemote('markCurrentMessageRead');
            /* and make it look like it has been read */
            try {
                var node = Nevow.Athena.NodeByAttribute(this.selectedRow, 'class', 'unread-message');
                if(node) {
                    node.className = 'read-message';
                }
            } catch(e) {}
        }
    }

    this.selectedRowOffset = offset;
    var newlySelectedRow = tdbController.nodeByAttribute('class', 'tdb-row-' + offset);

    if(this.selectedRow != null && this.selectedRow != newlySelectedRow)
        this.setChildBGColors(this.selectedRow, "");

    this.setChildBGColors(newlySelectedRow, Quotient.Mailbox.selectedMessageColor);
    this.setChildBorders(newlySelectedRow, "");
    this.selectedRow = newlySelectedRow;
}

Quotient.Mailbox.Controller.prototype.newMessage = function() {
    if(this.selectedRow)
        this.setChildBGColors(this.selectedRow, "");
    this.callRemote("newMessage").addCallback(
        this.setMessageContent).addCallback(this.fitMessageBodyToPage);
}

Quotient.Mailbox.Controller.prototype.fitMessageBodyToPage = function() {
    var e = MochiKit.DOM.getElement("message-body");
    e.style.height = document.documentElement.clientHeight - quotient_findPosY(e) - 35 + "px";
}

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

Quotient.Mailbox.Controller.prototype.attachPhoneToSender = function(number, node) {
    var outerthis = this;
    function swapImages(ign) {
        var newimg = MochiKit.DOM.IMG({"src": "/Quotient/static/images/attach-data-disabled.png"});
        node.parentNode.insertBefore(newimg, node);
        node.parentNode.removeChild(node);
        this._setExtractState("phone number", number, "acted-upon");
    }
    this.callRemote('attachPhoneToSender', number).addCallback(swapImages);
}

Quotient.Mailbox.Controller.prototype.transformURL = function(s) {
    var target = s
    if(quotient_startswith('www', s)) {
        target = 'http://' + target;
    }
    return MochiKit.DOM.A({"href":target}, s);
}

Quotient.Mailbox.Controller.prototype._setExtractState = function(etype, extract, state) {
    this.messageMetadata["message"]["extracts"][type][extract] = state;
}

Quotient.Mailbox.Controller.prototype._lookupExtractState = function(etype, extract) {
    return this.messageMetadata["message"]["extracts"][etype][extract];
}

Quotient.Mailbox.Controller.prototype.transformPhoneNumber = function(s) {
    const enabled = this.messageMetadata["sender"]["is-person"] &&
                        this._lookupExtractState("phone number", s) == "unused";
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
}

Quotient.Mailbox.Controller.prototype.transformEmailAddress = function(s) {
    return MochiKit.DOM.A({"href":"mailto:" + s}, s);
}

Quotient.Mailbox.Controller.prototype.getTransformationForExtractType = function(etype) {
    var f = null;

    if(etype == "url") {
        f = this.transformURL;
    } else if(etype == "phone number") {
        f = this.transformPhoneNumber;
    } else if(etype == "email address") {
        f = this.transformEmailAddress;
    }

    return MochiKit.Base.bind(f, this);
}

Quotient.Mailbox.Controller.prototype.highlightExtracts = function(outerp) {
    var body = MochiKit.DOM.getElement("message-body");
    var replacements = null;
    var replacement = null;

    var j = null;
    var i = null;
    var elem = null;
    var regex = null;
    const etypes = this.messageMetadata["message"]["extracts"];

    for(var k in etypes) {
        etype = etypes[k];

        i = 0;

        while(true) {
            elem = body.childNodes[i];

            if(!elem) { break };
            if(elem.tagName) { i++; continue };

            replacements = quotient_intermingle(
                                elem.nodeValue, etype["pattern"], this.getTransformationForExtractType(k));

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
}

Quotient.Mailbox.Controller.prototype.setMessageContent = function(data) {
    this.messageMetadata = data[0];
    var extractDict = this.messageMetadata["message"]["extracts"];
    for(var etypename in extractDict) {
        extractDict[etypename]["pattern"] = new RegExp().compile(
                                                    extractDict[etypename]["pattern"], "i");
    }
    this.loadMessageEnd = new Date();
    var md = MochiKit.DOM.getElement("message-detail");
    md.style.opacity = '';
    md.style.backgroundColor = '';
    this.replaceMessageDOMStart = new Date();
    md.innerHTML = data[1];
    this.replaceMessageDOMEnd = new Date();
    var iframe = MochiKit.DOM.getElement("content-iframe");
    if(iframe)
        resizeIFrame(iframe);
    this.hideThrobber();
    this.extractStart = new Date();
    this.highlightExtracts();
    this.extractEnd = new Date();
    this.reportTimes();
}

Quotient.Mailbox.Controller.prototype.reportTimes = function() {
    this.everythingEnd = new Date();
    function deltaInMsecs(first, last) {
        return last.getTime() - first.getTime();
    }
    var report =  "Load Message: " + deltaInMsecs(this.loadMessageStart, this.loadMessageEnd) + " ms | ";
    report += "Replace Message Detail DOM: " + deltaInMsecs(this.replaceMessageDOMStart,
                                                            this.replaceMessageDOMEnd) + " ms | ";
    report += "Extracts: " + deltaInMsecs(this.extractStart, this.extractEnd) + " ms | ";
    report += "Everything (not a total): " + deltaInMsecs(this.everythingStart,
                                                          this.everythingEnd) + " ms";
    var trb = MochiKit.DOM.getElement("time-report-box");
    if(!trb.childNodes.length) {
        trb.appendChild(document.createTextNode(""));
    }

    trb.firstChild.nodeValue = report;
}

Quotient.Mailbox.Controller.prototype.showTagEntry = function() {
    with(MochiKit.DOM) {
        hideElement("tags-plus");
        setDisplayForElement("", "tags-minus");
        setDisplayForElement("", "add-tags-dialog");
        getElement("add-tags-dialog-text-input").focus();
    }
}

Quotient.Mailbox.Controller.prototype.hideTagEntry = function() {
    with(MochiKit.DOM) {
        setDisplayForElement("", "tags-plus");
        hideElement("tags-minus");
        hideElement("add-tags-dialog");
    }
}

Quotient.Mailbox.Controller.prototype.dontBubbleEvent = function(event) {
    event.cancel = true;
    event.returnValue = false;
    event.preventDefault();
    return false;
}

Quotient.Mailbox.Controller.prototype.tagAutocompleteKeyDown = function(event) {
    const TAB = 9;
    const DEL = 8;

    if(event.keyCode == TAB) {
        var completions = MochiKit.DOM.getElement("tag-completions");
        if(0 < completions.childNodes.length) {
            this.appendTagCompletionToEntry(
                completions.firstChild.firstChild.nodeValue);
            MochiKit.DOM.replaceChildNodes(completions);
        }
        return this.dontBubbleEvent(event);
    } else if(event.keyCode == DEL) {
        var tags = event.originalTarget.value;
        if(0 < tags.length)
            tags = tags.slice(0, tags.length-1);
        this.completeCurrentTag(tags);
    }
    return true;
}

Quotient.Mailbox.Controller.prototype.completeCurrentTag = function(tags) {
    tags = tags.split(/,/);
    var last = quotient_normalizeTag(tags[tags.length - 1]);

    var completionContainer = MochiKit.DOM.getElement("tag-completions");
    MochiKit.DOM.replaceChildNodes(completionContainer);

    if(last.length == 0)
        return;

    var completions = MochiKit.Base.filter(
            MochiKit.Base.partial(quotient_startswith, last),
            this.allTags);

    var handler = "Quotient.Mailbox.Controller.get(this).appendTagCompletionToEntry(this.firstChild.nodeValue)";
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
}

Quotient.Mailbox.Controller.prototype.appendTagCompletionToEntry = function(completion) {
    var input = MochiKit.DOM.getElement("add-tags-dialog-text-input");
    var tags = input.value.split(/,/);
    var last = quotient_normalizeTag(tags[tags.length-1]);
    input.value += completion.slice(last.length, completion.length) + ", ";
    MochiKit.DOM.replaceChildNodes("tag-completions");
    input.focus();
}

Quotient.Mailbox.Controller.prototype.gotUpdatedTagList = function(html) {
    MochiKit.DOM.getElement("message-tags").innerHTML = html;
}

Quotient.Mailbox.Controller.prototype.addTags = function(form) {
    var mtags = MochiKit.DOM.getElement("message-tags");
    MochiKit.DOM.replaceChildNodes(mtags);
    mtags.appendChild(document.createTextNode("Loading..."));

    var tag  = form.tag.value;
    var tags = tag.match(/,/) ? tag.split(/,/) : [tag];
    tags = MochiKit.Base.filter(function(s) { return 0 < s.length },
                                MochiKit.Base.map(quotient_normalizeTag, tags));

    var newTags = 0;
    for(var i = 0; i < tags.length; i++) {
        for(var j = 0; j < this.allTags.length; j++) {
            if(this.allTags[j] == tags[i]) {
                newTags++;
                this.allTags.push(tags[i]);
                break;
            }
        }
    }

    if(0 < newTags) { /* at least pretend to be doing this efficiently */
        this.allTags = this.allTags.sort();
        this.stuffTagsInDropdown();
    }
    form.tag.value = ""; form.tag.focus();
    this.hideTagEntry();
    MochiKit.DOM.replaceChildNodes("tag-completions");
    this.callRemote("addTags", tags).addCallback(this.gotUpdatedTagList).addErrback(mailboxFeedback);
}

Quotient.Mailbox.Controller.prototype._makeHandler = function(fdesc) {
    return "Quotient.Mailbox.Controller.get(this)." + fdesc + ";return false";
}

Quotient.Mailbox.Controller.prototype.setAttachment = function(input) {
    MochiKit.DOM.hideElement(input);
    MochiKit.DOM.appendChildNodes(input.parentNode,
        MochiKit.DOM.SPAN({"style":"font-weight: bold"}, input.value + " | "),
        MochiKit.DOM.A({"href":"#",
            "onclick":this._makeHandler("removeAttachment(this)")}, "remove"),
        MochiKit.DOM.BR(),
        MochiKit.DOM.A({"href":"#",
            "onclick":this._makeHandler("addAttachment(this)")}, "Attach another file"));
}

Quotient.Mailbox.Controller.prototype.removeAttachment = function(link) {
    var parent = link.parentNode;
    parent.removeChild(link.previousSibling);
    parent.removeChild(link.nextSibling);
    parent.removeChild(link);
}

Quotient.Mailbox.Controller.prototype.addAttachment = function(link) {
    var parent = link.parentNode;
    parent.removeChild(link);
    parent.appendChild(MochiKit.DOM.INPUT(
        {"type":"file", "style":"display: block",
         "onchange":this._makeHandler("setAttachment(this)")}));
}

/* message actions - each of these asks the server to modify
   the current message somehow, and expects to receive the 
   content of the next message as a result, or a ValueError
   if there is no next message */

Quotient.Mailbox.Controller.prototype.markThisUnread = function() {
    _quotient_replaceWithDialog(this.selectedRowOffset, "Marking Unread...");
    var d = this.callRemote('markCurrentMessageUnread');
    d.addCallback(MochiKit.Base.bind(this.setMessageContent, this));
}

Quotient.Mailbox.Controller.prototype.archiveThis = function() {
    _quotient_replaceWithDialog(this.selectedRowOffset, "Archiving...");
    var d = this.callRemote('archiveCurrentMessage');
    d.addCallback(MochiKit.Base.bind(this.setMessageContent, this));
}

Quotient.Mailbox.Controller.prototype.deleteThis = function() {
    _quotient_replaceWithDialog(this.selectedRowOffset, "Deleting...");
    var d = this.callRemote('deleteCurrentMessage')
    d.addCallback(MochiKit.Base.bind(this.setMessageContent, this));
}

Quotient.Mailbox.Controller.prototype.replyToThis = function() {
    if(this.selectedRow)
        this.setChildBGColors(this.selectedRow, "");
    this.callRemote("replyToCurrentMessage").addCallback(
        MochiKit.Base.bind(this.setMessageContent, this)).addCallback(
                            MochiKit.Base.bind(this.fitMessageBodyToPage, this)).addErrback(
                                            mailboxFeedback);
}
