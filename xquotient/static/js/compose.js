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

Quotient.Compose.Controller.prototype.loaded = function() {
    //this.fitMessageBodyToPage();
    this.allPeople = new Array();

    var outerthis = this;

    this.callRemote("getPeople").addCallback(
        function(people) {
            outerthis.allPeople = outerthis.allPeople.concat(people);
            outerthis.stuffPeopleInDropdown();
        });
}

Quotient.Compose.Controller.prototype.fitMessageBodyToPage = function() {
    var e = MochiKit.DOM.getElement("message-body");
    e.style.height = document.documentElement.clientHeight - quotient_findPosY(e) - 55 + "px";
}

Quotient.Compose.Controller.prototype.stuffPeopleInDropdown = function() {
    var select = MochiKit.DOM.getElement("person-select");
    MochiKit.DOM.replaceChildNodes(select);
    select.appendChild(MochiKit.DOM.createDOM("OPTION", {"value":"--all--"}, "--all--"));

    for(i = 0; i < this.allPeople.length; i++)
        select.appendChild(
            MochiKit.DOM.createDOM("OPTION", {"value":this.allPeople[i]}, this.allPeople[i]));
}

Quotient.Compose.Controller.prototype.addrAutocompleteKeyDown = function(event) {
    var TAB = 9;
    var completions = MochiKit.DOM.getElement("address-completions");

    if(completions.style.display == "none")
        return true;

    if(event.keyCode == event.DOM_VK_ENTER || event.keyCode == TAB) {
        if(0 < completions.childNodes.length) {
            this.appendAddrCompletionToList(this.selectedAddrCompletion());
        }
        return this.dontBubbleEvent(event);
    } else if(event.keyCode == event.DOM_VK_DOWN) {
        this.shiftAddrCompletionHighlightDown();
    } else if(event.keyCode == event.DOM_VK_UP) {
        this.shiftAddrCompletionHighlightUp();
    } else {
        this.emptyAndHideAddressCompletions();
    }
    return true;
}

Quotient.Compose.Controller.prototype.dontBubbleEvent = function(event) {
    event.cancel = true;
    event.returnValue = false;
    event.preventDefault();
    return false;
}

Quotient.Compose.Controller.prototype.shiftAddrCompletionHighlightDown = function() {
    var completions = MochiKit.DOM.getElement("address-completions");
    var selectedOffset = this.selectedAddrCompletion();
    if(selectedOffset == completions.childNodes.length-1)
        return;
    var currentCompletion = completions.childNodes[selectedOffset];
    currentCompletion.className = "";
    currentCompletion.nextSibling.className = "selected-address-completion";
}

Quotient.Compose.Controller.prototype.highlightFirstAddrCompletion = function() {
    var completions = MochiKit.DOM.getElement("address-completions");
    completions.firstChild.className = "selected-address-completion";
}

Quotient.Compose.Controller.prototype.shiftAddrCompletionHighlightUp = function() {
    var completions = MochiKit.DOM.getElement("address-completions");
    var selectedOffset = this.selectedAddrCompletion();
    if(selectedOffset == 0)
        return;
    var currentCompletion = completions.childNodes[selectedOffset];
    currentCompletion.className = "";
    currentCompletion.previousSibling.className = "selected-address-completion";
}

Quotient.Compose.Controller.prototype.selectedAddrCompletion = function() {
    var completions = MochiKit.DOM.getElement("address-completions");
    for(var i = 0; i < completions.childNodes.length; i++)
        if(completions.childNodes[i].className == "selected-address-completion")
            return i;
    return null;
}

Quotient.Compose.Controller.prototype.emptyAndHideAddressCompletions = function () {
    with(MochiKit.DOM) {
        var completions = getElement("address-completions");
        replaceChildNodes(completions);
        hideElement(completions);
    }
}

Quotient.Compose.Controller.prototype.appendAddrCompletionToList = function(offset) {
    var input = MochiKit.DOM.getElement("compose-to-address");
    var addrs = input.value.split(/,/);
    var lastAddr = quotient_stripLeadingTrailingWS(addrs[addrs.length - 1]);
    var completions = MochiKit.DOM.getElement("address-completions");
    var word = completions.childNodes[offset].firstChild.nodeValue;
    // truncate the value of the text box so it includes all addresses up to
    // but not including the last one
    input.value = input.value.slice(0, input.value.length - lastAddr.length);
    // then replace it with the completion
    input.value += word + ", ";
    this.emptyAndHideAddressCompletions();
}

Quotient.Compose.Controller.prototype.reconstituteAddress = function(nameaddr) {
    return '"' + nameaddr[0] + '" <' + nameaddr[1] + '>';
}

Quotient.Compose.Controller.prototype.completeCurrentAddr = function(addresses) {
    addresses = addresses.split(/,/);

    if(addresses.length == 0)
        return;

    var completionContainer = MochiKit.DOM.getElement("address-completions");
    var lastAddress = quotient_stripLeadingTrailingWS(addresses[addresses.length - 1]);
    MochiKit.DOM.replaceChildNodes(completionContainer);

    if(lastAddress.length == 0)
        return;

    function nameOrAddressStartswith(addr, nameaddr) {
        return quotient_startswith(addr, nameaddr[0])
                    || quotient_startswith(addr, nameaddr[1]);
    }

    var completions = MochiKit.Base.filter(
        MochiKit.Base.partial(nameOrAddressStartswith, lastAddress),
        this.allPeople);

    var handler = "Quotient.Compose.Controller.get(this).appendAddrCompletionToList(this.firstChild.nodeValue)";
    var attrs = null;

    for(i = 0; i < completions.length; i++) {
        attrs = {"href":"#", "onclick":handler+";return false", "style":"display: block"}
        completionContainer.appendChild(
            MochiKit.DOM.A(attrs, this.reconstituteAddress(completions[i])));
    }

    if(0 < completions.length) {
        var input = MochiKit.DOM.getElement("compose-to-address");
        MochiKit.DOM.setDisplayForElement("", completionContainer);
        completionContainer.style.top  = quotient_findPosY(input) + input.clientHeight + "px";
        completionContainer.style.left = quotient_findPosX(input) + "px";
        this.highlightFirstAddrCompletion();
    }
}

Quotient.Compose.Controller.prototype.setAttachment = function(input) {
    MochiKit.DOM.hideElement(input);
    MochiKit.DOM.appendChildNodes(input.parentNode,
        MochiKit.DOM.SPAN({"style":"font-weight: bold"}, input.value + " | "),
        MochiKit.DOM.A({"href":"#",
            "onclick":this._makeHandler("removeAttachment(this)")}, "remove"),
        MochiKit.DOM.BR(),
        MochiKit.DOM.A({"href":"#",
            "onclick":this._makeHandler("addAttachment(this)")}, "Attach another file"));
}

Quotient.Compose.Controller.prototype.removeAttachment = function(link) {
    var parent = link.parentNode;
    parent.removeChild(link.previousSibling);
    parent.removeChild(link.nextSibling);
    parent.removeChild(link);
}

Quotient.Compose.Controller.prototype.addAttachment = function(link) {
    var parent = link.parentNode;
    parent.removeChild(link);
    parent.appendChild(MochiKit.DOM.INPUT(
        {"type":"file", "style":"display: block",
         "onchange":this._makeHandler("setAttachment(this)")}));
}
