
// import Divmod.Runtime
// import Nevow.Athena

Quotient.Console.LiveLog = Nevow.Athena.Widget.subclass('Quotient.Console.LiveLog');
Quotient.Console.LiveLog.methods(
    function loaded(self) {
        self.callRemote('clientLoaded');
    });
