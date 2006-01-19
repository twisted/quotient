/* this javascript file should be included by all quotient pages */

if(typeof(Quotient) == "undefined") {
    Quotient = {};
}

if(typeof(Quotient.Common) == "undefined") {
    Quotient.Common = {};
}

Quotient.Common.Util = Nevow.Athena.Widget.subclass();

Quotient.Common.Util.findPosX = function(obj) {
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

Quotient.Common.Util.findPosY = function(obj) {
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

Quotient.Common.Util.stripLeadingTrailingWS = function(str) {
    return str.replace(/^\s+/, "").replace(/\s+$/, "");
}

Quotient.Common.Util.startswith = function(needle, haystack) {
    return haystack.toLowerCase().slice(0, needle.length) == needle.toLowerCase();
}

Quotient.Common.Util.normalizeTag = function(tag) {
    return Quotient.Common.Util.stripLeadingTrailingWS(tag).replace(/\s{2,}/, " ").toLowerCase();
}

Quotient.Common.Util.resizeIFrame = function(frame) {
    // Code is from http://www.ozoneasylum.com/9671&latestPost=true
    try {
        innerDoc = (frame.contentDocument) ? frame.contentDocument : frame.contentWindow.document;
        objToResize = (frame.style) ? frame.style : frame;
        objToResize.height = innerDoc.body.scrollHeight + 20 + 'px';
        objToResize.width = innerDoc.body.scrollWidth + 5 + 'px';
    }
    catch (e) {}
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

Quotient.Common.SenderPerson.method('showAddPerson',
    function(self, node, event) {
        self.node = node;

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

        self.eventTarget = event.target.parentNode;
        self.eventTarget.onclick = function() { self.hideAddPerson(); return false };

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

Quotient.Common.SenderPerson.method('hideAddPerson',
    function(self) {
        MochiKit.DOM.hideElement(self.addPersonFragment);
        self.form.removeEventListener("submit", self.submitFunction, true);
        self.eventTarget.onclick = function(event) {
            self.showAddPerson(self.node, event);
            return false;
        }
    });
