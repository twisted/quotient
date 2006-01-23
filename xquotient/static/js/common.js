/* this javascript file should be included by all quotient pages */
// import Quotient
// import Mantissa.People

if(typeof(Quotient.Common) == "undefined") {
    Quotient.Common = {};
}

Quotient.Common.Util = Nevow.Athena.Widget.subclass('Quotient.Common.Util');

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

Quotient.Common.AddPerson = Nevow.Athena.Widget.subclass('Quotient.Common.AddPerson');
Quotient.Common.AddPerson.methods(
    function replaceAddPersonHTMLWithPersonHTML(self, identifier) {
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

Quotient.Common.SenderPerson = Nevow.Athena.Widget.subclass("Quotient.Common.SenderPerson");
Quotient.Common.SenderPerson.methods(
    function showAddPerson(self, node, event) {
        self.node = node;
        self.body = document.getElementsByTagName("body")[0];

        var name = self.nodeByAttribute('class', 'person-name').firstChild.nodeValue;
        var parts = new Object();

        parts["firstname"] = '';
        parts["lastname"] = '';

        if(name.match(/\s+/)) {
            var split = name.split(/\s+/, 2);
            parts["firstname"] = split[0];
            parts["lastname"]  = split[1];
        } else if(name.match(/@/)) {
            parts["firstname"] = name.split(/@/, 2)[0];
        } else { 
            parts["firstname"] = name;
        }

        self.email = self.nodeByAttribute('class', 'person-identifier').firstChild.nodeValue;
        parts["email"] = self.email;

        self.addPersonFragment = MochiKit.DOM.getElement("add-person-fragment");

        self.addPersonFragment.style.top = event.pageY + 'px';
        self.addPersonFragment.style.left = event.pageX + 25 + 'px';

        self.form = self.addPersonFragment.getElementsByTagName("form")[0];
        self.submitFunction = function() { self.submitForm() };

        self.form.addEventListener("submit", self.submitFunction, true);

        var inputs = Nevow.Athena.NodesByAttribute(self.addPersonFragment, 'type', 'text');

        for(var i = 0; i < inputs.length; i++) {
            if(inputs[i].name == "firstname") {
                inputs[i].focus();
            }
            if(inputs[i].name in parts) {
                inputs[i].value = parts[inputs[i].name];
            } else {
                inputs[i].value = "";
            }
        }

        self.eventTarget = event.target.parentNode;

        self.eventTarget.onclick = function() {
            self.body.onclick = null;
            self.hideAddPerson();
            return false
        }

        self.body.onclick = function(_event) {
            if(event.target == _event.target) {
                return false;
            }

            e = _event.target;
            while(e && e.id != self.addPersonFragment.id) {
                e = e.parentNode;
            }
            if (e) {
                return false;
            }
            self.hideAddPerson();
            self.body.onclick = null;
            return false;
        }
        MochiKit.DOM.showElement(self.addPersonFragment);
    },

    function submitForm(self) {
        var node = Nevow.Athena.NodeByAttribute(self.addPersonFragment, "class", "add-person");
        Quotient.Common.AddPerson.get(node).replaceAddPersonHTMLWithPersonHTML(self.email);
    },

    function hideAddPerson(self) {
        MochiKit.DOM.hideElement(self.addPersonFragment);
        self.form.removeEventListener("submit", self.submitFunction, true);
        self.eventTarget.onclick = function(event) {
            self.showAddPerson(self.node, event);
            return false;
        }
    });

Quotient.Common.CollapsiblePane = Nevow.Athena.Widget.subclass('Quotient.Common.CollapsiblePane');

Quotient.Common.CollapsiblePane.method(
    function toggle(self, element) {
        var body = Nevow.Athena.NodeByAttribute(element.parentNode, 'class', 'pane-body');
        var img = null;

        if(body.style.display == "none") {
            body.style.display = "block";
            img = "/Quotient/static/images/outline-expanded.png";
        } else {
            body.style.display = "none";
            img = "/Quotient/static/images/outline-collapsed.png";
        }

        Nevow.Athena.NodeByAttribute(element, "class", "collapse-arrow").src = img;
    });
