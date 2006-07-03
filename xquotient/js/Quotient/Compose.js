// import Quotient
// import Quotient.Common
// import Mantissa.LiveForm
// import Fadomatic
// import Mantissa.ScrollTable

Quotient.Compose.DraftListScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass(
                                                'Quotient.Compose.DraftListScrollingWidget');

Quotient.Compose.DraftListScrollingWidget.methods(
    function __init__(self, node) {
        self.columnAliases = {"sentWhen": "Date"};
        Quotient.Compose.DraftListScrollingWidget.upcall(self, "__init__", node);
    },

    function massageColumnValue(self, columnName, columnType, columnValue) {
        if(!columnValue) {
            if(columnName == "recipient") {
                columnValue = "No Recipient";
            }
            if(columnName == "subject") {
                columnValue = "No Subject";
            }
        }
        return Quotient.Compose.DraftListScrollingWidget.upcall(
                    self, "massageColumnValue", columnName, columnType, columnValue);

    });

Quotient.Compose.Controller = Mantissa.LiveForm.FormWidget.subclass('Quotient.Compose.Controller');
Quotient.Compose.Controller.methods(
    function __init__(self, node, inline, allPeople) {
        Quotient.Compose.Controller.upcall(self, "__init__", node);

        var cc = self.firstNodeByAttribute("name", "cc");
        if(0 < cc.value.length) {
            self.toggleCCForm(
                self.firstNodeByAttribute("class", "cc-link"));
        }

        self.fileList = self.firstNodeByAttribute("class", "file-list");
        if(0 < self.fileList.getElementsByTagName("li").length) {
            self.toggleFilesForm();
        }

        if(inline) {
            self.firstNodeByAttribute("class", "cancel-link").style.display = "";
        }

        self.inline = inline;
        self.allPeople = allPeople;

        self.draftNotification = self.nodeByAttribute("class", "draft-notification");
        self.completions = self.nodeByAttribute("class", "address-completions");

        self.attachDialog = self.nodeByAttribute("class", "attach-dialog");
        self.autoSaveInterval = 30000; /* 30 seconds */
        self.inboxURL = self.nodeByAttribute("class", "inbox-link").href;

        setTimeout(function() {
            self.saveDraft(false);
        }, self.autoSaveInterval);

        self.makeFileInputs();
    },

    function cancel(self) {
        self.widgetParent.hideInlineWidget();
    },

    function toggleFilesForm(self) {
        if(!self.filesForm) {
            self.filesForm = self.firstNodeByAttribute("class", "files-form");
        }
        if(self.filesForm.style.display == "none") {
            self.filesForm.style.display = "";
        } else {
            self.filesForm.style.display = "none";
        }
    },

    function toggleCCForm(self, node) {
        if(!self.ccForm) {
            self.ccForm = self.firstNodeByAttribute("class", "cc-form");
        }
        if(self.ccForm.style.display == "none") {
            self.ccForm.style.display = "";
            node.firstChild.nodeValue = "- Cc";
        } else {
            self.ccForm.style.display = "none";
            node.firstChild.nodeValue = "+ Cc";
        }
    },

    function toggleAttachDialog(self) {
        if(self.attachDialog.style.display == "none") {
            self.attachDialog.style.display = "";
            document.body.appendChild(
                MochiKit.DOM.DIV({"id": "attach-dialog-bg"}));
            if(self.attachDialog.style.left == "") {
                var elemSize = Divmod.Runtime.theRuntime.getElementSize(self.attachDialog);
                self.attachDialog.style.display = "none";
                var pageSize = Divmod.Runtime.theRuntime.getPageSize();
                self.attachDialog.style.left = (pageSize.w/2 - elemSize.w/2) + "px";
                self.attachDialog.style.top  = (pageSize.h/2 - elemSize.h/2) + "px"
                self.attachDialog.style.display = "";
            }
        } else {
            self.attachDialog.style.display = "none";
            document.body.removeChild(document.getElementById("attach-dialog-bg"));
        }
    },

    function saveDraft(self, userInitiated) {
        var showDialog = function(text, fade) {
            var elem = MochiKit.DOM.DIV({"class": "draft-dialog"}, text);
            MochiKit.DOM.replaceChildNodes(self.draftNotification, elem);
            if(fade) {
                new Fadomatic(elem, 2).fadeOut();
                setTimeout(function() {
                    MochiKit.DOM.replaceChildNodes(self.draftNotification);
                }, 1700);
            }
        }
        showDialog("Saving draft...");
        var e = self.nodeByAttribute("name", "draft");
        e.checked = true;
        self.submit().addCallback(
            function(ign) {
                var time = (new Date()).toTimeString();
                showDialog("Draft saved at " + time.substr(0, time.indexOf(' ')), true);
                if(!userInitiated) {
                    setTimeout(function() {
                        self.saveDraft(false)
                    }, self.autoSaveInterval);
                }
                return ign;
            });
        e.checked = false;
    },

    function submit(self) {
        var savingADraft = self.nodeByAttribute("name", "draft").checked;
        var D = Quotient.Compose.Controller.upcall(self, "submit");
        if(savingADraft) {
            return D;
        }
        return D.addCallback(function(ign) {
            if(self.inline) {
                self.cancel();
            } else {
                document.location = self.inboxURL;
            }
        });
    },

    function makeFileInputs(self) {
        var uploaded = self.nodeByAttribute("class", "uploaded-files");
        var lis = self.fileList.getElementsByTagName("li");
        var span;
        for(var i = 0; i < lis.length; i++) {
            span = lis[i].getElementsByTagName("span")[0];
            uploaded.appendChild(
                MochiKit.DOM.INPUT({"type": "text",
                                    "name": "files",
                                    "value": span.firstChild.nodeValue},
                                   lis[i].firstChild.nodeValue));
        }
    },

    function uploading(self) {
        self.nodeByAttribute("class", "upload-notification").style.visibility = "";
    },

    /**
     * Called after the iframe POST completes.  C{d} is a dictionary
     * obtained from the server, containing information about the file
     * we uploaded (currently a unique identifier and the filename)
     *
     * Using this information, we add a node representing the file to the
     * user-visible attachment list, and add the unique identifier to the
     * value of the hidden form field that indicates which files to attach
     * to the message (this gets modified if the attachment is removed by
     * the user before the message is sent, etc)
     */
    function gotFileData(self, d) {
        if(self.attachDialog.style.display != "none") {
            self.toggleAttachDialog();
        }

        self.nodeByAttribute("class", "upload-notification").style.visibility = "hidden";

        var lis = self.fileList.getElementsByTagName("li");

        if(0 == lis.length) {
            self.toggleFilesForm();
        }

        self.fileList.appendChild(MochiKit.DOM.LI(null, [d["name"],
            MochiKit.DOM.A({"style": "padding-left: 4px",
                            "href": "#",
                            "onclick": function() {
                                self.removeFile(this);
                                return false
                            }},
                            "(remove)")]));
        self.nodeByAttribute("class", "uploaded-files").appendChild(
            MochiKit.DOM.INPUT({"type": "text",
                                "name": "files",
                                "value": d["id"]}, d["name"]));
    },

    function removeFile(self, node) {
        var fname = node.previousSibling.nodeValue,
            lis = self.fileList.getElementsByTagName("li"),
            uploaded = self.firstNodeByAttribute('class', 'uploaded-files');

        self.fileList.removeChild(node.parentNode);
        if(0 == lis.length) {
            self.toggleFilesForm();
        }

        for(var i = 0; i < uploaded.childNodes.length; i++) {
            if(uploaded.childNodes[i].firstChild.nodeValue == fname) {
                uploaded.removeChild(uploaded.childNodes[i]);
                break;
            }
        }
    },

    function fitMessageBodyToPage(self) {
        var e = self.nodeByAttribute("class", "message-body");
        e.style.height = Divmod.Runtime.theRuntime.getPageHeight().h -
                         Quotient.Common.Util.findPosY(e) - 55 + "px";
    },

    function addrAutocompleteKeyDown(self, event) {
        var TAB = 9;

        if(self.completions.style.display == "none")
            return true;

        if(event.keyCode == event.DOM_VK_ENTER || event.keyCode == TAB) {
            if(0 < self.completions.childNodes.length) {
                self.appendAddrCompletionToList(self.selectedAddrCompletion());
            }
            return self.dontBubbleEvent(event);
        } else if(event.keyCode == event.DOM_VK_DOWN) {
            self.shiftAddrCompletionHighlightDown();
        } else if(event.keyCode == event.DOM_VK_UP) {
            self.shiftAddrCompletionHighlightUp();
        } else {
            self.emptyAndHideAddressCompletions();
        }
        return true;
    },

    function dontBubbleEvent(self, event) {
        event.cancel = true;
        event.returnValue = false;
        event.preventDefault();
        return false;
    },

    function shiftAddrCompletionHighlightDown(self) {
        var selectedOffset = self.selectedAddrCompletion();
        if(selectedOffset == self.completions.childNodes.length-1)
            return;
        var currentCompletion = self.completions.childNodes[selectedOffset];
        currentCompletion.className = "";
        currentCompletion.nextSibling.className = "selected-address-completion";
    },

    function highlightFirstAddrCompletion(self) {
        self.completions.firstChild.className = "selected-address-completion";
    },

    function shiftAddrCompletionHighlightUp(self) {
        var selectedOffset = self.selectedAddrCompletion();
        if(selectedOffset == 0)
            return;
        var currentCompletion = self.completions.childNodes[selectedOffset];
        currentCompletion.className = "";
        currentCompletion.previousSibling.className = "selected-address-completion";
    },

    function selectedAddrCompletion(self) {
        for(var i = 0; i < self.completions.childNodes.length; i++)
            if(self.completions.childNodes[i].className == "selected-address-completion")
                return i;
        return null;
    },

    function emptyAndHideAddressCompletions(self) {
        with(MochiKit.DOM) {
            replaceChildNodes(self.completions);
            hideElement(self.completions);
        }
    },

    function appendAddrCompletionToList(self, offset) {
        var input = self.nodeByAttribute("class", "compose-to-address");
        var addrs = input.value.split(/,/);
        var lastAddr = Quotient.Common.Util.stripLeadingTrailingWS(addrs[addrs.length - 1]);
        var word = self.completions.childNodes[offset].firstChild.nodeValue;
        // truncate the value of the text box so it includes all addresses up to
        // but not including the last one
        input.value = input.value.slice(0, input.value.length - lastAddr.length);
        // then replace it with the completion
        input.value += word + ", ";
        self.emptyAndHideAddressCompletions();
    },

    /**
     * For a pair C{nameaddr} containing [displayName, emailAddress], return something
     * of the form '"displayName" <emailAddress>'.  If displayName is the empty
     * string, return '<emailAddress>'.
     */
    function reconstituteAddress(self, nameaddr) {
        var addr;
        if(0 < nameaddr[0].length) {
            addr = '"' + nameaddr[0] + '" ';
        } else {
            addr = "";
        }
        return addr + '<' + nameaddr[1] + '>';
    },

    function completeCurrentAddr(self, addresses) {
        addresses = addresses.split(/,/);

        if(addresses.length == 0)
            return;

        var lastAddress = Quotient.Common.Util.stripLeadingTrailingWS(addresses[addresses.length - 1]);
        MochiKit.DOM.replaceChildNodes(self.completions);

        if(lastAddress.length == 0)
            return;

        /**
         * Given an email address C{addr}, and a pair containing [displayName,
         * emailAddress], return a boolean indicating whether emailAddress or
         * any of the words in displayName is a prefix of C{addr}
         */
        function nameOrAddressStartswith(addr, nameaddr) {
            var strings = nameaddr[0].split(/\s+/).concat(nameaddr);
            for(var i = 0; i < strings.length; i++) {
                if(Quotient.Common.Util.startswith(addr, strings[i])) {
                    return true;
                }
            }
            return false;
        }

        var completions = MochiKit.Base.filter(
            MochiKit.Base.partial(nameOrAddressStartswith, lastAddress),
            self.allPeople);


        var attrs = null;

        for(i = 0; i < completions.length; i++) {
            attrs = {"href": "#",
                     "onclick": function() {
                        self.appendAddrCompletionToList(this.firstChild.nodeValue);
                        return false;
                     },
                     "style": "display: block"};
            self.completions.appendChild(
                MochiKit.DOM.A(attrs, self.reconstituteAddress(completions[i])));
        }

        if(0 < completions.length) {
            var input = self.nodeByAttribute("class", "compose-to-address");
            MochiKit.DOM.setDisplayForElement("", self.completions);
            self.completions.style.top  = Quotient.Common.Util.findPosY(input) +
                                          Divmod.Runtime.theRuntime.getElementSize(input).h + "px";
            self.completions.style.left = Quotient.Common.Util.findPosX(input) + "px";
            self.highlightFirstAddrCompletion();
        }
        return completions;
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

    function _makeHandler(self, f) {
        return "Quotient.Compose.Controller.get(this)." + f + "; return false";
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
            {"type": "file",
             "style": "display: block",
             "onchange": self._makeHandler("setAttachment(this)")}));
    },

    function submitSuccess(self, result) {},

    function submitFailure(self, err) {
        alert(err);
        alert('CRAP');
    });
