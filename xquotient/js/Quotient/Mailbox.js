
// import Mantissa.People
// import Mantissa.ScrollTable

// import Quotient
// import Quotient.Common
// import Quotient.Throbber
// import Quotient.Message


Quotient.Mailbox.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass(
    "Quotient.Mailbox.ScrollingWidget");

Quotient.Mailbox.ScrollingWidget.methods(
    function __init__(self, node) {
        Quotient.Mailbox.ScrollingWidget.upcall(self, "__init__", node);
        self.selectedGroup = {};
        self.columnAliases = {"receivedWhen": "Date", "senderDisplay": "Sender"};
        self._scrollViewport.style.maxHeight = "";
        self.ypos = Quotient.Common.Util.findPosY(self._scrollViewport.parentNode);
        try {
            self.throbberNode = Nevow.Athena.FirstNodeByAttribute(self.node.parentNode, "class", "throbber");
        } catch (err) {
            self.throbberNode = document.createElement('span');
        }
        self.throbber = Quotient.Throbber.Throbber(self.throbberNode);
    },

    /**
     * Override default row to add some divs with particular classes, since
     * they will most likely change the height of our rows.
     */
    function _getRowGuineaPig(self) {
        return MochiKit.DOM.DIV(
            {"style": "visibility: hidden; font-weight: bold",
             "class": "q-scroll-row"},
            [MochiKit.DOM.DIV({"class": "sender"}, "TEST!!!"),
             MochiKit.DOM.DIV({"class": "subject"}, "TEST!!!"),
             MochiKit.DOM.DIV(null, "TEST!!!")]);
    },


    /**
     * Extend the base behavior to reset the message selection group tracking
     * object.
     *
     * XXX - The base scrolltable should really support selection, so all of
     * the selection related features like this one should move over there.
     */
    function emptyAndRefill(self) {
        self.selectedGroup = {};
        return Quotient.Mailbox.ScrollingWidget.upcall(self, 'emptyAndRefill');
    },

    /**
     * Override this to do nothing because the Inbox cannot be sorted at all!
     *
     * XXX - Hey, wtf, why can't the inbox be sorted? -exarkun
     */
    function setSortInfo(self, currentSortColumn, isAscendingNow) {},

    /**
     * Override this to return an empty Array because the Inbox has no row
     * headers.
     */
    function _createRowHeaders(self, columnNames) {
        return [];
    },

    /*****************************************************\
    |**         ISelectableScrollingWidget              **|
    \*****************************************************/

    /**
     * Change the current message selection to the given webID.
     *
     * If a message was already selected, change its background color back to
     * the unselected color.  Change the newly selected message's background
     * color to the selected color.
     *
     * If C{webID} is C{null}, only unselect the currently selected message.
     *
     * @type webID: string
     *
     * @rtype: string
     * @return: The webID of the previously selected message, or null if there
     * was no previously selected message.
     */
    function _selectWebID(self, webID) {
        var row;
        var node, oldNode = null;
        var oldSelectedRowID = null;

        if (self._selectedRowID) {
            oldSelectedRowID = self._selectedRowID;
            oldNode = self.model.findRowData(self._selectedRowID).__node__;
            oldNode.style.backgroundColor = '';
        }

        if (webID != null) {
            self._selectedRowID = webID;

            row = self.model.findRowData(webID);
            node = row.__node__;

            row["read"] = true;

            if (node.style.fontWeight == "bold") {
                self.decrementActiveMailViewCount();
            }

            node.style.fontWeight = "";
            node.style.backgroundColor = '#FFFFFF';
        } else {
            self._selectedRowID = null;
        }

        /*
         * XXX selectionChanged returns a Deferred, we should really be
         * propagating it.
         */
        self.selectionChanged(webID);
        return oldSelectedRowID;
    },

    /**
     * Called whenever the selected row is changed.
     *
     * This implementation updates the message detail area of the Controller
     * which is the parent widget of this widget.  It returns a Deferred which
     * fires when this has been completed.
     */
    function selectionChanged(self, webID) {
        if (webID == null) {
            self.widgetParent.clearMessageDetail();
            return Divmod.Defer.succeed(null);
        } else {
            return self.widgetParent.updateMessageDetail(webID);
        }
    },

    function decrementActiveMailViewCount(self) {
        return self.widgetParent.decrementActiveMailViewCount();
    },

    /**
     * Remove the row at the given index and update the message selection if
     * necessary.
     */
    function removeRow(self, index) {
        var row = self.model.getRowData(index);
        /*
         * The row was selected - unselect it quick or
         * something terrible will occur.
         */
        if (row.__id__ == self._selectedRowID) {
            self._selectWebID(null);
        }
        return Quotient.Mailbox.ScrollingWidget.upcall(self, 'removeRow', index);
    },

    /**
     * Return the row data for the currently selected row.  Return null if
     * there is no row selected.
     */
    function getSelectedRow(self) {
        if (self._selectedRowID != null) {
            return self.model.findRowData(self._selectedRowID);
        }
        return null;
    },

    /**
     * Call _selectWebID with the webID of the first row of data currently
     * available.
     *
     * If there are no rows, no action will be taken.
     */
    function _selectFirstRow(self) {
        if (self.model.rowCount()) {
            self._selectWebID(self.model.getRowData(0)['__id__']);
        }
    },


    /**
     * Override row creation to provide a different style.
     *
     * XXX - should be template changes.
     */
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
                self._selectWebID(rowData["__id__"]);
                self.widgetParent.fastForward(rowData["__id__"]);
                return false;
            }}, data);
    },

    /**
     * Extend base behavior to recognize the subject column and replace empty
     * subjects with a special string.
     *
     * XXX - Dynamic dispatch for column names or templates or something.
     */
    function massageColumnValue(self, name, type, value) {
        var res = Quotient.Mailbox.ScrollingWidget.upcall(
                        self, "massageColumnValue", name, type, value);

        var ALL_WHITESPACE = /^\s*$/;
        if(name == "subject" && ALL_WHITESPACE.test(res)) {
            res = "<no subject>";
        }
        return res;
    },

    /**
     * Override the base behavior to add a million and one special cases for
     * things like the "ever deferred" boomerang or to change the name of the
     * "receivedWhen" column to something totally unrelated like "sentWhen".
     *
     * XXX - Should just be template crap.
     */
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
            var content = [
                MochiKit.DOM.IMG({
                        "src": "/Quotient/static/images/checkbox-off.gif",
                        "class": "checkbox-image",
                        "border": 0,
                        "onclick": function senderDisplayClicked(event) {
                            self.groupSelectRowAndUpdateCheckbox(rowData["__id__"], this);

                            this.blur();

                            if (!event) {
                                event = window.event;
                            }
                            event.cancelBubble = true;
                            if(event.stopPropagation) {
                                event.stopPropagation();
                            }

                            return false;
                        }}), massage(colName)];

            if (rowData["everDeferred"]) {
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
     * Toggle the membership of a row in the group selection set.
     */
    function groupSelectRow(self, webID) {
        var state;
        if(webID in self.selectedGroup) {
            delete self.selectedGroup[webID];
            state = "off";
        } else {
            self.selectedGroup[webID] = true;
            state = "on";
        }

        var selcount = MochiKit.Base.keys(self.selectedGroup).length;
        /* are we transitioning from 0->1 or 1->0? */
        if (selcount == 0 && state == "off") {
            self.disableGroupActions();
        } else if (selcount == 1 && state == "on") {
            self.enableGroupActions();
        }
        return state;
    },

    /**
     * Enable the user-interface for performing actions on the selected group
     * of messages.
     *
     * XXX Give the widget parent a real enable method.
     */
    function enableGroupActions(self) {
        self.widgetParent.toggleGroupActions();
    },

    /**
     * Disable the user-interface for performing actions on the selected group
     * of messages.
     *
     * XXX Give the widget parent a real disable method.
     */
    function disableGroupActions(self) {
        self.widgetParent.toggleGroupActions();
    },

    /**
     * Toggle the membership of a row in the group selection set and update the
     * checkbox image for that row.
     */
    function groupSelectRowAndUpdateCheckbox(self, webID, checkboxImage) {
        var state = self.groupSelectRow(webID);
        var segs = checkboxImage.src.split("/");
        segs[segs.length - 1] = "checkbox-" + state + ".gif";
        checkboxImage.src = segs.join("/");
    },

    /**
     * Return the checkbox image node for the given row.
     */
    function _getCheckbox(self, row) {
        return Divmod.Runtime.theRuntime.firstNodeByAttribute(
            row.__node__, 'class', 'checkbox-image');
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

        var selected, row, webID, count=0;
        for(var i = 0; i < self.model.rowCount(); i++) {
            row = self.model.getRowData(i);
            if(row) {
                webID = row.__id__;
                selected = (webID in self.selectedGroup);
                /* if we like this row */
                if(predicate(row)) {
                    /* and it's selection status isn't the desired one */
                    if(selected != selectRows) {
                        /* then change it */
                        self.groupSelectRowAndUpdateCheckbox(webID, self._getCheckbox(row));
                        count++;
                    }
                /* if we don't like it, but it's in the target state */
                } else if(selected == selectRows) {
                    /* then change it */
                    self.groupSelectRowAndUpdateCheckbox(webID, self._getCheckbox(row));
                }
            }
        }
        return count;
    },

    /**
     * Override the base implementation to optionally use the specified second
     * Date instance as a point of reference.
     *
     * XXX - Why isn't this just the base implementation?
     */
    function formatDate(self, when, /* optional */ now) {
        if (now == undefined) {
            now = new Date();
        }
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
            return [d.getFullYear(), d.getMonth(), d.getDate()];
        }
        function arraysEqual(a, b) {
            if (a.length != b.length) {
                return false;
            }
            for (var i = 0; i < a.length; ++i) {
                if (a[i] != b[i]) {
                    return false;
                }
            }
            return true;
        }
        var parts = explode(when);
        var todayParts = explode(now);
        if (arraysEqual(parts, todayParts)) {
            /* it's today! Format it like "12:15 PM"
             */
            return to12Hour(when.getHours(), when.getMinutes());
        }
        if (parts[0] == todayParts[0]) {
            /* it's this year - format it like "Jan 12"
             *
             * XXX - Localization or whatever.
             */
            var monthNames = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            return monthNames[parts[1]] + " " + parts[2];
        }
        return [pad(when.getFullYear()),
                pad(when.getMonth() + 1),
                pad(when.getDate())].join("-");
    },

    /**
     * Override to hide any of the columns from which we're extracting row
     * metadata.
     */
    function skipColumn(self, name) {
        return name == "read" || name == "sentWhen" || name == "attachments" || name == "everDeferred";
    },

    /**
     * Override to update counts and do something else.
     *
     * XXX - This should be a callback on .scrolled()
     * XXX - And counts should be managed in some completely different way
     * XXX - And the _pendingRowSelection is just crazy, there should be a
     * Deferred or something for whatever that is.
     */
    function cbRowsFetched(self, count) {
        if(self._pendingRowSelection) {
            self._pendingRowSelection(count);
            self._pendingRowSelection = null;
        }
        self.widgetParent.rowsFetched(count);
    });


/**
 * Run interference for a ScrollTable.
 *
 * @ivar contentTableGrid: An Array of the the major components of an inbox
 * view.  The first element is an array with three elements: the td element for
 * the view selection area, the td element for the scrolltable, and the td
 * element for the message detail area.  The second element is also an array
 * with three elements: the footer td elements which correspond to the three td
 * elements in the first array.
 */
Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass('Quotient.Mailbox.Controller');
Quotient.Mailbox.Controller.methods(
    function __init__(self, node, messageCount, selectedMessageIdentifier, complexityLevel) {
        self.lastPageSize = Divmod.Runtime.theRuntime.getPageSize();

        /*
         * Hide the footer for some reason I can't guess.
         */
        var footer = document.getElementById("mantissa-footer");
        if (footer) {
            footer.style.display = "none";
        }

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

        /*
         * When the scroll widget is fully initialized, select the first row in
         * it.
         */
        self.scrollWidget.initializationDeferred.addCallback(
            function(passthrough) {
                self.scrollWidget._selectFirstRow();
                return passthrough;
            });

        self.scrolltableContainer = self.scrollWidget.node.parentNode;
        self.groupActionsForm = Nevow.Athena.FirstNodeByAttribute(
                                    self.contentTableGrid[1][1], "name", "group-actions");

        self.nextMessagePreview = self.firstWithClass(
            self.contentTableGrid[1][2],
            "next-message-preview");

        self.setMessageCount(messageCount);

        self.delayedLoad(complexityLevel);
    },

    function _getViewCountNode(self, view) {
        var viewNode = self.mailViewNodes[view];
        if (viewNode === undefined || viewNode === null) {
            throw new Error("Request for invalid view: " + view);
        }
        var count = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            viewNode.parentNode, 'class', 'count').firstChild;
        return count;
    },

    /**
     * Return the count of unread messages in the given view.
     *
     * @param view: One of "All", "Inbox", "Spam" or "Sent".
     */
    function getUnreadCountForView(self, view) {
        return parseInt(self._getViewCountNode(view).nodeValue);
    },

    function setUnreadCountForView(self, view, count) {
        var countNode = self._getViewCountNode(view);
        countNode.nodeValue = String(count);
    },

    /**
     * @return: an array of objects with C{name} and C{key} properties bound to
     * the name and unique server-side identifier for each person being
     * displayed in the view selection chooser.
     */
    function getPeople(self) {
        var people = [];
        var personChooser = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            self.contentTableGrid[0][0], 'class', 'person-chooser');
        var personChoices = Divmod.Runtime.theRuntime.nodesByAttribute(
            personChooser, 'class', 'list-option');
        var nameNode, keyNode;
        var name, key;
        for (var i = 0; i < personChoices.length; ++i) {
            nameNode = Divmod.Runtime.theRuntime.firstNodeByAttribute(
                personChoices[i], 'class', 'opt-name');
            keyNode = Divmod.Runtime.theRuntime.firstNodeByAttribute(
                personChoices[i], 'class', 'person-key');
            name = nameNode.firstChild.nodeValue;
            key = keyNode.firstChild.nodeValue;
            people.push({name: name, key: key});
        }
        return people;
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

    /**
     * XXX
     */
    function changeBatchSelectionByNode(self, buttonNode) {
        /*
         * This doesn't actually use the button node, since it has essentially
         * nothing to do with the state of the batch selection nodes in the
         * DOM.
         */
        var selectNode = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            self.node, 'name', 'batch-type');
        return self.changeBatchSelection(selectNode.value);
    },

    /**
     * XX
     */
    function changeBatchSelection(self, to) {
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

        for(var i = 0; i < sw.model.rowCount(); i++) {
            row = sw.model.getRowData(i);
            if(row != undefined) {
                webID = row["__id__"];
                /* if it's selected */
                if (webID in sw.selectedGroup) {
                    /* and it doesn't fulfill the predicate */
                    if (!pred(row)) {
                        /* then mark it for explicit inclusion */
                        include.push(webID);
                    }
                /* or it's not selected and does fulfill the predicate */
                } else if (pred(row)) {
                    /* then mark it for explicit exclusion */
                    exclude.push(webID);
                }
            }
        }
        return [include, exclude];
    },

    function _removeRows(self, rows) {
        /*
         * This action is removing rows from visibility.  Drop them
         * from the model.  Change the currently selected row, if
         * necessary.
         */
        var i, row, index, removed = 0;
        var indices = self.scrollWidget.model.getRowIndices();

        for (i = 0; i < indices.length; ++i) {
            index = indices[i] - removed;
            row = self.scrollWidget.model.getRowData(index);
            if (row.__id__ in self.scrollWidget.selectedGroup) {
                self.scrollWidget.removeRow(index);
                removed += 1;
            }
        }

        return self.scrollWidget.scrolled().addCallback(
            function(ignored) {
                /*
                 * XXX - Selecting the first row is wrong - we should select a
                 * row very near to the previously selected row, instead.
                 */
                if (self.scrollWidget.getSelectedRow() == null) {
                    self.scrollWidget._selectFirstRow();
                }
            });
    },

    /**
     * Call the given function after setting the message detail area's opacity
     * to 0.2.  Set the message detail area's opacity back to 1.0 after the
     * Deferred the given function returns has fired.
     */
    function withReducedMessageDetailOpacity(self, callable) {
        self.messageDetail.style.opacity = 0.2;
        var result = callable();
        result.addBoth(
            function(passthrough) {
                self.messageDetail.style.opacity = 1.0;
                return passthrough;
            });
        return result;
    },

    function touchBatch(self, action, isDestructive) {
        var exceptions = self.getBatchExceptions();
        var include = exceptions[0];
        var exclude = exceptions[1];

        var result = self.withReducedMessageDetailOpacity(
            function() {
                var acted = self.callRemote("actOnMessageBatch", action, self._batchSelection, include, exclude);
                acted.addCallback(
                    function(counts) {
                        var readTouchedCount = counts[0];
                        var unreadTouchedCount = counts[1];

                        /*
                         * XXX I don't know what this next line means or whether it is
                         * correct or not and there is no test coverage for it.
                         */
                        self.adjustProgressBar(readTouchedCount + unreadTouchedCount);

                        if (isDestructive) {
                            var result = self._removeRows(self.scrollWidget.selectedGroup);
                            self.scrollWidget.selectedGroup = {};
                            return result;
                        }
                        return null;

                    });
                return acted;
            });
        return result;
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
        self.setUnreadCountForView(
            viewName,
            self.getUnreadCountForView(viewName) - byHowMuch);
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


    function getHeight(self) {
        /* This is the cumulative padding/margin for all elements whose
         * heights we factor into the height calculation below.  clientHeight
         * includes border but not padding or margin.
         * FIXME: change all this code to use offsetHeight, not clientHeight
         */
        var basePadding = 14;
        return (Divmod.Runtime.theRuntime.getPageSize().h -
                self.messageBlockYPos -
                self.totalFooterHeight -
                basePadding);

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
        var setHeight = function(node, height) {
            if(0 < height) {
                node.style.height = height + "px";
            }
        }

        if(!self.totalFooterHeight) {
            var blockFooter = self.firstNodeByAttribute("class", "right-block-footer");
            self.blockFooterHeight = getHeight(blockFooter);
            self.totalFooterHeight = self.blockFooterHeight + 5;
        }

        var swHeight = self.getHeight();
        setHeight(self.contentTableGrid[0][1], swHeight);
        setHeight(self.scrollWidget._scrollViewport, swHeight);

        setHeight(self.messageDetail, (Divmod.Runtime.theRuntime.getPageSize().h -
                                       self.ypos - 14 -
                                       self.totalFooterHeight));

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
                self.scrollWidget.model.findRowData(toMessageID)["read"] = true;
                self.messageDetail.style.opacity = 1;
                self.setMessageContent(messageData[0], messageData[1], messageData[2]);
            });
    },


    /**
     * Change the set of messages currently being viewed.
     *
     * @param viewName: A short string identifying the new set of messages to
     * view.  For example, C{"All"} or C{"Spam"}.
     *
     * @return: A Deferred which fires when the view has been updated and the
     * new messages have been retrieved and displayed.
     */
    function switchView(self, viewName) {
        return self._sendViewRequest('viewByMailType', viewName);
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
        self.scrollWidget.throbber.startThrobbing();

        return self.callRemote(viewFunction, value).addCallback(
            function(messageData) {
                self.setMessageCount(messageData[0]);
                self.setMessageContent(messageData[1][0], messageData[1][1], messageData[1][2]);
                if (messageData[2] != null) {
                    self.updateMailViewCounts(messageData[2]);
                }
                self.scrollWidget.setViewportHeight(messageData[0]);
                self.scrollWidget._selectWebID(null);
                var newMessagesDisplayed = self.scrollWidget.emptyAndRefill();

                /*
                 * XXX - This can just be a callback on newMessagesDisplayed, I
                 * think. -exarkun
                 */
                self.scrollWidget._pendingRowSelection = function(count) {
                    if(0 < count) {
                        self._selectAndFetchFirstRow(false);
                    }
                }
                newMessagesDisplayed.addBoth(
                    function(passthrough) {
                        /*
                         * Select the first message now being displayed.
                         */
                        self.scrollWidget._selectFirstRow();

                        /*
                         * Stop the throbber since we're basically done now.
                         */
                        self.scrollWidget.throbber.stopThrobbing();
                        return passthrough;
                    });
                return newMessagesDisplayed;
            });
    },

    /**
     * Change the class of the given node to C{"selected-list-option"}, change
     * the class of any existing selected nodes in the same select group to
     * C{"list-option"}, and change the C{onclick} handler of those nodes to be
     * the same as the C{onclick} handler for the given node.
     */
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
     * Select a tag by its DOM node.
     */
    function chooseTagByNode(self, tagNode) {
        var tagName = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            tagNode, 'class', 'opt-name');
        self._selectListOption(tagNode);
        return self.chooseTag(tagName.firstChild.nodeValue);
    },

    /**
     * Select a new tag from which to display messages.  Adjust local state to
     * indicate which tag is being viewed and, if necessary, ask the server
     * for the messages to display.
     *
     * @type tagName: string
     * @param tagName: The tag to select.
     */
    function chooseTag(self, tagName) {
        if (tagName == 'All') {
            tagName = null;
        }
        return self._sendViewRequest('viewByTag', tagName);
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
     * Call chooseMailView with the view name contained in the child node of
     * C{viewNode} with class "opt-name".
     */
    function chooseMailViewByNode(self, viewNode) {
        var view = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            viewNode, 'class', 'opt-name');
        self._selectListOption(viewNode);
        return self.chooseMailView(view.firstChild.nodeValue);
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
            'viewByMailType', null, false, view);
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
     * Select a new account by DOM node.
     */
    function chooseAccountByNode(self, accountNode) {
        var accountName = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            accountNode, 'class', 'opt-name');
        self._selectListOption(accountNode);
        return self.chooseAccount(accountName.firstChild.nodeValue);
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
        if (tagName == 'All') {
            tagName = null;
        }
        return self._sendViewRequest('viewByAccount', tagName);
    },

    /**
     * Select a new person by DOM node.
     */
    function choosePersonByNode(self, personNode) {
        var personKey = Divmod.Runtime.theRuntime.firstNodeByAttribute(
            personNode, 'class', 'person-key');
        self._selectListOption(n);
        return self.choosePerson(personKey.firstChild.nodeValue);
    },

    /**
     * Select a new person, the messages from which to display.  Adjust local
     * state to indicate which person's messages are being viewed and, if
     * necessary, ask the server for the messages to display.
     *
     * @param n: The node which this input handler is attached to.
     * @return: C{undefined}
     */
    function choosePerson(self, personKey) {
        return self._sendViewRequest('viewByPerson', personKey);
    },

    function setupMailViewNodes(self) {
        if (!self.mailViewBody) {
            var mailViewPane = self.firstWithClass(self.contentTableGrid[0][0], "view-pane-content");
            var mailViewBody = self.firstWithClass(mailViewPane, "pane-body");
            self.mailViewBody = self.getFirstElementByTagNameShallow(mailViewBody, "div");
        }

        var nodes = {"All": null, "Trash": null, "Sent": null,
                     "Spam": null, "Inbox": null, "Deferred": null};
        var e, nameNode, name;

        for(var i = 0; i < self.mailViewBody.childNodes.length; i++) {
            e = self.mailViewBody.childNodes[i];
            try {
                nameNode = Divmod.Runtime.theRuntime.firstNodeByAttribute(
                    e, 'class', 'opt-name');
            } catch (err) {
                if (err instanceof Divmod.Runtime.NodeAttributeError) {
                    continue;
                }
                throw err;
            }
            name = nameNode.firstChild.nodeValue;
            nodes[name] = e.firstChild.nextSibling;
        }
        self.mailViewNodes = nodes;
    },

    function _selectAndFetchFirstRow(self, requestMoreRowsIfNeeded) {
        if(typeof requestMoreRowsIfNeeded === 'undefined') {
            requestMoreRowsIfNeeded = true;
        }

        var sw = self.scrollWidget;
        if (!sw.model.rowCount()) {
            if (requestMoreRowsIfNeeded) {
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
        var model = self.scrollWidget.model;
        var selected = self.scrollWidget._selectedRowID;
        var nextMessageID;

        if (selected === undefined) {
            throw new Error("No row selected.");
        }

        var result = self.withReducedMessageDetailOpacity(
            function() {
                var acted = self.callRemote("actOnMessageIdentifierList", action, [selected]);
                acted.addCallback(
                    function(ignored) {
                        if (isProgress) {
                            nextMessageID = model.findNextRow(selected);
                            if (!nextMessageID) {
                                nextMessageID = model.findPrevRow(selected);
                            }

                            self.scrollWidget.removeRow(self.scrollWidget.model.findIndex(selected));

                            if (nextMessageID) {
                                self.scrollWidget._selectWebID(nextMessageID);
                            }

                            return self.scrollWidget.scrolled();

                        }
                    });
                return acted;
            });
        return result;
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
        self.disableGroupActions();
        var result = self.withReducedMessageDetailOpacity(
            function() {
                var acted = self.callRemote(
                    "actOnMessageIdentifierList", action,
                    Divmod.dir(self.scrollWidget.selectedGroup));
                acted.addCallback(
                    function(counts) {
                        var readTouchedCount = counts[0];
                        var unreadTouchedCount = counts[1];

                        /*
                         * XXX I don't know what this next line means or whether it is
                         * correct or not and there is no test coverage for it.
                         */
                        self.adjustProgressBar(readTouchedCount + unreadTouchedCount);

                        if (isDestructive) {
                            var result = self._removeRows(self.scrollWidget.selectedGroup);
                            self.scrollWidget.selectedGroup = {};
                            return result;
                        } else {
                            self.enableGroupActions();
                            return null;
                        }

                    });
                return acted;
            });
        return result;
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
                    self.setMessageContent(nextMessage[0], nextMessage[1], nextMessage[2]);
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

    function enableGroupActions(self) {
        self._changeGroupActionAvailability(true);
    },

    /**
     * Return the node with the event handler which allows an action to be
     * applied to a group of messages.
     */
    function _getGroupActionPerformButton(self) {
        return self.getFirstNode(
            self.groupActionsForm.parentNode.parentNode,
            "group-action-perform");
    },

    /**
     * @param available: boolean.  true = enable, false = disable
     */
    function _changeGroupActionAvailability(self, available) {
        var form = self.groupActionsForm;
        var gap = self._getGroupActionPerformButton();
        var select = form.elements["group-action"];

        if(available) {
            select.style.opacity = gap.style.opacity = "";
            select.removeAttribute("disabled");
            gap.style.cursor = "";
            gap.onclick = function() {
                try {
                    var form = self.groupActionsForm;
                    var actionName = form.elements["group-action"].value;

                    if(actionName == "train-spam") {
                        actionName = "trainSpam";
                    } else if (actionName == "train-ham") {
                        actionName = "trainHam";
                    }
                    if (self._batchSelection) {
                        self.touchBatch(actionName, true);
                    } else {
                        self.touchSelectedGroup(actionName, true);
                    }
                } catch (err) {
                    Divmod.err(err);
                }
                return false;
            };
        } else {
            select.style.opacity = gap.style.opacity = ".3";
            select.setAttribute("disabled", "true");
            gap.style.cursor = "default";
            gap.onclick = function() {
                return false;
            }
        }
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
     * L{Quotient.Message.MessageDetail.printable}
     */
    function printable(self) {
        Quotient.Message.MessageDetail.get(
            self.firstWithClass(
                self.messageDetail, "message-detail-fragment")).printable();
    },

    /**
     * Empty the message detail view area of content.
     */
    function clearMessageDetail(self) {
        self.messageDetail.scrollTop = 0;
        self.messageDetail.scrollLeft = 0;
        Divmod.Runtime.theRuntime.setNodeContent(
            self.messageDetail,
            '<span xmlns="http://www.w3.org/1999/xhtml"></span>');
        Divmod.Runtime.theRuntime.setNodeContent(
            self.nextMessagePreview,
            '<span xmlns="http://www.w3.org/1999/xhtml"></span>');
    },

    /**
     * Update the message detail area to display the specified message.  Return
     * a Deferred which fires when this has finished.
     */
    function updateMessageDetail(self, webID) {
        return self.callRemote("fastForward", webID).addCallback(
            function(info) {
                return self.setMessageContent(
                    info[0], info[1], info[2]);
            });
    },

    /**
     * @param data: Three-Array of the html for next message preview, the
     * html for the current message, and some structured data describing
     * the current message
     */
    function setMessageContent(self, nextMessagePreview, currentMessageDisplay, currentMessageData) {
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
