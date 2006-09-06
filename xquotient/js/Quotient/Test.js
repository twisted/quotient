// import Nevow.Athena.Test

// import Mantissa.Test

// import Quotient.Throbber
// import Quotient.Message
// import Quotient.Mailbox
// import Quotient.Compose

Quotient.Test.ThrobberTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.ThrobberTestCase');
Quotient.Test.ThrobberTestCase.methods(
    function setUp(self) {
        self.throbberNode = document.createElement('div');
        self.throbberNode.style.display = 'block';
        self.node.appendChild(self.throbberNode);
        self.throbber = Quotient.Throbber.Throbber(self.throbberNode);
    },

    /**
     * Test that the L{Throbber.startThrobbing} method sets the wrapped node's
     * style so that it is visible.
     */
    function test_startThrobbing(self) {
        self.setUp();

        self.throbber.startThrobbing();
        self.assertEqual(self.throbberNode.style.display, '');
    },

    /**
     * Test that the L{Throbber.stopThrobbing} method sets the wrapped node's
     * style so that it is invisible.
     */
    function test_stopThrobbing(self) {
        self.setUp();

        self.throbber.stopThrobbing();
        self.assertEqual(self.throbberNode.style.display, 'none');
    });


/**
 * Testable stand-in for the real throbber class.  Used by tests to assert that
 * the throbber is manipulated properly.
 */
Quotient.Test.TestThrobber = Divmod.Class.subclass("Quotient.Test.TestThrobber");
Quotient.Test.TestThrobber.methods(
    function __init__(self) {
        self.throbbing = false;
    },

    function startThrobbing(self) {
        self.throbbing = true;
    },

    function stopThrobbing(self) {
        self.throbbing = false;
    });


Quotient.Test.ScrollTableTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.ScrollTableTestCase');
Quotient.Test.ScrollTableTestCase.methods(
    /**
     * Find the ScrollWidget which is a child of this test and save it as a
     * convenient attribute for test methods to use.
     */
    function setUp(self) {
        self.scrollWidget = null;
        for (var i = 0; i < self.childWidgets.length; ++i) {
            if (self.childWidgets[i] instanceof Quotient.Mailbox.ScrollingWidget) {
                self.scrollWidget = self.childWidgets[i];
                break;
            }
        }
        self.assertNotEqual(self.scrollWidget, null, "Could not find ScrollingWidget.")
    },

    /**
     * Test the custom date formatting method used by the Mailbox ScrollTable.
     */
    function test_formatDate(self) {
        self.setUp();

        var now;

        /*
         * August 21, 2006, 1:36:10 PM
         */
        var when = new Date(2006, 7, 21, 13, 36, 10);

        /*
         * August 21, 2006, 5:00 PM
         */
        now = new Date(2006, 7, 21, 17, 0, 0);
        self.assertEqual(
            self.scrollWidget.formatDate(when, now), '1:36 PM',
            "Different hour context failed.");

        /*
         * August 22, 2006, 12:00 PM
         */
        now = new Date(2006, 7, 22, 12, 0, 0);
        self.assertEqual(
            self.scrollWidget.formatDate(when, now), 'Aug 21',
            "Different day context failed.");

        /*
         * September 22, 2006, 12:00 PM
         */
        now = new Date(2006, 8, 22, 12, 0, 0);
        self.assertEqual(
            self.scrollWidget.formatDate(when, now), 'Aug 21',
            "Different month context failed.");

        /*
         * January 12, 2007, 9:00 AM
         */
        now = new Date(2007, 1, 12, 9, 0, 0);
        self.assertEqual(
            self.scrollWidget.formatDate(when, now), '2006-08-21',
            "Different year context failed.");
    });


Quotient.Test.ScrollingWidgetTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.ScrollingWidgetTestCase');
Quotient.Test.ScrollingWidgetTestCase.methods(
    function setUp(self) {
        var result = self.callRemote('getScrollingWidget', 5);
        result.addCallback(function(widgetMarkup) {
                return Mantissa.Test.addChildWidgetFromMarkup(
                    self.node, widgetMarkup,
                    'Quotient.Mailbox.ScrollingWidget');
            });
        result.addCallback(function(widget) {
                self.scrollingWidget = widget;
                self.node.appendChild(widget.node);
                return widget.initializationDeferred;
            });
        return result;
    },

    /**
     * Test that selecting the first message in a
     * L{Quotient.Mailbox.ScrollingWidget} properly selects it and returns
     * C{null} as the previously selected message webID.
     */
    function test_firstSelectWebID(self) {
        return self.setUp().addCallback(function() {
                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                var result = self.scrollingWidget._selectWebID(webID);
                self.assertEqual(
                    result, null,
                    "Expected null as previously selected message ID.");
            });
    },

    /**
     * Test that selecting another message returns the message ID which was
     * already selected.
     */
    function test_secondSelectWebID(self) {
        return self.setUp().addCallback(function() {
                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                self.scrollingWidget._selectWebID(webID);
                var otherWebID = self.scrollingWidget.model.getRowData(1).__id__;
                var oldWebID = self.scrollingWidget._selectWebID(otherWebID);
                self.assertEqual(
                    oldWebID, webID,
                    "Expected first message ID as previous message ID.");
            });
    },

    /**
     * Test that removing the selection by passing C{null} to C{_selectWebID}
     * properly returns the previously selected message ID.
     */
    function test_unselectWebID(self) {
        return self.setUp().addCallback(function() {
                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                self.scrollingWidget._selectWebID(webID);
                var oldWebID = self.scrollingWidget._selectWebID(null);
                self.assertEqual(
                    oldWebID, webID,
                    "Expected first message ID as previous message ID.");
            });
    },

    /**
     * Test that a row can be added to the group selection with
     * L{ScrollingWidget.groupSelectRow} and that the proper state is returned
     * for that row.
     */
    function test_groupSelectRow(self) {
        return self.setUp().addCallback(function() {
                /*
                 * Test setup doesn't give the scrolling widget a parent which
                 * can toggle group actions.  Clobber that method on our
                 * instance so it doesn't explode.
                 *
                 * XXX This is terrible.  Find some way to remove it.
                 */
                self.scrollingWidget.enableGroupActions = function() {};

                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                var state = self.scrollingWidget.groupSelectRow(webID);
                self.assertEqual(state, "on");
                self.failUnless(
                    webID in self.scrollingWidget.selectedGroup,
                    "Expected selected webID to be in the selected group.");
            });
    },

    /**
     * Test that a row can be removed from the group selection with
     * L{ScrollingWidget.groupSelectRow} and that the proper state is returned
     * for that row.
     */
    function test_groupUnselectRow(self) {
        return self.setUp().addCallback(function() {
                /*
                 * Test setup doesn't give the scrolling widget a parent which
                 * can toggle group actions.  Clobber that method on our
                 * instance so it doesn't explode.
                 *
                 * XXX This is terrible.  Find some way to remove it.
                 */
                self.scrollingWidget.disableGroupActions = function() {};

                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                self.scrollingWidget.selectedGroup[webID] = null;
                var state = self.scrollingWidget.groupSelectRow(webID);
                self.assertEqual(state, "off");
                self.failIf(
                    webID in self.scrollingWidget.selectedGroup,
                    "Expected selected webID not to be in the selected group.");
            });
    },

    /**
     * Test that group actions are enabled when the first row is added to the
     * group selection.
     */
    function test_enableGroupActions(self) {
        return self.setUp().addCallback(function() {
                var enabled = false;
                self.scrollingWidget.enableGroupActions = function enableGroupActions() {
                    enabled = true;
                };

                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                var state = self.scrollingWidget.groupSelectRow(webID);
                self.failUnless(enabled, "Adding row should have enabled group actions.");
            });
    },

    /**
     * Test that group actions are disabled when the last row is removed from
     * the group selection.
     */
    function test_disableGroupActions(self) {
        return self.setUp().addCallback(function() {
                var disabled = false;
                self.scrollingWidget.disableGroupActions = function disableGroupActions() {
                    disabled = true;
                };

                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                self.scrollingWidget.selectedGroup[webID] = null;
                var state = self.scrollingWidget.groupSelectRow(webID);
                self.failUnless(disabled, "Removing row should have dsiabled group actions.");
            });
    }
    );


Quotient.Test.ControllerTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.ControllerTestCase');
Quotient.Test.ControllerTestCase.methods(
    /**
     * Utility method to extract data from display nodes and return it as an
     * array of objects mapping column names to values.
     */
    function collectRows(self) {
        var rows = self.controllerWidget.scrollWidget.nodesByAttribute(
            "class", "q-scroll-row");
        var divs, j, row;
        for (var i = 0; i < rows.length; i++) {
            divs = rows[i].getElementsByTagName("div");
            row = {};
            for (j = 0; j < divs.length; j++) {
                row[divs[j].className] = divs[j].firstChild.nodeValue;
            }
            rows[i] = row;
        }
        return rows;
    },

    /**
     * Retrieve a Controller Widget for an inbox from the server.
     */
    function setUp(self) {
        var result = self.callRemote('getControllerWidget');
        result.addCallback(function(widgetMarkup) {
                return Mantissa.Test.addChildWidgetFromMarkup(
                    self.node, widgetMarkup,
                    'Quotient.Mailbox.Controller');
            });
        result.addCallback(function(widget) {
                self.controllerWidget = widget;
                self.node.appendChild(widget.node);
                return self.controllerWidget.scrollWidget.initializationDeferred;
            });
        return result;
    },

    /**
     * Test that the L{getPeople} method returns an Array of objects describing
     * the people names visible.
     */
    function test_getPeople(self) {
        var result = self.setUp();
        result.addCallback(function(ignored) {
                var people = self.controllerWidget.getPeople();
                people.sort(function(a, b) {
                        if (a.name < b.name) {
                            return -1;
                        } else if (a.name == b.name) {
                            return 0;
                        } else {
                            return 1;
                        }
                    });
                self.assertEqual(people.length, 2);

                self.assertEqual(people[0].name, 'Alice');
                self.assertEqual(people[1].name, 'Bob');

                /*
                 * Check that the keys are actually associated with these
                 * people.
                 */
                var result = self.callRemote('personNamesByKeys',
                                             people[0].key, people[1].key);
                result.addCallback(function(names) {
                        self.assertArraysEqual(names, ['Alice', 'Bob']);
                    });
                return result;

            });
        return result;
    },

    /**
     * Test that the unread counts associated with various views are correct.
     * The specific values used here are based on the initialization the server
     * does.
     */
    function test_unreadCounts(self) {
        return self.setUp().addCallback(function(ignored) {
                /*
                 * This is one instead of two since rendering the page marks
                 * one of the unread messages as read.
                 */
                self.assertEqual(
                    self.controllerWidget.unreadCountForView("Inbox"), 1);

                self.assertEqual(
                    self.controllerWidget.unreadCountForView("Spam"), 1);

                /*
                 * Three instead of four for the reason mentioned above.
                 */
                self.assertEqual(
                    self.controllerWidget.unreadCountForView("All"), 1);

                self.assertEqual(
                    self.controllerWidget.unreadCountForView("Sent"), 0);
            });
    },

    /**
     * Test that the correct subjects show up in the view.
     */
    function test_subjects(self) {
        var result = self.setUp();
        result.addCallback(function(ignored) {
                var rows = self.collectRows();

                self.assertEqual(
                    rows.length, 2,
                    "Should have been 2 rows in the initial inbox view.");

                self.assertEquals(rows[0]["subject"], "2nd message");
                self.assertEquals(rows[1]["subject"], "1st message");
            });
        return result;
    },

    /**
     * Test that the correct dates show up in the view.
     */
    function test_dates(self) {
        var result = self.setUp();
        result.addCallback(function(ignored) {
                var rows = self.collectRows();

                self.assertEqual(
                    rows.length, 2,
                    "Should have been 2 rows in the initial inbox view.");

                /*
                 * Account for timezone differences.
                 */
                var date = new Date(
                    new Date(1999, 12, 13, 0, 0).valueOf() -
                    new Date().getTimezoneOffset() * 100000).getDate();

                self.assertEquals(rows[0]["date"], "1999-12-" + date);
                self.assertEquals(rows[1]["date"], "1999-12-" + date);
            });
        return result;
    },

    /**
     * Test that the correct list of people shows up in the chooser.
     */
    function test_people(self) {
        var result = self.setUp();
        result.addCallback(function(ignored) {
                var nodesByClass = function nodesByClass(root, value) {
                    return Divmod.Runtime.theRuntime.nodesByAttribute(
                        root, 'class', value);
                };
                /*
                 * Find the node which lets users select to view messages from
                 * a particular person.
                 */
                var viewSelectionNode = self.controllerWidget.contentTableGrid[0][0];
                var personChooser = nodesByClass(
                    viewSelectionNode, "person-chooser")[0];

                /*
                 * Get the nodes with the names of the people in the chooser.
                 */
                var personChoices = nodesByClass(personChooser, "list-option");

                /*
                 * Get the names out of those nodes.
                 */
                var personNames = [];
                var personNode = null;
                for (var i = 0; i < personChoices.length; ++i) {
                    personNode = nodesByClass(personChoices[i], "opt-name")[0];
                    personNames.push(personNode.firstChild.nodeValue);
                }

                personNames.sort();
                self.assertArraysEqual(personNames, ["Alice", "Bob"]);
            });
        return result;
    },

    /**
     * Test switching to the archive view.
     */
    function test_archiveView(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.switchView('All');
            });
        result.addCallback(
            function(ignored) {
                var rows = self.collectRows();

                self.assertEqual(
                    rows.length, 4,
                    "Should have been 4 rows in the archive view.");

                self.assertEqual(rows[0]["subject"], "4th message");
                self.assertEqual(rows[1]["subject"], "3rd message");
                self.assertEqual(rows[2]["subject"], "2nd message");
                self.assertEqual(rows[3]["subject"], "1st message");
            });
        return result;
    },

    /**
     * Test switching to the spam view.
     */
    function test_spamView(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.switchView('Spam');
            });
        result.addCallback(
            function(ignored) {
                var rows = self.collectRows();

                self.assertEqual(
                    rows.length, 1,
                    "Should have been 1 row in the spam view.");

                self.assertEqual(rows[0]["subject"], "5th message");
            });
        return result;
    },

    /**
     * Test switching to the sent view.
     */
    function test_sentView(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.switchView('Sent');
            });
        result.addCallback(
            function(ignored) {
                var rows = self.collectRows();

                self.assertEqual(
                    rows.length, 1,
                    "Should have been 1 row in the sent view.");

                self.assertEqual(rows[0]["subject"], "6th message");
            });
        return result;
    },

    /**
     * Test switching to a view of messages from a particular person.
     */
    function test_personView(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var people = self.controllerWidget.getPeople();

                /*
                 * I know the first one is Alice, but I'll make sure.
                 */
                self.assertEqual(people[0].name, 'Alice');

                /*
                 * Change to the all view, so that we see all messages instead
                 * of just inbox messages.
                 */
                var result = self.controllerWidget.switchView('All');
                result.addCallback(function(ignored) {
                        /*
                         * Next view only messages from Alice.
                         */
                        return self.controllerWidget._sendViewRequest(
                            'viewByPerson', people[0].key);
                    });

                /*
                 * Once that is done, assert that only Alice's messages show
                 * up.
                 */
                result.addCallback(function(ignored) {
                        var rows = self.collectRows();

                        self.assertEquals(
                            rows.length, 4, "Should have been 4 rows in Alice view.");

                        self.assertEquals(rows[0]["subject"], "4th message");
                        self.assertEquals(rows[1]["subject"], "3rd message");
                        self.assertEquals(rows[2]["subject"], "2nd message");
                        self.assertEquals(rows[3]["subject"], "1st message");
                    });
                return result;
            });
        return result;
    },

    /**
     * Test switching to a view of messages with a particular tag.
     */
    function test_tagView(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                /*
                 * Change to the view of messages with the foo tag.
                 */
                return self.controllerWidget._sendViewRequest(
                    'viewByTag', 'foo');
            });
        /*
         * Once the view is updated, test that only the message tagged "foo" is
         * visible.
         */
        result.addCallback(
            function(ignored) {
                var rows = self.collectRows();

                self.assertEquals(
                    rows.length, 1, "Should have been 1 row in the 'foo' tag view.");

                self.assertEquals(rows[0]["subject"], "1st message");
            });
        return result;
    },

    /**
     * Test that sending a view request starts the throbber throbbing and that
     * when the request has been completed the throbber stops throbbing.
     */
    function test_throbberStates(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                /*
                 * Hook the throbber.
                 */
                self.throbber = Quotient.Test.TestThrobber();
                self.controllerWidget.scrollWidget.throbber = self.throbber;

                var result = self.controllerWidget.switchView('All');

                /*
                 * Throbber should have been started by the view change.
                 */
                self.failUnless(
                    self.throbber.throbbing,
                    "Throbber should have been throbbing after view request.");

                return result;
            });
        result.addCallback(
            function(ignored) {
                /*
                 * View has been changed, the throbber should have been stopped.
                 */
                self.failIf(
                    self.throbber.throbbing,
                    "Throbber should have been stopped after view change.");
            });
        return result;
    },

    /**
     * Test that the first row of the initial view is selected after the widget
     * loads.
     */
    function test_initialSelection(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                self.assertEqual(
                    self.controllerWidget.scrollWidget._selectedRowID,
                    self.controllerWidget.scrollWidget.model.getRowData(0).__id__,
                    "Expected first row to be selected.");
            });
        return result;
    },

    /**
     * Test that the first row after a view change completes is selected.
     */
    function test_viewChangeSelection(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.switchView('All');
            });
        result.addCallback(
            function(ignored) {
                self.assertEqual(
                    self.controllerWidget.scrollWidget._selectedRowID,
                    self.controllerWidget.scrollWidget.model.getRowData(0).__id__,
                    "Expected first row to be selected after view change.");
            });
        return result;
    }

    /**
     * XXX TODO
     *
     * - Test Controller.toggleGroupActions
     * - Test Controller.disableGroupActions
     * - Test Controller.touchSelectedGroup
     * - Test Controller.changeBatchSelection
     * - Test Controller.touchBatch
     */

    );


Quotient.Test.EmptyControllerTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.EmptyControllerTestCase');
Quotient.Test.EmptyControllerTestCase.methods(
    /**
     * Get an empty Controller widget and add it as a child to this test case's
     * node.
     */
    function setUp(self) {
        var result = self.callRemote('getEmptyControllerWidget');
        result.addCallback(function(widgetMarkup) {
                return Mantissa.Test.addChildWidgetFromMarkup(
                    self.node, widgetMarkup,
                    'Quotient.Mailbox.Controller');
            });
        result.addCallback(function(widget) {
                self.controllerWidget = widget;
                self.node.appendChild(widget.node);
                return widget.initializationDeferred;
            });
        return result;
    },

    /**
     * Test that loading an empty mailbox doesn't result in any errors, that no
     * message is initially selected, etc.
     */
    function test_emptyLoad(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                self.assertEqual(
                    self.controllerWidget.scrollWidget._selectedRowID,
                    null,
                    "No rows exist, so none should have been selected.");
            });
        return result;
    },

    /**
     * Test that switching to an empty view doesn't result in any errors, that
     * no message is initially selected, etc.
     */
    function test_emptySwitch(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.switchView('All');
            });
        result.addCallback(
            function(ignored) {
                self.assertEqual(
                    self.controllerWidget.scrollWidget._selectedRowID,
                    null,
                    "No rows exist, so none should have been selected.");
            });
        return result;
    }
    );

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
            self.widget = Quotient.Message.MessageDetail.get(
                            Nevow.Athena.NodeByAttribute(
                                self.node.parentNode,
                                "athena:class",
                                "Quotient.Message.MessageDetail"));
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
     * L{Quotient.Message.MessageDetail} widget that's associated with
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

Quotient.Test.AddGrabberTestCase = Nevow.Athena.Test.TestCase.subclass(
                                        'Quotient.Test.AddGrabberTestCase');

Quotient.Test.AddGrabberTestCase.methods(
    function test_addGrabber(self) {
        var form = Nevow.Athena.Widget.get(
                        self.firstNodeByAttribute(
                            'athena:class',
                            'Quotient.Grabber.AddGrabberFormWidget'));
        var inputs = form.gatherInputs();

        inputs['domain'].value = 'foo.bar';
        inputs['username'].value = 'foo';
        inputs['password1'].value = 'foo';
        inputs['password2'].value = 'zoo';

        return form.submit().addErrback(
            function() {
                self.fail('AddGrabberFormWidget did not catch the submit error');
            });
    });

Quotient.Test.GrabberListTestCase = Nevow.Athena.Test.TestCase.subclass(
                                        'Quotient.Test.GrabberListTestCase');

Quotient.Test.GrabberListTestCase.methods(
    /**
     * Test that the grabber list is initially visible when
     * we have one grabber, and that it becomes invisible when
     * we delete the grabber
     */
    function test_visibility(self) {
        var scrollerNode = self.firstNodeByAttribute(
                            "class", "scrolltable-widget-node");

        /* there is one grabber.  make sure the table is visible */
        self.assertEquals(scrollerNode.style.display, "");

        var D = self.callRemote("deleteGrabber");
        D.addCallback(
            function() {
                /* grabber has been deleted.  reload scrolltable */
                D = Nevow.Athena.Widget.get(scrollerNode).emptyAndRefill();
                D.addCallback(
                    function() {
                        /* make sure it isn't visible */
                        self.assertEquals(scrollerNode.style.display, "none");
                    });
                return D;
            });
        return D;
    });

Quotient.Test.ShowNodeAsDialogTestCase = Nevow.Athena.Test.TestCase.subclass(
                                            'Quotient.Test.ShowNodeAsDialogTestCase');

Quotient.Test.ShowNodeAsDialogTestCase.methods(
    function test_showNodeAsDialog(self) {
        /* get the original node */
        var node = self.firstNodeByAttribute(
                        "class",
                        "ShowNodeAsDialogTestCase-dialog");
        /* show it as a dialog */
        Quotient.Common.Util.showNodeAsDialog(node);

        var getElements = function() {
            return Nevow.Athena.NodesByAttribute(
                    document.body,
                    "class",
                    "ShowNodeAsDialogTestCase-dialog");
        }

        /* get all elements with the same class name as our node */
        var nodes = getElements();

        /* should be two - the original and the cloned dialog */
        self.assertEquals(nodes.length, 2);
        var orignode = nodes[0], dlgnode = nodes[1];

        self.assertEquals(orignode.style.display, "none");
        self.assertEquals(dlgnode.style.display, "");
        self.assertEquals(dlgnode.style.position, "absolute");
    });

Quotient.Test.DraftsTestCase = Nevow.Athena.Test.TestCase.subclass(
                                    'Quotient.Test.DraftsTestCase');

/**
 * Tests for xquotient.compose.DraftsScreen
 */
Quotient.Test.DraftsTestCase.methods(
    /**
     * Get a handle on the drafts scrolltable, and return
     * a deferred that'll fire when it's done initializing
     */
    function setUp(self) {
        if(!self.scroller) {
            self.scroller = Nevow.Athena.Widget.get(
                                self.firstNodeByAttribute(
                                    "athena:class",
                                    "Quotient.Compose.DraftListScrollingWidget"));
        }
        return self.scroller.initializationDeferred;
    },

    /**
     * Basic test, just make sure the scrolltable can initialize
     */
    function test_initialization(self) {
        return self.setUp();
    },

    /**
     * Assert that the rows in the drafts scrolltable have subjects
     * that match those of the items created by our python counterpart
     */
    function test_rows(self) {
        return self.setUp().addCallback(
            function() {
                for(var i = 4; i <= 0; i--) {
                    self.assertEquals(
                        parseInt(self.scroller.model.getRowData(i).subject), i);
                }
            });
    });
