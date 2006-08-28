// import Quotient
// import Quotient.Common
// import Mantissa.People
// import Mantissa.ScrollTable

Quotient.Mailbox.MessageDetail = Nevow.Athena.Widget.subclass("Quotient.Mailbox.MessageDetail");
Quotient.Mailbox.MessageDetail.methods(
    function __init__(self, node, showMoreDetail) {
        Quotient.Mailbox.MessageDetail.upcall(self, "__init__", node);
        if(showMoreDetail) {
            self.toggleMoreDetail();
        }
    },

    function _getMoreDetailNode(self) {
        if(!self.moreDetailNode) {
            self.moreDetailNode = self.firstNodeByAttribute("class", "detail-toggle");
        }
        return self.moreDetailNode;
    },

    function messageSource(self) {
        self.callRemote("getMessageSource").addCallback(
            function(source) {
                MochiKit.DOM.replaceChildNodes(
                    self.nodeByAttribute("class", "message-body"),
                    MochiKit.DOM.PRE(null, source));
        });
    },

    /**
     * Toggle the visibility of the "more detail" panel, which contains
     * some extra headers, or more precise values for headers that are
     * summarized or approximated elsewhere.
     *
     * @param node: the toggle link node (if undefined, will locate in DOM)
     * @return: undefined
     */
    function toggleMoreDetail(self, node) {
        if(node == undefined) {
            node = self._getMoreDetailNode();
        }

        node.blur();

        if(node.firstChild.nodeValue == "More Detail") {
            node.firstChild.nodeValue = "Less Detail";
        } else {
            node.firstChild.nodeValue = "More Detail";
        }

        if(!self.headerTable) {
            self.headerTable = self.firstNodeByAttribute("class", "msg-header-table");
        }

        var visible;
        var rows = self.headerTable.getElementsByTagName("tr");
        for(var i = 0; i < rows.length; i++) {
            if(rows[i].className == "detailed-row") {
                if(rows[i].style.display == "none") {
                    rows[i].style.display = "";
                } else {
                    rows[i].style.display = "none";
                }
                if(visible == undefined) {
                    visible = rows[i].style.display != "none";
                }
            }
        }
        return self.callRemote("persistMoreDetailSetting", visible);
    },

    /**
     * Show the original, unscrubbed HTML for this message
     */
    function showOriginalHTML(self) {
        var mbody = self.firstNodeByAttribute("class", "message-body"),
            iframe = mbody.getElementsByTagName("iframe")[0];

        if(iframe.src.match(/\?/)) {
            iframe.src += "&noscrub=1";
        } else {
            iframe.src += "?noscrub=1";
        }

        var sdialog = self.firstNodeByAttribute("class", "scrubbed-dialog");
        sdialog.parentNode.removeChild(sdialog);
    },

    /**
     * Open a window that contains a printable version of
     * the current message
     *
     * @param node: an <a>
     */
    function printable(self) {
        window.open(self.firstNodeByAttribute("class", "printable-link").href);
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
        tdc.style.display = "none";
        self.editTagsContainer.style.display = "";

        /* IE throws an exception if an invisible element receives focus */
        input.focus();
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
            if(self.widgetParent) {
                self.widgetParent.addTagsToViewSelector(tagsToAdd);
            }
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
        self._scrollViewport.style.maxHeight = "";
        self.ypos = Quotient.Common.Util.findPosY(self._scrollViewport.parentNode);
        self.throbber = Nevow.Athena.FirstNodeByAttribute(self.node.parentNode, "class", "throbber");
    },

    /**
     * The super implementation looks at clientHeight, and then at style.height
     * if clientHeight doesn't make sense.  This is problematic because our
     * scrolltable is often display: none, and while firefox returns 0 for
     * the clientHeight of display: none elements, IE seems to return the
     * height of the element before it was made invisible.
     */
    function getScrollViewportHeight(self) {
        var height = parseInt(self._scrollViewport.style.height);
        if(isNaN(height)) {
            /* called too early, just give the page height.  at worst
               we'll end up requesting 5 extra rows or whatever */
            height = Divmod.Runtime.theRuntime.getPageSize().h;
        }
        return height;
    },

    function emptyAndRefill(self) {
        Quotient.Mailbox.ScrollingWidget.upcall(self, "emptyAndRefill");
        self.selectedGroup = {};
    },

    function getHeight(self, wp) {
        if(!wp) {
            wp = self.widgetParent;
        }

        /* This is the cumulative padding/margin for all elements whose
         * heights we factor into the height calculation below.  clientHeight
         * includes border but not padding or margin.
         * FIXME: change all this code to use offsetHeight, not clientHeight
         */
        var basePadding = 14;
        return (Divmod.Runtime.theRuntime.getPageSize().h -
                wp.messageBlockYPos -
                wp.totalFooterHeight -
                basePadding);

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

        document.body.appendChild(r);
        var rowHeight = Divmod.Runtime.theRuntime.getElementSize(r).h;
        document.body.removeChild(r);

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
        var rowData = self._rows[self.findRowOffset(row)][0];
        rowData["read"] = true;
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
            data.push(MochiKit.DOM.IMG({"src": "/Quotient/static/images/paperclip.png",
                                        "style": "float: right; border: none"}));
        }
        return MochiKit.DOM.A(
            {"class": "q-scroll-row",
             "href": "#",
             "style": style,
             "onclick": function(event) {
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
            res = "<no subject>";
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
            var content = [MochiKit.DOM.IMG({"src": "/Quotient/static/images/checkbox-off.gif",
                                             "class": "checkbox-image",
                                             "border": 0,
                                             "onclick": function(event) {
                                                self.groupSelectRow(rowData["__id__"], this);

                                                this.blur();

                                                if(!event) {
                                                    event = window.event;
                                                }
                                                event.cancelBubble = true;
                                                if(event.stopPropagation) {
                                                    event.stopPropagation();
                                                }

                                                return false;
                                             }}), massage(colName)];
            if(rowData["everDeferred"]) {
                content.push(IMG({"src": "/Quotient/static/images/boomerang.gif",
                                  "border": "0"}));
            }

            return MochiKit.DOM.DIV(attrs, content);

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

    /**
     * Add, or remove all *already requested* rows to the group selection
     * @param selectRows: if true, select matching rows, otherwise deselect
     * @param predicate: function that accepts a mapping of column names to
     *                   column values & returns a boolean indicating whether
     *                   the row should be included in the selection
     * @return: the number of matching rows
     */
    function massSelectOrNot(self,
                             selectRows/*=true*/,
                             predicate/*=null*/) {

        if(selectRows == undefined) {
            selectRows = true;
        }
        if(predicate == undefined) {
            predicate = function(r) {
                return true
            }
        }

        var getCheckbox = function(n) {
            return Nevow.Athena.FirstNodeByAttribute(n, "class", "checkbox-image");
        }

        var selected, row, webID, count=0;
        for(var i = 0; i < self._rows.length; i++) {
            row = self._rows[i];
            if(row) {
                webID = row[0]["__id__"];
                selected = (webID in self.selectedGroup);
                /* if we like this row */
                if(predicate(row[0])) {
                    /* and it's selection status isn't the desired one */
                    if(selected != selectRows) {
                        /* then change it */
                        self.groupSelectRow(webID, getCheckbox(row[1]));
                        count++;
                    }
                /* if we don't like it, but it's in the target state */
                } else if(selected == selectRows) {
                    /* then change it */
                    self.groupSelectRow(webID, getCheckbox(row[1]));
                }
            }
        }
        return count;
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
        /* don't display any of the columns from which we're extracting row metadata */
        return name == "read" || name == "sentWhen" || name == "attachments" || name == "everDeferred";
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
     * Find the row data for the row with web id C{webID}
     */
    function findRowData(self, webID) {
        for(var i = 0; i < self._rows.length; i++) {
            if(self._rows[i] && self._rows[i][0]["__id__"] == webID) {
                return self._rows[i][0];
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
        self.widgetParent.rowsFetched(count);
    });


Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass('Quotient.Mailbox.Controller');
Quotient.Mailbox.Controller.methods(
    function __init__(self, node, messageCount, complexityLevel) {
        self.lastPageSize = Divmod.Runtime.theRuntime.getPageSize();
        document.getElementById("mantissa-footer").style.display = "none";

        MochiKit.DOM.addToCallStack(window, "onload",
            function() {
                MochiKit.DOM.addToCallStack(window, "onresize",
                    function() {
                        var pageSize = Divmod.Runtime.theRuntime.getPageSize();
                        if(pageSize.w != self.lastPageSize.w || pageSize.h != self.lastPageSize.h) {
                            self.lastPageSize = pageSize;
                            self.resized(false);
                        }
                    }, false);
            }, false);

        var search = document.getElementById("search-button");
        if(search) {
            /* if there aren't any search providers available,
             * then there won't be a search button */
            var width = Divmod.Runtime.theRuntime.getElementSize(search.parentNode).w;
            var contentTableContainer = Nevow.Athena.FirstNodeByAttribute(
                                    node, "class", "content-table-container");
            contentTableContainer.style.paddingRight = width + "px";
        }

        Quotient.Mailbox.Controller.upcall(self, "__init__", node);

        self._batchSelectionPredicates = {read:   function(r) { return  r["read"] },
                                          unread: function(r) { return !r["read"] }}

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

        self.viewPaneCell = self.firstWithClass(self.contentTableGrid[0][0], "view-pane-cell");
        self.viewShortcutSelect = self.firstWithClass(self.node, "view-shortcut-container");

        var scrollNode = Nevow.Athena.FirstNodeByAttribute(self.node,
                                                           "athena:class",
                                                           "Quotient.Mailbox.ScrollingWidget");

        self.scrollWidget = Nevow.Athena.Widget.get(scrollNode);
        self.scrolltableContainer = self.scrollWidget.node.parentNode;
        self.groupActionsForm = Nevow.Athena.FirstNodeByAttribute(
                                    self.contentTableGrid[1][1], "name", "group-actions");

        self._selectAndFetchFirstRow();

        self.setMessageCount(messageCount);

        self.delayedLoad(complexityLevel);
    },

    function _cacheContentTableGrid(self) {
        self.inboxContent = self.firstNodeByAttribute("class", "inbox-content");
        var firstByTagName = function(container, tagName) {
            return self.getFirstElementByTagNameShallow(container, tagName);
        }
        var contentTableContainer = Divmod.Runtime.theRuntime.getElementsByTagNameShallow(
                                        self.inboxContent, "div")[1];
        var contentTable = firstByTagName(contentTableContainer, "table");
        var contentTableRows = Divmod.Runtime.theRuntime.getElementsByTagNameShallow(
                                    firstByTagName(contentTable, "tbody"), "tr");
        var contentTableGrid = [];

        for(var i = 0; i < contentTableRows.length; i++) {
            contentTableGrid.push(
                Divmod.Runtime.theRuntime.getElementsByTagNameShallow(
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

    function rowsFetched(self, count) {
        if(0 < count && self._batchSelection) {
            var pred = self._batchSelectionPredicates[self._batchSelection];
            self.scrollWidget.massSelectOrNot(true, pred);
        }
    },

    function changeBatchSelection(self, to) {
        if(to == undefined) {
            to = document.forms["batch-selection"].elements["batch-type"].value;
        }
        var args = [to != "none"];
        if(to in self._batchSelectionPredicates) {
            args.push(self._batchSelectionPredicates[to]);
        }

        /* we can't actually do anything useful with this count, like
         * only enabling aggregate actions if it's > 0 because there
         * could be as-yet unrequested rows that the action will affect.
         * we could probably treat is as meaningful if we know we've
         * already requested all of the rows, but that's not so important
         * right now */
        var count = self.scrollWidget.massSelectOrNot.apply(self.scrollWidget, args);
        if(to == "none") {
            self._changeGroupActionAvailability(false);
            self._batchSelection = null;
        } else {
            self._changeGroupActionAvailability(true);
            self._batchSelection = to;
        }
    },

    function adjustProgressBar(self, lessHowManyMessages) {
        if(self.progressBar) {
            self.progressBar = self.firstWithClass(self.contentTableGrid[1][2],
                                                   "progress-bar");
        }
        self.progressBar.style.borderRight = "solid 1px #6699CC";
        self.remainingMessages -= lessHowManyMessages;
        self.setProgressWidth();
    },

    /**
     * Return a two element list.  The first element will be a sequence
     * of web IDs for currently selected messages who do not fit the batch
     * selection criteria, and the second element will be a sequence of
     * web IDs for messages who fit the batch selection criteria but are
     * not currently selected.  Both lists may be empty
     */
    function getBatchExceptions(self) {
        var row, webID,
            sw = self.scrollWidget,
            rows = sw._rows,
            sel = self._batchSelection,
            pred = self._batchSelectionPredicates[sel],
            include = [],
            exclude = [];

        if(!pred) {
            pred = function(r) {
                /* always true for "all", always false for "none" */
                return sel == "all";
            }
        }

        for(var i = 0; i < rows.length; i++) {
            row = rows[i];
            if(row) {
                webID = row[0]["__id__"];
                /* if it's selected */
                if(webID in sw.selectedGroup) {
                    /* and it doesn't fulfill the predicate */
                    if(!pred(row[0])) {
                        /* then mark it for explicit inclusion */
                        include.push(webID);
                    }
                /* or it's not selected and does fulfill the predicate */
                } else if(pred(row[0])) {
                    /* then mark it for explicit exclusion */
                    exclude.push(webID);
                }
            }
        }
        return [include, exclude];
    },

    function touchBatch(self, action, isDestructive) {
        var remoteArgs = [action + "MessageBatch", self._batchSelection];
        remoteArgs = remoteArgs.concat(self.getBatchExceptions());

        for(var i = 3; i < arguments.length; i++) {
            remoteArgs.push(arguments[i]);
        }

        self.messageDetail.style.opacity = .2;
        return self.callRemote.apply(self, remoteArgs).addCallback(
            function(data) {
                self.messageDetail.style.opacity = 1;
                self.setMessageContent(data[0]);

                var affectedCount = data[1];
                var affectedUnreadCount = data[2];

                self.adjustProgressBar(affectedCount);
                self.adjustCounts(remoteArgs, affectedUnreadCount);

                self._batchSelection = null;
                self._changeGroupActionAvailability(false);
                self.scrollWidget.emptyAndRefill();

                var D = Divmod.Defer.Deferred();

                self.scrollWidget._pendingRowSelection = function(count) {
                    if(0 < count) {
                        self.scrollWidget._selectFirstRow();
                    }
                    D.callback(null);
                }
                return D;
            });
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

    /**
     * Decrement the unread message count that is displayed next
     * to the name of the view called C{viewName} C{byHowMuch}
     *
     * @param viewName: string
     * @param byHowMuch: number
     * @return: undefined
     */
    function decrementMailViewCount(self, viewName, byHowMuch) {
        var decrementNodeValue = function(node) {
            node.firstChild.nodeValue = parseInt(node.firstChild.nodeValue) - byHowMuch;
        }

        var cnode = self.firstWithClass(self.mailViewNodes[viewName], "count");
        decrementNodeValue(cnode);

        if(viewName == "Inbox") {
            decrementNodeValue(self.firstWithClass(self.mailViewNodes["All"], "count"));
        }
    },

    /**
     * Decrement the unread message count that is displayed next to
     * the name of the currently active view in the view selector.
     *
     * (e.g. "Inbox (31)" -> "Inbox (30)")
     */
    function decrementActiveMailViewCount(self, byHowMuch/*=1*/) {
        if(byHowMuch == undefined) {
            byHowMuch = 1;
        }

        self.decrementMailViewCount(self._viewingByView, byHowMuch);
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
            self.setInitialComplexity(complexityLevel).addCallback(
                function() {
                    self.finishedLoading();
                    self.resized(true);
                });
        }, 0);
    },

    function setInitialComplexity(self, complexityLevel) {
        var cc = self.firstWithClass(self.node, "complexity-icons");
        self.setComplexity(complexityLevel,
                            cc.getElementsByTagName("img")[3-complexityLevel],
                            false);
        /* firefox goofs the table layout unless we make it
            factor all three columns into it.  the user won't
            actually see anything strange */
        if(complexityLevel == 1) {
            var D = Divmod.Defer.Deferred();
            self._setComplexityVisibility(3);
            /* two vanilla calls aren't enough, firefox won't
                update the viewport */
            setTimeout(function() {
                self._setComplexityVisibility(1);
                D.callback(null);
            }, 1);
            return D;
        }
        return Divmod.Defer.succeed(null);
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
            var blockFooter = self.firstNodeByAttribute("class", "right-block-footer");
            self.blockFooterHeight = getHeight(blockFooter);
            self.totalFooterHeight = self.blockFooterHeight + 5;
        }

        var swHeight = self.scrollWidget.getHeight(self);
        self.contentTableGrid[0][1].style.height = swHeight + "px";
        self.scrollWidget._scrollViewport.style.height = swHeight + "px";

        self.messageDetail.style.height = (Divmod.Runtime.theRuntime.getPageSize().h -
                                           self.ypos - 14 -
                                           self.totalFooterHeight) + "px";

        setTimeout(
            function() {
                self.recalculateMsgDetailWidth(initialResize);
            }, 0);
    },

    function recalculateMsgDetailWidth(self, initialResize) {
        if(!self.initialResize) {
            self.messageDetail.style.width = "100%";
        }

        document.body.style.overflow = "hidden";
        self.messageDetail.style.overflow = "hidden";

        self.messageDetail.style.width = Divmod.Runtime.theRuntime.getElementSize(
                                            self.messageDetail).w + "px";

        self.messageDetail.style.overflow = "auto";
        document.body.style.overflow = "auto";
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
            if(nodes[i]) {
                nodes[i].style.display = display;
            }
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
            self.contentTableGrid[0][0].style.display = "none";
            self.contentTableGrid[1][0].style.display = "none";
            self.hideAll(self._getContentTableColumn(1));
            self.setScrollTablePosition("absolute");
            self.viewShortcutSelect.style.display = "";
            /* use the default font-size, because complexity 1
               is the default complexity. */
            fontSize = "";
        } else if(c == 2) {
            self.contentTableGrid[0][0].style.display = "none";
            self.contentTableGrid[1][0].style.display = "none";
            self.showAll(self._getContentTableColumn(1));
            self.setScrollTablePosition("static");
            self.viewShortcutSelect.style.display = "";
            fontSize = "1.3em";
        } else if(c == 3) {
            self.viewShortcutSelect.style.display = "none";
            self.contentTableGrid[0][0].style.display = "";
            self.contentTableGrid[1][0].style.display = "";
            self.showAll(self._getContentTableColumn(1));
            self.setScrollTablePosition("static");
            fontSize = "1.3em";
        }
        try {
            var messageBody = self.firstWithClass(self.messageDetail, "message-body");
            messageBody.style.fontSize = fontSize;
        } catch(e) {}

        /* store this for next time we load a message
           in this complexity level */
        self.fontSize = fontSize;
    },

    /**
     * level = integer between 1 and 3
     * node = the image that represents this complexity level
     * report = boolean - should we persist this change
     */
    function setComplexity(self, level, node, report) {
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
        self.recalculateMsgDetailWidth(false);
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
    },

    function fastForward(self, toMessageID) {
        self.messageDetail.style.opacity = .2;
        return self.callRemote("fastForward", toMessageID).addCallback(
            function(messageData) {
                self.scrollWidget.findRowData(toMessageID)["read"] = true;
                self.messageDetail.style.opacity = 1;
                self.setMessageContent(messageData, true);
            });
    },

    /**
     * pre-process a request to call a remote view-changing method.
     * @param viewFunction: name of the remote method
     * @param node: (optional) node containing the argument for the method
     * @param catchAll: treat "All" as a special view name
     * @param value: (optional) must be specified if C{node} isn't.
     *               this is the argument that'll get passed to the remote
     *               method
     */
    function _chooseViewParameter(self, viewFunction, node,
                                  catchAll /* = true */,
                                  value /* = null */) {
        if (catchAll == undefined) {
            catchAll = true;
        }

        if(value == undefined) {
            value = node.firstChild.firstChild.nodeValue;
        }
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
                if (messageData[2] != null) {
                    self.updateMailViewCounts(messageData[2]);
                }
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
        var tc = self.firstWithClass(self.contentTableGrid[0][0], "tag-chooser");
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
            Spam:     {show: [delete_, train_ham],
                       hide: [archive, defer, train_spam]},
            All:      {show: [delete_, train_spam],
                       hide: [archive, defer, train_ham]},
            Inbox:    {show: [archive, defer, delete_, train_spam],
                       hide: [train_ham]},
            Sent:     {show: [delete_],
                       hide: [train_ham, train_spam, archive, defer]},
            Trash:    {show: [],
                       hide: [train_ham, train_spam, archive, defer, delete_]},
            Deferred: {show: [],
                       hide: [train_ham, train_spam, archive, defer, delete_]}}
    },

    /**
     * Select a new, semantically random set of messages to display.  Adjust
     * local state to indicate which random crap is being viewed and, if
     * necessary, ask the server for the messages to display.
     *
     * @param view: the name of the view to switch to
     * @return: L{Deferred}, which will fire after view change is complete
     */
    function chooseMailView(self, view) {
        self.disableGroupActions();

        self._viewingByView = view;
        self._selectListOption(self.mailViewNodes[view]);
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

        self.setGroupActions(namesOnly("show"));

        return self._chooseViewParameter(
                    'viewByMailType', self.mailViewNodes[view], false);
    },

    /**
     * Select the view shortcut link that corresponds to the
     * current mail view, if any.
     */
    function _selectViewShortcut(self) {
        if(self._viewingByView != "Inbox"
            && self._viewingByView != "Sent"
            && self._viewingByView != "Spam") {
            return;
        }

        var options = self.viewShortcutSelect.getElementsByTagName("option");
        for(var i = 0; i < options.length; i++) {
            if(options[i].value == self._viewingByView) {
                self.viewShortcutSelect.selectedIndex = i;
                break;
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
     * Internet Explorer doesn't honour the "display" CSS property
     * or the "disabled" attribute on <option> nodes, so each time
     * the list of available actions needs to change, we'll just
     * remove all of the nodes in the group action <select> and
     * replace them with the ones that we know we need.
     *
     * @param: array of available action names.  (e.g. train-ham,
     *         train-spam, delete, archive, defer)
     * @return: undefined
     */
    function setGroupActions(self, actionNames) {
        var select = self.groupActionsForm.elements["group-action"];
        while(0 < select.childNodes.length) {
            select.removeChild(select.firstChild);
        }
        var nameToDisplay = {"train-ham": "Not Spam",
                             "train-spam": "Is Spam",
                             "delete": "Delete",
                             "archive": "Archive",
                             "defer": "Defer"};
        for(var i = 0; i < actionNames.length; i++) {
            /* XXX hack.  we should be able to defer multiple msgs */
            if(actionNames[i] == "defer") {
                continue;
            }
            select.appendChild(
                MochiKit.DOM.OPTION(
                    {"value": actionNames[i]}, nameToDisplay[actionNames[i]]));
        }
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
        return self._chooseViewParameter('viewByPerson', null, true, keyn.firstChild.nodeValue);
    },

    function setupMailViewNodes(self) {
        if(!self.mailViewBody) {
            var mailViewPane = self.firstWithClass(self.contentTableGrid[0][0], "view-pane-content");
            var mailViewBody = self.firstWithClass(mailViewPane, "pane-body");
            self.mailViewBody = self.getFirstElementByTagNameShallow(mailViewBody, "div");
        }

        var nodes = {"All": null, "Trash": null, "Sent": null,
                     "Spam": null, "Inbox": null, "Deferred": null};
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

        return self.doTouch(remoteArgs, isProgress, 1, 0);
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
        var args = [];
        for(var i = 1; i < arguments.length; i++) {
            args.push(arguments[i]);
        }
        /* make sure additional arguments get forwarded correctly */
        if(self._batchSelection) {
            return self.touchBatch.apply(self, args);
        }
        var sw = self.scrollWidget;
        var selgroup = sw.selectedGroup;
        var webIDs = MochiKit.Base.keys(selgroup);
        var selectedRowOffset = sw.findRowOffset(sw._selectedRow);
        var selectedRowID = sw._rows[selectedRowOffset][0]["__id__"];
        var next, isProgress = isDestructive;

        var affectedUnreadCount = 0;
        if(isDestructive) {
            var rowData, offset;
            /* FIXME optimize.  selectedGroup can be a mapping of
               webIDs to column dictionaries or something */
            for(var i in selgroup) {
                offset = sw.findRowOffset(selgroup[i]);
                if(offset == null) {
                    delete selgroup[i];
                    continue;
                }
                rowData = sw._rows[offset][0];
                if(!rowData["read"]) {
                    affectedUnreadCount++;
                }
            }
            /* if this action is going to dismiss the message being viewed */
            if(selectedRowID in selgroup) {
                /* is there a row after the selected row that isn't earmarked for destruction */
                var predicate = function(rowOffset, rowData, rowElement) {
                                    return !(rowData["__id__"] in selgroup);
                                }
                next = sw.findNextRow(sw._selectedRow, predicate, true)
                        || sw.findPrevRow(sw._selectedRow, predicate, true);
            /* if it isn't, then we aren't going to progress */
            } else {
                isProgress = false;
            }
        }

        var nextMessageID = null;
        if(next) {
            nextMessageID = sw._rows[next[1]][0]["__id__"];
        }

        if(isDestructive) {
            for(var k in selgroup) {
                sw.removeRow(selgroup[k]);
            }
            self.disableGroupActions();
            if(next && next[0].tagName) {
                sw._selectRow(next[0]);
                sw.scrolled();
            }
        }

        sw.selectedGroup = {};
        var remoteArgs = [action + "MessageGroup", isProgress, nextMessageID, webIDs];
        remoteArgs = remoteArgs.concat(args.slice(2));

        return self.doTouch(remoteArgs, isProgress, webIDs.length, affectedUnreadCount);
    },

    /**
     * Adjust the unread message counts.  Typically called after
     * performing a destructive action.  Takes into account the
     * destination of a set of messages by looking at the current
     * view and the action that was performed.
     *
     * @param args: array of arguments passed to callRemote() to
     *              initiate the action server-side.  typically
     *              something like ["archiveCurrentMessage"] or
     *              ["trainMessageGroup", true]
     * @param affectedUnreadCount: number of unread messages
     *                             affected by the action.
     * @return: undefined
     */
    function adjustCounts(self, args, affectedUnreadCount) {
        if(affectedUnreadCount == 0) {
            return;
        }

        var suffixes = ["CurrentMessage", "MessageGroup", "MessageBatch"];
        var action = args[0];
        for(var i = 0; i < suffixes.length; i++) {
            if(action.substr(action.length-suffixes[i].length) == suffixes[i]) {
                action = action.substr(0, action.length-suffixes[i].length);
                break;
            }
        }
        self.decrementActiveMailViewCount(affectedUnreadCount);

        var addTo;

        if(action == "archive") {
            addTo = "All";
        } else if(action == "train") {
            if(args[args.length-1]) {
                addTo = "Spam";
            } else {
                addTo = "Inbox";
            }
        } else {
            return;
        }

        self.decrementMailViewCount(addTo, -affectedUnreadCount);
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
    function doTouch(self, remoteArgs, isProgress, touchingHowMany, touchingHowManyUnread) {
        self.messageDetail.style.opacity = .2;
        return self.callRemote.apply(self, remoteArgs).addCallback(
            function(nextMessage) {
                self.messageDetail.style.opacity = 1;

                self.adjustProgressBar(touchingHowMany);
                self.adjustCounts(remoteArgs, touchingHowManyUnread);

                if(isProgress) {
                    self.setMessageContent(nextMessage);
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
        var form = self.groupActionsForm;
        var currentlyEnabled = !form.elements["group-action"].disabled;
        self._changeGroupActionAvailability(!currentlyEnabled);
    },

    function disableGroupActions(self) {
        self._changeGroupActionAvailability(false);
    },

    /**
     * @param available: boolean.  true = enable, false = disable
     */
    function _changeGroupActionAvailability(self, available) {
        var form = self.groupActionsForm;
        var gap = self.getFirstNode(form.parentNode.parentNode, "group-action-perform");
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
        var form = self.groupActionsForm;
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
        self.inboxContent.style.display = "none";
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
        self.inboxContent.style.display = "";
    },

    function setMessageCount(self, count) {
        self.remainingMessages = count;
        self.totalMessages = count;
        self.setProgressWidth();
    },

    function setProgressWidth(self) {
        if(!self.progressBar) {
            self.progressBar = self.firstWithClass(
                                self.contentTableGrid[1][2], "progress-bar");
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

    /** Fragment-boundary-crossing proxy for
     * L{Quotient.Mailbox.MessageDetail.printable}
     */
    function printable(self) {
        Quotient.Mailbox.MessageDetail.get(
            self.firstWithClass(
                self.messageDetail, "message-detail-fragment")).printable();
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

        Divmod.msg("setMessageContent(" +
                   currentMessageData +
                   ")");

        self.messageDetail.scrollTop = 0;
        self.messageDetail.scrollLeft = 0;

        Divmod.Runtime.theRuntime.setNodeContent(
            self.messageDetail,
            ('<div xmlns="http://www.w3.org/1999/xhtml">' +
             currentMessageDisplay +
             '</div>'));

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

        if (nextMessagePreview != null) {
            if(!self.nextMessagePreview) {
                self.nextMessagePreview = self.firstWithClass(
                                            self.contentTableGrid[1][2],
                                            "next-message-preview");
            }
            /* so this is a message, not a compose fragment */
            Divmod.Runtime.theRuntime.setNodeContent(
                self.nextMessagePreview,
                ('<div xmlns="http://www.w3.org/1999/xhtml">' +
                 nextMessagePreview +
                 '</div>'));
            self.highlightExtracts();
        }

        /* if this is the "no more messages" pseudo-message,
           then there won't be any message body */
        try {
            var messageBody = self.firstWithClass(
                                self.messageDetail,
                                "message-body");
        } catch(e) {
            return;
        }
        /* set the font size to the last value used in
           _setComplexityVisibility() */
        messageBody.style.fontSize = self.fontSize;
    })
