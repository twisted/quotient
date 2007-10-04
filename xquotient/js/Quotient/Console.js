
// import Divmod.Runtime
// import Nevow.Athena

Quotient.Console.LiveLog = Nevow.Athena.Widget.subclass('Quotient.Console.LiveLog');
Quotient.Console.LiveLog.methods(
    function loaded(self) {
        self.callRemote('clientLoaded');
    },

    function newEntry(self, entry) {
        function makeText() {
            var text;
            if (entry.href) {
                text = document.createElement('a');
                text.setAttribute('href', entry.text);
                text.appendChild(document.createTextNode(entry.text));
            } else {
                text = document.createTextNode(entry.text);
            }
            var bold = document.createElement('b');
            bold.appendChild(text);
            return bold;
        }
        var e = document.createElement('div');
        e.setAttribute('style', 'margin: 1em');
        e.appendChild(document.createTextNode('Found '+entry.type+': '));
        e.appendChild(document.createTextNode('...'+entry.before));
        e.appendChild(makeText());
        e.appendChild(document.createTextNode(entry.after+'...'));
        self.node.appendChild(e);
    });
