
// import Mantissa.LiveForm
// import Quotient

Quotient.Filter = {};

Quotient.Filter.RuleWidget = Mantissa.LiveForm.FormWidget.subclass("Quotient.Filter.RuleWidget");
Quotient.Filter.RuleWidget.methods(
    function submit(self) {
        Quotient.Filter.RuleWidget.upcall(self, 'submit');
        return false;
    });
