/* this javascript file should be included by all quotient pages */

var TDB_Y_POS = null;
var TDB_X_POS = null;

/* 
   these two functions are optimizations, so we don't have to
   traverse the DOM all the way up to the document element in
   order to figure out the height of some element that is inside
   the tdb 
*/

function quotient_findRelPosX(e) {
    var x = TDB_X_POS;
    while(e.id != "tdb-container") {
        x += e.offsetLeft;
        e = e.offsetParent;
    }
    return x;
}

function quotient_findRelPosY(e) {
    var y = TDB_Y_POS;
    while(e.id != "tdb-container") {
        y += e.offsetTop;
        e = e.offsetParent;
    }
    return y;
}

function quotient_stripLeadingTrailingWS(s) {
    return s.replace(/^\s+/, "").replace(/\s+$/, "");
}

function quotient_startswith(needle, haystack) {
    return haystack.toLowerCase().slice(0, needle.length) == needle.toLowerCase();
}

function quotient_normalizeTag(tag) {
    return quotient_stripLeadingTrailingWS(tag).replace(/\s{2,}/, " ").toLowerCase();
}

function quotient_exposeActions(event) {
/*
    if(!TDB_X_POS) {
        var tdbc = MochiKit.DOM.getElement("tdb-container");
        TDB_X_POS = quotient_findPosX(tdbc);
        TDB_Y_POS = quotient_findPosY(tdbc);
    }
*/
    var actions = Nevow.Athena.NodeByAttribute(
        event.originalTarget.parentNode, "class", "person-actions"
    );

    var xpos = quotient_findPosX(event.originalTarget);
    var ypos = quotient_findPosY(event.originalTarget);

    actions.style.top  = ypos + "px";
    actions.style.left = xpos + "px";
    MochiKit.DOM.showElement(actions);

    var body = document.getElementsByTagName("body")[0];

    actions.onclick = function() {
        // stop this event from reaching the <body> onclick handler
        if(event.originalTarget.tagName == "A") {
            body.onclick = null;
            return true;
        }
        event.stopPropagation();
        return false;
    }

    function addClickHandler() {
        body.onclick = function() {
            body.onclick = null;
            actions.style.display = "none";
        };
    }

    setTimeout(addClickHandler, 100);
}

function resizeIFrame(frame) {
  // Code is from http://www.ozoneasylum.com/9671&latestPost=true
  try {
    innerDoc = (frame.contentDocument) ? frame.contentDocument : frame.contentWindow.document;
    objToResize = (frame.style) ? frame.style : frame;
    objToResize.height = innerDoc.body.scrollHeight + 20 + 'px';
    objToResize.width = innerDoc.body.scrollWidth + 5 + 'px';
  }
  catch (e) {}
}

function quotient_findPosY(obj) {
    var curtop = 0;
    if (obj.offsetParent)
    {
        while (obj.offsetParent)
        {
            curtop += obj.offsetTop
            obj = obj.offsetParent;
        }
    }
    else if (obj.y)
        curtop += obj.y;
    return curtop;
}

function quotient_findPosX(obj) {
    var curleft = 0;
    if (obj.offsetParent)
    {
        while (obj.offsetParent)
        {
            curleft += obj.offsetLeft
            obj = obj.offsetParent;
        }
    }
    else if (obj.x)
        curleft += obj.x;
    return curleft;
}



if(typeof(Quotient) == "undefined") {
    Quotient = {};
}

if(typeof(Quotient.Common) == "undefined") {
    Quotient.Common = {};
}

Quotient.Common.SenderPerson = Nevow.Athena.Widget.subclass();

Quotient.Common.SenderPerson.prototype.replaceWithPersonHTML = function(personHTML, node) {
    /* we have to find other person-identifier elements with the same person identifier
       as ours and replace them with the person html we got in addPerson() (so that
       they dont prompt the user to add a person they just added via a different link)
       it is unfortunate we have to do this, but it is the price we pay for no page loads */

    var personIdentifiers = Nevow.Athena.NodesByAttribute(
                                document.documentElement, 'class', 'person-identifier');
    var identifier = Nevow.Athena.NodeByAttribute(
                        node, 'class', 'person-identifier').firstChild.nodeValue;

    var e = null;
    for(var i = 0; i < personIdentifiers.length; i++) {
        e = personIdentifiers[i];
        if(e.firstChild.nodeValue == identifier) {
            e.parentNode.innerHTML = personHTML;
        }
    }
}

Quotient.Common.SenderPerson.prototype.addEventListener = function(type, f, useCapture) {
    f = MochiKit.Base.bind(f, this);
    this.addPersonFragment.addEventListener(type, f, useCapture);
    const outerThis = this;
    return function() {
        outerThis.addPersonFragment.removeEventListener(type, f, useCapture);
    }
}

Quotient.Common.SenderPerson.prototype.showAddPerson = function(node, event) {
    if(this.working == true) {
        return;
    }

    this.working = true;
    this.node = node;
    this.popdownTimeout = null;

    var name = this.nodeByAttribute('class', 'person-name').firstChild.nodeValue;
    var first = '';
    var last = ''
    if(name.match(/\s+/)) {
        var parts = name.split(/\s+/, 2);
        first = parts[0];
        last  = parts[1];
    } else {
        first = name;
    }
    var email = this.nodeByAttribute('class', 'person-identifier').firstChild.nodeValue;

    this.addPersonFragment = MochiKit.DOM.getElement("add-person-fragment");
    var outerThis = this;

    function setValueOfFormElement(name, value) {
        var e = Nevow.Athena.NodeByAttribute(outerThis.addPersonFragment, 'name', name);
        e.value = value;
    }

    setValueOfFormElement('firstname', first);
    setValueOfFormElement('nickname', first);
    setValueOfFormElement('lastname', last);
    setValueOfFormElement('email', email);

    this.addPersonFragment.style.top = event.pageY + 'px';
    this.addPersonFragment.style.left = event.pageX + 25 + 'px';

    var undoMouseover = this.addEventListener("mouseover",
                                function() { this.engagedPopup() }, true);
    var undoMouseout  = this.addEventListener("mouseout",
                                function() { this.hideAddPersonFragment(false) }, true);

    this.removeEventListeners = function() {
        undoMouseover();
        undoMouseout();
    }

    MochiKit.DOM.showElement(this.addPersonFragment);
}

Quotient.Common.SenderPerson.prototype.engagedPopup = function() {
    if(this.popdownTimeout != null) {
        clearTimeout(this.popdownTimeout);
    }
}

Quotient.Common.SenderPerson.prototype.hideAddPersonFragment = function(force) {
    var outerThis = this;

    function reallyHide() {
        MochiKit.DOM.hideElement(outerThis.addPersonFragment);
        outerThis.removeEventListeners();
        outerThis.working = false;
    }

    if(force) {
        reallyHide();
    } else {
        this.popdownTimeout = setTimeout(reallyHide, 1000);
    }
}
