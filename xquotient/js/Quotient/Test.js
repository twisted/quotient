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

Quotient.Test.MailboxTestBase = Nevow.Athena.Test.TestCase.subclass('MailboxTestBase');
Quotient.Test.MailboxTestBase.methods(
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

    function waitForScrollTableRefresh(self) {
        var d = new Divmod.Defer.Deferred();
        var pendingRowSelection = self.mailbox.scrollWidget._pendingRowSelection;
        self.mailbox.scrollWidget._pendingRowSelection = function(count) {
            pendingRowSelection && pendingRowSelection(count);
            d.callback(null);
        }
        return d;
    },

    function switchView(self, viewf, viewn, f) {
        if(!viewf) {
            viewf = "viewByMailType";
        }
        return self.mailbox._sendViewRequest(viewf, viewn).addCallback(
            function() {
                return self.waitForScrollTableRefresh().addCallback(f);
            });
    },

    function makeViewSwitcher(self, viewf, viewn, subjects, debugInfo) {
        return function() {
            return self.switchView(viewf, viewn,
                function() {
                    self.assertSubjectsAre(subjects, debugInfo);
                });
        }
    },

    function assertSubjectsAre(self, expSubjects, debugInfo) {
        var gotSubjects = MochiKit.Base.map(
                            MochiKit.Base.itemgetter("subject"),
                            self.collectRows());

        if(MochiKit.Base.compare(expSubjects, gotSubjects) != 0) {
            var msg = expSubjects.toSource() + " != " + gotSubjects.toSource();
            if(debugInfo != undefined) {
                msg = debugInfo + ": " + msg;
            }
            self.fail(msg);
        }
    },

    /* convert scrolltable rows into a list of dicts mapping
        class names to node values, e.g. {"sender": "foo", "subject": "bar"}, etc. */

    function collectRows(self) {
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
    });

Quotient.Test.InboxTestCase = Quotient.Test.MailboxTestBase.subclass('InboxTestCase');
Quotient.Test.InboxTestCase.methods(
    function doTests(self) {
        var unreadCountsPerView = function(view) {
            return parseInt(Nevow.Athena.NodeByAttribute(
                                    self.mailbox.mailViewNodes[view],
                                    "class", "count").firstChild.nodeValue);
        }

        /* inbox would have two messages, but it's the initial view,
           so the first message will have been marked read already */

        self.assertEquals(unreadCountsPerView("Inbox"), 1);
        self.assertEquals(unreadCountsPerView("Spam"), 1);

        /* similarly, this would have 4, but one of them has been read */

        self.assertEquals(unreadCountsPerView("All"), 3);
        self.assertEquals(unreadCountsPerView("Sent"), 0);

        var rows = self.collectRows();

        /* check message order and date formatting */
        self.assertEquals(rows[0]["subject"], "Message 2");
        self.assertEquals(rows[1]["subject"], "Message 1");

        /*
         * Months are zero-based instead of one-based.  Account for this by
         * subtracting or adding a one.
         */
        var expectedDate = new Date(Date.UTC(1999, 11, 13));
        self.assertEquals(
            expectedDate.getFullYear() + "-" +
            (expectedDate.getMonth() + 1) + "-" +
            expectedDate.getDate(),
            rows[1]["date"]);

        var personChooser = Nevow.Athena.FirstNodeByAttribute(
                                self.mailbox.contentTableGrid[1][0], "class", "person-chooser");
        var personChoices = Nevow.Athena.NodesByAttribute(
                                personChooser, "class", "list-option");
        var nameToPersonKey = {};
        var optName, personKey;

        for(var i = 0; i < personChoices.length; i++) {
            optName   = Nevow.Athena.FirstNodeByAttribute(personChoices[i], "class", "opt-name");
            personKey = Nevow.Athena.FirstNodeByAttribute(personChoices[i], "class", "person-key");
            nameToPersonKey[optName.firstChild.nodeValue] = personKey.firstChild.nodeValue;
        }

        var expectedPeople = ["Bob", "Joe"];
        var gotPeople = MochiKit.Base.keys(nameToPersonKey).sort();

        if(MochiKit.Base.compare(gotPeople, expectedPeople) != 0) {
            self.fail(expectedPeople.toSource() + " != " + gotPeople.toSource());
        }

        var D = self.switchView(null, "Spam",
            function() {
                self.assertSubjectsAre(["SPAM SPAM SPAM"], "Spam view");
            });

        var archived = ["Archived Message 2", "Archived Message 1"];
        var normal = ["Message 2", "Message 1"];
        var bobs = archived;
        var joes = normal;
        var all = archived.concat(normal);

        var args = [
            [null, "Sent", [], "Sent View"],
            [null, "All", all, "All view"],

            ["viewByPerson", nameToPersonKey["Bob"], bobs, "All view, Viewing by Bob"],
            ["viewByPerson", nameToPersonKey["Joe"], joes, "All view, Viewing By Joe"],

            ["viewByPerson", null, all, "All view"],

            [null, "Inbox", normal, "Inbox view"],

            ["viewByPerson", nameToPersonKey["Joe"], joes, "Inbox view, Viewing By Joe"],
            ["viewByPerson", nameToPersonKey["Bob"], [], "Inbox view, Viewing By Bob"],

            ["viewByPerson", null, normal, "Inbox view"],

            ["viewByTag", "Joe's Stuff", joes, "Inbox view, Viewing by tag \"Joe's Stuff\""],

            ["viewByPerson", nameToPersonKey["Joe"], joes, "Inbox view, Viewing by Joe & tag \"Joe's Stuff\""],
            ["viewByPerson", nameToPersonKey["Bob"], [], "Inbox view, Viewing by Bob & tag \"Joe's Stuff\""],

            ["viewByTag", "Bob's Stuff", [], "Inbox view, Viewing by Bob & tag \"Bob's Stuff\""],

            ["viewByMailType", "All", bobs, "All view, Viewing by Bob & tag \"Bob's Stuff\""],

            ["viewByTag", null, bobs, "All View, Viewing by Bob"],

            ["viewByPerson", null, all, "All View"]];

        for(var i = 0; i < args.length; i++) {
            D.addCallback(self.makeViewSwitcher.apply(self, args[i]));
        }

        D.addCallback(function() { self.testActionGroupStuff() });

        return D;
    },

    function testActionGroupStuff(self) {
        var sw = self.mailbox.scrollWidget;

        var anyPredicate = function() {
            return true;
        }

        for(var i = 0; i < 3; i++) {
            self.assertEquals(sw.findNextRow(sw._rows[i][1], anyPredicate), sw._rows[i+1][1]);
        }
        self.assertEquals(sw.findNextRow(sw._rows[3][1], anyPredicate), undefined);

        for(i = 3; 0 < i; i--) {
            self.assertEquals(sw.findPrevRow(sw._rows[i][1], anyPredicate), sw._rows[i-1][1]);
        }
        self.assertEquals(sw.findPrevRow(sw._rows[0][1], anyPredicate), undefined);

        var nonePredicate = function() {
            return false;
        }

        self.assertEquals(sw.findNextRow(sw._rows[0][1], nonePredicate), undefined);
        self.assertEquals(sw.findNextRow(sw._rows[3][1], nonePredicate), undefined);

        self.assertEquals(sw.findPrevRow(sw._rows[3][1], nonePredicate), undefined);
        self.assertEquals(sw.findPrevRow(sw._rows[0][1], nonePredicate), undefined);

        var richAssertEquals = function(x, y) {
            self.assertEquals(MochiKit.Base.compare(x, y), 0, x + " != " + y);
        }

        richAssertEquals(sw.findNextRow(sw._rows[0][1], anyPredicate, true), [sw._rows[1][1], 1]);
        self.assertEquals(sw.findNextRow(sw._rows[3][1], anyPredicate, true), undefined);

        richAssertEquals(sw.findPrevRow(sw._rows[3][1], anyPredicate, true), [sw._rows[2][1], 2]);
        self.assertEquals(sw.findPrevRow(sw._rows[0][1], anyPredicate, true), undefined);

        var select = document.forms["group-actions"].elements["group-action"];

        self.assertEquals(select.value, "archive");

        /* find out what appears right after 'archive' in the <select> */
        var nextAction = select.getElementsByTagName("option")[select.selectedIndex+1];

        /* hide the archive option */
        self.mailbox.setDisplayForGroupActions("none", ["archive"]);
        self.mailbox.selectFirstVisible(select);

        self.assertEquals(select.value, nextAction.value);

        self.mailbox.setDisplayForGroupActions("", ["archive"]);
        self.mailbox.selectFirstVisible(select);

        self.assertEquals(select.value, "archive");

        var groupSelect = function(i) {
            var row = sw._rows[i][1];
            var img = Nevow.Athena.FirstNodeByAttribute(
                        row, "src", "/Quotient/static/images/checkbox-off.gif");
            sw.groupSelectRow(sw._rows[i][0]["__id__"], img);
        }

        /* select the first and last messages */
        groupSelect(0);
        groupSelect(3);

        self.assertEquals(sw.findRowOffset(sw._selectedRow), 0);

        var selectedIDs = MochiKit.Base.keys(sw.selectedGroup);
        selectedIDs.sort();

        var expectedIDs = [sw._rows[0][0]["__id__"], sw._rows[3][0]["__id__"]];
        expectedIDs.sort();

        richAssertEquals(selectedIDs, expectedIDs);

        self.assertEquals(0, sw.findRowOffset(sw._rows[0][1]));
        self.assertEquals(3, sw.findRowOffset(sw._rows[3][1]));

        /* find out the webID of the second row, which is what should become
           the active message once we get the first and third out of the way */
        var nextActiveWebID = sw._rows[1][0]["__id__"];

        /* declare 0 & 3 to be spam */
        var D = self.mailbox.touchSelectedGroup("train", true, true);
        return D.addCallback(
            function() {
                self.assertEquals(sw._rows[0][0]["__id__"], nextActiveWebID);
            });
    });

Quotient.Test.BatchActionsTestCase = Quotient.Test.MailboxTestBase.subclass('BatchActionsTestCase');
Quotient.Test.BatchActionsTestCase.methods(
    function doTests(self) {
        var sw = self.mailbox.scrollWidget;

        var webIDToSubject = function(webID) {
            return sw.findRowData(webID)["subject"];
        }

        self.assertEquals(sw._rows[0][0]["subject"], "Message #0");
        self.assertEquals(sw._rows[0][0]["read"], true);

        /* assert every row after the first is unread, and has the right subject */
        for(var i = 1; i < sw._rows.length; i++) {
            self.assertEquals(sw._rows[i][0]["read"], false);
            self.assertEquals(sw._rows[i][0]["subject"], "Message #" + i);
        }

        var checkSubjects = function(indices) {
            self.assertSubjectsAre(
                MochiKit.Base.map(function(n) {
                    return "Message #" + n;
                }, indices));
        }

        /* select row #2 */
        return self.mailbox.fastForward(sw._rows[2][0]["__id__"]).addCallback(
            function() {
                /* assert that it's now read */
                self.assertEquals(sw._rows[2][0]["read"], true);

                self.mailbox.changeBatchSelection("read");

                return self.mailbox.touchBatch("archive", true);
        }).addCallback(
            function() {
                var indices = [/* 0 is gone */ 1, /* 2 is gone */ 3, 4, 5, 6, 7, 8, 9];
                checkSubjects(indices);

                /* deleting #0 and #2 should load #1, which is now at index 0 */
                self.assertEquals(sw._rows[0][0]["read"], true);

                self.mailbox.changeBatchSelection("read");

                return self.mailbox.touchBatch("delete", true).addCallback(
                    function() {
                        indices.shift();
                        checkSubjects(indices);
                    });
        }).addCallback(
            self.makeViewSwitcher(null, "Trash", ["Message #1"], "Trash view")
        ).addCallback(
            function() {
                var D = self.mailbox._sendViewRequest("viewByMailType", "All");
                return D.addCallback(
                    function() {
                        return self.waitForScrollTableRefresh();
                    });
        }).addCallback(
            function() {
                checkSubjects([0, /* #1 is missing (trash) */ 2, 3, 4, 5, 6, 7, 8, 9]);
                var D = self.mailbox._sendViewRequest("viewByMailType", "Inbox");
                return D.addCallback(
                    function() {
                        return self.waitForScrollTableRefresh();
                    });
        }).addCallback(
            function() {
                /* 0 = archived, 1 = trash, 2 = archived */
                checkSubjects([3, 4, 5, 6, 7, 8, 9]);

                /* now #3 (index 0) has been read */
                self.assertEquals(sw._rows[0][0]["read"], true);

                /* mark #5 (index 2) as read */
                return self.mailbox.fastForward(sw._rows[2][0]["__id__"]);
        }).addCallback(
            function() {
                self.assertEquals(sw._rows[2][0]["read"], true);

                self.mailbox.changeBatchSelection("read");

                var selectedMessages = MochiKit.Base.keys(sw.selectedGroup).length;
                self.assertEquals(selectedMessages, 2, "selected message count is " +
                                                       selectedMessages +
                                                       " instead of 2");

                /* let's include an unread message in the selection (#6) */
                sw.selectedGroup[sw._rows[3][0]["__id__"]] = sw._rows[3][1];

                var batchExceptions = self.mailbox.getBatchExceptions();
                var included = batchExceptions[0];
                var excluded = batchExceptions[1];

                if(included.length != 1 || included[0] != sw._rows[3][0]["__id__"]) {
                    self.fail("getBatchExceptions() included these subjects: " +
                              MochiKit.Base.map(webIDToSubject, included) +
                              " instead of only 'Message #6'");
                }
                self.assertEquals(excluded.length, 0,
                                  "getBatchExceptions() excluded these subjects: " +
                                  MochiKit.Base.map(webIDToSubject, excluded) +
                                  " but it wasn't supposed to exclude any");

                /* so #3 & #5 are read, and will be affected by the batch
                 * action.  #6 is unread, but we manually selected it, so
                 * it should also be affected */
                return self.mailbox.touchBatch("train", true, /*spam=*/true);
        }).addCallback(
            self.makeViewSwitcher(null, "Spam", ["Message #3",
                                                 "Message #5",
                                                 "Message #6"], "Spam view")
        ).addCallback(
            self.makeViewSwitcher(null, "Inbox", ["Message #4",
                                                  "Message #7",
                                                  "Message #8",
                                                  "Message #9"], "Inbox view")
        ).addCallback(
            function() {
                self.assertEquals(sw._rows[0][0]["read"], true);

                self.mailbox.changeBatchSelection("unread");

                /* unselect the last message */
                delete(sw.selectedGroup[sw._rows[3][0]["__id__"]]);

                var batchExceptions = self.mailbox.getBatchExceptions();
                var included = batchExceptions[0];
                var excluded = batchExceptions[1];

                self.assertEquals(included.length, 0,
                                  "getBatchExceptions() included these subjects: " +
                                  MochiKit.Base.map(webIDToSubject, included) +
                                  " but it wasn't supposed to include any");

                if(excluded.length != 1 || excluded[0] != sw._rows[3][0]["__id__"]) {
                    self.fail("getBatchExceptions() excluded these subjects: " +
                              MochiKit.Base.map(webIDToSubject, excluded) +
                              " instead of only 'Message #9'");
                }

                return self.mailbox.touchBatch("delete", true);
        }).addCallback(
            function() {
                checkSubjects([4, 9]);
                self.mailbox.changeBatchSelection("all");
                return self.mailbox.touchBatch("train", true, true);
        }).addCallback(
            function() {
                checkSubjects([]);
        });
    });
