// import Quotient
// import Quotient.Common
// import Mantissa.People
// import LightBox
// import Mantissa.ScrollTable

Quotient.Mailbox.MessageDetail = Nevow.Athena.Widget.subclass("Quotient.Mailbox.MessageDetail");
Quotient.Mailbox.MessageDetail.methods(
    function messageSource(self) {
        self.callRemote("getMessageSource").addCallback(
            function(source) {
                MochiKit.DOM.replaceChildNodes(
                    self.nodeByAttribute("class", "message-body"),
                    MochiKit.DOM.PRE(null, source));
        });
    },

    /**
     * Open a window that contains a printable version of
     * the Message pointed to by the given link
     *
     * @param node: an <a>
     */
    function printable(self, node) {
        window.open(node.href);
    },

    /**
     * Present an element that contains an editable list of tags for my message
     */
    function editTags(self) {
        if(!self.tagsDisplayContainer) {
            var tagsContainer = self.firstNodeByAttribute("class", "tags-container");
            self.tagsDisplayContainer = Nevow.Athena.FirstNodeByAttribute(
                                            tagsContainer, "class", "tags-display-container");
            self.tagsDisplay = self.tagsDisplayContainer.firstChild;
            self.editTagsContainer = Nevow.Athena.FirstNodeByAttribute(
                                        tagsContainer, "class", "edit-tags-container");
        }
        var tdc = self.tagsDisplayContainer;
        var input = self.editTagsContainer.getElementsByTagName("input")[0];
        if(self.tagsDisplay.firstChild.nodeValue != "No Tags") {
            input.value = self.tagsDisplay.firstChild.nodeValue;
        }
        input.focus();

        tdc.style.display = "none";
        self.editTagsContainer.style.display = "";
    },

    function hideTagEditor(self) {
        self.editTagsContainer.style.display = "none";
        self.tagsDisplayContainer.style.display = "";
    },

    /**
     * Inspect the contents of the tag editor element and persist any
     * changes that have occured (deleted tags, added tags)
     */
    function saveTags(self) {
        var _gotTags = self.editTagsContainer.tags.value.split(/,\s*/);
        var  gotTags = [];
        var seen = {};
        for(var i = 0; i < _gotTags.length; i++) {
            if(0 < _gotTags[i].length && !(_gotTags[i] in seen)) {
                seen[_gotTags[i]] = 1;
                gotTags.push(_gotTags[i]);
            }
        }

        var existingTags;
        if(self.tagsDisplay.firstChild.nodeValue == "No Tags") {
            existingTags = [];
        } else {
            existingTags = self.tagsDisplay.firstChild.nodeValue.split(/,\s*/);
        }

        var tagsToDelete = Quotient.Common.Util.difference(existingTags, gotTags);
        var tagsToAdd = Quotient.Common.Util.difference(gotTags, existingTags);

        if(tagsToAdd || tagsToDelete) {
            self.callRemote("modifyTags", tagsToAdd, tagsToDelete);
        }

        if(0 < gotTags.length) {
            self.tagsDisplay.firstChild.nodeValue = gotTags.join(", ");
            self.widgetParent.addTagsToViewSelector(tagsToAdd);
        } else {
            self.tagsDisplay.firstChild.nodeValue = "No Tags";
        }

        self.hideTagEditor();
    });


Quotient.Mailbox.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass(
    "Quotient.Mailbox.ScrollingWidget");

Quotient.Mailbox.ScrollingWidget.methods(
    function __init__(self, node) {
        Quotient.Mailbox.ScrollingWidget.upcall(self, "__init__", node);
        self.selectedGroup = {};
        self.columnAliases = {"receivedWhen": "Date", "senderDisplay": "Sender"};
        self.node.style.width = "300px";
        self._scrollViewport.style.maxHeight = "";
        self.node.style.border = "";
        self.node.style.borderLeft = self.node.style.borderBottom = "solid 1px #7FCCE5";
        self.ypos = Quotient.Common.Util.findPosY(self._scrollViewport.parentNode);
        self.throbber = Nevow.Athena.FirstNodeByAttribute(self.node.parentNode, "class", "throbber");
    },

    function resized(self, wp) {
        if(!wp) {
            wp = self.widgetParent;
        }

        /* This is the cumulative padding/margin for all elements whose
         * heights we factor into the height calculation below.  clientHeight
         * includes border but not padding or margin.
         * FIXME: change all this code to use offsetHeight, not clientHeight
         */
        var basePadding = 14;
        self._scrollViewport.style.height = (Divmod.Runtime.theRuntime.getPageSize().h -
                                             wp.messageBlockYPos -
                                             wp.totalFooterHeight -
                                             wp.scrollHeaderHeight -
                                             basePadding) + "px";

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
        var r = MochiKit.DOM.DIV({"style": "visibility: hidden; font-weight: bold",
                                  "class": "q-scroll-row"},
                    [MochiKit.DOM.DIV({"class": "sender"}, "TEST!!!"),
                     MochiKit.DOM.DIV({"class": "subject"}, "TEST!!!"),
                     MochiKit.DOM.DIV(null, "TEST!!!")]);

        self._scrollContent.appendChild(r);
        var rowHeight = Divmod.Runtime.theRuntime.getElementSize(r).h;
        self._scrollContent.removeChild(r);

        self._rowHeight = rowHeight;
    },

    function _selectRow(self, row) {
        if(self._selectedRow) {
            self._selectedRow.style.backgroundColor = '';
        }

        if(row.style.fontWeight == "bold") {
            self.widgetParent.decrementActiveMailViewCount();
        }

        row.style.fontWeight = "";
        row.style.backgroundColor = '#FFFFFF';

        self._selectedRow = row;
    },

    function _selectFirstRow(self) {
        self._selectRow(self._rows[0][1]);
    },

    function makeRowElement(self, rowOffset, rowData, cells) {
        var style = "border-top: solid 1px #FFFFFF; height: " + (self._rowHeight - 9) + "px";
        if(!rowData["read"]) {
            style += ";font-weight: bold";
        }
        var data = [MochiKit.Base.filter(null, cells)];
        if(0 < rowData["attachments"]) {
            data.push(MochiKit.DOM.IMG({"src": "/Quotient/static/images/paperclip.gif",
                                        "style": "float: right; border: none"}));
        }
        return MochiKit.DOM.A(
            {"class": "q-scroll-row",
             "href": "#",
             "style": style,
             "onclick": function(event) {
                if(event.target.onclick) {
                    return false;
                }
                /* don't select based on rowOffset because it'll change as rows are removed */
                self._selectRow(this);
                self.widgetParent.fastForward(rowData["__id__"]);
                return false;
            }}, data);
    },

    function massageColumnValue(self, name, type, value) {
        var res = Quotient.Mailbox.ScrollingWidget.upcall(
                        self, "massageColumnValue", name, type, value);

        var ALL_WHITESPACE = /^\s*$/;
        if(name == "subject" && ALL_WHITESPACE.test(res)) {
            res = "<Empty Subject>";
        }
        return res;
    },

    function makeCellElement(self, colName, rowData) {
        if(colName == "receivedWhen") {
            colName = "sentWhen";
        }
        var massage = function(colName) {
            return self.massageColumnValue(
                colName, self.columnTypes[colName][0], rowData[colName]);
        }

        var attrs = {};
        if(colName == "senderDisplay") {
            attrs["class"] = "sender";
            return MochiKit.DOM.DIV(attrs,
                [MochiKit.DOM.IMG({"src": "/Quotient/static/images/checkbox-off.gif",
                                   "class": "checkbox-image",
                                   "border": 0,
                                   "onclick": function(event) {
                                        self.groupSelectRow(rowData["__id__"], this);
                                        event.target.blur();
                                        return false;
                                   }}), massage(colName)]);

        } else if(colName == "subject") {
            attrs["class"] = "subject";
        } else {
            attrs["class"] = "date";
        }

        return MochiKit.DOM.DIV(attrs, massage(colName));
    },

    /**
     * Add row with C{webID} to the group selection
     */
    function groupSelectRow(self, webID, checkboxImage) {
        var state;
        if(webID in self.selectedGroup) {
            delete self.selectedGroup[webID];
            state = "off";
        } else {
            self.selectedGroup[webID] = checkboxImage.parentNode.parentNode;
            state = "on";
        }

        var selcount = MochiKit.Base.keys(self.selectedGroup).length;
        /* are we transitioning from 0->1 or 1->0? */
        if(selcount == 0 || (selcount == 1 && state == "on")) {
            self.widgetParent.toggleGroupActions();
        }

        var segs = checkboxImage.src.split("/");
        segs[segs.length-1] = "checkbox-" + state + ".gif";
        checkboxImage.src = segs.join("/");
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
            return parts[1] + " " + parts[2]; /* e.g. Jan 12 */
        }
        return [pad(d.getFullYear()),
                pad(d.getMonth()+1),
                pad(d.getDate())].join("-");
    },

    function skipColumn(self, name) {
        return name == "read" || name == "sentWhen" || name == "attachments";
    },

    /**
     * Remove the given row from the scrolltable
     * @param row: node
     */
    function removeRow(self, row) {
        row.parentNode.removeChild(row);
        self.adjustViewportHeight(-1);

        var _row, index = self.findRowOffset(row);
        for(var i = index+1; i < self._rows.length; i++) {
            if(self._rows[i]) {
                _row = self._rows[i][1];
                _row.style.top = (parseInt(_row.style.top) - self._rowHeight) + "px";
            }
        }

        self._rows = self._rows.slice(0, index).concat(
                            self._rows.slice(index+1, self._rows.length));
    },

    /**
     * Find the offset at which the given row appears in the scrolltable
     * @param row: node
     */
    function findRowOffset(self, row) {
        for(var i = 0; i < self._rows.length; i++) {
            if(self._rows[i] && self._rows[i][1] == row) {
                return i;
            }
        }
    },

    /**
     * Find the first row which appears after C{row} in the scrolltable and
     * satisfies C{predicate}
     *
     * @param row: node
     * @param predicate: function(rowIndex, rowData, rowNode) -> boolean
     * @param wantOffset: boolean.  if true, the offset of the row will be returned
     * @return: C{rowNode} for the first set of arguments that satisfies C{predicate},
     *          or array of [C{rowNode}, C{rowOffset}] if C{wantOffset} is true
     */
    function findNextRow(self, row, predicate, wantOffset) {
        var args;
        for(var i = self.findRowOffset(row)+1; i < self._rows.length; i++) {
            if(self._rows[i]) {
                args = [i].concat(self._rows[i]);
                if(!predicate || predicate.apply(null, args)) {
                    if(wantOffset) {
                        return [args[2], i];
                    }
                    return args[2];
                }
            }
        }
    },

    /**
     * Same as L{findNextRow}, except returns the first row which appears before C{row}
     */
    function findPrevRow(self, row, predicate, wantOffset) {
        var args;
        for(var i = self.findRowOffset(row)-1; 0 <= i; i--) {
            if(self._rows[i]) {
                args = [i].concat(self._rows[i]);
                if(!predicate || predicate.apply(null, args)) {
                    if(wantOffset) {
                        return [args[2], i];
                    }
                    return args[2];
                }
            }
        }
    },

    function removeCurrentRow(self) {
        self.removeRow(self._selectedRow);
    },

    function cbRowsFetched(self, count) {
        self.throbber.style.display = "none";
        if(self._pendingRowSelection) {
            self._pendingRowSelection(count);
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

            var search = document.getElementById("search-button");
            if(search) {
                alert(search);
                /* if there aren't any search providers available,
                 * then there won't be a search button */
                var width = Divmod.Runtime.theRuntime.getElementSize(search.parentNode).w;
                node.style.paddingRight = width + "px";
            }

        Quotient.Mailbox.Controller.upcall(self, "__init__", node);
        self.currentMessageData = null;

        self._cacheContentTableGrid();

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
        self.setupMailViewNodes();

        self.messageDetail = self.firstWithClass(self.contentTableGrid[0][2], "message-detail");

        self.ypos = Quotient.Common.Util.findPosY(self.messageDetail);
        self.messageBlockYPos = Quotient.Common.Util.findPosY(self.messageDetail.parentNode);

        var scrollHeader = self.firstWithClass(self.contentTableGrid[0][1], "scrolltable-header");
        scrollHeader.parentNode.style.display = "";
        self.scrollHeaderHeight = Divmod.Runtime.theRuntime.getElementSize(scrollHeader).h;
        scrollHeader.parentNode.style.display = "none";
        self.scrollHeader = scrollHeader;

        var scrollNode = Nevow.Athena.FirstNodeByAttribute(self.node,
                                                           "athena:class",
                                                           "Quotient.Mailbox.ScrollingWidget");

        self.scrollWidget = Nevow.Athena.Widget.get(scrollNode);
        self.scrolltableContainer = self.scrollWidget.node.parentNode;
        self.resized(true);

        self._selectAndFetchFirstRow();

        self.setMessageCount(messageCount);

        self.delayedLoad(complexityLevel);
    },

    function _cacheContentTableGrid(self) {
        var contentTable = self.getFirstElementByTagNameShallow(self.node, "table");
        var contentTableRows = self.getElementsByTagNameShallow(
                self.getFirstElementByTagNameShallow(contentTable, "tbody"), "tr");
        var contentTableGrid = [];
        for(var i = 0; i < contentTableRows.length; i++) {
            contentTableGrid.push(
                self.getElementsByTagNameShallow(
                    contentTableRows[i], "td"));
        }
        self.contentTable = contentTable;
        self.contentTableGrid = contentTableGrid;
    },

    function _getContentTableColumn(self, offset) {
        return MochiKit.Base.map(
            function(r) {
                if(offset+1 <= r.length) {
                    return r[offset];
                }
            }, self.contentTableGrid);
    },

    /**
     * similar to document.getElementsByTagName(), except it only returns
     * matching elements that are immediate children of C{node}
     */
    function getElementsByTagNameShallow(self, node, tagName) {
        return MochiKit.Base.filter(
            function(n) {
                if(n.tagName && n.tagName.toLowerCase() == tagName) {
                    return n;
                }
            }, node.childNodes);
    },

    /**
     * similar to C{getElementsByTagNameShallow}, but returns the
     * first matching element
     */
    function getFirstElementByTagNameShallow(self, node, tagName) {
        var child;
        for(var i = 0; i < node.childNodes.length; i++) {
            child = node.childNodes[i];
            if(child.tagName && child.tagName.toLowerCase() == tagName) {
                return child;
            }
        }
    },

    /* Decrement the unread message count that is displayed next to
     * the name of the currently active view in the view selector.
     *
     * (e.g. "Inbox (31)" -> "Inbox (30)")
     */
    function decrementActiveMailViewCount(self) {
        var decrementNodeValue = function(node) {
            node.firstChild.nodeValue = parseInt(node.firstChild.nodeValue) - 1;
        }

        var cnode = self.firstWithClass(
                            self.mailViewNodes[self._viewingByView], "count");
        decrementNodeValue(cnode);

        if(self._viewingByView == "Inbox") {
            decrementNodeValue(self.firstWithClass(self.mailViewNodes["All"], "count"));
        }
    },

    /**
     * Update the counts that are displayed next
     * to the names of mailbox views in the view selector
     *
     * @param counts: mapping of view names to unread
     *                message counts
     */
    function updateMailViewCounts(self, counts) {
        var cnode;
        for(var k in counts) {
            cnode = self.firstWithClass(self.mailViewNodes[k], "count");
            cnode.firstChild.nodeValue = counts[k];
        }
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
            var cc = self.firstWithClass(self.node, "complexity-container");
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

    /**
     * resize the inbox table and contents.
     * @param initialResize: is this the first/initial resize?
     *                       (if so, then our layout constraint jiggery-pokery
     *                        is not necessary)
     */

    function resized(self, initialResize) {
        var getHeight = function(node) {
            return Divmod.Runtime.theRuntime.getElementSize(node).h;
        }

        if(!self.totalFooterHeight) {
            var footer = document.getElementById("mantissa-footer");
            var blockFooter = self.firstNodeByAttribute("class", "right-block-footer");
            self.totalFooterHeight = getHeight(blockFooter) + getHeight(footer);
        }

        self.scrollWidget.resized(self);

        var scrollViewport = self.scrollWidget._scrollViewport;
        scrollViewport.style.height = (scrollViewport.style.height - getHeight(blockFooter)) + "px";

        self.messageDetail.style.height = (Divmod.Runtime.theRuntime.getPageSize().h -
                                           self.ypos - 13 -
                                           self.totalFooterHeight) + "px";

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
        self.node.removeChild(self.firstWithClass(self.node, "loading"));
    },

    function firstWithClass(self, n, cls) {
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

    function _groupSetDisplay(self, nodes, display) {
        for(var i = 0; i < nodes.length; i++) {
            nodes[i].style.display = display;
        }
    },

    function hideAll(self, nodes) {
        self._groupSetDisplay(nodes, "none");
    },

    function showAll(self, nodes) {
        self._groupSetDisplay(nodes, "");
    },

    function _setComplexityVisibility(self, c) {
        var fontSize;

        if(c == 1) {
            self.hideAll(self._getContentTableColumn(0));
            self.hideAll(self._getContentTableColumn(1));
            self.setScrollTablePosition("absolute");
            fontSize = "";
        } else if(c == 2) {
            self.hideAll(self._getContentTableColumn(0));
            self.showAll(self._getContentTableColumn(1));
            self.setScrollTablePosition("static");
            fontSize = "1.3em";
        } else if(c == 3) {
            self.showAll(self._getContentTableColumn(0));
            self.showAll(self._getContentTableColumn(1));
            self.setScrollTablePosition("static");
            fontSize = "1.3em";
        }
        try {
            var messageBody = self.firstWithClass(self.messageDetail, "message-body");
            messageBody.style.fontSize = fontSize;
        } catch(e) {}
    },

    /**
     * level = integer between 1 and 3
     * node = the image that represents this complexity level
     * report = boolean - should we persist this change
     */
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
        self.scrollHeader.style.display = d;
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
        return self._sendViewRequest(viewFunction, value);
    },

    function _sendViewRequest(self, viewFunction, value) {
        self.scrollWidget.throbber.style.display = "";

        return self.callRemote(viewFunction, value).addCallback(
            function(messageData) {
                self.setMessageCount(messageData[0]);
                self.setMessageContent(messageData[1], true);
                self.updateMailViewCounts(messageData[2]);
                self.scrollWidget.setViewportHeight(messageData[0]);
                self.scrollWidget.emptyAndRefill();
                self.scrollWidget._selectedRow = null;
                self.scrollWidget._pendingRowSelection = function(count) {
                    if(0 < count) {
                        self._selectAndFetchFirstRow(false);
                    }
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
     * Add the given tags as options inside the "View By Tag" element
     */
    function addTagsToViewSelector(self, taglist) {
        var tc = self.firstWithClass(self.contentTableGrid[1][0], "tag-chooser");
        var choices = tc.getElementsByTagName("span");
        var currentTags = [];
        for(var i = 0; i < choices.length; i++) {
            currentTags.push(choices[i].firstChild.nodeValue);
        }
        var needToAdd = Quotient.Common.Util.difference(taglist, currentTags);
        /* the tags are unordered at the moment, probably not ideal */
        for(i = 0; i < needToAdd.length; i++) {
            tc.appendChild(
                MochiKit.DOM.DIV({"class": "list-option",
                                  "onclick": function() {
                                      self.chooseTag(this);
                                    }}, MochiKit.DOM.SPAN({"class": "opt-name"}, needToAdd[i])));
        }
    },

    /**
     * Return a mapping of view names to mappings of
     * visibility values to lists of button descriptors
     */
    function createVisibilityMatrix(self) {
        var train_ham = ["train-ham", false];
        var train_spam  = ["train-spam", false];
        var delete_ = ["delete", true];
        var archive = ["archive", true];
        var defer   = ["defer", true];

        return {
            Spam:  {show: [train_ham, delete_],
                    hide: [archive, defer, train_spam]},
            All:   {show: [train_spam, delete_],
                    hide: [archive, defer, train_ham]},
            Inbox: {show: [archive, defer, train_spam, delete_],
                    hide: [train_ham]},
            Sent:  {show: [delete_],
                    hide: [train_ham, train_spam, archive, defer]},
            Trash: {show: [],
                    hide: [train_ham, train_spam, archive, defer, delete_]}}
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
        self.mailViewNode = n;

        self.disableGroupActions();

        self._viewingByView = n.firstChild.firstChild.nodeValue;
        self._selectListOption(n);
        self._selectViewShortcut();

        if(!self.visibilityByView) {
            self.visibilityByView = self.createVisibilityMatrix();
        }

        var visibilityForThisView = self.visibilityByView[self._viewingByView];
        self.setDisplayForButtons("",     visibilityForThisView["show"]);
        self.setDisplayForButtons("none", visibilityForThisView["hide"]);

        var namesOnly = function(k) {
            return MochiKit.Base.map(MochiKit.Base.itemgetter(0),
                                     visibilityForThisView[k]);
        }

        self.setDisplayForGroupActions("",     namesOnly("show"));
        self.setDisplayForGroupActions("none", namesOnly("hide"));

        self.selectFirstVisible(
                document.forms["group-actions"].elements["group-action"]);

        self._chooseViewParameter('viewByMailType', n, false);
    },

    /**
     * select the first visible <option> inside the given <select>
     */
    function selectFirstVisible(self, select) {
        var opts = select.getElementsByTagName("option");
        for(var i = 0; i < opts.length; i++) {
            if(opts[i].style.display != "none") {
                select.selectedIndex = i;
                return;
            }
        }
    },

    /**
     * Select the view shortcut link that corresponds to the
     * current mail view, if any.
     */
    function _selectViewShortcut(self) {
        if(self._viewingByView != "Inbox"
            || self._viewingByView != "Sent"
            || self._viewingByView != "Spam") {
            return;
        }

        if(!self.viewShortcuts) {
            var viewShortcutContainer = self.firstWithClass(
                                            self.scrolltableHeader,
                                            "view-shortcut-container");
            self.viewShortcuts = Nevow.Athena.NodesByAttribute(viewShortcutContainer,
                                                               "class",
                                                               "view-shortcut");
            self.viewShortcuts.push(
                self.firstWithClass(
                    viewShortcutContainer, "selected-view-shortcut"));
        }

        var shortcut;
        for(var i = 0; i < self.viewShortcuts.length; i++) {
            shortcut = self.viewShortcuts[i];
            if(shortcut.firstChild.nodeValue == self._viewingByView) {
                shortcut.className = "selected-view-shortcut";
            } else {
                shortcut.className = "view-shortcut";
            }
        }
    },

    /**
     * Return the node for the named button
     *
     * @param topRow: boolean - from top button row?
     */
    function getButton(self, name, topRow) {
        if(!self.buttons) {
            self.buttons = {};
        }
        if(!([name, topRow] in self.buttons)) {
            self.buttons[[name, topRow]] = self.firstWithClass(
                                                    self.messageActions[new Number(!topRow)],
                                                    name + "-button");
        }
        return self.buttons[[name, topRow]];
    },

    /**
     * Apply display value C{display} to each button identified in C{buttonArgs}
     * @param buttonArgs: list of [C{name}, C{topRow}] (see signature of L{getButton})
     */
    function setDisplayForButtons(self, display, buttonArgs) {
        var button;
        for(var i = 0; i < buttonArgs.length; i++) {
            button = self.getButton.apply(self, buttonArgs[i]);
            button.style.display = display;
        }
    },

    /**
     * Similar to C{setDisplayForButtons}: apply display value C{display}
     * to the <option> in the group actions <select> that corresponds to
     * each action name in C{actionNames}
     */
    function setDisplayForGroupActions(self, display, actionNames) {
        var action;
        for(var i = 0; i < actionNames.length; i++) {
            /* temporary hack, defer needs better UI, and the form
               needs to go somewhere besides the message detail if
               it's going to be a group action */
            if(actionNames[i] == "defer") {
                continue;
            }
            self.getGroupActionElement(actionNames[i]).style.display = display;
        }
    },

    /*
     Locate the element that corresponds to the given group action name
     */
    function getGroupActionElement(self, actionName) {
        var select = document.forms["group-actions"].elements["group-action"];
        return Nevow.Athena.FirstNodeByAttribute(select, "value", actionName);
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

    function viewShortcut(self, n) {
        var type = n.firstChild.nodeValue;
        self._sendViewRequest('viewByMailType', type);

        var e;
        for(var i = 0; i < n.parentNode.childNodes.length; i++) {
            e = n.parentNode.childNodes[i];
            if(e.className == "selected-view-shortcut") {
                e.className = "view-shortcut";
            }
        }
        n.className = "selected-view-shortcut";

        /* make sure the right thing is selected in the full views browser
           FIXME
           self._selectListOption(...); */

        n.blur();
    },

    function setupMailViewNodes(self) {
        if(!self.mailViewBody) {
            var mailViewPane = self.firstWithClass(self.contentTableGrid[1][0], "view-pane-content");
            var mailViewBody = self.firstWithClass(mailViewPane, "pane-body");
            self.mailViewBody = self.getFirstElementByTagNameShallow(mailViewBody, "div");
        }

        var nodes = {"All": null, "Trash": null, "Sent": null, "Spam": null, "Inbox": null};
        for(var i = 0; i < self.mailViewBody.childNodes.length; i++) {
            var e = self.mailViewBody.childNodes[i];
            if(e.tagName && (e.firstChild.firstChild.nodeValue in nodes)) {
                nodes[e.firstChild.firstChild.nodeValue] = e;
            }
        }
        self.mailViewNodes = nodes;
    },

    function _selectAndFetchFirstRow(self, requestMoreRowsIfNeeded) {
        if(typeof requestMoreRowsIfNeeded === 'undefined') {
            requestMoreRowsIfNeeded = true;
        }

        var sw = self.scrollWidget;
        if(sw._rows.length == 0) {
            if(requestMoreRowsIfNeeded) {
                /* free up some space */
                sw._scrollViewport.scrollTop += sw._rowHeight * 3;
                sw.scrolled();
                /* the scroll widget's cbRowsFetched
                   method will call this function when
                   it gets rows */
                sw._pendingRowSelection = function(count) {
                    /* call ourselves, passing additional argument
                       indicating that we shouldn't go through this
                       rigmarole a second time if there still aren't enough rows */
                    if(0 < count) {
                        self._selectAndFetchFirstRow(false);
                    }
                }
            }
            return;
        }

        sw._selectFirstRow();
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
     *     "forward"
     *     "train"
     *
     * @param isProgress: A boolean indicating whether the message will be
     * removed from the current message list and the progress bar updated to
     * reflect this.
     *
     * @return: C{undefined}
     */
    function touch(self, action, isProgress) {
        var remoteArgs = [action + "CurrentMessage", isProgress];
        for(var i = 3; i < arguments.length; i++) {
            remoteArgs.push(arguments[i]);
        }
        var next = self.scrollWidget.findNextRow(self.scrollWidget._selectedRow)
                    || self.scrollWidget.findPrevRow(self.scrollWidget._selectedRow);

        if (isProgress) {
            self.scrollWidget.removeCurrentRow();
            if(next && next.tagName) {
                self.scrollWidget._selectRow(next);
                self.scrollWidget.scrolled();
            }
        }

        self.doTouch(remoteArgs, isProgress, 1);
    },

    /**
     * Like L{touch}, but acts upon the set of currently selected
     * messages in the scrolltable.
     *
     * @param isDestructive: does this action remove messages from the current
     *                       view?  this is subtly different to touchSelectedGroup's
     *                       "isProgress", because even for destructive message
     *                       actions, we might not need to request a new message
     *                       if the currently selected one is not a member of the
     *                       group being acted upon.
     */
    function touchSelectedGroup(self, action, isDestructive) {
        var selgroup = self.scrollWidget.selectedGroup;
        var webIDs = MochiKit.Base.keys(selgroup);
        var selectedRowOffset = self.scrollWidget.findRowOffset(self.scrollWidget._selectedRow);
        var selectedRowID = self.scrollWidget._rows[selectedRowOffset][0]["__id__"];
        var next, isProgress = isDestructive;

        if(isDestructive) {
            /* if this action is going to dismiss the message being viewed */
            if(selectedRowID in selgroup) {
                /* is there a row after the selected row that isn't earmarked for destruction */
                var predicate = function(rowOffset, rowData, rowElement) {
                                    return !(rowData["__id__"] in selgroup);
                                }
                next = self.scrollWidget.findNextRow(self.scrollWidget._selectedRow, predicate, true)
                        || self.scrollWidget.findPrevRow(self.scrollWidget._selectedRow, predicate, true);
            /* if it isn't, then we aren't going to progress */
            } else {
                isProgress = false;
            }
        }

        var nextMessageID = null;
        if(next) {
            nextMessageID = self.scrollWidget._rows[next[1]][0]["__id__"];
        }

        if(isDestructive) {
            for(var k in selgroup) {
                self.scrollWidget.removeRow(selgroup[k]);
            }
            self.disableGroupActions();
            if(next && next[0].tagName) {
                self.scrollWidget._selectRow(next[0]);
                self.scrollWidget.scrolled();
            }
        }

        self.scrollWidget.selectedGroup = {};
        var remoteArgs = [action + "MessageGroup", isProgress, nextMessageID, webIDs];

        for(var i = 3; i < arguments.length; i++) {
            remoteArgs.push(arguments[i]);
        }

        return self.doTouch(remoteArgs, isProgress, webIDs.length);
    },

    /**
     * Call a remote method and handle it's result, which is expected
     * to be a new set of message-related UI state.  This is typically
     * done when acting on a message.
     *
     * @param remoteArgs: array of arguments for callRemote()
     *
     * @param isProgress: A boolean indicating whether the message will be
     * removed from the current message list and the progress bar updated to
     * reflect this.
     *
     * @param touchingHowMany: integer, indicating the number of messages
     *                         that are affected by this action
     */
    function doTouch(self, remoteArgs, isProgress, touchingHowMany) {
        self.messageDetail.style.opacity = .2;
        return self.callRemote.apply(self, remoteArgs).addCallback(
            function(nextMessage) {
                self.messageDetail.style.opacity = 1;
                if(isProgress) {
                    self.setMessageContent(nextMessage);
                    if(!self.progressBar) {
                        self.progressBar = self.firstWithClass(
                                            self.contentTableGrid[0][2], "progress-bar");
                    }
                    self.progressBar.style.borderRight = "solid 1px #6699CC";
                    self.remainingMessages -= touchingHowMany;
                    self.setProgressWidth();
                } else if(nextMessage) {
                    self.displayInlineWidget(nextMessage);
                }
            });
    },

    /**
     * Get the first node with class name C{className} below
     * C{parent}.  Repeated calls will yield cached results.
     *
     * At some point change calls to firstWithClass() to use this
     */
    function getFirstNode(self, parent, className) {
        if(!self._nodeCache) {
            self._nodeCache = {};
        }
        if(!(parent in self._nodeCache)) {
            self._nodeCache[parent] = {};
        }
        if(!(className in self._nodeCache[parent])) {
            self._nodeCache[parent][className] = Nevow.Athena.FirstNodeByAttribute(
                                                    parent, "class", className);
        }
        return self._nodeCache[parent][className];
    },

    /**
     * called by the scrolltable when the number of messages
     * in the message group selection transitions from 0->1
     * or 1->0.
     *
     * enables or disables group message actions, depending
     * on whether any messages are selected
     */
    function toggleGroupActions(self) {
        var form = document.forms["group-actions"];
        var currentlyEnabled = !form.elements["group-action"].hasAttribute("disabled");
        self._changeGroupActionAvailability(!currentlyEnabled);
    },

    function disableGroupActions(self) {
        self._changeGroupActionAvailability(false);
    },

    /**
     * @param available: boolean.  true = enable, false = disable
     */
    function _changeGroupActionAvailability(self, available) {
        var form = document.forms["group-actions"];
        var gap = self.getFirstNode(form, "group-action-perform");
        var select = form.elements["group-action"];

        if(available) {
            select.style.opacity = gap.style.opacity = "";
            select.removeAttribute("disabled");
            gap.style.cursor = "";
            gap.onclick = function() {
                self.performSelectedGroupAction();
                return false;
            }
        } else {
            select.style.opacity = gap.style.opacity = ".3";
            select.setAttribute("disabled", "true");
            gap.style.cursor = "default";
            gap.onclick = function() {
                return false;
            }
        }
    },

    function performSelectedGroupAction(self) {
        var form = document.forms["group-actions"];
        var actionName = form.elements["group-action"].value;

        var args = [];

        if(actionName == "train-spam" || actionName == "train-ham") {
            args.push(actionName.split("-")[1] == "spam");
            actionName = "train";
        }

        /* for now, all group actions are destructive */
        self.touchSelectedGroup.apply(self, [actionName, true].concat(args));
    },

    /**
     * Hide the inbox controls and splat the given HTML ontop
     */
    function displayInlineWidget(self, html) {
        self.contentTable.style.display = "none";
        if(!self.widgetContainer) {
            self.widgetContainer = self.firstWithClass(self.node, "widget-container");
        }
        Divmod.Runtime.theRuntime.setNodeContent(
            self.widgetContainer, '<div xmlns="http://www.w3.org/1999/xhtml">' + html + '</div>');
    },

    /**
     * Inverse of displayInlineWidget()
     */
    function hideInlineWidget(self) {
        MochiKit.DOM.replaceChildNodes(self.widgetContainer);
        self.contentTable.style.display = "";
    },

    function setMessageCount(self, count) {
        self.remainingMessages = count;
        self.totalMessages = count;
        self.setProgressWidth();
    },

    function setProgressWidth(self) {
        if(!self.progressBar) {
            self.progressBar = self.firstWithClass(
                                self.contentTableGrid[0][2], "progress-bar");
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

    function archiveSelectedGroup(self) {
        self.touchSelectedGroup("archive", self._viewingByView != "All");
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
        /* We have to fetch the message body node each time because it gets
         * removed from the document each time a message is loaded.  We wrap it
         * in a try/catch because there are some cases where it's not going
         * to be available, like the "out of messages" case.  it's easier to
         * determine this here than with logic someplace else */
        try {
            var messageBody = self.firstWithClass(self.messageDetail, "message-body");
        } catch(e) {
            return;
        }

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

    /**
     * @param data: Three-Array of the html for next message preview, the
     * html for the current message, and some structured data describing
     * the current message
     */
    function setMessageContent(self, data) {
        var nextMessagePreview = data.shift();
        var currentMessageDisplay = data.shift();
        var currentMessageData = data.shift();

        self.currentMessageData = currentMessageData;

        Divmod.msg("setMessageContent(" + currentMessageData.toSource() + ")");

        Divmod.Runtime.theRuntime.setNodeContent(
            self.messageDetail, '<div xmlns="http://www.w3.org/1999/xhtml">' + currentMessageDisplay + '</div>');

        var modifier, spamConfidence;
        if (currentMessageData.trained) {
            spamConfidence = 'definitely';
        } else {
            spamConfidence = 'probably';
        }
        if (currentMessageData.spam) {
            modifier = '';
        } else {
            modifier = 'not';
        }


        if(!self.spamButton) {
            self.spamButton = self.firstWithClass(self.messageActions[1], "spam-state");
        }

        Divmod.Runtime.theRuntime.setNodeContent(self.spamButton,
                                                 '<span xmlns="http://www.w3.org/1999/xhtml">' +
                                                 spamConfidence + ' ' + modifier +
                                                 '</span>');

        if (nextMessagePreview != null) {
            if(!self.nextMessagePreview) {
                self.nextMessagePreview = self.firstWithClass(
                                            self.contentTableGrid[0][2], "next-message-preview");
            }
            /* so this is a message, not a compose fragment */
            Divmod.Runtime.theRuntime.setNodeContent(
                self.nextMessagePreview, '<div xmlns="http://www.w3.org/1999/xhtml">' + nextMessagePreview + '</div>');
            self.highlightExtracts();
        }
    })
