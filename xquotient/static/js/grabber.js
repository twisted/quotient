// import Quotient
// import Nevow.Athena
// import Mantissa.LiveForm
// import Mantissa.TDB

Quotient.Grabber = {};

Quotient.Grabber.Controller = Nevow.Athena.Widget.subclass('Quotient.Grabber.Controller');
Quotient.Grabber.Controller.methods(
    function loaded(self) {
        var lognode = self.nodeByAttribute("class", "grabber-log");
        Divmod.logger.addObserver(function(err) {
            if(err.debug && err.channel == "liveform") {
                lognode.appendChild(document.createTextNode(err.message))
            }
        });
    },

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
        var d = self.callRemote('startObserving');
        d.addCallback(function(newStatus) { self.setStatus(newStatus); });
        d.addErrback(function(err) { self.setStatus(err.message); });
    });

Quotient.Grabber.StatusWidget.method(
    function setStatus(self, newStatus) {
        while (self.node.childNodes.length) {
            self.node.removeChild(self.node.firstChild);
        }
        self.node.appendChild(document.createTextNode(newStatus));
    });

Quotient.Grabber.AddGrabberFormWidget = Mantissa.LiveForm.FormWidget.subclass(
                                                    'Quotient.Grabber.AddGrabberFormWidget');

Quotient.Grabber.AddGrabberFormWidget.method(
    function submitSuccess(self, result) {
        var tdbNode = Nevow.Athena.NodeByAttribute(self.widgetParent.node,
                                                   'athena:class',
                                                   'Mantissa.TDB.Controller');

        var tdbController = Mantissa.TDB.Controller.get(tdbNode);

        tdbController._setTableContent(result[0]);
        tdbController._setPageState.apply(tdbController, result[1]);
    });
