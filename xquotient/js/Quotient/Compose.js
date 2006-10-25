// import Quotient
// import Quotient.Common
// import Mantissa.LiveForm
// import Fadomatic
// import Mantissa.ScrollTable

Quotient.Compose.AddAddressFormWidget = Mantissa.LiveForm.FormWidget.subclass('Quotient.Compose.AddAddressFormWidget');
/**
 * Trivial Mantissa.LiveForm.FormWidget subclass which reloads the closest
 * sibling FromAddressScrollTable after we have successfully submitted
 */
Quotient.Compose.AddAddressFormWidget.methods(
    function submitSuccess(self, result) {
        /* get our sibling FromAddressScrollTable */
        var sf = Nevow.Athena.FirstNodeByAttribute(
                    self.widgetParent.node,
                    "athena:class",
                    "Quotient.Compose.FromAddressScrollTable");
        Nevow.Athena.Widget.get(sf).emptyAndRefill();
        return Quotient.Compose.AddAddressFormWidget.upcall(
                    self, "submitSuccess", result);
    });

Quotient.Compose.DeleteFromAddressAction = Mantissa.ScrollTable.Action.subclass("Quotient.Compose.DeleteFromAddressAction");
/**
 * Action which deletes from addresses, and prevents the system address from
 * getting deleted
 */
Quotient.Compose.DeleteFromAddressAction.methods(
    function __init__(self, systemAddrWebID) {
        Quotient.Compose.DeleteFromAddressAction.upcall(
            self, "__init__", "delete", "Delete", null,
            "/Mantissa/images/delete.png");
        self.systemAddrWebID = systemAddrWebID;
    },

    function handleSuccess(self, scrollingWidget, row, result) {
        return scrollingWidget.emptyAndRefill();
    },

    function enableForRow(self, row) {
        return !(row._default || row.__id__ == self.systemAddrWebID);
    });

Quotient.Compose.SetDefaultFromAddressAction = Mantissa.ScrollTable.Action.subclass("Quotient.Compose.SetDefaultFromAddressAction");
/**
 * Action which sets a from address as the default
 */
Quotient.Compose.SetDefaultFromAddressAction.methods(
    function __init__(self) {
        Quotient.Compose.SetDefaultFromAddressAction.upcall(
            self, "__init__", "setDefaultAddress", "Set Default");
    },

    function handleSuccess(self, scrollingWidget, row, result) {
        return scrollingWidget.emptyAndRefill();
    },

    function enableForRow(self, row) {
        return !row._default;
    });

Quotient.Compose.FromAddressScrollTable = Mantissa.ScrollTable.ScrollingWidget.subclass('Quotient.Compose.FromAddressScrollTable');
/**
 * Mantissa.ScrollTable.ScrollingWidget subclass for displaying FromAddress
 * items
 */
Quotient.Compose.FromAddressScrollTable.methods(
    function __init__(self, node, systemAddrWebID) {
        Quotient.Compose.FromAddressScrollTable.upcall(self, "__init__", node, 5);
        self.columnAliases = {smtpHost: "SMTP Host",
                              smtpPort: "SMTP Port",
                              smtpUsername: "SMTP Username",
                              _address: "Address",
                              _default: "Default"};
        self.actions = [Quotient.Compose.SetDefaultFromAddressAction(),
                        Quotient.Compose.DeleteFromAddressAction(
                            systemAddrWebID)];
        self.systemAddrWebID = systemAddrWebID;
    },

    /**
     * Override default implementation to provide fallback column values -
     * "None" instead of the empty string.  Also mark the default row
     */
    function makeCellElement(self, colName, rowData) {
        if(rowData[colName] === null) {
            rowData[colName] = "None";
        }
        return Quotient.Compose.FromAddressScrollTable.upcall(
                    self, "makeCellElement", colName, rowData);
    });


Quotient.Compose.FileUploadController = Divmod.Class.subclass('Quotient.Compose.FileUploadController');

/**
 * I am the controller for the file upload form, which gets loaded
 * in a iframe inside the compose page
 */
Quotient.Compose.FileUploadController.methods(
    /**
     * @param iframeDocument: "document" in the namespace of the file upload iframe
     * @param form: the file upload form element
     */
    function __init__(self, iframeDocument, form) {
        self.form = form;
        self.compose = Quotient.Compose.Controller.get(
                        Nevow.Athena.NodeByAttribute(
                               document.documentElement,
                               "athena:class",
                               "Quotient.Compose.Controller"));
        self.iframeDocument = iframeDocument;
    },

    /**
     * Tell our parent - the compose widget - that we're busy uploading a file
     */
    function notifyParent(self) {
        self.compose.uploading();
        self.iframeDocument.body.style.opacity = .1;
        self.form.onsubmit = function() {
            return false;
        }
    },

    /**
     * Called when our document loads.  Checks whether the document contains
     * information about a completed upload, e.g. if the page load is the
     * result of a form POST.
     */
    function checkForFileData(self) {
        var fileData = self.iframeDocument.getElementById("file-data");
        if(fileData.childNodes.length) {
            self.compose.gotFileData(
                eval("(" + fileData.firstChild.nodeValue + ")"));
        }
    },

    /**
     * Called when the value of our <input type="file"> changes value.
     * Enables the upload button.
     */
    function fileInputChanged(self) {
        self.form.elements.upload.disabled = false;
    });

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

        var mbody = self.firstNodeByAttribute("class", "message-body");
        /* use a separate js class and/or template if this grows any more */
        if(inline) {
            self.firstNodeByAttribute("class", "cancel-link").style.display = "";
            self.firstNodeByAttribute("class", "compose-table").style.width = "100%";
            self.node.style.borderTop = "";
        }

        self.inline = inline;
        self.allPeople = allPeople;

        self.draftNotification = self.nodeByAttribute("class", "draft-notification");
        self.completions = self.nodeByAttribute("class", "address-completions");

        self.attachDialog = self.nodeByAttribute("class", "attach-dialog");
        self.autoSaveInterval = 30000; /* 30 seconds */
        self.inboxURL = self.nodeByAttribute("class", "inbox-link").href;

        self.startSavingDrafts();

        self.makeFileInputs();

        self.completionDeferred = Divmod.Defer.Deferred();
    },

    /**
     * Arrange for the state of the message being composed to be saved as a
     * draft every C{self.autoSaveInterval} milliseconds.
     */
    function startSavingDrafts(self) {
        self._savingDrafts = true;

        var saveDraftLoop = function saveDraftLoop() {
            self._draftCall = null;
            if (self._savingDrafts) {
                var saved = self.saveDraft(false);
                saved.addCallback(
                    function(ignored) {
                        self._draftCall = setTimeout(saveDraftLoop, self.autoSaveInterval);
                    });
            }
        };

        /*
         * XXX We need a scheduling API
         */
        self._draftCall = setTimeout(saveDraftLoop, self.autoSaveInterval);
    },

    /**
     * Stop periodically saving drafts.
     */
    function stopSavingDrafts(self) {
        self._savingDrafts = false;
        /*
         * XXX We need a scheduling API
         */
        if (self._draftCall != null) {
            clearTimeout(self._draftCall);
            self._draftCall = null;
        }
    },

    function cancel(self) {
        self.stopSavingDrafts();
        self.node.parentNode.removeChild(self.node);
        self.completionDeferred.callback(null);
        /*
         * XXX Remove this from Athena's widget map, too.
         */
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

            var pageSize = Divmod.Runtime.theRuntime.getPageSize();
            var bg = MochiKit.DOM.DIV({"id": "attach-dialog-bg"});
            bg.style.height = pageSize.h + "px";
            bg.style.width = pageSize.w + "px";
            self.node.parentNode.appendChild(bg);

            if(self.attachDialog.style.left == "") {
                var elemSize = Divmod.Runtime.theRuntime.getElementSize(self.attachDialog);
                self.attachDialog.style.display = "none";
                self.attachDialog.style.left = (pageSize.w/2 - elemSize.w/2) + "px";
                self.attachDialog.style.top  = (pageSize.h/2 - elemSize.h/2) + "px"
                self.attachDialog.style.display = "";
            }
        } else {
            self.attachDialog.style.display = "none";
            self.node.parentNode.removeChild(document.getElementById("attach-dialog-bg"));
        }
    },

    /**
     * Send the current message state to the server to be saved as a draft.
     * Announce when this begins and ends graphically.
     */
    function saveDraft(self, userInitiated) {
        var showDialog = function(text, fade) {
            var elem = MochiKit.DOM.DIV({"class": "draft-dialog"}, text);
            MochiKit.DOM.replaceChildNodes(self.draftNotification, elem);
            if(fade) {
                new Fadomatic(elem, 2).fadeOut();
            }
        }
        showDialog("Saving draft...");
        var e = self.nodeByAttribute("name", "draft");
        e.checked = true;
        var result = self.submit().addCallback(
            function(shouldLoop) {
                var time = (new Date()).toTimeString();
                showDialog("Draft saved at " + time.substr(0, time.indexOf(' ')), true);
            });
        e.checked = false;
        return result;
    },

    function submit(self) {
        if (self._submitting) {
            throw new Error("Concurrent submission rejected.");
        }
        self._submitting = true;

        self.savingADraft = self.nodeByAttribute("name", "draft").checked;
        var D = Quotient.Compose.Controller.upcall(self, "submit");
        D.addCallback(
            function(passthrough) {
                self._submitting = false;
                return passthrough;
            });
        if (!self.savingADraft) {
            D.addCallback(function(ign) {
                    if (self.inline) {
                        self.cancel();
                    }
                    return false;
                });
        }
        return D;
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

    /**
     * Expand compose widget to take up all the space inside C{node}.
     * Do this by making the message body textarea taller
     */
    function fitInsideNode(self, node) {
        var e = self.nodeByAttribute("class", "message-body");

        e.style.height = (Divmod.Runtime.theRuntime.getElementSize(node).h -
                          (Quotient.Common.Util.findPosY(e) -
                           Quotient.Common.Util.findPosY(self.node)) -
                          1)+ "px";
    },

    function addrAutocompleteKeyDown(self, node, event) {
        var TAB = 9, ENTER = 13, UP = 38, DOWN = 40;

        if(event.keyCode < 32 ||
            (event.keyCode >= 33 && event.keyCode <= 46) ||
            (event.keyCode >= 112 && event.keyCode <= 123)) {

            if(self.completions.style.display == "none") {
                return true;
            }
            if(event.keyCode == ENTER || event.keyCode == TAB) {
                if(0 < self.completions.childNodes.length) {
                    self.appendAddrCompletionToList(self.selectedAddrCompletion());
                }
                return false;
            } else if(event.keyCode == DOWN) {
                self.shiftAddrCompletionHighlightDown();
            } else if(event.keyCode == UP) {
                self.shiftAddrCompletionHighlightUp();
            } else {
                self.emptyAndHideAddressCompletions();
            }
        } else {
            setTimeout(
                function() {
                    self.completeCurrentAddr(node.value);
                }, 0);
        }
        return true;
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

    function showProgressMessage(self) {
        if(!self.savingADraft) {
            return Quotient.Compose.Controller.upcall(self, "showProgressMessage");
        }
    },

    function submitSuccess(self, result) {
        if(!self.savingADraft) {
            return Quotient.Compose.Controller.upcall(self, "submitSuccess", result);
        }
    }

    );
