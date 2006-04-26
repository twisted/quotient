// import Nevow.Athena.Test
// import Quotient.Mailbox

Quotient.Test.TestableMailboxSubclass = Quotient.Mailbox.Controller.subclass('TestableMailboxSubclass');
Quotient.Test.TestableMailboxSubclass.methods(
    function __init__(self, node, cl) {
        self.pendingDeferred = new Divmod.Defer.Deferred();
        Quotient.Test.TestableMailboxSubclass.upcall(self, "__init__", node, cl);
    },

    function finishedLoading(self) {
        self.pendingDeferred.callback(null);
    });

Quotient.Test.InboxTestCase = Nevow.Athena.Test.TestCase.subclass('InboxTestCase');
Quotient.Test.InboxTestCase.methods(
    function run(self) {
        self.mailbox = Quotient.Test.TestableMailboxSubclass.get(
                                Nevow.Athena.NodeByAttribute(
                                    self.node.parentNode,
                                    "athena:class",
                                    "Quotient.Test.TestableMailboxSubclass"));

        self.mailbox.pendingDeferred.addCallback(
            function() {
                self.mailbox.scrollWidget._rowHeight = 1;
                return self.mailbox.scrollWidget._getSomeRows().addCallback(
                    function() {
                        return self.doTests();
                    });
            });
        return self.mailbox.pendingDeferred;
    },

    function doTests(self) {
        /*
           convert scrolltable rows into a list of dicts mapping
           class names to node values, e.g. {"sender": "foo", "subject": "bar"}, etc.
         */
        function collectRows() {
            var rows = self.mailbox.scrollWidget.nodesByAttribute("class", "q-scroll-row");
            var divs, j, row;
            for(var i = 0; i < rows.length; i++) {
                divs = rows[i].getElementsByTagName("div");
                row = {};
                for(j = 0; j < divs.length; j++) {
                    row[divs[j].className] = divs[j].firstChild.nodeValue;
                }
                rows[i] = row;
            }
            return rows;
        }

        var rows = collectRows();

        /* check message order and date formatting */
        self.assertEquals(rows[0]["subject"], "Message 2");
        self.assertEquals(rows[1]["subject"], "Message 1");

        self.assertEquals(rows[1]["date"], "1999-12-13");

        return self.mailbox._sendViewRequest("viewByMailType", "Spam").addCallback(
            function() {
                var deferred = new Divmod.Defer.Deferred();
                var pendingRowSelection = self.mailbox.scrollWidget._pendingRowSelection;
                self.mailbox.scrollWidget._pendingRowSelection = function() {
                    pendingRowSelection && pendingRowSelection();
                    deferred.callback(null);
                }
                return deferred;
        }).addCallback(
            function() {
                    rows = collectRows();
                    self.assertEquals(rows[0]["subject"], "SPAM SPAM SPAM");
                    self.assertEquals(rows.length, 1);
            });
    });
