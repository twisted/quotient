// import Quotient
// import Quotient.Common
// import Quotient.Compose
// import Mantissa.People
// import LightBox
// import Mantissa.ScrollTable

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

Quotient.Mailbox.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass();
Quotient.Mailbox.ScrollingWidget.methods(
    function _selectRow(self, rowOffset, row) {
        if(self._selectedRow) {
            self._selectedRow.style.backgroundColor = '#FFFFFF';
        }
        row.style.backgroundColor = '#CACACA';
        self._selectedRow = row;
        self._selectedRowOffset = rowOffset;
    },

    function makeRowElement(self, rowOffset, rowData, cells) {
        return MochiKit.DOM.A(
            {"class": "scroll-row",
             "href": "#",
             "style": rowData["read"] ? "" : "font-weight: bold",
             "onclick": function() {
                self._selectRow(rowOffset, this);
                self.widgetParent.loadMessageFromID(rowData["__id__"]);
                return false;
            }},
            cells);
    },

    function skipColumn(self, name) {
        return name == "read";
    },
    
    function cbRowsFetched(self) {
        if(self._pendingRowSelection) {
            self._pendingRowSelection();
            self._pendingRowSelection = null;
        }
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
                                                      "Quotient.Mailbox.ScrollingWidget");
        self.scrollWidget = Quotient.Mailbox.ScrollingWidget.get(scrollNode);
        self.messageDetailNode = self.nodeByAttribute("class", "message-detail");
        var topControls = self.nodeByAttribute("class", "top-controls");
        var splitPane = self.nodeByAttribute("class", "dojoHtmlSplitPane");
        var splitPaneWidget = dojo.widget.byType("SplitPane")[0];

        function setSplitPaneSize() {
            var totalHeight = document.documentElement.clientHeight;
            var remainingSpace = totalHeight - Quotient.Common.Util.findPosY(splitPane);
            splitPane.style.height = remainingSpace + 'px';
            for(var i = 0; i < splitPaneWidget.children.length; i++) {
                splitPaneWidget.children[i].onResized();
            }
        }
        setSplitPaneSize();
        window.onresize = setSplitPaneSize;
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
        var data = sw._rows[offset][0];
        self.callRemote("loadMessageFromID", data["__id__"]).addCallback(
            function(stuff) { self.setMessageContent(stuff) });
    },

    function nextMessage(self) {
        var sw = self.scrollWidget;
        self._selectAndFetchRow(++sw._selectedRowOffset,
                                function() {
                                    return sw._selectedRow.nextSibling
                                });
    },

    function prevMessage(self) {
        var sw = self.scrollWidget;
        self._selectAndFetchRow(--sw._selectedRowOffset,
                                function() {
                                    return sw._selectedRow.previousSibling
                                });
    },

    function archiveThis(self) {
        self.replaceWithDialog(self.selectedRowOffset, "Archiving...");
        self.callRemote('archiveCurrentMessage').addCallback(
            function(ign) { self.twiddleMessageCount(-1) }).addCallback(
            function(data) { self.setMessageContent(data) });
    },


    function loadMessageFromID(self, id) {
        self.callRemote("loadMessageFromID", id).addCallback(
                        function(data) { self.setMessageContent(data) }
                            ).addErrback(alert);
    },

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

    function nextUnread(self) {
        self.callRemote("nextUnread").addCallback(
            function(stuff) {
                if(!stuff) { return; }
                var rowRange = stuff[0];
                var rows = stuff[1];
                var webID = stuff[2];
                var messageData = stuff[3];

                var sw = self.scrollWidget;
                sw.createRows(rowRange[0], rows);
                for(var i = 0; i < sw._rows.length; i++) {
                   if(sw._rows[i] && sw._rows[i][0]["__id__"] == webID) {
                        var rowElement = sw._rows[i][1];
                        break;
                    }
                }
                sw._selectRow(i, rowElement);
                self.setMessageContent(messageData);
                var newPos = sw._rowHeight * i;
                if(sw._scrollViewport.scrollTop < newPos) {
                    sw._scrollViewport.scrollTop = newPos;
                    sw.scrolled();
                }
            });
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
        self.messageDetailNode.style.opacity = '';
        self.messageDetailNode.style.backgroundColor = '';
        self.messageDetailNode.innerHTML = data[1];
        var iframe = document.getElementById("content-iframe");
        if(iframe) {
            Quotient.Common.Util.resizeIFrame(iframe);
        }
        if(self.messageMetadata) {
            self.highlightExtracts();
        }
        initLightbox();
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
    });
