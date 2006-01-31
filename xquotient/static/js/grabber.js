// import Quotient
// import Nevow.Athena
// import Mantissa.LiveForm
// import Mantissa.TDB

Quotient.Grabber = {};

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
