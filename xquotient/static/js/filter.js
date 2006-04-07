
// import Mantissa.LiveForm
// import Quotient

Quotient.Filter = {};

Quotient.Filter.RuleWidget = Mantissa.LiveForm.FormWidget.subclass("Quotient.Filter.RuleWidget");
Quotient.Filter.RuleWidget.methods(
    function submit(self) {
        Quotient.Filter.RuleWidget.upcall(self, 'submit');
        return false;
    });

Quotient.Filter.HamConfiguration = Nevow.Athena.Widget.subclass("Quotient.Filter.HamConfiguration");
Quotient.Filter.HamConfiguration.methods(
    function retrain(self) {
        self.callRemote('retrain').addCallback(function(result) {
            self.node.appendChild(document.createTextNode('Training reset.'));
        }).addErrback(function(err) {
            self.node.appendChild(document.createTextNode('Error: ' + err.description));
        });
        return false;
    },

    function reclassify(self) {
        self.callRemote('reclassify').addCallback(function(result) {
            self.node.appendChild(document.createTextNode('Beginning reclassification.'));
        }).addErrback(function(err) {
            self.node.appendChild(document.createTextNode('Error: ' + err.description));
        });
        return false;
    });
