// import Quotient
// import Nevow.Athena
// import Mantissa.LiveForm
// import Mantissa.TDB
// import Mantissa.ScrollTable

Quotient.Grabber.EditAction = Mantissa.ScrollTable.Action.subclass(
                                'Quotient.Grabber.EditAction');

Quotient.Grabber.EditAction.methods(
    function enact(self, scrollingWidget, row) {
        return scrollingWidget.widgetParent.loadEditForm(row.__id__);
    });

Quotient.Grabber.RefillingAction = Mantissa.ScrollTable.Action.subclass(
                                    'Quotient.Grabber.RefillingAction');

/**
 * Trivial L{Mantissa.ScrollTable.Action} subclass with a handler that refills
 * the scrolltable after the server-side action completes successfully.
 * XXX: we should really just mutate the row node in place, e.g. to change
 *      paused="true" to "false"
 */
Quotient.Grabber.RefillingAction.methods(
    function __init__(self, name, displayName, icon) {
        Quotient.Grabber.RefillingAction.upcall(
            self, "__init__", name, displayName,
            function(scrollingWidget, row, result) {
                return scrollingWidget.emptyAndRefill();
            },
            icon);
    });

Quotient.Grabber.ScrollingWidget = Mantissa.ScrollTable.ScrollingWidget.subclass(
                                        'Quotient.Grabber.ScrollingWidget');

Quotient.Grabber.ScrollingWidget.methods(
    function __init__(self, node) {
        self.columnWidths = {"username": "150px",
                             "domain": "150px",
                             "status": "200px",
                             "paused": "90px",
                             "actions": "100px"};

        self.actions = [Quotient.Grabber.RefillingAction(
                            "delete", "Delete",
                            "/Mantissa/images/delete.png"),

                        Quotient.Grabber.EditAction("edit", "Edit"),

                        Quotient.Grabber.RefillingAction(
                            "pause", "Pause",
                            "/Quotient/static/images/action-pause.png"),

                        Quotient.Grabber.RefillingAction(
                            "resume", "Resume",
                            "/Quotient/static/images/action-resume.png")];

        Quotient.Grabber.ScrollingWidget.upcall(self, "__init__", node);
        self._scrollViewport.style.height = '100px';
        self.node.style.display = "none";
        self.initializationDeferred.addCallback(
            function() {
                self.reevaluateVisibility();
            });
    },

    /**
     * Change the visibility of our node depending on our row count.
     *  If 0 < row count, then show, otherwise hide
     */
    function reevaluateVisibility(self) {
        if(0 < self.model.rowCount()) {
            self.node.style.display = "";
        } else {
            self.node.style.display = "none";
        }
    },

    /**
     * Override Mantissa.ScrollTable.ScrollingWidget.emptyAndRefill and add a
     * callback that fiddles our visibility depending on how many rows were
     * fetched
     */
    function emptyAndRefill(self) {
        var D = Quotient.Grabber.ScrollingWidget.upcall(self, "emptyAndRefill");
        return D.addCallback(
            function() {
                self.reevaluateVisibility();
            });
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
