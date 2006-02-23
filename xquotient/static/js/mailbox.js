// import Quotient
// import Quotient.Common
// import Quotient.Compose
// import Mantissa.People
// import LightBox

if(typeof(Quotient.Mailbox) == "undefined") {
Quotient.Mailbox = { selectedMessageColor : "#FFFF00" };
}

Quotient.Mailbox.MessageDetail = Nevow.Athena.Widget.subclass("Quotient.Mailbox.MessageDetail");
Quotient.Mailbox.MessageDetail.methods(
function messageSource(self) {
    self.callRemote("getMessageSource").addCallback(
        function(source) {
            MochiKit.DOM.replaceChildNodes("message-body",
                MochiKit.DOM.PRE(null, source));
        });
    });

Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass('Quotient.Mailbox.Controller');
Quotient.Mailbox.Controller.methods(
    function loaded(self) {
        /* temporarily disable any inbox behaviour, at the moment the
            inbox is just a scrolled table, so we don't need a lot of 
            this tdb hacking cleverness (it also won't work).  eventually
            we'll want to re-enable a lot of this functionality, like view by tag
            and such, but some of it will move into the message detail
            fragment/jsclass
        */
        var scrollContainer = self.nodeByAttribute("class", "scrolltable-container");
        var scrollNode = Nevow.Athena.NodeByAttribute(scrollContainer,
                                                        "athena:class",
                                                        "Mantissa.ScrollTable.ScrollingWidget");

        self.scrollWidget = Mantissa.ScrollTable.ScrollingWidget.get(scrollNode);
        return;

        self.allTags   = new Array();
        self.selectedRow = null;
        self.selectedRowOffset = null;

        self.callRemote("getTags").addCallback(
            function(tags) {
                self.allTags = self.allTags.concat(tags).sort();
                self.stuffTagsInDropdown();
            });

    },

    /*
    function checkTDBSize(self) {
        var row = document.getElementById("tdb-item-1");
        if(!row) {
            return setTimeout(function() { self.checkTDBSize() }, 100);
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
    },
    */

    function mailboxFeedback(self, msg) {
        document.getElementById("mailbox-log").appendChild(
            MochiKit.DOM.DIV(null, msg));
    },

    function changedView(self, select) {
        self.emptySecondAndThirdSelects(select.parentNode.parentNode);
        var options = select.getElementsByTagName("option");
        var newView = options[select.selectedIndex].firstChild.nodeValue;

        if(newView == "Tags") {
            self.filterByTag(select);
        } else if(newView == "People") {
            self.filterByPerson(select);
        } else if(newView == "Mail") {
            self.filterMail(select);
        }
    },

    function filterMail(self, firstSelect) {
        var container = firstSelect.parentNode.parentNode.parentNode;
        self.callRemote("fetchFilteredCounts", ["Mail", null]).addCallback(
            function(counts) {
                var secondSelect = Nevow.Athena.NodeByAttribute(container, 'class', 'select-2'); 
                self.populateSelectWithLabels(counts, secondSelect);

                secondSelect.onchange = function() {
                    self.filterMessages(container);
                }
            });
    },


    function filterByTag(self, firstSelect) {
        self.populateSecondSelect(firstSelect.parentNode.parentNode, self.allTags);
    },

    function filterByPerson(self, firstSelect) {
        var select = self.lookBusy(firstSelect.parentNode.parentNode, 2);
        self.callRemote("getPeople").addCallback(
            function(people) {
                self.populateSecondSelect(firstSelect.parentNode.parentNode, people);
                select.style.opacity = '1';
            }).addErrback(alert);
    },

    function emptySecondAndThirdSelects(self, container) {
        var secondSelect = Nevow.Athena.NodeByAttribute(container, 'class', 'select-2');

        while(0 < secondSelect.childNodes.length) {
            secondSelect.removeChild(secondSelect.firstChild);
        }

        self.emptyThirdSelect(container);
    },

    function emptyThirdSelect(self, container) {
        var thirdSelect = Nevow.Athena.NodeByAttribute(container, 'class', 'select-3');

        while(0 < thirdSelect.childNodes.length) {
            thirdSelect.removeChild(thirdSelect.firstChild);
        }
    },

    function populateSecondSelect(self, container, list) {
        var secondSelect = Nevow.Athena.NodeByAttribute(container, 'class', 'select-2');

        for(var i = 0; i < list.length; i++) {
            secondSelect.appendChild(
                MochiKit.DOM.OPTION(null, list[i]));
        }
        secondSelect.style.opacity = '1';
        secondSelect.onchange = function() { 
            self.emptyThirdSelect(container);
            self.fetchCountsForThirdSelect(self.lookBusy(container, 3)) };
    },


    function fetchCountsForThirdSelect(self, thirdSelect) {
        while(0 < thirdSelect.childNodes.length) {
            thirdSelect.removeChild(thirdSelect.firstChild);
        }

        var parent = thirdSelect.parentNode.parentNode.parentNode;
        var filters = [self._getFilter(parent, 'select-1'),
                        self._getFilter(parent, 'select-2')];

        self.callRemote('fetchFilteredCounts', filters).addCallback(
            function(labels) {
                self.populateSelectWithLabels(labels, thirdSelect);
                thirdSelect.onchange = function() { 
                    self.filterMessages(thirdSelect.parentNode.parentNode)
                };
            });
    },

    function lookBusy(self, containingNode, listOffset) {
        var select = Nevow.Athena.NodeByAttribute(containingNode, 'class', 'select-' + listOffset);
        select.style.opacity = '.3';
        return select;
    },

    function _getFilter(self, parent, className) {
        var select = Nevow.Athena.NodeByAttribute(parent, 'class', className);
        var options = select.getElementsByTagName('option');
        if(options.length == 0) {
            return null;
        }
        return options[select.selectedIndex].firstChild.nodeValue;
    },

    function populateSelectWithLabels(self, labels, select) {
        
        var nodeArgs = null;
        for(var i = 0; i < labels.length; i++) {
            if(labels[i][1] == 0) {
                nodeArgs = {"disabled": true};
            } else {
                nodeArgs = null;
            }
            select.appendChild(
                    MochiKit.DOM.OPTION(nodeArgs,
                        labels[i][0] + " (" + labels[i][1] + ")"));
        }
        select.style.opacity = '1';
    },

    function filterMessages(self, parent) {
        var filters = [self._getFilter(parent, 'select-1'),
                        self._getFilter(parent, 'select-2'),
                        self._getFilter(parent, 'select-3')];

        if(!filters[2]) {
            filters[2] = filters[1];
            filters[1] = null;
        }

        filters[2] = filters[2].substr(0, filters[2].match(/\(/).index - 1);

        self.callRemote('filterMessages', filters).addCallback(
            function(data) { self.replaceTDB(data) });

    },

    function replaceWithDialog(self, index, dialog) {
        var row = self.inboxTDB.nodeByAttribute('class', 'tdb-row-' + index);
        self.setChildBGColors(row, "");
        var cell = row.getElementsByTagName("td")[0];
        MochiKit.DOM.replaceChildNodes(cell,
            MochiKit.DOM.DIV({"class":"embedded-action-dialog"}, dialog));
    },

    function nextPage(self) {
        self.inboxTDB.nextPage();
    },

    function prevPage(self) {
        self.inboxTDB.prevPage();
    },

    function stuffTagsInDropdown(self) {
        var select = document.getElementById("tag-select");
        MochiKit.DOM.replaceChildNodes(select);
        select.appendChild(MochiKit.DOM.createDOM("OPTION", {"value":"--all--"}, "--all--"));

        for(i = 0; i < self.allTags.length; i++)
            select.appendChild(
                MochiKit.DOM.createDOM("OPTION", {"value":self.allTags[i]}, self.allTags[i]));
    },

    function nextOrPrevMessage(self, next) {
        var offset = self.selectedRowOffset + (next ? 1 : -1);

        var row = null;
        
        try {
            row = self.inboxTDB.nodeByAttribute('class', 'tdb-row-' + offset);
        } catch(e) {}

        /* if there is a next/prev message on this page */
        if(row) {
            /* select it, and get the message content */
            self.prepareForMessage(offset);
            self.callRemote("getMessageContent", offset).addCallback(
                function(data) { self.setMessageContent(data) });
        } else if(self.messageMetadata["has-" + (next ? "next" : "prev") + "-page"]) {
            self.callRemote((next ? "next" : "prev") + "PageAndMessage").addCallback(
                /* squish the round-trips by getting the tdb page and
                    the next/prev message at the same time */
                function(data) {
                    self.replaceTDB(data[0]);
                    self.prepareForMessage(0);
                    self.setMessageContent(data[1]);
                });
        } else {
            /* do something stupid */
            alert("sorry, there is not a next/prev message");
        }
    },

    function nextMessage(self) {
        self.nextOrPrevMessage(true);
    },

    function prevMessage(self) {
        self.nextOrPrevMessage(false);
    },

    function viewChanged(self) {
        var vselect = document.getElementById("more-views-select");
        for(var i = 0; i < vselect.childNodes.length; i++) {
            var subvselect = document.getElementById(vselect.childNodes[i].value + "-select");
            subvselect.style.display = (i == vselect.selectedIndex) ?  "" : "none";
        }
    },

    function viewByTagChanged(self, select) {
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
    },

    function viewByPersonChanged(self, select) {
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
            self.callRemote("viewByPerson", selectedValue).addErrback(
                function(err) { self.mailboxFeedback(err) });
        }
    },

    function chooseAccount(self, select) {
        var value = select.value;
        if (value == 'All') {
            value = null;
        }
        self.callRemote("viewByAccount", value).addCallback(
            function(rowCount) {
                self.scrollWidget.setViewportHeight(rowCount);
                self.scrollWidget.emptyAndRefill();
            });
    },

    function replaceTDB(self, data) {
        self.inboxTDB._setTableContent(data[0]);
        self.inboxTDB._setPageState.apply(self.inboxTDB, data[1]);
    },

    function replaceSender(self, data) {
        document.getElementById("message-detail-sender").innerHTML = data;
    },

    function toggleShowRead(self) {
        self.callRemote("toggleShowRead").addCallback(
            function(linkHTML) { self.setShowReadLinks(linkHTML) });
    },

    function _changeView(self, viewName) {
        self.callRemote(viewname).addCallback(
            function(linkHTML) { self.setViewLinks(linkHTML) }).addCallback(
                function(ign) { self.hideShowReadLinks() });
    },

    function trashView(self) { self._changeView("trashView") },

    function archiveView(self) { self._changeView("archiveView") },

    function inboxView(self) { self._changeView("inboxView") },

    function setViewLinks(self, html) {
        document.getElementById("view-container").innerHTML = html;
    },

    function showShowReadLinks(self) {
        MochiKit.DOM.setDisplayForElement("", "show-read-outer-container");
    },

    function hideShowReadLinks(self) {
        MochiKit.DOM.hideElement("show-read-outer-container");
    },

    function setShowReadLinks(self, html) {
        document.getElementById("show-read-container").innerHTML = html;
    },

    function loadMessage(self, index) {
        var md = document.getElementById("message-detail");
        md.style.opacity = '.3';
        md.style.backgroundColor = '#CACACA';

        self.everythingStart = self.loadMessageStart = new Date();
        self.showThrobber();
        self.prepareForMessage(index);
        self.callRemote("getMessageContent", index).addCallback(
            function(data) { self.setMessageContent(data) });
    },

    function maybeLoadMessage(self, event, index) {
        if(event.target.tagName == "A" || event.target.tagName == "IMG") {
            return;
        }
        self.loadMessage(index);
    },

    function applyToChildren(self, f, parent) {
        MochiKit.Base.map(function(e) { if(e.tagName) { f(e) }}, parent.childNodes);
    },

    function setChildBGColors(self, parent, color) {
        self.applyToChildren(function(e) { e.style.backgroundColor = color }, parent);
    },

    function setChildBorders(self, parent, style) {
        self.applyToChildren(function(e) { e.style.border = style }, parent);
    },

    function showThrobber(self) {
        document.getElementById("throbber").style.visibility = "visible";
    },

    function hideThrobber(self) {
        document.getElementById("throbber").style.visibility = "hidden";
    },

    function reselectMessage(self) {
        self.prepareForMessage(self.selectedRowOffset);
    },

    function prepareForMessage(self, offset) {
        /* if we are selecting a message, and there was a message selected before self */
        if(self.selectedRow) {
            /* and it hadn't been read before */
            if(self.messageMetadata && !self.messageMetadata["message"]["read"]) {
                /* and make it look like it has been read */
                try {
                    var node = Nevow.Athena.NodeByAttribute(self.selectedRow, 'class', 'unread-message');
                    if(node) {
                        node.className = 'read-message';
                    }
                    self.twiddleUnreadMessageCount(-1);
                } catch(e) {}
            }
        }

        self.selectedRowOffset = offset;
        var newlySelectedRow = self.inboxTDB.nodeByAttribute('class', 'tdb-row-' + offset);

        if(self.selectedRow != null && self.selectedRow != newlySelectedRow)
            self.setChildBGColors(self.selectedRow, "");

        self.setChildBGColors(newlySelectedRow, Quotient.Mailbox.selectedMessageColor);
        self.setChildBorders(newlySelectedRow, "");
        self.selectedRow = newlySelectedRow;
    },

    function newMessage(self) {
        if(self.selectedRow)
            self.setChildBGColors(self.selectedRow, "");
        self.callRemote("newMessage").addCallback(
            function(data) { self.setMessageContent(data) }).addCallback(
                function(ign) { self.fitMessageBodyToPage() });
    },

    function nextUnread(self) {
        if(self.messageMetadata["next-unread"]) {
            /* this thing returns [tdbhtml or null, msghtml, msgoffset] */
            self.callRemote("nextUnread").addCallback(
                function(data) {
                    if(data[0]) {
                        self.replaceTDB(data[0]);
                        self.prepareForMessage(data[2]);
                    } else {
                        self.prepareForMessage(data[2]);
                    }
                    self.setMessageContent(data[1]);
                });
        } else {
            alert("sorry, but there is not a next unread message.");
        }
    },

    function fitMessageBodyToPage(self) {
        var e = document.getElementById("message-body");
        e.style.height = document.documentElement.clientHeight - Quotient.Common.Util.findPosY(e) - 35 + "px";
    },

    function intermingle(self, string, regex, transformation) {
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
    },

    function attachPhoneToSender(self, number, node) {
        function swapImages(ign) {
            var newimg = MochiKit.DOM.IMG({"src": "/Quotient/static/images/attach-data-disabled.png"});
            node.parentNode.insertBefore(newimg, node);
            node.parentNode.removeChild(node);
            self._setExtractState("phone number", number, "acted-upon");
        }
        self.callRemote('attachPhoneToSender', number).addCallback(swapImages);
    },

    function transformURL(self, s) {
        var target = s
        if(Quotient.Common.Util.startswith('www', s)) {
            target = 'http://' + target;
        }
        return MochiKit.DOM.A({"href":target}, s);
    },

    function _setExtractState(self, etype, extract, state) {
        self.messageMetadata["message"]["extracts"][type][extract] = state;
    },

    function _lookupExtractState(self, etype, extract) {
        return self.messageMetadata["message"]["extracts"][etype][extract];
    },

    function transformPhoneNumber(self, s) {
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
    },

    function transformEmailAddress(self, s) {
        return MochiKit.DOM.A({"href":"mailto:" + s}, s);
    },

    function getTransformationForExtractType(self, etype) {
        var f = null;

        if(etype == "url") {
            return function(URL) { return self.transformURL(URL) };
        } else if(etype == "phone number") {
            return function(phone) { return self.transformPhoneNumber(phone) };
        } else if(etype == "email address") {
            return function(addr) { return self.transformEmailAddress(addr) };
        }
    },

    function highlightExtracts(self) {
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
                replacements = self.intermingle(
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
    },

    function setMessageContent(self, data) {
        self.messageMetadata = data[0];
        if(self.messageMetadata) {
            var extractDict = self.messageMetadata["message"]["extracts"];
            for(var etypename in extractDict) {
                extractDict[etypename]["pattern"] = new RegExp().compile(
                                                            extractDict[etypename]["pattern"], "i");
            }
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
        if(self.messageMetadata) {
            self.highlightExtracts();
        }
        self.extractEnd = new Date();
        //self.reportTimes();
        initLightbox();
    },

    function reportTimes(self) {
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
    },

    function showTagEntry(self) {
        with(MochiKit.DOM) {
            hideElement("tags-plus");
            setDisplayForElement("", "tags-minus");
            setDisplayForElement("", "add-tags-dialog");
            getElement("add-tags-dialog-text-input").focus();
        }
    },

    function hideTagEntry(self) {
        with(MochiKit.DOM) {
            setDisplayForElement("", "tags-plus");
            hideElement("tags-minus");
            hideElement("add-tags-dialog");
        }
    },

    function dontBubbleEvent(self, event) {
        event.cancel = true;
        event.returnValue = false;
        event.preventDefault();
        return false;
    },

    function tagAutocompleteKeyDown(self, event) {
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
    },

    function completeCurrentTag(self, tags) {
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
    },

    function appendTagCompletionToEntry(self, completion) {
        var input = document.getElementById("add-tags-dialog-text-input");
        var tags = input.value.split(/,/);
        var last = Quotient.Common.Util.normalizeTag(tags[tags.length-1]);
        input.value += completion.slice(last.length, completion.length) + ", ";
        MochiKit.DOM.replaceChildNodes("tag-completions");
        input.focus();
    },

    function gotUpdatedTagList(self, html) {
        document.getElementById("message-tags").innerHTML = html;
    },

    function addTags(self, form) {
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
                function(err) { self.mailboxFeedback(err) });
    },

    function _makeHandler(self, fdesc) {
        return "Quotient.Mailbox.Controller.get(self)." + fdesc + ";return false";
    },

    function setAttachment(self, input) {
        MochiKit.DOM.hideElement(input);
        MochiKit.DOM.appendChildNodes(input.parentNode,
            MochiKit.DOM.SPAN({"style":"font-weight: bold"}, input.value + " | "),
            MochiKit.DOM.A({"href":"#",
                "onclick":self._makeHandler("removeAttachment(this)")}, "remove"),
            MochiKit.DOM.BR(),
            MochiKit.DOM.A({"href":"#",
                "onclick":self._makeHandler("addAttachment(this)")}, "Attach another file"));
    },

    function removeAttachment(self, link) {
        var parent = link.parentNode;
        parent.removeChild(link.previousSibling);
        parent.removeChild(link.nextSibling);
        parent.removeChild(link);
    },

    function addAttachment(self, link) {
        var parent = link.parentNode;
        parent.removeChild(link);
        parent.appendChild(MochiKit.DOM.INPUT(
            {"type":"file", "style":"display: block",
            "onchange":self._makeHandler("setAttachment(self)")}));
    },

    function _twiddleCount(self, className, howMuch) {
        if(!self.counterElements) {
            self.counterElements = {};
        }
        if(!(className in self.counterElements)) {
            self.counterElements[className] = self.nodeByAttribute('class', className);
        }
        var node = self.counterElements[className];
        node.firstChild.nodeValue = parseInt(node.firstChild.nodeValue) + howMuch;
    },

    function twiddleMessageCount(self, howMuch) {
        self._twiddleCount('message-count', howMuch);
        /* we'll make the assumption that you cannot act on
           messages that are not loaded into message detail */
        if(!self.messageMetadata["message"]["read"]) {
            self.twiddleUnreadMessageCount(howMuch);
        }
    },

    function twiddleUnreadMessageCount(self, howMuch) {
        self._twiddleCount('unread-message-count', howMuch);
    },

/* message actions - each of these asks the server to modify
   the current message somehow, and expects to receive the 
   content of the next message as a result, or a ValueError
   if there is no next message */

    function markThisUnread(self) {
        self.replaceWithDialog(self.selectedRowOffset, "Marking Unread...");
        self.callRemote('markCurrentMessageUnread').addCallback(
            function(data) { self.setMessageContent(data) });
    },

    function archiveThis(self) {
        self.replaceWithDialog(self.selectedRowOffset, "Archiving...");
        self.callRemote('archiveCurrentMessage').addCallback(
            function(ign) { self.twiddleMessageCount(-1) }).addCallback(
            function(data) { self.setMessageContent(data) });
    },

    function deleteThis(self) {
        self.replaceWithDialog(self.selectedRowOffset, "Deleting...");
        self.callRemote('deleteCurrentMessage').addCallback(
            function(ign) { self.twiddleMessageCount(-1) }).addCallback(
            function(data) { self.setMessageContent(data) });
    },

    function replyToThis(self) {
        if(self.selectedRow)
            self.setChildBGColors(self.selectedRow, "");
        self.callRemote("replyToCurrentMessage").addCallback(
            function(data) { self.setMessageContent(data) }).addCallback(
                function(ign) { self.fitMessageBodyToPage() }).addErrback(
                    function(err) { self.mailboxFeedback(err) });
    },
    
    function forwardThis(self) {
        if(self.selectedRow)
            self.setChildBGColors(self.selectedRow, "");
        self.callRemote("forwardCurrentMessage").addCallback(
            function(data) { self.setMessageContent(data) }).addCallback(
                function(ign) { self.fitMessageBodyToPage() }).addErrback(
                    function(err) { self.mailboxFeedback(err) });
    });
