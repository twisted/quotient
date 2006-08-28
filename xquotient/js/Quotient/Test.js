// import Nevow.Athena.Test
// import Quotient.Mailbox
// import Quotient.Compose

Quotient.Test.TestableMailboxSubclass = Quotient.Mailbox.Controller.subclass('TestableMailboxSubclass');
Quotient.Test.TestableMailboxSubclass.methods(
    function __init__(self) {
        var args = [];
        for(var i = 1; i < arguments.length; i++) {
            args.push(arguments[i]);
        }
        self.pendingDeferred = new Divmod.Defer.Deferred();
        Quotient.Test.TestableMailboxSubclass.upcall.apply(self, [self, "__init__"].concat(args));
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

    /**
     * Add row at index C{i} to the scrolltable's group selection
     */
    function groupSelect(self, i) {
        var sw = self.mailbox.scrollWidget;
        var row = sw._rows[i][1];
        /* calling nodeByAttribute on the src attribute and passing
           the relative URL won't work, because IE rewrites them as
           absolute URLs in the DOM */
        var img = row.getElementsByTagName("img")[0];
        var segs = img.src.split('/');
        if(segs[segs.length-1] != "checkbox-off.gif") {
            throw new Error("expected 'off' checkbox");
        }
        sw.groupSelectRow(sw._rows[i][0]["__id__"], img);
    },

    /**
     * Figure out the number of unread messages in the view C{view}
     * @param view: string
     * @return: integer
     */
    function unreadCountForView(self, view) {
        return parseInt(Nevow.Athena.NodeByAttribute(
                                self.mailbox.mailViewNodes[view],
                                "class", "count").firstChild.nodeValue);
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
        /* inbox would have two messages, but it's the initial view,
           so the first message will have been marked read already */

        self.assertEquals(self.unreadCountForView("Inbox"), 1);
        self.assertEquals(self.unreadCountForView("Spam"), 1);

        /* similarly, this would have 4, but one of them has been read */

        self.assertEquals(self.unreadCountForView("All"), 3);
        self.assertEquals(self.unreadCountForView("Sent"), 0);

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
                                self.mailbox.contentTableGrid[0][0], "class", "person-chooser");
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

        D.addCallback(function() { self._testActionGroupStuff() });

        return D;
    },

    function _testActionGroupStuff(self) {
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

        var select = self.mailbox.groupActionsForm.elements["group-action"];

        self.assertEquals(select.value, "archive");

        /* find out what appears right after 'archive' in the <select> */
        var nextAction = select.getElementsByTagName("option")[select.selectedIndex+1];

        /* hide the archive option */

        var visibility = self.mailbox.createVisibilityMatrix();
        var visible = visibility["Inbox"]["show"];
        for(var i = 0; i < visible.length; i++) {
            visible[i] = visible[i][0];
        }

        var minusView = function(view) {
            var result = [];
            for(var i = 0; i < visible.length; i++) {
                if(view != visible[i]) {
                    result.push(visible[i]);
                }
            }
            return result;
        }

        self.mailbox.setGroupActions(minusView("archive"));

        self.assertEquals(select.value, nextAction.value);

        self.mailbox.setGroupActions(visible);

        self.assertEquals(select.value, "archive");

        /* select the first and last messages */
        self.groupSelect(0);
        self.groupSelect(3);

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

Quotient.Test.InboxDOMHandlersTestCase = Quotient.Test.MailboxTestBase.subclass(
                                            'InboxDOMHandlersTestCase');

Quotient.Test.InboxDOMHandlersTestCase.methods(
    /**
     * test inbox methods that are tied to the DOM
     */

    function doTests(self) {
        var viewPaneContents = Nevow.Athena.NodesByAttribute(
                                   self.mailbox.firstNodeByAttribute("class", "view-pane"),
                                   "class", "view-pane-content"),
            collapsiblePane, i, name, viewChoosersByName = {};

        for(i = 0; i < viewPaneContents.length; i++) {
            collapsiblePane = viewPaneContents[i];
            name = Nevow.Athena.FirstNodeByAttribute(
                        collapsiblePane, "class", "view-pane-name").firstChild.nodeValue;
            viewChoosersByName[name] = Nevow.Athena.FirstNodeByAttribute(
                                            collapsiblePane, "class", "pane-body");
        }

        /**
         * @param category: the view category, e.g. "Mail", "People"
         * @param choice: the view choice, e.g. "Inbox", "Joe"
         * @param return: the option node that represents the specified choice
         */
        var optionNodeForViewChoice = function(category, choice) {
            var opts = Nevow.Athena.NodesByAttribute(
                            viewChoosersByName[category], "class", "opt-name");
            for(i = 0; i < opts.length; i++) {
                if(opts[i].firstChild.nodeValue == choice) {
                    return opts[i].parentNode;
                }
            }
        }

        var makeViewChoice = function(mailboxf, category, choice) {
            var D = mailboxf(optionNodeForViewChoice(category, choice));
            return D.addCallback(
                function() {
                    return self.waitForScrollTableRefresh();
                });
        }

        var makeMailViewChoice = function(choice) {
            return makeViewChoice(
                function(n) {
                    return self.mailbox.chooseMailView(n);
                }, "Mail", choice);
        }
        var makePersonChoice = function(choice) {
            return makeViewChoice(
                function(n) {
                    return self.mailbox.choosePerson(n);
                }, "People", choice);
        }

        self.assertSubjectsAre(["Message 2", "Message 1"]);

        return makeMailViewChoice("All").addCallback(
            function() {
                self.assertSubjectsAre(["Archived Message 2",
                                        "Archived Message 1",
                                        "Message 2",
                                        "Message 1"]);
                return makePersonChoice("Bob");
        }).addCallback(
            function() {
                self.assertSubjectsAre(["Archived Message 2", "Archived Message 1"]);
                return makeMailViewChoice("Inbox");
        }).addCallback(
            function() {
                self.assertSubjectsAre([]);
        });
    });

Quotient.Test.ComposeController = Quotient.Compose.Controller.subclass('ComposeController');
Quotient.Test.ComposeController.methods(
    function saveDraft(self, userInitiated) {
        return;
    });

Quotient.Test.ComposeTestCase = Nevow.Athena.Test.TestCase.subclass('ComposeTestCase');
Quotient.Test.ComposeTestCase.methods(
    function run(self) {
        /* get the ComposeController */
        var controller = Quotient.Test.ComposeController.get(
                            Nevow.Athena.NodeByAttribute(
                                self.node.parentNode,
                                "athena:class",
                                "Quotient.Test.ComposeController"));

        var richAssertEquals = function(x, y, msg) {
            self.assertEquals(MochiKit.Base.compare(x, y), 0, msg || (x + " != " + y));
        }

        /* these are the pairs of [displayName, emailAddress] that we expect
         * the controller to have received from getPeople() */

        var moe     = ["Moe Aboulkheir", "maboulkheir@divmod.com"];
        var tobias  = ["Tobias Knight", "localpart@domain"];
        var madonna = ["Madonna", "madonna@divmod.com"];
        var kilroy  = ["", "kilroy@foo"];

        /**
         * For an emailAddress C{addr} (or part of one), assert that the list of
         * possible completions returned by ComposeController.completeCurrentAddr()
         * matches exactly the list of lists C{completions}, where each element
         * is a pair containing [displayName, emailAddress]
         */
        var assertCompletionsAre = function(addr, completions) {
            var _completions = controller.completeCurrentAddr(addr);
            richAssertEquals(_completions, completions,
                             "completions for " +
                             addr +
                             " are " +
                             _completions +
                             " instead of " +
                             completions);
        }

        /* map email address prefixes to lists of expected completions */
        var completionResults = {
            "m": [moe, madonna],
            "a": [moe],
            "ma": [moe, madonna],
            "maboulkheir@divmod.com": [moe],
            "Moe Aboulkheir": [moe],
            "AB": [moe],
            "k": [tobias, kilroy],
            "KnigHT": [tobias],
            "T": [tobias],
            "l": [tobias],
            "localpart@": [tobias]
        };

        /* check they match up */
        for(var k in completionResults) {
            assertCompletionsAre(k, completionResults[k]);
        }

        /* map each [displayName, emailAddress] pair to the result
         * we expect from ComposeController.reconstituteAddress(),
         * when passed the pair */
        var reconstitutedAddresses = [
            [moe, '"Moe Aboulkheir" <maboulkheir@divmod.com>'],
            [tobias, '"Tobias Knight" <localpart@domain>'],
            [madonna, '"Madonna" <madonna@divmod.com>'],
            [kilroy, '<kilroy@foo>']
        ];

        /* check they match up */
        for(var i = 0; i < reconstitutedAddresses.length; i++) {
            self.assertEquals(
                controller.reconstituteAddress(reconstitutedAddresses[i][0]),
                reconstitutedAddresses[i][1]);
        }
    });

Quotient.Test.GroupActionsTestCase = Quotient.Test.MailboxTestBase.subclass('GroupActionsTestCase');
Quotient.Test.GroupActionsTestCase.methods(
    function doTests(self) {
        var sw = self.mailbox.scrollWidget;

        var assertUnreadCountsAre = function(d) {
            var count, views = ["Inbox", "Trash", "Sent", "All", "Spam"];
            for(var i = 0; i < views.length; i++) {
                if(!(views[i] in d)) {
                    count = 0;
                } else {
                    count = d[views[i]];
                }
                self.assertEquals(self.unreadCountForView(views[i]), count);
            }
        }

        assertUnreadCountsAre({Inbox: 9, All: 9});

        /* select the first three messages */
        self.groupSelect(0);
        self.groupSelect(1);
        self.groupSelect(2);

        /* archive the first one */
        return self.mailbox.touch("archive", true).addCallback(
            function() {
                /* #1 got read when it was loaded into the message
                   detail after #0 was dismissed */
                assertUnreadCountsAre({Inbox: 8, All: 8});

                /* act on the group selection, checking the code
                   is smart enough not to explode when it finds
                   that one of the rows it wants to act on is missing */
                return self.mailbox.touchSelectedGroup("archive", true);
        }).addCallback(
            function() {
                /* #2 is gone from the inbox, and #3 was loaded
                   into the message detail, making 6 unread.
                   7 for All because #2 was the only unread
                   message that got moved there */
                assertUnreadCountsAre({Inbox: 6, All: 7});
        });
    });

Quotient.Test.MsgDetailTestBase = Nevow.Athena.Test.TestCase.subclass('MsgDetailTestBase');
Quotient.Test.MsgDetailTestBase.methods(
    /**
     * Assert that the msg detail header fields that belong
     * inside the "More Detail" panel are visible or not
     *
     * @param visible: boolean
     * @return: undefined
     */
    function assertMoreDetailVisibility(self, visible) {
        var rows = Nevow.Athena.NodesByAttribute(
                    self.node.parentNode, "class", "detailed-row");
        if(rows.length == 0) {
            self.fail("expected at least one 'More Detail' row");
        }
        for(var i = 0; i < rows.length; i++) {
            self.assertEquals(rows[i].style.display != "none", visible);
        }
    },

    function getMsgDetailWidget(self) {
        if(!self.widget) {
            self.widget = Quotient.Mailbox.MessageDetail.get(
                            Nevow.Athena.NodeByAttribute(
                                self.node.parentNode,
                                "athena:class",
                                "Quotient.Mailbox.MessageDetail"));
        }
        return self.widget;
    },

    /**
     * Find out the current value of the C{showMoreDetail} setting
     * @return: string
     */
     function getMoreDetailSetting(self) {
        return self.getMsgDetailWidget().callRemote("getMoreDetailSetting");
    },

    /**
     * Wrapper for the C{toggleMoreDetail} method on the
     * L{Quotient.Mailbox.MessageDetail} widget that's associated with
     * this test.
     */
    function toggleMoreDetail(self) {
        return self.getMsgDetailWidget().toggleMoreDetail();
    });

/**
 * Check that the message detail renders correctly
 */
Quotient.Test.MsgDetailTestCase = Quotient.Test.MsgDetailTestBase.subclass('MsgDetailTestCase');
Quotient.Test.MsgDetailTestCase.methods(
    function run(self) {
        var hdrs = Nevow.Athena.FirstNodeByAttribute(
                        self.node.parentNode, "class", "msg-header-table");
        var fieldvalues = {};
        var rows = hdrs.getElementsByTagName("tr");
        var cols, fieldname;

        for(var i = 0; i < rows.length; i++) {
            cols = rows[i].getElementsByTagName("td");
            if(cols.length < 2) {
                continue;
            }
            fieldname = cols[0].firstChild.nodeValue;
            fieldname = fieldname.toLowerCase().slice(0, -1);
            fieldvalues[fieldname] = cols[1].firstChild.nodeValue;
        }
        var assertFieldsEqual = function(answers) {
            for(var k in answers) {
                self.assertEquals(fieldvalues[k], answers[k]);
            }
        }

        assertFieldsEqual(
            {from: "sender@host",
             to: "recipient@host",
             subject: "the subject",
             sent: "Wed, 31 Dec 1969 19:00:00 -0500",
             received: "Wed, 31 Dec 1969 19:00:01 -0500"});

        return self.getMoreDetailSetting().addCallback(
            function(moreDetail) {
                self.assertEquals(moreDetail, false);
                self.assertMoreDetailVisibility(false);
                return self.toggleMoreDetail();
        }).addCallback(
            function() {
                return self.getMoreDetailSetting();
        }).addCallback(
            function(moreDetail) {
                self.assertEquals(moreDetail, true);
                self.assertMoreDetailVisibility(true);
                return self.toggleMoreDetail();
        }).addCallback(
            function() {
                return self.getMoreDetailSetting();
        }).addCallback(
            function(moreDetail) {
                self.assertEquals(moreDetail, false);
                self.assertMoreDetailVisibility(false);
        });
    });

Quotient.Test.MsgDetailInitArgsTestCase = Quotient.Test.MsgDetailTestBase.subclass(
                                                'MsgDetailInitArgsTestCase');
Quotient.Test.MsgDetailInitArgsTestCase.methods(
    function run(self) {
        self.assertMoreDetailVisibility(true);
    });


Quotient.Test.PostiniConfigurationTestCase = Nevow.Athena.Test.TestCase.subclass(
    'Quotient.Test.PostiniConfigurationTestCase');
Quotient.Test.PostiniConfigurationTestCase.methods(
    function run(self) {
        /**
         * Test that the postini configuration form is rendered with a checkbox
         * and a text field and that the checkbox defaults to unchecked and the
         * text field to "0.5".
         */
        var postiniConfig = self.childWidgets[0].childWidgets[0];
        var usePostiniScore = postiniConfig.nodeByAttribute(
            'name', 'usePostiniScore');
        var postiniThreshhold = postiniConfig.nodeByAttribute(
            'name', 'postiniThreshhold');

        self.assertEquals(usePostiniScore.checked, false);
        self.assertEquals(postiniThreshhold.value, '0.5');

        /**
         * Submit the form with different values and make sure they end up
         * changed on the server.
         */
        usePostiniScore.checked = true;
        postiniThreshhold.value = '5.0';

        return postiniConfig.submit().addCallback(
            function() {
                return self.callRemote('checkConfiguration');
            });
    });

