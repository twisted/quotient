/*
if(tinyMCE) {
    tinyMCE.init({
        mode: "exact",
        elements: "message-body",
        theme: "simple"});
}
*/

// import Quotient
// import Quotient.Common
// import Mantissa.LiveForm

if(typeof(Quotient.Compose) == "undefined") {
    Quotient.Compose = {};
}

Quotient.Compose.Controller = Mantissa.LiveForm.FormWidget.subclass('Quotient.Compose.Controller');
Quotient.Compose.Controller.methods(
    function loaded(self) {
        //self.fitMessageBodyToPage();
        self.allPeople = new Array();
    
        self.completions = self.nodeByAttribute("class", "address-completions");
        self.callRemote("getPeople").addCallback(
            function(people) {
                self.allPeople = self.allPeople.concat(people);
                self.stuffPeopleInDropdown();
            });
    },

    function uploadedFile(self, fname) {
        function relpath(s) {
            var c = (-1 < s.lastIndexOf('/')) ? '/' : '\\';
            return s.substring(s.lastIndexOf(c)+1, s.length);
        }
        var flist = self.nodeByAttribute('class', 'file-list');
        flist.appendChild(MochiKit.DOM.LI(null, [fname,
            MochiKit.DOM.A({"style": "padding-left: 4px",
                            "href": "#",
                            "onclick": function() {
                                self.removeFile(this);
                                return false
                            }},
                            "remove")]));
        self.nodeByAttribute('class', 'uploaded-files').appendChild(
            MochiKit.DOM.INPUT({"type": "text",
                                "name": "files",
                                "value": relpath(fname)}, fname));
    },

    function removeFile(self, node) {
        var fname = node.previousSibling.nodeValue;
        node.parentNode.parentNode.removeChild(node.parentNode);
        var uploaded = self.nodeByAttribute('class', 'uploaded-files');
        for(var i = 0; i < uploaded.childNodes.length; i++) {
            if(uploaded.childNodes[i].firstChild.nodeValue == fname) {
                uploaded.removeChild(uploaded.childNodes[i]);
                break;
            }
        }
    },

    function toggleMoreOptions(self, node) {
        var opts = Nevow.Athena.NodeByAttribute(
                            node.parentNode.parentNode, "class", "options-container");
        opts.style.display = (opts.style.display == "none") ? "" : "none";
    },

    function fitMessageBodyToPage(self) {
        var e = self.nodeByAttribute("class", "message-body");
        e.style.height = document.documentElement.clientHeight - Quotient.Common.Util.findPosY(e) - 55 + "px";
    },

    function stuffPeopleInDropdown(self) {
        var select = self.nodeByAttribute("class", "person-select");
        MochiKit.DOM.replaceChildNodes(select);
        select.appendChild(MochiKit.DOM.createDOM("OPTION", {"value":"--all--"}, "--all--"));

        for(i = 0; i < self.allPeople.length; i++)
            select.appendChild(
                MochiKit.DOM.createDOM("OPTION", {"value":self.allPeople[i]}, self.allPeople[i]));
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
        var input = self.nodeByAttribute("compose-to-address");
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

    function reconstituteAddress(self, nameaddr) {
        return '"' + nameaddr[0] + '" <' + nameaddr[1] + '>';
    },

    function completeCurrentAddr(self, addresses) {
        addresses = addresses.split(/,/);

        if(addresses.length == 0)
            return;

        var lastAddress = Quotient.Common.Util.stripLeadingTrailingWS(addresses[addresses.length - 1]);
        MochiKit.DOM.replaceChildNodes(self.completions);

        if(lastAddress.length == 0)
            return;

        function nameOrAddressStartswith(addr, nameaddr) {
            return Quotient.Common.Util.startswith(addr, nameaddr[0])
                        || Quotient.Common.Util.startswith(addr, nameaddr[1]);
        }

        var completions = MochiKit.Base.filter(
            MochiKit.Base.partial(nameOrAddressStartswith, lastAddress),
            self.allPeople);

        var handler = "Quotient.Compose.Controller.get(this)";
        handler += ".appendAddrCompletionToList(this.firstChild.nodeValue)";

        var attrs = null;

        for(i = 0; i < self.completions.length; i++) {
            attrs = {"href":"#", "onclick":handler+";return false", "style":"display: block"}
            self.completions.appendChild(
                MochiKit.DOM.A(attrs, self.reconstituteAddress(self.completions[i])));
        }

        if(0 < self.completions.length) {
            var input = self.nodeByAttribute("class", "compose-to-address");
            MochiKit.DOM.setDisplayForElement("", self.completions);
            self.completions.style.top  = Quotient.Common.Util.findPosY(input) + input.clientHeight + "px";
            self.completions.style.left = Quotient.Common.Util.findPosX(input) + "px";
            self.highlightFirstAddrCompletion();
        }
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

    function submitSuccess(self, result) {
        alert('GREAT');
    },

    function submitFailure(self, err) {
        alert('CRAP');
    });
