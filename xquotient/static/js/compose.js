/*
if(tinyMCE) {
    tinyMCE.init({
        mode: "exact",
        elements: "message-body",
        theme: "simple"});
}
*/

// import Quotient.Common

if(typeof(Quotient) == "undefined") {
    Quotient = {};
}

if(typeof(Quotient.Compose) == "undefined") {
    Quotient.Compose = {};
}

Quotient.Compose.Controller = Nevow.Athena.Widget.subclass();

Quotient.Compose.Controller.method("loaded",
    function(self) {
        //self.fitMessageBodyToPage();
        self.allPeople = new Array();

        self.callRemote("getPeople").addCallback(
            function(people) {
                self.allPeople = self.allPeople.concat(people);
                self.stuffPeopleInDropdown();
            });
    });

Quotient.Compose.Controller.method("fitMessageBodyToPage", 
    function(self) {
        var e = document.getElementById("message-body");
        e.style.height = document.documentElement.clientHeight - Quotient.Common.Util.findPosY(e) - 55 + "px";
    });

Quotient.Compose.Controller.method("stuffPeopleInDropdown",
    function(self) {
        var select = document.getElementById("person-select");
        MochiKit.DOM.replaceChildNodes(select);
        select.appendChild(MochiKit.DOM.createDOM("OPTION", {"value":"--all--"}, "--all--"));

        for(i = 0; i < self.allPeople.length; i++)
            select.appendChild(
                MochiKit.DOM.createDOM("OPTION", {"value":self.allPeople[i]}, self.allPeople[i]));
    });

Quotient.Compose.Controller.method("addrAutocompleteKeyDown",
    function(self, event) {
        var TAB = 9;
        var completions = document.getElementById("address-completions");

        if(completions.style.display == "none")
            return true;

        if(event.keyCode == event.DOM_VK_ENTER || event.keyCode == TAB) {
            if(0 < completions.childNodes.length) {
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
    });

Quotient.Compose.Controller.method("dontBubbleEvent",
    function(self, event) {
        event.cancel = true;
        event.returnValue = false;
        event.preventDefault();
        return false;
    });

Quotient.Compose.Controller.method("shiftAddrCompletionHighlightDown",
    function(self) {
        var completions = document.getElementById("address-completions");
        var selectedOffset = self.selectedAddrCompletion();
        if(selectedOffset == completions.childNodes.length-1)
            return;
        var currentCompletion = completions.childNodes[selectedOffset];
        currentCompletion.className = "";
        currentCompletion.nextSibling.className = "selected-address-completion";
    });

Quotient.Compose.Controller.method("highlightFirstAddrCompletion",
    function(self) {
        var completions = document.getElementById("address-completions");
        completions.firstChild.className = "selected-address-completion";
    });

Quotient.Compose.Controller.method("shiftAddrCompletionHighlightUp",
    function(self) {
        var completions = document.getElementById("address-completions");
        var selectedOffset = self.selectedAddrCompletion();
        if(selectedOffset == 0)
            return;
        var currentCompletion = completions.childNodes[selectedOffset];
        currentCompletion.className = "";
        currentCompletion.previousSibling.className = "selected-address-completion";
    });

Quotient.Compose.Controller.method("selectedAddrCompletion",
    function(self) {
        var completions = document.getElementById("address-completions");
        for(var i = 0; i < completions.childNodes.length; i++)
            if(completions.childNodes[i].className == "selected-address-completion")
                return i;
        return null;
    });

Quotient.Compose.Controller.method("emptyAndHideAddressCompletions",
    function (self) {
        with(MochiKit.DOM) {
            var completions = getElement("address-completions");
            replaceChildNodes(completions);
            hideElement(completions);
        }
    });

Quotient.Compose.Controller.method("appendAddrCompletionToList",
    function(self, offset) {
        var input = document.getElementById("compose-to-address");
        var addrs = input.value.split(/,/);
        var lastAddr = Quotient.Common.Util.stripLeadingTrailingWS(addrs[addrs.length - 1]);
        var completions = document.getElementById("address-completions");
        var word = completions.childNodes[offset].firstChild.nodeValue;
        // truncate the value of the text box so it includes all addresses up to
        // but not including the last one
        input.value = input.value.slice(0, input.value.length - lastAddr.length);
        // then replace it with the completion
        input.value += word + ", ";
        self.emptyAndHideAddressCompletions();
    });

Quotient.Compose.Controller.method("reconstituteAddress",
    function(self, nameaddr) {
        return '"' + nameaddr[0] + '" <' + nameaddr[1] + '>';
    });

Quotient.Compose.Controller.method("completeCurrentAddr",
    function(self, addresses) {
        addresses = addresses.split(/,/);

        if(addresses.length == 0)
            return;

        var completionContainer = document.getElementById("address-completions");
        var lastAddress = Quotient.Common.Util.stripLeadingTrailingWS(addresses[addresses.length - 1]);
        MochiKit.DOM.replaceChildNodes(completionContainer);

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

        for(i = 0; i < completions.length; i++) {
            attrs = {"href":"#", "onclick":handler+";return false", "style":"display: block"}
            completionContainer.appendChild(
                MochiKit.DOM.A(attrs, self.reconstituteAddress(completions[i])));
        }

        if(0 < completions.length) {
            var input = document.getElementById("compose-to-address");
            MochiKit.DOM.setDisplayForElement("", completionContainer);
            completionContainer.style.top  = Quotient.Common.Util.findPosY(input) + input.clientHeight + "px";
            completionContainer.style.left = Quotient.Common.Util.findPosX(input) + "px";
            self.highlightFirstAddrCompletion();
        }
    });

Quotient.Compose.Controller.method("setAttachment",
    function(self, input) {
        MochiKit.DOM.hideElement(input);
        MochiKit.DOM.appendChildNodes(input.parentNode,
            MochiKit.DOM.SPAN({"style":"font-weight: bold"}, input.value + " | "),
            MochiKit.DOM.A({"href":"#",
                "onclick":self._makeHandler("removeAttachment(this)")}, "remove"),
            MochiKit.DOM.BR(),
            MochiKit.DOM.A({"href":"#",
                "onclick":self._makeHandler("addAttachment(this)")}, "Attach another file"));
    });

Quotient.Compose.Controller.method("removeAttachment",
    function(self, link) {
        var parent = link.parentNode;
        parent.removeChild(link.previousSibling);
        parent.removeChild(link.nextSibling);
        parent.removeChild(link);
    });

Quotient.Compose.Controller.method("addAttachment",
    function(self, link) {
        var parent = link.parentNode;
        parent.removeChild(link);
        parent.appendChild(MochiKit.DOM.INPUT(
            {"type": "file",
             "style": "display: block",
             "onchange": self._makeHandler("setAttachment(this)")}));
    });
