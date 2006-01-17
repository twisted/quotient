/* this javascript file should be included by all quotient pages */

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

Quotient.Common.AddPerson = Nevow.Athena.Widget.subclass();

Quotient.Common.AddPerson.method('replaceAddPersonHTMLWithPersonHTML',
    function(self, identifier) {
        var D = self.callRemote('getPersonHTML');
        D.addCallback(function(HTML) {
            var personIdentifiers = Nevow.Athena.NodesByAttribute(
                                      document.documentElement, 'class', 'person-identifier');
            var e = null;
            for(var i = 0; i < personIdentifiers.length; i++) {
                e = personIdentifiers[i];
                if(e.firstChild.nodeValue == identifier) {
                    e.parentNode.innerHTML = HTML;
                }
            }
        });
    });

Quotient.Common.SenderPerson = Nevow.Athena.Widget.subclass();

Quotient.Common.SenderPerson.method('addEventListener',
    function(self, type, f, useCapture) {
        self.addPersonFragment.addEventListener(type, f, useCapture);
    });

Quotient.Common.SenderPerson.method('showAddPerson',
    function(self, node, event) {
        if(self.working == true) {
            return;
        }

        self.working = true;
        self.node = node;
        self.popdownTimeout = null;

        var name = self.nodeByAttribute('class', 'person-name').firstChild.nodeValue;
        var first = '';
        var last = '';

        if(name.match(/\s+/)) {
            var parts = name.split(/\s+/, 2);
            first = parts[0];
            last  = parts[1];
        } else {
            first = name;
        }

        self.email = self.nodeByAttribute('class', 'person-identifier').firstChild.nodeValue;

        self.addPersonFragment = MochiKit.DOM.getElement("add-person-fragment");

        function setValueOfFormElement(name, value) {
            var e = Nevow.Athena.NodeByAttribute(self.addPersonFragment, 'name', name);
            e.value = value;
        }

        setValueOfFormElement('firstname', first);
        setValueOfFormElement('nickname', first);
        setValueOfFormElement('lastname', last);
        setValueOfFormElement('email', self.email);

        self.addPersonFragment.style.top = event.pageY + 'px';
        self.addPersonFragment.style.left = event.pageX + 25 + 'px';

        self.mouseoverFunction = function() { self.engagedPopup() };
        self.mouseoutFunction  = function() { self.disengagedPopup() };

        self.addEventListener("mouseover", self.mouseoverFunction, true);
        self.addEventListener("mouseout", self.mouseoutFunction, true);

        self.form = self.addPersonFragment.getElementsByTagName("form")[0];
        self.submitFunction = function() { self.submitForm() };

        self.form.addEventListener("submit", self.submitFunction, true);

        MochiKit.DOM.showElement(self.addPersonFragment);
    });

Quotient.Common.SenderPerson.method('submitForm',
    function(self) {
        var node = Nevow.Athena.NodeByAttribute(self.addPersonFragment, "class", "add-person");
        Quotient.Common.AddPerson.get(node).replaceAddPersonHTMLWithPersonHTML(self.email);
    });

Quotient.Common.SenderPerson.method('disengagedPopup',
    function(self) { self.hideAddPersonFragment(false) });

Quotient.Common.SenderPerson.method('removeEventListeners',
    function(self) {
        self.addPersonFragment.removeEventListener("mouseover", self.mouseoverFunction, true);
        self.addPersonFragment.removeEventListener("mouseout", self.mouseoutFunction, true);
        self.form.removeEventListener("submit", self.submitFunction, true);
    });

Quotient.Common.SenderPerson.method('engagedPopup',
    function(self) {
        if(self.popdownTimeout != null) {
            clearTimeout(self.popdownTimeout);
        }
    });

Quotient.Common.SenderPerson.method('hideAddPersonFragment',
    function(self, force) {

        function reallyHide() {
            MochiKit.DOM.hideElement(self.addPersonFragment);
            self.removeEventListeners();
            self.working = false;
        }

        if(force) {
            reallyHide();
        } else {
            self.popdownTimeout = setTimeout(reallyHide, 1000);
        }
    });
