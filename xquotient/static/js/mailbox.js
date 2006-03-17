// import Quotient
// import Quotient.Common
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
                MochiKit.DOM.replaceChildNodes(
                    self.nodeByAttribute("class", "message-body"),
                    MochiKit.DOM.PRE(null, source));
        });
    });

Quotient.Mailbox.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass();
Quotient.Mailbox.ScrollingWidget.methods(
    function __init__(self, node) {
        self.columnAliases = {"receivedWhen": "Date", "senderDisplay": "Sender"};
        Quotient.Mailbox.ScrollingWidget.upcall(self, "__init__", node);
        self._scrollViewport.style.height = '100px'
    },

    function _selectRow(self, rowOffset, row) {
        if(self._selectedRow) {
            self._selectedRow.style.backgroundColor = '#FFFFFF';
        }
        if(!row) {
            row = self._rows[rowOffset][1];
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
                self.widgetParent.fastForward(rowData["__id__"]);
                return false;
            }},
            cells);
    },

    function makeCellElement(self, colName, rowData) {
        if(colName == "receivedWhen") {
            colName = "sentWhen";
        }
        return MochiKit.DOM.DIV({"class": "scroll-cell"},
                                self.massageColumnValue(
                                     colName, self.columnTypes[colName], rowData[colName]));
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
        var value = [pad(d.getDate()), pad(d.getMonth() + 1), d.getFullYear()].join("/");
        return value + " " + to12Hour(d.getHours(), pad(d.getMinutes()));
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
        if(self._selectedRowOffset == 0) {
            self.scrolled();
        }
    },
        
   
    function cbRowsFetched(self) {
        if(self._pendingRowSelection) {
            self._pendingRowSelection();
            self._pendingRowSelection = null;
        }
    });


Quotient.Mailbox.Controller = Nevow.Athena.Widget.subclass('Quotient.Mailbox.Controller');
Quotient.Mailbox.Controller.methods(
    function __init__(self, node) {
        Quotient.Mailbox.Controller.upcall(self, "__init__", node);
        self.inboxContainer = self.firstNodeByAttribute("class", "inbox-container");
        var firstWithClass = function(cls, n) {
            if(!n) {
                n = self.inboxContainer;
            }
            return Nevow.Athena.FirstNodeByAttribute(n, "class", cls);
        }

        self.messageDetail = firstWithClass("message-detail");
        self.nextMessagePreview = firstWithClass("next-message-preview");

        var progressMeter = firstWithClass("progress-meter");
        self.progressBar  = firstWithClass("progress-bar", progressMeter);

        self.messageActions = firstWithClass("message-actions");

        self.highlightExtracts();

        var scrollNode = self.firstNodeByAttribute("athena:class", "Quotient.Mailbox.ScrollingWidget");
        self.scrollWidget = Quotient.Mailbox.ScrollingWidget.get(scrollNode);
        self._selectAndFetchRow(0, function() { return null });

        self.callRemote("getMessageCount").addCallback(
            function(count) { self.setMessageCount(count) });
    },

    function fastForward(self, toMessageID) {
        self.callRemote("fastForward", toMessageID).addCallback(
            function(messageData) {
                self.setMessageContent(messageData, true);
            });
    },

    function _chooseViewParameter(self, viewFunction, select) {
        var value = select.value;
        if (value == 'All') {
            value = null;
        }
        self.callRemote(viewFunction, value).addCallback(
            function(messageData) {
                self.setMessageCount(messageData[0]);
                self.setMessageContent(messageData[1], true);
                self.scrollWidget.setViewportHeight(messageData[0]);
                self.scrollWidget.emptyAndRefill();
            });
    },

    function chooseTag(self, select) {
        return self._chooseViewParameter('viewByTag', select);
    },

    function chooseAccount(self, select) {
        return self._chooseViewParameter('viewByAccount', select);
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

        self.scrollWidget.removeCurrentRow();

        var select = self.scrollWidget._selectedRowOffset;
        if(select == self.scrollWidget._rows.length) {
            select--;
        }

        self._selectAndFetchRow(select,
                                function() {
                                    return null;
                                });

        self.messageDetail.style.opacity = .2;
        self.callRemote.apply(self, remoteArgs).addCallback(
            function(nextMessage) {
                self.messageDetail.style.opacity = 1;
                self.setMessageContent(nextMessage, true);
                if(isProgress) {
                    self.progressBar.style.borderRight = "solid 1px #000000";
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
        if(self.remainingMessages == 0) {
            self.messageActions.style.visibility = "hidden";
            self.progressBar.style.visibility = "hidden";
        } else {
            self.progressBar.style.visibility = "";
            self.messageActions.style.visibility = "";
            self.progressBar.style.width = Math.ceil((self.remainingMessages / self.totalMessages) * 100) + "%";
        }
    },

    function archiveThis(self, n) {
        self.touch("archive", true);
    },

    function deleteThis(self, n) {
        self.touch("delete", true);
    },

    function showDeferForm(self) {
        self.deferForm = self.nodeByAttribute("class", "defer-form");
        self.deferForm.style.display = "";
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
            /* so this is a message, not a compose fragment */
            Divmod.Runtime.theRuntime.setNodeContent(
                self.nextMessagePreview, '<div xmlns="http://www.w3.org/1999/xhtml">' + data[0] + '</div>');
            self.highlightExtracts();
        }
    });
