
"""
Tests for the upgrader from version 4 to version 5 of quotient's Message
item.
"""

from axiom.test.historic.stubloader import StubbedTest

from xquotient.exmess import (Message, MailboxSelector,
                              INBOX_STATUS,
                              ARCHIVE_STATUS,
                              UNREAD_STATUS,
                              READ_STATUS,
                              DEFERRED_STATUS,
                              DRAFT_STATUS,
                              CLEAN_STATUS,
                              SENT_STATUS)

class MessageUpgradeTest(StubbedTest):

    def assertMessages(self, statuses, messageIndexes):
        """
        Fail this test unless the result of a listing of given message statuses
        matches the given message indices.

        @param statuses: a list of unicode status strings.

        @param messageIndexes: a list of message indexes.
        """
        sq = MailboxSelector(self.store)
        for statusName in statuses:
            sq.refineByStatus(statusName)
        self.assertMessageQuery(sq, messageIndexes)

    def assertMessageQuery(self, ms, messageIndexes):
        """
        Fail this test unless the result of a given mailbox selector matches
        the given message indices.

        @param statuses: a list of unicode status strings.

        @param messageIndexes: a list of message indexes.
        """
        self.assertEquals(
            set(map(self.messageList.index, list(ms))),
            set(messageIndexes))

    def setUp(self):
        """
        Load stub as usual, then set up properly ordered list for
        assertMessages.
        """
        r = super(MessageUpgradeTest, self).setUp()
        def setupList(result):
            self.messageList = list(
                self.store.query(Message, sort=Message.storeID.ascending))

        return r.addCallback(setupList)


    def test_statusesStayTheSame(self):
        """
        Verify that messages upgraded from the stub have appropriate statuses.
        """
        self.assertMessages([INBOX_STATUS], [0])
        self.assertMessages([ARCHIVE_STATUS], [1])
        self.assertMessages([UNREAD_STATUS], [0, 1, 3, 4, 5, 6, 7])
        self.assertMessages([READ_STATUS], [2])
        self.assertMessages([DEFERRED_STATUS], [2])
        self.assertMessages([DRAFT_STATUS], [4])
        # this next check here verifies that the 'CLEAN_STATUS' was unfrozen by
        # the upgrader.
        self.assertMessages([CLEAN_STATUS], [0, 1, 2])
        # Really tested by workflow tests, but sanity check:
        self.assertMessages([UNREAD_STATUS, CLEAN_STATUS], [0, 1])
        self.assertMessages([SENT_STATUS], [3])

