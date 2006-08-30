// import Quotient
// import Nevow.Athena
// import Mantissa.LiveForm
// import Mantissa.TDB
// import Mantissa.ScrollTable

Quotient.Grabber.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass(
                                        'Quotient.Grabber.ScrollingWidget');

Quotient.Grabber.ScrollingWidget.methods(
    function __init__(self, node) {
        self.columnWidths = {"username": "150px",
                             "domain": "150px",
                             "status": "200px",
                             "paused": "90px",
                             "actions": "100px"};

        Quotient.Grabber.ScrollingWidget.upcall(self, "__init__", node);
        self._scrollViewport.style.height = '100px';
        self.node.style.display = "none";
    },

    /**
     * Hide our node if the last row fetch resulted in 0 rows.  Show it
     * otherwise
     */
    function cbRowsFetched(self, count) {
        if(count == 0) {
            self.node.style.display = "none";
        } else {
            self.node.style.display = "";
        }
    },

    function clickEventForAction(self, actionID, rowData) {
        if(actionID == "edit") {
            return function() {
                Nevow.Athena.Widget.get(this).widgetParent.loadEditForm(rowData["__id__"]);
                return false;
            }
        }
    });

Quotient.Grabber.Controller = Nevow.Athena.Widget.subclass('Quotient.Grabber.Controller');
Quotient.Grabber.Controller.methods(
    function loadEditForm(self, targetID) {
        var D = self.callRemote("getEditGrabberForm", targetID);
        D.addCallback(
            function(html) {
                var node = null;
                try {
                    node = self.nodeByAttribute("class", "edit-grabber-form");
                } catch(e) {}

                if(!node) {
                    node = MochiKit.DOM.DIV({"class": "edit-grabber-form"});
                    var cont = self.nodeByAttribute("class", "edit-grabber-form-container");
                    cont.appendChild(node);
                }
                Divmod.Runtime.theRuntime.setNodeContent(node,
                    '<div xmlns="http://www.w3.org/1999/xhtml">' + html + '</div>');
            });
    },
    function hideEditForm(self) {
        var form = self.nodeByAttribute("class", "edit-grabber-form");
        while(form.childNodes) {
            form.removeChild(form.firstChild);
        }
    });

Quotient.Grabber.StatusWidget = Nevow.Athena.Widget.subclass('Grabber.StatusWidget');
Quotient.Grabber.StatusWidget.method(
    function __init__(self, node) {
        Quotient.Grabber.StatusWidget.upcall(self, '__init__', node);
        self._pendingStatusUpdate = null;
        var d = self.callRemote('startObserving');
        d.addCallback(function(newStatus) { self.setStatus(newStatus); });
        d.addErrback(function(err) { self.setStatus(err.message); });
    });

Quotient.Grabber.StatusWidget.method(
    function setStatus(self, newStatus) {
        self._pendingStatus = newStatus;
        if (self._pendingStatusUpdate == null) {
            self._pendingStatusUpdate = setTimeout(function() {
                var pendingStatus = self._pendingStatus;
                self._pendingStatus = self._pendingStatusUpdate = null;
                self.node.innerHTML = pendingStatus;
            }, 5);
        }
    });

Quotient.Grabber.AddGrabberFormWidget = Mantissa.LiveForm.FormWidget.subclass(
                                                    'Quotient.Grabber.AddGrabberFormWidget');

Quotient.Grabber.AddGrabberFormWidget.methods(
    function submitSuccess(self, result) {
        self.emptyErrorNode();
        var sf = Nevow.Athena.NodeByAttribute(self.widgetParent.node,
                                              'athena:class',
                                              'Quotient.Grabber.ScrollingWidget');

        Quotient.Grabber.ScrollingWidget.get(sf).emptyAndRefill();
        return Quotient.Grabber.AddGrabberFormWidget.upcall(self, "submitSuccess", result);
    },

    /**
     * Empty the node that contains error messages
     */
    function emptyErrorNode(self) {
        if(self.errorNode && 0 < self.errorNode.childNodes.length) {
            self.errorNode.removeChild(self.errorNode.firstChild);
        }
    },

    /**
     * Show an error message for Error C{err}
     */
    function submitFailure(self, err) {
        if(!self.errorNode) {
            self.errorNode = MochiKit.DOM.DIV({"class": "add-grabber-error"});
            self.node.appendChild(self.errorNode);
        }
        self.emptyErrorNode();
        self.errorNode.appendChild(
            document.createTextNode("Error submitting form: " + err.error.message));
    });
