
// import Nevow.Athena

if (typeof Quotient == 'undefined') {
    Quotient = {};
}

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
