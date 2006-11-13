/* this javascript file should be included by all quotient pages */
// import Quotient
// import Mantissa.People
// import MochiKit.DOM

Quotient.Common.Util = Nevow.Athena.Widget.subclass('Quotient.Common.Util');

/**
 * Show C{node} as a dialog - center it vertically and horizontally, grey
 * out the rest of the document, and hide it when the user clicks outside
 * of the dialog.
 *
 * @return: pair of [dialog node, hide function]
 */
Quotient.Common.Util.showNodeAsDialog = function(node) {
    /* clone the node so we can add it to the document in the different place */
    node = node.cloneNode(true);

    var pageSize = Divmod.Runtime.theRuntime.getPageSize();

    /* make an overlay element */
    var blurOverlay = MochiKit.DOM.DIV({"class": "blur-overlay"}, "&#160;");
    blurOverlay.style.height = document.documentElement.scrollHeight + "px";

    /* add it to the document */
    document.body.appendChild(blurOverlay);
    /* add our cloned node after it */
    document.body.appendChild(node);

    node.style.position = "absolute";
    node.style.display = "";
    var elemSize = Divmod.Runtime.theRuntime.getElementSize(node);

    node.style.left = Math.floor((pageSize.w / 2) - (elemSize.w / 2)) + "px";
    node.style.top  = Math.floor((pageSize.h / 2) - (elemSize.h / 2)) + "px";

    var hidden = false;

    var hide = function() {
        if(hidden) {
            return;
        }
        hidden = true;
        document.body.removeChild(blurOverlay);
        document.body.removeChild(node);
        blurOverlay.onclick = null;
    }

    /* we use setTimeout(... 0) so the handler gets added after the current
     * onclick event (if any) is done
     */
    setTimeout(
        function() {
            blurOverlay.onclick = hide;
        }, 0);

    return {node: node, hide: hide};
}

Quotient.Common.Util.showSimpleWarningDialog = function(text) {
    var node = document.createElement("div");
    node.setAttribute("class", "simple-warning-dialog");
    node.setAttribute("style", "display: none");
    var title = document.createElement("div");
    title.setAttribute("class", "simple-warning-dialog-title");
    title.appendChild(document.createTextNode("Warning"));
    node.appendChild(title);
    node.appendChild(document.createTextNode(text));
    document.body.appendChild(node);
    return Quotient.Common.Util.showNodeAsDialog(node);
}

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
        return D.addCallback(function(HTML) {
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
    },

    /**
     * Return the L{Mantissa.LiveForm.FormWidget} instance which controls our
     * form
     */
    function getAddPersonForm(self) {
        return Nevow.Athena.Widget.get(self.node.getElementsByTagName("form")[0]);
    });

Quotient.Common.SenderPerson = Nevow.Athena.Widget.subclass("Quotient.Common.SenderPerson");
Quotient.Common.SenderPerson.methods(
    /**
     * Pre-fill the add person form with the information we know about this
     * sender
     */
    function _preFillForm(self) {
        var getValueOfNodeWithClass = function(cls) {
            return self.firstNodeByAttribute("class", cls).firstChild.nodeValue;
        }

        var name = getValueOfNodeWithClass("sender-person-name");
        var values = {lastname: [""]};

        if(name.match(/\s+/)) {
            var split = name.split(/\s+/, 2);
            values["firstname"] = [split[0]];
            values["lastname"]  = [split[1]];
        } else if(name.match(/@/)) {
            values["firstname"] = [name.split(/@/, 2)[0]];
        } else {
            values["firstname"] = [name];
        }

        self.email = getValueOfNodeWithClass("person-identifier");
        values["email"] = [self.email];

        self.addPersonFormWidget.setInputValues(values);
    },

    /**
     * Show an "Add Person" dialog, with the form fields pre-filled with the
     * information we know about the sender (first name, last name, email
     * address)
     */
    function showAddPerson(self) {
        var addPersonDialogNode = Nevow.Athena.FirstNodeByAttribute(
                                    self.widgetParent.node,
                                    "class",
                                    "add-person-fragment");
        self.addPersonFormWidget = Nevow.Athena.Widget.get(
                                    Nevow.Athena.FirstNodeByAttribute(
                                        addPersonDialogNode,
                                        "class",
                                        "add-person")).getAddPersonForm();

        self._preFillForm();

        self.dialog = Quotient.Common.Util.showNodeAsDialog(addPersonDialogNode);

        /* set the handlers on the cloned node returned by showNodeAsDialog().
         * FIXME should do a better thing here */
        var form = self.dialog.node.getElementsByTagName("form")[0];
        form.onsubmit = function() {
            var liveform = Nevow.Athena.Widget.get(form);
            liveform.submit().addCallback(
                function() {
                    return self._personAdded();
                });
            return false;
        }
        return false;
    },

    /**
     * Person has been added.  Tell AddPerson to replace the "Add Person"
     * nodes with Person nodes & hide the "Add Person" dialog
     */
    function _personAdded(self) {
        self.dialog.hide();
        return self.addPersonFormWidget.widgetParent.replaceAddPersonHTMLWithPersonHTML(self.email);
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
