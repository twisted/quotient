// import MochiKit.DOM
// import Divmod.Runtime
// import Nevow.Athena

Quotient.Console.ConsoleView = Nevow.Athena.Widget.subclass('Quotient.Console.ConsoleView');
Quotient.Console.ConsoleView.methods(
    function loaded(self) {
        // Notify the server when we're ready to receive log events.
        self.callRemote('clientLoaded');

        // XXX hack
        //self.node.appendChild(BUTTON({onclick: function () {self.callRemote('_retrigger')}}, 'XXX retrigger'));
    },

    function newEntry(self, html) {
        Divmod.Runtime.theRuntime.appendNodeContent(self.node, html)
    });
