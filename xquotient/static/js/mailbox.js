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
        var ypos = Quotient.Common.Util.findPosY(self._scrollViewport);
        var pageHeight = document.documentElement.clientHeight;
        self._scrollViewport.style.height = pageHeight - ypos - 14 + "px";
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
    function __init__(self, node, messageCount) {
        Quotient.Mailbox.Controller.upcall(self, "__init__", node);
        
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
        var mastheadBottom = self.firstWithClass("masthead-bottom",
                                                 self.contentTableRows[2]);

        var ypos = Quotient.Common.Util.findPosY(self.messageDetail);
        var pageHeight = document.documentElement.clientHeight;
        self.messageDetail.style.height = pageHeight - ypos - 15 - mastheadBottom.clientHeight + "px";

        var scrollNode = Nevow.Athena.FirstNodeByAttribute(self.contentTableRows[1],
                                                           "athena:class",
                                                           "Quotient.Mailbox.ScrollingWidget");

        self.scrollWidget = Quotient.Mailbox.ScrollingWidget.get(scrollNode);
        self.scrolltableContainer = self.scrollWidget.node.parentNode;
        self.scrollWidget._scrollViewport.style.height = 
            parseInt(self.scrollWidget._scrollViewport.style.height) - mastheadBottom.clientHeight + "px";

        self._selectAndFetchRow(0, function() { return null });

        self.setMessageCount(messageCount);

        self.currentComplexity = 1;
        setTimeout(function() {
            self.setScrollTablePosition("absolute");
            self.highlightExtracts();
            self.finishedLoading();
        }, 0);
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

    function setComplexity(self, c, node) {
        if(node.className == "selected-complexity-icon") {
            return;
        }
        if(c == 1) {
            self.setViewsContainerDisplay("none");
            self.setScrollTablePosition("absolute");
        } else if(c == 2) {
            self.setViewsContainerDisplay("none");
            self.setScrollTablePosition("static");
        } else if(c == 3) {
            self.setScrollTablePosition("static");
            self.setViewsContainerDisplay("");
        }
        var gparent = node.parentNode.parentNode;
        var selected = Nevow.Athena.FirstNodeByAttribute(
                        gparent, "class", "selected-complexity-icon");
        selected.className = "complexity-icon";
        self.complexityHover(selected);
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
        if(typeof(catchAll) == 'undefined') {
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

    function chooseTag(self, n) {
        self._selectListOption(n);
        return self._chooseViewParameter('viewByTag', n);
    },

    function chooseMailView(self, n) {
        self._selectListOption(n);
        self._chooseViewParameter('viewByMailType', n, false);
    },
        
    function chooseAccount(self, n) {
        self._selectListOption(n);
        return self._chooseViewParameter('viewByAccount', n);
    },

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

    function touch(self, action, isProgress) {
        var remoteArgs = [action + "CurrentMessage"];
        for(var i = 3; i < arguments.length; i++) {
            remoteArgs.push(arguments[i]);
        }
        var next = self.scrollWidget._selectedRow.nextSibling;
        self.scrollWidget.removeCurrentRow();
        
        self.scrollWidget._selectRow(
            self.scrollWidget._selectedRowOffset,
            next);

        self.scrollWidget.scrolled();

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
        self.touch("archive", true);
    },

    function deleteThis(self, n) {
        self.touch("delete", true);
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
        self.touch("replyTo", false);
    },

    function forwardThis(self, n) {
        self.touch("forward", false);
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

    function setMessageContent(self, data, msg) {
        /* data = [html for next msg preview, html for curmsg] */
        var n;
        if(msg) {
            n = self.messageDetail;
        } else {
            n = self.inboxContainer;
        }
        Divmod.Runtime.theRuntime.setNodeContent(
            n, '<div xmlns="http://www.w3.org/1999/xhtml">' + data[1] + '</div>');
        if(data[0] != null) {
            if(!self.nextMessagePreview) {
                self.nextMessagePreview = self.firstWithClass("next-message-preview",
                                                              self.contentTableRows[0]);
            }
            /* so this is a message, not a compose fragment */
            Divmod.Runtime.theRuntime.setNodeContent(
                self.nextMessagePreview, '<div xmlns="http://www.w3.org/1999/xhtml">' + data[0] + '</div>');
            self.highlightExtracts();
        }
    })
