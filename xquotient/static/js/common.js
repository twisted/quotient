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

        parts["nickname"] = parts["firstname"];

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

        self.body.onclick = function(_event) {
            if(event.target == _event.target) {
                return false;
            }
            var e = _event.target;
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
        //self.eventTarget.onclick = function(event) {
        //    self.showAddPerson(self.node, event);
        //    return false;
        //}
    });
