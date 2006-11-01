// import Nevow.Athena.Test

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
     * Test receipt of timestamps from the server and their formatting.
     */
    function test_massageTimestamp(self) {
        self.setUp();
        self.callRemote('getTimestamp').addCallback(function (timestamp) {
                var date = new Date(timestamp*1000);
                self.assertEqual(self.scrollWidget.massageColumnValue(
                            "", "timestamp",
                            timestamp + date.getTimezoneOffset() * 60),
                                 "12:00 AM")});
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

        self.assertEqual(
            self.scrollWidget.formatDate(new Date(2006, 7, 21, 13, 1, 10),
                                         now), '1:01 PM');
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
        result.addCallback(function(widgetInfo) {
                return self.addChildWidgetFromWidgetInfo(widgetInfo);
            });
        result.addCallback(function(widget) {
                self.scrollingWidget = widget;
                self.node.appendChild(widget.node);

                /*
                 * XXX Clobber these methods, since our ScrollingWidget doesn't
                 * have a widgetParent which implements the necessary methods.
                 */
                widget.decrementActiveMailViewCount = function() {};
                widget.selectionChanged = function selectionChanged() {
                    return Divmod.Defer.succeed(null);
                };

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
                return self.scrollingWidget._selectWebID(webID).addCallback(
                    function(oldWebID) {
                        self.assertEqual(
                            oldWebID, null,
                            "Expected null as previously selected message ID.");
                    });
            });
    },

    /**
     * Test that selecting another message returns the message ID which was
     * already selected.
     */
    function test_secondSelectWebID(self) {
        return self.setUp().addCallback(function() {
                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                return self.scrollingWidget._selectWebID(webID).addCallback(
                    function(ignored) {
                        var otherWebID = self.scrollingWidget.model.getRowData(1).__id__;
                        return self.scrollingWidget._selectWebID(otherWebID).addCallback(
                            function(oldWebID) {
                                self.assertEqual(
                                    oldWebID, webID,
                                    "Expected first message ID as previous message ID.");
                            });
                    });
            });
    },

    /**
     * Test that the selected web ID determines the row returned by
     * L{getSelectedRow}.
     */
    function test_getSelectedRow(self) {
        return self.setUp().addCallback(function() {
                var webID;

                webID = self.scrollingWidget.model.getRowData(0).__id__;
                self.scrollingWidget._selectWebID(webID);
                self.assertEqual(self.scrollingWidget.getSelectedRow().__id__, webID);

                webID = self.scrollingWidget.model.getRowData(1).__id__;
                self.scrollingWidget._selectWebID(webID);
                self.assertEqual(self.scrollingWidget.getSelectedRow().__id__, webID);

                self.scrollingWidget._selectWebID(null);
                self.assertEqual(self.scrollingWidget.getSelectedRow(), null);
            });
    },

    /**
     * Test that removing the selection by passing C{null} to C{_selectWebID}
     * properly returns the previously selected message ID.
     */
    function test_unselectWebID(self) {
        return self.setUp().addCallback(function() {
                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                return self.scrollingWidget._selectWebID(webID).addCallback(
                    function(ignored) {
                        return self.scrollingWidget._selectWebID(null).addCallback(
                            function(oldWebID) {
                                self.assertEqual(
                                    oldWebID, webID,
                                    "Expected first message ID as previous message ID.");
                            });
                    });
            });
    },

    /**
     * Test that a row can be added to the group selection with
     * L{ScrollingWidget.groupSelectRow} and that the proper state is returned
     * for that row.
     */
    function test_groupSelectRow(self) {
        return self.setUp().addCallback(function() {
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
                var webID = self.scrollingWidget.model.getRowData(0).__id__;
                self.scrollingWidget.selectedGroup = {};
                self.scrollingWidget.selectedGroup[webID] = null;
                var state = self.scrollingWidget.groupSelectRow(webID);
                self.assertEqual(state, "off");
                self.assertEqual(
                    self.scrollingWidget.selectedGroup, null,
                    "Expected the selected group to be null.");
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
        result.addCallback(
            function(widgetInfo) {
                return self.addChildWidgetFromWidgetInfo(widgetInfo);
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
                    self.controllerWidget.getUnreadCountForView("inbox"), 1);

                self.assertEqual(
                    self.controllerWidget.getUnreadCountForView("spam"), 1);

                /*
                 * Three instead of four for the reason mentioned above.
                 */
                self.assertEqual(
                    self.controllerWidget.getUnreadCountForView("all"), 1);

                self.assertEqual(
                    self.controllerWidget.getUnreadCountForView("sent"), 0);
            });
    },

    /**
     * Test the mutation function for unread counts by view.
     */
    function test_setUnreadCounts(self) {
        return self.setUp().addCallback(function(ignored) {
                self.controllerWidget.setUnreadCountForView("inbox", 7);
                self.assertEquals(self.controllerWidget.getUnreadCountForView("inbox"), 7);
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
                self.assertEquals(rows[1]["date"], "4:05 PM");
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
                return self.controllerWidget.chooseMailView('all');
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
                return self.controllerWidget.chooseMailView('spam');
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
                return self.controllerWidget.chooseMailView('sent');
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
     * Test that the sent view has a "to" column instead of a "from" column.
     */
    function test_sentViewToColumn(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                /* Sanity check - sender should be displayed in this view.
                 */
                self.failIf(
                    self.controllerWidget.scrollWidget.skipColumn(
                        "senderDisplay"));
                self.failUnless(
                    self.controllerWidget.scrollWidget.skipColumn(
                        "recipient"));

                return self.controllerWidget.chooseMailView("sent");
            });
        result.addCallback(
            function(ignored) {
                var scrollWidget = self.controllerWidget.scrollWidget;

                self.failUnless(
                    self.controllerWidget.scrollWidget.skipColumn(
                        "senderDisplay"));
                self.failIf(
                    self.controllerWidget.scrollWidget.skipColumn(
                        "recipient"));

                /* Make sure the values are correct.
                 */
                var node = scrollWidget.model.getRowData(0).__node__;
                self.assertNotEqual(
                    node.innerHTML.indexOf('alice@example.com'),
                    -1);
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
                var result = self.controllerWidget.chooseMailView('all');
                result.addCallback(function(ignored) {
                        /*
                         * Next view only messages from Alice.
                         */
                        return self.controllerWidget.choosePerson(people[0].key);
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
                return self.controllerWidget.chooseTag('foo');
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

                var result = self.controllerWidget.chooseMailView('all');

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
                return self.controllerWidget.chooseMailView('all');
            });
        result.addCallback(
            function(ignored) {
                self.assertEqual(
                    self.controllerWidget.scrollWidget._selectedRowID,
                    self.controllerWidget.scrollWidget.model.getRowData(0).__id__,
                    "Expected first row to be selected after view change.");
            });
        return result;
    },

    /**
     * Test that the currently selected message can be archived.
     */
    function test_archiveCurrentMessage(self) {
        var model;
        var rowIdentifiers;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                return self.controllerWidget.archive(null);
            });
        result.addCallback(
            function(ignored) {
                return self.callRemote(
                    "archivedFlagsByWebIDs",
                    rowIdentifiers[0],
                    rowIdentifiers[1]);
            });
        result.addCallback(
            function(flags) {
                self.assertArraysEqual(
                    flags,
                    [true, false]);

                self.assertEqual(
                    model.getRowData(0).__id__, rowIdentifiers[1]);
            });
        return result;
    },

    /**
     * Test that an archive request issued while another is outstanding also
     * completes successfully.
     */
    function test_concurrentArchive(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var firstArchive = self.controllerWidget.archive(null);
                var secondArchive = self.controllerWidget.archive(null);
                return Divmod.Defer.gatherResults([firstArchive, secondArchive]);
            });
        result.addCallback(
            function(ignored) {
                self.assertEqual(self.controllerWidget.scrollWidget.model.rowCount(), 0);
                self.assertEqual(self.controllerWidget.scrollWidget.getSelectedRow(), null);
            });
        return result;
    },

    /**
     * Test that the checkbox for a row changes to the checked state when that
     * row is added to the group selection.
     */
    function test_groupSelectRowCheckbox(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var scroller = self.controllerWidget.scrollWidget;
                var row = scroller.model.getRowData(0);
                var webID = row.__id__;
                var checkboxImage = scroller._getCheckbox(row);
                scroller.groupSelectRowAndUpdateCheckbox(
                    webID, checkboxImage);
                /*
                 * The checkbox should be checked now.
                 */
                self.assertNotEqual(
                    checkboxImage.src.indexOf("checkbox-on.gif"), -1,
                    "Checkbox image was not the on image.");
            });
        return result;
    },

    /**
     * Test that the checkbox for a row changes to the unchecked state when
     * that row is removed from the group selection.
     */
    function test_groupUnselectRowCheckbox(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var scroller = self.controllerWidget.scrollWidget;
                var row = scroller.model.getRowData(0);
                var webID = row.__id__;
                var checkboxImage = scroller._getCheckbox(row);

                /*
                 * Select it first, so the next call will unselect it.
                 */
                scroller.groupSelectRow(webID);

                scroller.groupSelectRowAndUpdateCheckbox(
                    webID, checkboxImage);
                /*
                 * The checkbox should be checked now.
                 */
                self.assertNotEqual(
                    checkboxImage.src.indexOf("checkbox-off.gif"), -1,
                    "Checkbox image was not the on image.");
            });
        return result;
    },

    /**
     * Test changing the batch selection to all messages.
     */
    function test_changeBatchSelectionAll(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                self.controllerWidget.changeBatchSelection("all");

                var scroller = self.controllerWidget.scrollWidget
                var selected = scroller.selectedGroup;

                self.assertEqual(Divmod.dir(selected).length, 2);
                self.assertIn(scroller.model.getRowData(0).__id__, selected);
                self.assertIn(scroller.model.getRowData(1).__id__, selected);
            });
        return result;
    },

    /**
     * Test changing the batch selection to read messages.
     */
    function test_changeBatchSelectionRead(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                self.controllerWidget.changeBatchSelection("read");

                var scroller = self.controllerWidget.scrollWidget
                var selected = scroller.selectedGroup;

                self.assertEqual(Divmod.dir(selected).length, 1);
                self.assertIn(scroller.model.getRowData(0).__id__, selected);
            });
        return result;
    },

    /**
     * Test changing the batch selection to unread messages.
     */
    function test_changeBatchSelectionUnread(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                self.controllerWidget.changeBatchSelection("unread");

                var scroller = self.controllerWidget.scrollWidget
                var selected = scroller.selectedGroup;

                self.assertEqual(Divmod.dir(selected).length, 1);
                self.assertIn(scroller.model.getRowData(1).__id__, selected);
            });
        return result;
    },

    function _actionTest(self, viewName, individualActionNames, batchActionNames) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.chooseMailView(viewName);
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Make sure that each individual action's button is displayed,
                 * and any action not explicitly mentioned is hidden.
                 */
                var actions = self.controllerWidget.actions[viewName];
                var allActionNames = Divmod.dir(actions);
                var excludedActionNames = Divmod.dir(actions);

                for (var i = 0; i < individualActionNames.length; ++i) {
                    self.assertEqual(
                        actions[individualActionNames[i]].button.style.display,
                        "");

                    for (var j = 0; j < excludedActionNames.length; ++j) {
                        if (excludedActionNames[j] == individualActionNames[i]) {
                            excludedActionNames.splice(j, 1);
                            break;
                        }
                    }
                }

                /*
                 * All the other actions should be hidden.
                 */
                for (var i = 0; i < excludedActionNames.length; ++i) {
                    self.assertEqual(
                        actions[excludedActionNames[i]].button.style.display,
                        "none",
                        excludedActionNames[i] + " was available in " + viewName + " view.");
                }
            });
        return result;
    },

    /**
     * Test that the correct actions (and batch actions) are available in the inbox view.
     */
    function test_actionsForInbox(self) {
        return self._actionTest(
            "inbox",
            ["archive", "defer", "delete", "forward",
             "reply", "print", "train-spam"],
            ["archive", "delete", "train-spam"]);
    },

    /**
     * Like L{test_actionsForInbox}, but for the all view.
     */
    function test_actionsForAll(self) {
        return self._actionTest(
            "all",
            ["unarchive", "defer", "delete", "forward",
             "reply", "print", "train-spam"],
            ["unarchive", "delete", "train-spam"]);
    },

    /**
     * Like L{test_actionsForInbox}, but for the trash view.
     */
    function test_actionsForTrash(self) {
        return self._actionTest(
            "trash",
            ["undelete", "forward", "reply", "print"],
            ["undelete"]);
    },

    /**
     * Like L{test_actionsForInbox}, but for the spam view.
     */
    function test_actionsForSpam(self) {
        return self._actionTest(
            "spam",
            ["delete", "train-ham"],
            ["delete", "train-ham"]);
    },

    /**
     * Like L{test_actionsForInbox}, but for the deferred view.
     */
    function test_actionsForDeferred(self) {
        return self._actionTest(
            "deferred",
            ["forward", "reply", "print"],
            []);
    },

    /**
     * Like L{test_actionsForInbox}, but for the sent view.
     */
    function test_actionsForSent(self) {
        return self._actionTest(
            "sent",
            ["delete", "forward", "reply", "print"],
            ["delete"]);
    },

    /**
     * Test deleting the currently selected message batch.
     */
    function test_deleteBatch(self) {
        var rowIdentifiers;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                self.controllerWidget.changeBatchSelection("unread");
                return self.controllerWidget.trash(null);
            });
        result.addCallback(
            function(ignored) {
                return self.callRemote(
                    'deletedFlagsByWebIDs',
                    rowIdentifiers[0],
                    rowIdentifiers[1]);
            });
        result.addCallback(
            function(deletedFlags) {
                self.assertArraysEqual(
                    deletedFlags,
                    [false, true]);
            });
        return result;
    },

    /**
     * Test archiving the currently selected message batch.
     */
    function test_archiveBatch(self) {
        var rowIdentifiers;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                self.controllerWidget.changeBatchSelection("unread");
                return self.controllerWidget.archive(null);
            });
        result.addCallback(
            function(ignored) {
                return self.callRemote(
                    'archivedFlagsByWebIDs',
                    rowIdentifiers[0],
                    rowIdentifiers[1]);
            });
        result.addCallback(
            function(deletedFlags) {
                self.assertArraysEqual(
                    deletedFlags,
                    [false, true]);
            });
        return result;
    },

    /**
     * Test archiving a batch which includes the currently selected message.
     * This should change the message selection to the next message in the
     * mailbox.
     */
    function test_archiveBatchIncludingSelection(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                self.controllerWidget.changeBatchSelection("read");
                return self.controllerWidget.archive(null);
            });
        result.addCallback(
            function(ignored) {
                var model = self.controllerWidget.scrollWidget.model;
                self.assertEqual(
                    model.getRowData(0).__id__,
                    self.controllerWidget.scrollWidget.getSelectedRow().__id__);
            });
        return result;
    },

    /**
     * Test selecting every message in the view and then archiving them.
     */
    function test_archiveAllBySelection(self) {
        var rowNodes;
        var scroller;
        var model;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                scroller = self.controllerWidget.scrollWidget;
                model = scroller.model;

                var rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                rowNodes = [
                    model.getRowData(0).__node__,
                    model.getRowData(1).__node__];

                scroller.groupSelectRow(rowIdentifiers[0]);
                scroller.groupSelectRow(rowIdentifiers[1]);

                return self.controllerWidget.archive(null);
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Everything has been archived, make sure there are no rows
                 * left.
                 */
                self.assertEqual(model.rowCount(), 0);

                /*
                 * And none of those rows that don't exist in the model should
                 * be displayed, either.
                 */
                self.assertEqual(rowNodes[0].parentNode, null);
                self.assertEqual(rowNodes[1].parentNode, null);
            });
        return result;
    },

    /**
     * Test archiving the selected group of messages.
     */
    function test_archiveGroupSelection(self) {
        var rowIdentifiers;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                self.controllerWidget.scrollWidget.groupSelectRow(rowIdentifiers[1]);
                return self.controllerWidget.archive(null);
            });
        result.addCallback(
            function(ignored) {
                return self.callRemote(
                    'archivedFlagsByWebIDs',
                    rowIdentifiers[0],
                    rowIdentifiers[1]);
            });
        result.addCallback(
            function(deletedFlags) {
                self.assertArraysEqual(
                    deletedFlags,
                    [false, true]);
            });
        return result;
    },

    /**
     * Test archiving the selected group of messages, including the currently
     * selected message.
     */
    function test_archiveGroupSelectionIncludingSelection(self) {
        var model;
        var rowIdentifiers;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                self.controllerWidget.scrollWidget.groupSelectRow(rowIdentifiers[0]);
                return self.controllerWidget.archive(null);
            });
        result.addCallback(
            function(ignored) {
                self.assertEqual(
                    model.getRowData(0).__id__,
                    self.controllerWidget.scrollWidget.getSelectedRow().__id__);
                self.assertEqual(
                    model.getRowData(0).__id__,
                    rowIdentifiers[1]);
            });
        return result;
    },

    /**
     * Test the spam filter can be trained on a particular message.
     */
    function test_trainSpam(self) {
        var model;
        var rowIdentifiers;

        var result = self.setUp();
        result.addCallback(
            function(ignored) {

                model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__
                    ];

                return self.controllerWidget._trainSpam();
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Should have removed message from the current view, since it
                 * is not the spam view.
                 */
                self.assertEqual(model.rowCount(), 1);
                self.assertEqual(model.getRowData(0).__id__, rowIdentifiers[1]);

                /*
                 * Make sure the server thinks the message was trained as spam.
                 */
                return self.callRemote(
                    "trainedStateByWebIDs",
                    rowIdentifiers[0], rowIdentifiers[1]);
            });
        result.addCallback(
            function(trainedStates) {
                /*
                 * This one was trained as spam.
                 */
                self.assertEqual(trainedStates[0].trained, true);
                self.assertEqual(trainedStates[0].spam, true);

                /*
                 * This one was not.
                 */
                self.assertEqual(trainedStates[1].trained, false);
            });
        return result;
    },


    /**
     * Like L{test_trainSpam}, only for training a message as ham rather than
     * spam.
     */
    function test_trainHam(self) {
        var model;
        var rowIdentifiers;

        var result = self.setUp();
        result.addCallback(
            function(ignored) {

                /*
                 * Change to the spam view so training as ham will remove the
                 * message from the view.
                 */

                return self.controllerWidget.chooseMailView("spam");
            });
        result.addCallback(
            function(ignored) {
                model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [model.getRowData(0).__id__];

                return self.controllerWidget._trainHam();
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Should have removed message from the current view.
                 */
                self.assertEqual(model.rowCount(), 0);

                /*
                 * Make sure the server thinks the message was trained as spam.
                 */
                return self.callRemote(
                    "trainedStateByWebIDs", rowIdentifiers[0]);
            });
        result.addCallback(
            function(trainedStates) {
                /*
                 * It was trained as ham.
                 */
                self.assertEqual(trainedStates[0].trained, true);
                self.assertEqual(trainedStates[0].spam, false);
            });
        return result;
    },


    /**
     * Test that the utility method L{_getDeferralPeriod} returns the correct
     * values from the form in the document.
     */
    function test_getDeferralPeriod(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                var period;
                var form = self.controllerWidget.deferForm;
                var days = form.days;
                var hours = form.hours;
                var minutes = form.minutes;

                days.value = hours.value = minutes.value = 1;
                period = self.controllerWidget._getDeferralPeriod();
                self.assertEqual(period.days, 1);
                self.assertEqual(period.hours, 1);
                self.assertEqual(period.minutes, 1);

                days.value = 2;
                period = self.controllerWidget._getDeferralPeriod();
                self.assertEqual(period.days, 2);
                self.assertEqual(period.hours, 1);
                self.assertEqual(period.minutes, 1);

                hours.value = 3;
                period = self.controllerWidget._getDeferralPeriod();
                self.assertEqual(period.days, 2);
                self.assertEqual(period.hours, 3);
                self.assertEqual(period.minutes, 1);

                minutes.value = 4;
                period = self.controllerWidget._getDeferralPeriod();
                self.assertEqual(period.days, 2);
                self.assertEqual(period.hours, 3);
                self.assertEqual(period.minutes, 4);
            });
        return result;
    },

    /**
     * Like L{test_getDeferralPeriod}, but for the utility method
     * L{_deferralStringToPeriod} and L{_getDeferralSelection} (Sorry for
     * putting these together, I think this is a really icky test and I didn't
     * want to type out all this boilerplate twice -exarkun).
     */
    function test_deferralStringtoPeriod(self) {
        var result = self.setUp(self);
        result.addCallback(
            function(ignored) {
                var period;
                var node = self.controllerWidget.deferSelect;

                var deferralPeriods = {
                    "one-day": {
                        "days": 1,
                        "hours": 0,
                        "minutes": 0},
                    "one-hour": {
                        "days": 0,
                        "hours": 1,
                        "minutes": 0},
                    "twelve-hours": {
                        "days": 0,
                        "hours": 12,
                        "minutes": 0},
                    "one-week": {
                        "days": 7,
                        "hours": 0,
                        "minutes": 0}
                };

                var option;
                var allOptions = node.getElementsByTagName("option");
                for (var cls in deferralPeriods) {
                    option = Divmod.Runtime.theRuntime.firstNodeByAttribute(node, "class", cls);
                    period = self.controllerWidget._deferralStringToPeriod(option.value);
                    self.assertEqual(period.days, deferralPeriods[cls].days);
                    self.assertEqual(period.hours, deferralPeriods[cls].hours);
                    self.assertEqual(period.minutes, deferralPeriods[cls].minutes);

                    for (var i = 0; i < allOptions.length; ++i) {
                        if (allOptions[i] === option) {
                            node.selectedIndex = i;
                            break;
                        }
                    }
                    if (i == allOptions.length) {
                        self.fail("Could not find option node to update selection index.");
                    }
                    period = self.controllerWidget._getDeferralSelection();
                    self.assertEqual(period.days, deferralPeriods[cls].days);
                    self.assertEqual(period.hours, deferralPeriods[cls].hours);
                    self.assertEqual(period.minutes, deferralPeriods[cls].minutes);
                }
            });
        return result;
    },

    /**
     * Test the message deferral functionality.
     */
    function test_defer(self) {
        var model;
        var rowIdentifiers;

        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                model = self.controllerWidget.scrollWidget.model;

                rowIdentifiers = [
                    model.getRowData(0).__id__,
                    model.getRowData(1).__id__];

                return self.controllerWidget.formDefer();
            });
        result.addCallback(
            function(ignored) {
                self.assertEqual(model.rowCount(), 1);

                self.assertEqual(model.getRowData(0).__id__, rowIdentifiers[1]);

                return self.callRemote(
                    "deferredStateByWebIDs",
                    rowIdentifiers[0], rowIdentifiers[1]);
            });
        result.addCallback(
            function(deferredStates) {
                /*
                 * First message should have an undeferral time that is at
                 * least 30 minutes after the current time, since the minimum
                 * deferral time is 1 hour. (XXX This is garbage - we need to
                 * be able to test exact values here).
                 */
                self.assertNotEqual(deferredStates[0], null);
                self.failUnless(
                    deferredStates[0] - (30 * 60) > new Date().getTime() / 1000);
                /*
                 * Second message wasn't deferred
                 */
                self.assertEqual(deferredStates[1], null);
            });
        return result;
    },

    /**
     * Test that selecting the reply-to action for a message brings up a
     * compose widget.
     */
    function test_replyTo(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.replyTo(false);
            });
        result.addCallback(
            function(ignored) {
                var children = self.controllerWidget.childWidgets;
                var lastChild = children[children.length - 1];
                self.failUnless(lastChild instanceof Quotient.Compose.Controller);

                /*
                 * XXX Stop it from saving drafts, as this most likely won't
                 * work and potentially corrupts page state in ways which will
                 * break subsequent tests.
                 */
                lastChild.stopSavingDrafts();

                /*
                 * Make sure it's actually part of the page
                 */
                var parentNode = lastChild.node;
                while (parentNode != null && parentNode != self.node) {
                    parentNode = parentNode.parentNode;
                }
                self.assertEqual(parentNode, self.node);
            });
        return result;
    },

    /**
     * Test that selecting the forward action for a message brings up a
     * compose widget.
     */
    function test_forward(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.forward(false);
            });
        result.addCallback(
            function(ignored) {
                var children = self.controllerWidget.childWidgets;
                var lastChild = children[children.length - 1];
                self.failUnless(lastChild instanceof Quotient.Compose.Controller);

                /*
                 * XXX Stop it from saving drafts, as this most likely won't
                 * work and potentially corrupts page state in ways which will
                 * break subsequent tests.
                 */
                lastChild.stopSavingDrafts();

                /*
                 * Make sure it's actually part of the page
                 */
                var parentNode = lastChild.node;
                while (parentNode != null && parentNode != self.node) {
                    parentNode = parentNode.parentNode;
                }
                self.assertEqual(parentNode, self.node);
            });
        return result;
    },

    /**
     * Test that the send button on the compose widget returns the view to its
     * previous state.
     */
    function test_send(self) {
        var composer;
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.replyTo(false);
            });
        result.addCallback(
            function(ignored) {
                var children = self.controllerWidget.childWidgets;
                composer = children[children.length - 1];
                /*
                 * Sanity check.
                 */
                self.failUnless(composer instanceof Quotient.Compose.Controller);

                composer.stopSavingDrafts();

                return composer.submit();
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Composer should no longer be displayed.
                 */
                self.assertEqual(composer.node.parentNode, null);

                return composer.callRemote('getInvokeArguments');
            });
        result.addCallback(
            function(invokeArguments) {
                /*
                 * Should have been called once.
                 */
                self.assertEqual(invokeArguments.length, 1);

                self.assertArraysEqual(invokeArguments[0].toAddresses, ['alice@example.com']);
                self.assertArraysEqual(invokeArguments[0].cc, ['bob@example.com']);
                self.assertArraysEqual(invokeArguments[0].bcc, ['']);
                self.assertArraysEqual(invokeArguments[0].subject, ['Test Message']);
                self.assertArraysEqual(invokeArguments[0].draft, [false]);
                self.assertArraysEqual(invokeArguments[0].messageBody, ['message body text']);
            });
        return result;
    },

    /**
     * Test that a message in the trash can be undeleted.
     */
    function test_undelete(self) {
        var model;
        var rowIdentifier;

        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                model = self.controllerWidget.scrollWidget.model;
                return self.controllerWidget.chooseMailView("trash");
            });
        result.addCallback(
            function(ignored) {
                rowIdentifier = model.getRowData(0).__id__;
                return self.controllerWidget.untrash(null);
            });
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.chooseMailView("all");
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Undeleted message should be here _somewhere_.
                 */
                var row = model.findRowData(rowIdentifier);
            });
        return result;
    },

    /**
     * Test that a message in the archive can be unarchived.
     */
    function test_unarchive(self) {
        var model;
        var rowIdentifier;

        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                model = self.controllerWidget.scrollWidget.model;
                return self.controllerWidget.chooseMailView("all");
            });
        result.addCallback(
            function(ignored) {
                rowIdentifier = model.getRowData(0).__id__;
                return self.controllerWidget.unarchive(null);
            });
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.chooseMailView("inbox");
            });
        result.addCallback(
            function(ignored) {
                /*
                 * Undeleted message should be here _somewhere_.
                 */
                var row = model.findRowData(rowIdentifier);
            });
        return result;
    },

    /**
     * Test that the (undisplayed) Message.sender column is passed to the
     * scrolltable model
     */
    function test_senderColumn(self) {
        var model = self.controllerWidget.scrollWidget.model;
        self.failUnless(model.getRowData(0).sender);
    },

    /**
     * Test that the node generated for the "senderDisplay" column of the
     * first row
     */
    function test_cellNode(self) {
        var view = self.controllerWidget.scrollWidget;
        var rowData = view.model.getRowData(0);
        var cell = view.makeCellElement("senderDisplay", rowData);
        self.assertEqual(cell.title, rowData["sender"]);
        self.assertEqual(cell.firstChild.nodeValue, rowData["senderDisplay"]);
        self.assertEqual(cell.className, "sender");
    },

    /**
     * Test that changing the view from the view shortcut selector
     * changes the view and selects the corresponding list-item in
     * the main view selector.  Also test the inverse.
     */
    function test_viewShortcut(self) {
        var select = self.controllerWidget.viewShortcutSelect;
        var options = select.getElementsByTagName("option");
        var changeView = function(name) {
            for(var i = 0; i < options.length; i++) {
                if(options[i].value == name) {
                    select.selectedIndex = i;
                    return;
                }
            }
        }
        changeView("all");
        var D = self.controllerWidget.chooseMailViewByShortcutNode(select);
        return D.addCallback(
            function() {
                var viewSelectorNode = self.controllerWidget.mailViewNodes["all"];
                self.assertEqual(
                    viewSelectorNode.parentNode.className,
                    "selected-list-option");

                return self.controllerWidget.chooseMailViewByNode(
                            self.controllerWidget.mailViewNodes["inbox"].parentNode);
        }).addCallback(
            function() {
                self.assertEqual(select.value, "inbox");
        });
    },


    /**
     * Test that values passed to setMessageContent show up in the display.
     */
    function test_setMessageContent(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.callRemote('getMessageDetail');
            });
        result.addCallback(
            function(messageDetailInfo) {
                var subject = 'test subject string';
                self.controllerWidget.setMessageContent(
                    {subject: subject},
                    messageDetailInfo);
                self.assertNotEqual(self.controllerWidget.node.innerHTML.indexOf(subject), -1);

            });
        return result;
    },

    /**
     * Test that the subject of the message preview passed to setMessageContent
     * is properly escaped if necessary.
     */
    function test_setPreviewQuoting(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.callRemote('getMessageDetail');
            });
        result.addCallback(
            function(messageDetailInfo) {
                var subject = 'test <subject> & string';
                var escaped = 'test &lt;subject&gt; &amp; string';
                self.controllerWidget.setMessageContent(
                    {subject: subject},
                    messageDetailInfo);
                self.assertNotEqual(self.controllerWidget.node.innerHTML.indexOf(escaped), -1);

            });
        return result;
    },

    /**
     * @return: a function which can be added as a callback to a deferred
     * which fires with an L{Quotient.Compose.Controller} instance.  Checks
     * the the compose instance is inside the message detail of our
     * L{Quotient.Mailbox.Controller}, and has the "inline" attribute set
     */
    function _makeComposeTester(self) {
        return function(composer) {
            self.failUnless(
                composer instanceof Quotient.Compose.Controller);

            self.assertEqual(composer.node.parentNode,
                                self.controllerWidget.messageDetail);
            self.failUnless(composer.inline);

            return composer;
        }
    },

    /**
     * Test L{Quotient.Mailbox.Controller.splatComposeWidget} when not passed
     * composeInfo or reloadMessage.
     */
    function test_splatCompose(self) {
        var result = self.setUp();
        result.addCallback(
            function() {
                return self.controllerWidget.splatComposeWidget();
            });
        result.addCallback(self._makeComposeTester());
        return result;
    },

    /**
     * Test L{Quotient.Mailbox.Controller.splatComposeWidget} when passed a
     * composeInfo argument
     */
    function test_splatComposeComposeInfo(self) {
        var result = self.setUp();
        result.addCallback(
            function() {
                return self.controllerWidget.callRemote("getComposer");
            });
        result.addCallback(
            function(composeInfo) {
                return self.controllerWidget.splatComposeWidget(composeInfo);
            });
        result.addCallback(self._makeComposeTester());
    },

    /**
     * Test L{Quotient.Mailbox.Controller.reloadMessageAfterComposeCompleted}
     */
    function test_reloadMessageAfterComposeCompleted(self) {
        var cancelled = false;

        var result = self.setUp();
        result.addCallback(
            function() {
                return self.controllerWidget.splatComposeWidget();
            });
        result.addCallback(
            function(composer) {
                var controller = self.controllerWidget;
                var curmsg = controller.scrollWidget.getSelectedRow();
                var reload = controller.reloadMessageAfterComposeCompleted(composer);

                setTimeout(
                    function() {
                        composer.cancel();
                        cancelled = true;
                    }, 1000);

                return reload.addCallback(
                    function() {
                        return curmsg;
                    });
            });
        result.addCallback(
            function(curmsg) {
                self.failUnless(cancelled);

                /* check that the compose widget has been replaced with a
                 * message detail, and that the current message in the
                 * scrolltable is still curmsg */

                Nevow.Athena.Widget.get(
                    Nevow.Athena.FirstNodeByAttribute(
                        self.controllerWidget.messageDetail,
                        "athena:class",
                        "Quotient.Message.MessageDetail"));

                self.assertEqual(
                    self.controllerWidget.scrollWidget.getSelectedRow().__id__,
                    curmsg.__id__);
            });
        return result;
    }

    /**
     * XXX TODO
     *
     * - Test Controller.touchSelectedGroup including selected message
     */

    );


Quotient.Test.EmptyInitialViewControllerTestCase = Nevow.Athena.Test.TestCase.subclass(
    'Quotient.Test.EmptyInitialViewControllerTestCase');
Quotient.Test.EmptyInitialViewControllerTestCase.methods(
    /**
     * Retrieve a Controller Widget for an inbox from the server.
     */
    function setUp(self) {
        var result = self.callRemote('getControllerWidget');
        result.addCallback(
            function(widgetInfo) {
                return self.addChildWidgetFromWidgetInfo(widgetInfo);
            });
        result.addCallback(function(widget) {
                self.controllerWidget = widget;
                self.node.appendChild(widget.node);
                return self.controllerWidget.scrollWidget.initializationDeferred;
            });
        result.addCallback(function(widget) {
                return self.controllerWidget.chooseMailView('all');
            });
        return result;
    },

    /**
     * Test that the forward action works in this configuration.
     */
    function test_forward(self) {
        var result = self.setUp();
        result.addCallback(
            function(ignored) {
                return self.controllerWidget.forward(false);
            });
        result.addCallback(
            function(ignored) {
                var children = self.controllerWidget.childWidgets;
                var lastChild = children[children.length - 1];
                self.failUnless(lastChild instanceof Quotient.Compose.Controller);

                /*
                 * XXX Stop it from saving drafts, as this most likely won't
                 * work and potentially corrupts page state in ways which will
                 * break subsequent tests.
                 */
                lastChild.stopSavingDrafts();

                /*
                 * Make sure it's actually part of the page
                 */
                var parentNode = lastChild.node;
                while (parentNode != null && parentNode != self.node) {
                    parentNode = parentNode.parentNode;
                }
                self.assertEqual(parentNode, self.node);
            });
        return result;
    });



Quotient.Test.EmptyControllerTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.EmptyControllerTestCase');
Quotient.Test.EmptyControllerTestCase.methods(
    /**
     * Get an empty Controller widget and add it as a child to this test case's
     * node.
     */
    function setUp(self) {
        var result = self.callRemote('getEmptyControllerWidget');
        result.addCallback(
            function(widgetInfo) {
                return self.addChildWidgetFromWidgetInfo(widgetInfo);
            });
        result.addCallback(function(widget) {
                self.controllerWidget = widget;

                /*
                 * XXX
                 */
                widget.selectionChanged = function selectionChanged() {
                    return Divmod.Defer.succeed(null);
                };

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
                return self.controllerWidget.chooseMailView('all');
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

/**
 * Tests for Quotient.Compose.FromAddressScrollTable
 */
Quotient.Test.FromAddressScrollTableTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.FromAddressScrollTableTestCase');
Quotient.Test.FromAddressScrollTableTestCase.methods(
    /**
     * Retreive a L{Quotient.Compose.FromAddressScrollTable} from the server
     */
    function setUp(self)  {
        var result = self.callRemote("getFromAddressScrollTable");
        result.addCallback(
            function(widgetInfo) {
                return self.addChildWidgetFromWidgetInfo(widgetInfo);
            });
        result.addCallback(
            function(widget) {
                self.scrollTable = widget;
                self.node.appendChild(widget.node);
                return widget.initializationDeferred;
            });
        return result;
    },

    /**
     * @return: the scrolltable action with name C{name}
     * @rtype: L{Mantissa.ScrollTable.Action}
     */
    function getAction(self, name) {
        for(var i = 0; i < self.scrollTable.actions.length; i++){
            if(self.scrollTable.actions[i].name == name) {
                return self.scrollTable.actions[i];
            }
        }
        throw new Error("no action with name " + name);
    },

    /**
     * Test that the model contains the right stuff for the two FromAddress
     * items in the database
     */
    function test_model(self) {
        return self.setUp().addCallback(
            function() {
                self.assertEqual(self.scrollTable.model.rowCount(), 2);

                var first = self.scrollTable.model.getRowData(0);
                var second = self.scrollTable.model.getRowData(1);

                self.failUnless(first._default);
                self.failIf(second._default);
        });
    },

    /**
     * Test that the setDefaultAddress action works
     */
    function test_setDefaultAddress(self) {
        return self.setUp().addCallback(
            function() {
                var second = self.scrollTable.model.getRowData(1);
                var action = self.getAction("setDefaultAddress");
                return action.enact(self.scrollTable, second).addCallback(
                    function() {
                        second = self.scrollTable.model.getRowData(1)
                        var first = self.scrollTable.model.getRowData(0);

                        self.failUnless(second._default);
                        self.failIf(first._default);
                    })
            });
    },

    /**
     * Test that the delete & set default actions are disabled for the system
     * address, which is also the default
     */
    function test_actionsDisabled(self) {
        return self.setUp().addCallback(
            function() {
                var systemAddr = self.scrollTable.model.getRowData(0);
                self.failUnless(systemAddr._default);
                self.assertEqual(systemAddr.__id__, self.scrollTable.systemAddrWebID);

                var actions = self.scrollTable.getActionsForRow(systemAddr);
                self.assertEqual(actions.length, 0);

                var otherAddr = self.scrollTable.model.getRowData(1);
                actions = self.scrollTable.getActionsForRow(otherAddr);
                self.assertEqual(actions.length, 2);
            });
    },

    /**
     * Test the delete action
     */
    function test_deleteAction(self) {
        return self.setUp().addCallback(
            function() {
                var row = self.scrollTable.model.getRowData(1);
                var action = self.getAction("delete");
                return action.enact(self.scrollTable, row).addCallback(
                    function() {
                        self.assertEqual(self.scrollTable.model.rowCount(), 1);
                    });
            });
    });

Quotient.Test.ComposeController = Quotient.Compose.Controller.subclass('ComposeController');
Quotient.Test.ComposeController.methods(
    function saveDraft(self, userInitiated) {
        return;
    },

    function startSavingDrafts(self) {
        return;
    },

    function submitSuccess(self, passthrough) {
        return passthrough;
    });

Quotient.Test.ComposeTestCase = Nevow.Athena.Test.TestCase.subclass('ComposeTestCase');
Quotient.Test.ComposeTestCase.methods(
    /**
     * Test the name completion method
     * L{Quotient.Compose.Controller.reconstituteAddress} generates the correct
     * address lists for various inputs.
     */
    function test_addressCompletion(self) {
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
    }
    );

/**
 * Tests for roundtripping of recipient addresses
 */
Quotient.Test.ComposeToAddressTestCase = Nevow.Athena.Test.TestCase.subclass('Quotient.Test.ComposeToAddressTestCase');
Quotient.Test.ComposeToAddressTestCase.methods(
    /**
     * Retrieve a compose widget from the server, add it as a child widget
     *
     * @param key: unique identifier for the test method
     * @param fromAddress: comma separated string of email addresses with
     * which to seed the ComposeFragment.
     */
    function setUp(self, key, fromAddress) {
        var result  = self.callRemote('getComposeWidget', key, fromAddress);
        result.addCallback(
            function(widgetInfo) {
                return self.addChildWidgetFromWidgetInfo(widgetInfo);
            });
        result.addCallback(
            function(widget) {
                self.scrollingWidget = widget;
                self.node.appendChild(widget.node);
                return widget;
            });
        return result;
    },

    /**
     * Create a compose widget initialized with some from addresses, save a
     * draft, make sure that the server got the addresses which we specified
     */
    function test_roundtrip(self) {
        var addrs = ['foo@bar', 'bar@baz'];
        var result = self.setUp('roundtrip', addrs.join(', '));
        result.addCallback(
            function(composer) {
                /* save a draft, but bypass all the dialog/looping stuff */
                composer.nodeByAttribute("name", "draft").checked = true;
                return composer.submit();
            });
        result.addCallback(
            function(result) {
                self.assertArraysEqual(result, addrs);
            });
        return result;
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
            {from: '"Sender" <sender@host>',
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

Quotient.Test.MsgDetailAddPersonTestCase = Quotient.Test.MsgDetailTestBase.subclass(
                                                'MsgDetailAddPersonTestCase');

Quotient.Test.MsgDetailAddPersonTestCase.methods(
    /**
     * Test showing Add Person dialog, and adding a person
     */
    function test_addPerson(self) {
        var msg = self.getMsgDetailWidget();
        var sp = Nevow.Athena.Widget.get(
                    msg.firstNodeByAttribute(
                        "athena:class",
                        "Quotient.Common.SenderPerson"));
        sp.showAddPerson();

        self.assertEquals(sp.dialog.node.style.display, "");
        self.assertEquals(sp.dialog.node.style.position, "absolute");

        var dialogLiveForm = Nevow.Athena.Widget.get(sp.dialog.node.getElementsByTagName("form")[0]);

        return dialogLiveForm.submit().addCallback(
            function() {
                return self.callRemote("verifyPerson");
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

        var scrollWidget = Nevow.Athena.Widget.get(scrollerNode)
        scrollWidget.initializationDeferred.addCallback(
            function(ignored) {
                /* there is one grabber.  make sure the table is visible */
                self.assertEquals(scrollerNode.style.display, "");

                var D = self.callRemote("deleteGrabber");
                D.addCallback(
                    function() {
                        /* grabber has been deleted.  reload scrolltable */
                        D = scrollWidget.emptyAndRefill();
                        D.addCallback(
                            function() {
                                /* make sure it isn't visible */
                                self.assertEquals(scrollerNode.style.display, "none");
                            });
                        return D;
                    });
                return D;
            });
        return scrollWidget.initializationDeferred;
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
        var dialog = Quotient.Common.Util.showNodeAsDialog(node);

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
        self.assertEquals(dlgnode, dialog.node);

        self.assertEquals(orignode.style.display, "none");
        self.assertEquals(dlgnode.style.display, "");
        self.assertEquals(dlgnode.style.position, "absolute");

        dialog.hide();

        nodes = getElements();

        /* should be one, now that the dialog has been hidden */
        self.assertEquals(nodes.length, 1);
        self.assertEquals(nodes[0], orignode);
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
