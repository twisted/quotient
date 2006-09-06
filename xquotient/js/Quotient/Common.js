/* this javascript file should be included by all quotient pages */
// import Quotient
// import Mantissa.People

Quotient.Common.Util = Nevow.Athena.Widget.subclass('Quotient.Common.Util');

/**
 * @return: array of values that appear in a1 and not a2
 * @param a1: array with no duplicate elements
 * @param a2: array
 *
 * difference([1,2,3], [1,4,6]) => [2,3]
 */
Quotient.Common.Util.difference = function(a1, a2) {
    var j, seen;
    var diff = [];
    for(var i = 0; i < a1.length; i++) {
        seen = false;
        for(j = 0; j < a2.length; j++) {
            if(a1[i] == a2[j]) {
                seen = true;
                break;
            }
        }
        if(!seen) {
            diff.push(a1[i]);
        }
    }
    return diff;
}

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
        var innerDoc = (frame.contentDocument) ? frame.contentDocument : frame.contentWindow.document;
        var objToResize = (frame.style) ? frame.style : frame;
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
    function showAddPerson(self, event, node, eventTarget) {
        self.node = node;

        var name = self.nodeByAttribute('class', 'sender-person-name').firstChild.nodeValue;
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

        self.addPersonFragment = document.getElementById("add-person-fragment");

        var coords = Divmod.Runtime.theRuntime.getEventCoords(event);
        self.addPersonFragment.style.top = coords.y + 'px';
        self.addPersonFragment.style.left = coords.x + 25 + 'px';

        self.form = self.addPersonFragment.getElementsByTagName("form")[0];
        self.submitFunction = function() { self.submitForm() };

        self.originalSubmitHandler = self.form.onsubmit;
        self.form.onsubmit = function() {
            var liveform = Nevow.Athena.Widget.get(self.form);
            liveform.submit().addCallback(
                function() {
                    self.submitForm();
                });
            return false;
        }

        var inputs = Nevow.Athena.NodesByAttribute(self.addPersonFragment, 'type', 'text');
        var firstnameInput;

        for(var i = 0; i < inputs.length; i++) {
            if(!firstnameInput && inputs[i].name == "firstname") {
                firstnameInput = inputs[i];
            }
            if(inputs[i].name in parts) {
                inputs[i].value = parts[inputs[i].name];
            } else {
                inputs[i].value = "";
            }
        }

        setTimeout(
            function() {
                eventTarget.onclick = function() {
                    document.body.onclick = null;
                    self.hideAddPerson();
                    return false;
                }
            }, 0);

        self.eventTarget = eventTarget;
        self.addPersonFragment.style.display = "";
        firstnameInput.focus();
    },

    function submitForm(self) {
        var node = Nevow.Athena.NodeByAttribute(self.addPersonFragment, "class", "add-person");
        Quotient.Common.AddPerson.get(node).replaceAddPersonHTMLWithPersonHTML(self.email);
        self.hideAddPerson();
    },

    function hideAddPerson(self) {
        self.addPersonFragment.style.display = "none";
        self.form.onsubmit = self.originalSubmitHandler;
        self.eventTarget.onclick = function(event) {
            self.showAddPerson(event, self.node, self.eventTarget);
            return false;
        }
    });

Quotient.Common.CollapsiblePane = {};

/**
 * Toggle the visibility of the collapsible pane whose expose arrow is
 * C{element}.  If C{prefix} is provided, it will be prepended to the
 * image filenames "outline-expanded.png" and "outline-collapsed.png"
 * which are used to source the expose arrow image for the expanded
 * and collapsed states.  C{parent} points to the closest element that
 * contains both the expose arrow and the contents of the pane
 */
Quotient.Common.CollapsiblePane.toggle = function(element,
                                                  prefix/*=''*/,
                                                  parent/*=element.parentNode*/) {

    var body = Nevow.Athena.FirstNodeByAttribute(
                    parent || element.parentNode,
                    'class',
                    'pane-body');
    var img = null;
    if(typeof(prefix) == 'undefined') {
        prefix = '';
    }

    if(body.style.position == "absolute") {
        body.style.position = "static";
        img = "/Quotient/static/images/" + prefix + "outline-expanded.png";
    } else {
        body.style.position = "absolute";
        img = "/Quotient/static/images/" + prefix + "outline-collapsed.png";
    }

    Nevow.Athena.NodeByAttribute(element, "class", "collapse-arrow").src = img;
}
