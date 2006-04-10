// import Quotient
// import Quotient.Common
// import Mantissa.People
// import LightBox
// import Mantissa.ScrollTable

Quotient.Mailbox = {};

Quotient.Mailbox.MessageDetail = Nevow.Athena.Widget.subclass("Quotient.Mailbox.MessageDetail");
Quotient.Mailbox.MessageDetail.methods(
    function messageSource(self) {
        self.callRemote("getMessageSource").addCallback(
            function(source) {
                MochiKit.DOM.replaceChildNodes(
                    self.nodeByAttribute("class", "message-body"),
                    MochiKit.DOM.PRE(null, source));
        });
    });

Quotient.Mailbox.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass();
Quotient.Mailbox.ScrollingWidget.methods(
    function __init__(self, node) {
        Quotient.Mailbox.ScrollingWidget.upcall(self, "__init__", node);
        self.columnAliases = {"receivedWhen": "Date", "senderDisplay": "Sender"};
        self.node.style.width = '300px';
        self.node.style.border = "";
        self.node.style.borderLeft = self.node.style.borderBottom = "solid 1px #336699";
        self.ypos = Quotient.Common.Util.findPosY(self._scrollViewport);
        self.resized();
    },

    function resized(self) {
        var pageHeight = document.documentElement.clientHeight;
        self._scrollViewport.style.height = (pageHeight - self.ypos - 14) + "px";
    },

    function _createRowHeaders(self, columnNames) {
        var columnOffsets = {};
        for( var i = 0; i < columnNames.length; i++ ) {
            if(self.skipColumn(columnNames[i])) {
                continue;
            }
            columnOffsets[columnNames[i]] = i;
        }
        self._columnOffsets = columnOffsets;
    },

    function setSortInfo(self, currentSortColumn, isAscendingNow) {},

    function setRowHeight(self) {
        var r = MochiKit.DOM.DIV({"style": "visibility: hidden",
                                  "class": "q-scroll-row"},
                    [MochiKit.DOM.DIV({"class": "subject"}, "TEST!!!"),
                     MochiKit.DOM.DIV({"class": "sender"}, "TEST!!!"),
                     MochiKit.DOM.DIV(null, "TEST!!!")]);

        self._scrollContent.appendChild(r);
        var rowHeight = r.clientHeight + 1;
        self._scrollContent.removeChild(r);

        self._rowHeight = rowHeight;
    },

    function _selectRow(self, rowOffset, row) {
        if(self._selectedRow) {
            self._selectedRow.style.backgroundColor = '';
        }
        if(!row) {
            row = self._rows[rowOffset][1];
        }

        row.style.backgroundColor = '#FFFFFF';
        self._selectedRow = row;
        self._selectedRowOffset = rowOffset;
    },

    function makeRowElement(self, rowOffset, rowData, cells) {
        var style = "";
        if(!rowData["read"]) {
            style += "font-weight: bold";
        }
        return MochiKit.DOM.A(
            {"class": "q-scroll-row",
             "href": "#",
             "style": style,
             "onclick": function() {
                self._selectRow(rowOffset, this);
                self.widgetParent.fastForward(rowData["__id__"]);
                return false;
            }},
            MochiKit.Base.filter(null, cells));
    },

    function makeCellElement(self, colName, rowData) {
        if(colName == "receivedWhen") {
            colName = "sentWhen";
        }
        var massage = function(colName) {
            return self.massageColumnValue(
                colName, self.columnTypes[colName], rowData[colName]);
        }

        var attrs = {};
        if(colName == "senderDisplay") {
            attrs["class"] = "sender";
        } else if(colName == "subject") {
            attrs["class"] = "subject";
        }
            
        return MochiKit.DOM.DIV(attrs, massage(colName));
    },

    function formatDate(self, d) {
        function to12Hour(HH, MM) {
            var meridian;
            if(HH == 0) {
                HH += 12;
                meridian = "AM";
            } else if(0 < HH && HH < 12) {
                meridian = "AM";
            } else if(HH == 12) {
                meridian = "PM";
            } else {
                HH -= 12;
                meridian = "PM";
            }
            return HH + ":" + MM + " " + meridian;
        }
        function pad(n) {
            return (n < 10) ? "0" + n : n;
        }
        function explode(d) {
            return d.toString().split(/ /);
        }
        var parts = explode(d);
        var todayParts = explode(new Date());
        
        /* parts.slice(1,4) == [Month, Day, Year] */
        if(parts.slice(1, 4) == todayParts.slice(1, 4)) {
            /* it's today! */
            return to12Hour(d.getHours(), d.getMinutes()); /* e.g. 12:15 PM */
        }
        if(parts[3] == todayParts[3]) {
            /* it's this year */
            parts[1] + " " + parts[2]; /* e.g. Jan 12 */
        }
        return [pad(d.getFullYear()),
                pad(d.getMonth()+1),
                pad(d.getDate())].join("-");
    },

    function skipColumn(self, name) {
        return name == "read" || name == "sentWhen";
    },

    function removeCurrentRow(self) {
        self._selectedRow.parentNode.removeChild(self._selectedRow);
        self.adjustViewportHeight(-1);
        var top;
        for(var i = self._selectedRowOffset; i < self._rows.length && self._rows[i]; i++) {
            top = parseInt(self._rows[i][1].style.top);
            self._rows[i][1].style.top = (top - self._rowHeight) + "px";
        }
        self._rows = self._rows.slice(
                        0, self._selectedRowOffset).concat(
                            self._rows.slice(self._selectedRowOffset+1, self._rows.length));
    },

    function cbRowsFetched(self) {
        if(self._pendingRowSelection) {
            self._pendingRowSelection();
            self._pendingRowSelection = null;
        }
    });


Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass('Quotient.Mailbox.Controller');
Quotient.Mailbox.Controller.methods(
    function __init__(self, node, messageCount, complexityLevel) {
        MochiKit.DOM.addToCallStack(window, "onresize",
            function() {
                self.resized(false);
            }, false);

        Quotient.Mailbox.Controller.upcall(self, "__init__", node);
        self.currentMessageData = null;

        /*
         * This attribute keeps track of which of the weird message view
         * settings is currently selected.  Currently, the server renders the
         * initially selected view as Inbox.  If that changes, this code will
         * need to be updated.
         *
         * Hopefully, this will all be thrown away before too long, though,
         * because it is stupid.
         */
        self._viewingByView = 'Inbox';

        var contentTable = self.firstNodeByAttribute("class", "content-table");
        var tbody = contentTable.getElementsByTagName("tbody")[0];
        self.contentTableRows = [];
        for(var i = 0; i < tbody.childNodes.length; i++) {
            if(tbody.childNodes[i].tagName && 
               tbody.childNodes[i].tagName.toLowerCase() == "tr") {
                self.contentTableRows.push(tbody.childNodes[i]);
            }
        }
        self.inboxContainer = self.firstWithClass("inbox-container",
                                                  self.contentTableRows[0]);

        self.messageDetail = self.firstWithClass("message-detail",
                                                 self.contentTableRows[1]);
        self.mastheadBottom = self.firstWithClass("masthead-bottom",
                                                  self.contentTableRows[2]);

        self.ypos = Quotient.Common.Util.findPosY(self.messageDetail);

        var scrollNode = Nevow.Athena.FirstNodeByAttribute(self.contentTableRows[1],
                                                           "athena:class",
                                                           "Quotient.Mailbox.ScrollingWidget");

        self.scrollWidget = Quotient.Mailbox.ScrollingWidget.get(scrollNode);
        self.scrolltableContainer = self.scrollWidget.node.parentNode;
        self.resized(true);

        self._selectAndFetchRow(0, function() { return null });

        self.setMessageCount(messageCount);

        self.delayedLoad(complexityLevel);
    },
     
    function delayedLoad(self, complexityLevel) {
        setTimeout(function() {
            self.setScrollTablePosition("absolute");
            self.highlightExtracts();
            self.setInitialComplexity(complexityLevel);
            self.finishedLoading();
        }, 0);
    },

    function setInitialComplexity(self, complexityLevel) {
        if(1 < complexityLevel) {
            var cc = self.firstWithClass("complexity-container", self.inboxContainer);
            self.setComplexity(complexityLevel,
                                cc.getElementsByTagName("img")[3-complexityLevel],
                                false);
            /* firefox goofs the table layout unless we make it
                factor all three columns into it.  the user won't
                actually see anything strange */
            if(complexityLevel == 2) {
                self._setComplexityVisibility(3);
                /* two vanilla calls aren't enough, firefox won't
                    update the viewport */
                setTimeout(function() {
                    self._setComplexityVisibility(2);
                }, 1);
            }
        }
    },

    /* resize the inbox table and contents.
     * @param initialResize: is this the first/initial resize? 
     *                       (if so, then our layout constraint jiggery-pokery
     *                        is not necessary)
     */

    function resized(self, initialResize) {
        if(!initialResize) {
            self.scrollWidget.resized();
        }
        self.scrollWidget._scrollViewport.style.height = 
            (parseInt(self.scrollWidget._scrollViewport.style.height) - self.mastheadBottom.clientHeight) + "px";
        var pageHeight = document.documentElement.clientHeight;
        self.messageDetail.style.height = (pageHeight - self.ypos - 15 - self.mastheadBottom.clientHeight) + "px";
        var pos = self.scrolltableContainer.style.position;

        if(initialResize) {
            return;
        }

        if(self.complexityLevel == undefined) {
            self.complexityLevel = 1;
        }
        var complexityLevel = self.complexityLevel;
        var newComplexityLevel = complexityLevel + 1;
        if(newComplexityLevel == 4) {
            newComplexityLevel = 1;
        }
        /* so this kind of sucks.  what happens is that changing the
         * height of the elements in the middle row results in a bunch
         * of whitespace underneath, because the y position of the
         * bottom row isn't recalculated for some reason.  once the
         * browser is jogged a little bit, it recalculates the position
         * fine.  changing the complexity setting to something different,
         * and then changing it back after a token delay seems to be the
         * easiest way to do this */

        self._setComplexityVisibility(newComplexityLevel);
        setTimeout(function() {
            self._setComplexityVisibility(complexityLevel)
            }, 1);
    },

    function finishedLoading(self) {
        self.node.removeChild(self.firstWithClass("loading", self.node));
    },

    function firstWithClass(self, cls, n) {
        if(!n) {
            n = self.inboxContainer;
        }
        return Nevow.Athena.FirstNodeByAttribute(n, "class", cls);
    },

    function complexityHover(self, img) {
        if(img.className == "selected-complexity-icon") {
            return;
        }
        if(-1 < img.src.search("unselected")) {
            img.src = img.src.replace("unselected", "selected");
        } else {
            img.src = img.src.replace("selected", "unselected");
        }
    },

    function _setComplexityVisibility(self, c) {
        if(c == 1) {
            self.setViewsContainerDisplay("none");
            self.setScrollTablePosition("absolute");
        } else if(c == 2) {
            self.setScrollTablePosition("static");
            self.setViewsContainerDisplay("none");
        } else if(c == 3) {
            self.setScrollTablePosition("static");
            self.setViewsContainerDisplay("");
        }
    },

    function setComplexity(self, level, node, report) {
        /* level = integer between 1 and 3
           node = the image that represents this complexity level
           report = boolean - should we persist this change */
        if(node.className == "selected-complexity-icon") {
            return;
        }

        self._setComplexityVisibility(level);
        self.complexityLevel = level;

        if(report) {
            self.callRemote("setComplexity", level);
        }

        var gparent = node.parentNode.parentNode;
        var selected = Nevow.Athena.FirstNodeByAttribute(
                        gparent, "class", "selected-complexity-icon");
        selected.className = "complexity-icon";
        self.complexityHover(selected);
        if(!report) {
            self.complexityHover(node);
        }
        node.className = "selected-complexity-icon";
    },

    function setViewsContainerDisplay(self, d) {
        if(!self.viewsContainer) {
            self.viewsContainer = self.firstWithClass("view-pane-container",
                                                      self.contentTableRows[1]);
        }
        self.viewsContainer.style.display = d;
    },

    function setScrollTablePosition(self, p) {
        self.scrolltableContainer.style.position = p;
        var d;
        if(p == "absolute") {
            d = "none";
        } else {
            d = "";
        }
        if(!self.scrolltableHeader) {
            self.scrolltableHeader = self.firstWithClass("scrolltable-header",
                                                         self.contentTableRows[0]);
            self.scrolltableFooter = self.firstWithClass("scrolltable-footer",
                                                         self.contentTableRows[2]);
        }

        self.scrolltableHeader.style.display = self.scrolltableFooter.style.display = d;
    },

    function fastForward(self, toMessageID) {
        self.messageDetail.style.opacity = .2;
        self.callRemote("fastForward", toMessageID).addCallback(
            function(messageData) {
                self.messageDetail.style.opacity = 1;
                self.setMessageContent(messageData, true);
            });
    },

    function _chooseViewParameter(self, viewFunction, n, catchAll /* = true */) {
        if (catchAll == undefined) {
            catchAll = true;
        }

        var value = n.firstChild.firstChild.nodeValue;
        if (catchAll && value == 'All') {
            value = null;
        }
        self.callRemote(viewFunction, value).addCallback(
            function(messageData) {
                self.setMessageCount(messageData[0]);
                self.setMessageContent(messageData[1], true);
                self.scrollWidget.setViewportHeight(messageData[0]);
                self.scrollWidget.emptyAndRefill();
                self.scrollWidget._pendingRowSelection = function() {
                    self._selectAndFetchRow(0, function() { return null }, false);
                }
            });
    },

    function _selectListOption(self, n) {
        var sibs = n.parentNode.childNodes;
        for(var i = 0; i < sibs.length; i++) {
            if(sibs[i].className == "selected-list-option") {
                sibs[i].className = "list-option";
                if(!sibs[i].onclick) {
                    sibs[i].onclick = n.onclick;
                }
            }
        }
        n.className = "selected-list-option";
    },

    /**
     * Select a new tag from which to display messages.  Adjust local state to
     * indicate which tag is being viewed and, if necessary, ask the server
     * for the messages to display.
     *
     * @param n: The node which this input handler is attached to.
     * @return: C{undefined}
     */
    function chooseTag(self, n) {
        self._selectListOption(n);
        return self._chooseViewParameter('viewByTag', n);
    },

    /**
     * Select a new, semantically random set of messages to display.  Adjust
     * local state to indicate which random crap is being viewed and, if
     * necessary, ask the server for the messages to display.
     *
     * @param n: The node which this input handler is attached to.
     * @return: C{undefined}
     */
    function chooseMailView(self, n) {
        self._viewingByView = n.firstChild.firstChild.nodeValue;
        self._selectListOption(n);
        self._chooseViewParameter('viewByMailType', n, false);
    },

    /**
     * Select a new account, the messages from which to display.  Adjust local
     * state to indicate which account's messages are being viewed and, if
     * necessary, ask the server for the messages to display.
     *
     * @param n: The node which this input handler is attached to.
     * @return: C{undefined}
     */
    function chooseAccount(self, n) {
        self._selectListOption(n);
        return self._chooseViewParameter('viewByAccount', n);
    },

    /**
     * Select a new person, the messages from which to display.  Adjust local
     * state to indicate which person's messages are being viewed and, if
     * necessary, ask the server for the messages to display.
     *
     * @param n: The node which this input handler is attached to.
     * @return: C{undefined}
     */
    function choosePerson(self, n) {
        var keyn = Nevow.Athena.FirstNodeByAttribute(n, "class", "person-key");
        self._selectListOption(n);
        return self._chooseViewParameter('viewByPerson', keyn);
    },

    function _selectAndFetchRow(self, offset, elementFactory, requestMoreRowsIfNeeded) {
        /* ideally we want to disable these actions if they aren't going
           to behave as advertised - as it stands they'll just do nothing
           if there isn't a next/prev row.
           
           elementFactory is a function that returns the row that should be
           highlighted.  it is a function because the row element might or
           might not exist when we called (e.g. if we have to request more
           rows to fufill the request) */
        
        if(offset < 0) { return }
        if(typeof requestMoreRowsIfNeeded === 'undefined') {
            requestMoreRowsIfNeeded = true;
        }

        var sw = self.scrollWidget;
        if(sw._rows.length < offset+1) {
            if(requestMoreRowsIfNeeded) {
                /* free up some space */
                sw._scrollViewport.scrollTop += sw._rowHeight * 3;
                sw.scrolled();
                /* the scroll widget's cbRowsFetched
                   method will call this function when
                   it gets rows */
                sw._pendingRowSelection = function() {
                    /* call ourselves, passing additional argument
                       indicating that we shouldn't go through this
                       rigmarole a second time if there still aren't enough rows */
                    self._selectAndFetchRow(offset, elementFactory, false);
                }
            }
            return;
        }

        sw._selectRow(offset, elementFactory());
    },

    /**
     * Tell the server to perform some action on the currently visible
     * message.
     *
     * @param action: A string describing the action to be performed.  One of::
     *
     *     "archive"
     *     "delete"
     *     "defer"
     *     "replyTo"
     *     "train"
     *
     * @param isProgress: A boolean indicating whether the message will be
     * removed from the current message list and the progress bar updated to
     * reflect this.
     *
     * @return: C{undefined}
     */
    function touch(self, action, isProgress) {
        var remoteArgs = [action + "CurrentMessage"];
        remoteArgs.push(isProgress);
        for(var i = 3; i < arguments.length; i++) {
            remoteArgs.push(arguments[i]);
        }
        var next = self.scrollWidget._selectedRow.nextSibling;
        var index = self.scrollWidget._selectedRowOffset;

        if(!next) {
            next = self.scrollWidget._selectedRow.previousSibling;
            index--;
        }

        if (isProgress) {
            self.scrollWidget.removeCurrentRow();
        }

        if(next.tagName) {
            self.scrollWidget._selectRow(index, next);
            self.scrollWidget.scrolled();
        }

        self.messageDetail.style.opacity = .2;
        self.callRemote.apply(self, remoteArgs).addCallback(
            function(nextMessage) {
                self.messageDetail.style.opacity = 1;
                self.setMessageContent(nextMessage, true);
                if(isProgress) {
                    if(!self.progressBar) {
                        self.progressBar = self.firstWithClass("progress-bar",
                                                               self.contentTableRows[0]);
                    }
                    self.progressBar.style.borderRight = "solid 1px #6699CC";
                    self.remainingMessages--;
                    self.setProgressWidth();
                }
            });
    },

    function setMessageCount(self, count) {
        self.remainingMessages = count;
        self.totalMessages = count;
        self.setProgressWidth();
    },

    function setProgressWidth(self) {
        if(!self.progressBar) {
            self.progressBar = self.firstWithClass("progress-bar",
                                                   self.contentTableRows[0]);
            self.messageActions = self.nodesByAttribute("class", "message-actions");
        }
        var visibility;
        if(self.remainingMessages == 0) {
            visibility = "hidden";
        } else {
            visibility = "";
            self.progressBar.style.width = Math.ceil((self.remainingMessages / self.totalMessages) * 100) + "%";
        }

        self.progressBar.style.visibility = visibility;
        for(var i = 0; i < self.messageActions.length; i++) {
            self.messageActions[i].style.visibility = visibility;
        }
    },

    function archiveThis(self, n) {
        /*
         * Archived messages show up in the "All" view.  So, if we are in any
         * view other than that, this action should make the message
         * disappear.
         */
        self.touch("archive", self._viewingByView != "All");
    },

    function deleteThis(self, n) {
        self.touch("delete", self._viewingByView != "Trash");
    },

    function showDeferForm(self) {
        if(!self.deferForm) {
            self.deferForm = self.nodeByAttribute("class", "defer-form");
        }
        self.deferForm.style.display = "";
    },

    function hideDeferForm(self) {
        self.deferForm.style.display = "none";
    },

    function defer(self, node) {
        var options = node.getElementsByTagName("option");
        var value = options[node.selectedIndex].firstChild.nodeValue;
        node.selectedIndex = 0;

        if(value == "other...") {
            self.showDeferForm();
            return;
        }
        if(value == "Defer") {
            return;
        }
        var args;
        if(value == "1 day") { 
            args = [1, 0, 0];
        } else if(value == "1 hour") {
            args = [0, 1, 0];
        } else if(value == "12 hours") {
            args = [0, 12, 0];
        } else if(value == "1 week") {
            args = [7, 0, 0];
        }
        self.touch.apply(self, ["defer", true].concat(args));
    },

    function deferThis(self) {
        var days = parseInt(self.deferForm.days.value);
        var hours = parseInt(self.deferForm.hours.value);
        var minutes = parseInt(self.deferForm.minutes.value);
        self.deferForm.style.display = "none";
        self.touch("defer", true, days, hours, minutes);
    },

    function replyToThis(self, n) {
        /*
         * This brings up a composey widget thing.  When you *send* that
         * message (or save it as a draft or whatever, I suppose), *then* this
         * action is considered to have been taken, and the message should be
         * archived and possibly removed from the view.  But nothing happens
         * *here*.
         */
        self.touch("replyTo", false);
    },

    function forwardThis(self, n) {
        /*
         * See replyToThis
         */
        self.touch("forward", false);
    },


    function trainSpam(self) {
        self.touch(
            "train",
            (self._viewingByView != "Spam"),
            true);
        return false;
    },

    function trainHam(self) {
        self.touch(
            "train",
            (self._viewingByView == "Spam"),
            false);
        return false;
    },

    function intermingle(self, string, regex, transformation) {
        var lpiece, mpiece, rpiece, piece, match;
        var pieces = [string];
        var matches = 0;

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

    function transformURL(self, s) {
        var target = s
        if(Quotient.Common.Util.startswith('www', s)) {
            target = 'http://' + target;
        }
        return MochiKit.DOM.A({"href":target}, s);
    },

    function highlightExtracts(self) {
        try {
            var messageBody = self.firstNodeByAttribute("class", "message-body");
        } catch(e) { return }
        var replacements, replacement, replacementLen, j, elem;
        var i = 0;
        var regex = /(?:\w+:\/\/|www\.)[^\s\<\>\'\(\)\"]+[^\s\<\>\(\)\'\"\?\.]/;

        while(true) {
            elem = messageBody.childNodes[i];

            if(!elem) {
                break
            }

            if(elem.tagName) {
                i++;
                continue
            }

            replacements = self.intermingle(
                                elem.nodeValue, regex, self.transformURL);

            if(!replacements) {
                i++;
                continue
            }

            replacementLen = replacements.length;
            for(j = 0; j < replacementLen; j++) {
                replacement = replacements[j];
                if(!replacement.tagName) {
                    replacement = document.createTextNode(replacement);
                }
                messageBody.insertBefore(replacement, elem);
            }
            messageBody.removeChild(elem);
            i += j;
        }
    },

    function setMessageContent(self, data, isMessage) {
        /* @param data: Three-Array of the html for next message preview, the
         * html for the current message, and some structured data describing
         * the current message (if isMessage is true)
         *
         * @param isMessage: Boolean indicating whether a message is actually
         * being displayed (???).
         */
        var nextMessagePreview = data.shift();
        var currentMessageDisplay = data.shift();
        var currentMessageData = data.shift();

        self.currentMessageData = currentMessageData;

        Divmod.msg("setMessageContent(" + currentMessageData.toSource() + ")");

        var n;
        if (isMessage) {
            n = self.messageDetail;
        } else {
            n = self.inboxContainer;
        }

        Divmod.Runtime.theRuntime.setNodeContent(
            n, '<div xmlns="http://www.w3.org/1999/xhtml">' + currentMessageDisplay + '</div>');

        var isItSpam, spamConfidence;
        if (currentMessageData.spam) {
            isItSpam = 'spam';
        } else {
            isItSpam = 'not spam';
        }
        if (currentMessageData.trained) {
            spamConfidence = 'definitely';
        } else {
            spamConfidence = 'probably';
        }

        var spambutton = self.nodeByAttribute('class', 'spam-state');
        Divmod.Runtime.theRuntime.setNodeContent(spambutton,
                                                 '<span xmlns="http://www.w3.org/1999/xhtml">' +
                                                 spamConfidence + ' ' + isItSpam +
                                                 '</span>');

        if (nextMessagePreview != null) {
            if(!self.nextMessagePreview) {
                self.nextMessagePreview = self.firstWithClass("next-message-preview",
                                                              self.contentTableRows[0]);
            }
            /* so this is a message, not a compose fragment */
            Divmod.Runtime.theRuntime.setNodeContent(
                self.nextMessagePreview, '<div xmlns="http://www.w3.org/1999/xhtml">' + nextMessagePreview + '</div>');
            self.highlightExtracts();
        }
    })
