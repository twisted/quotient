# -*- test-case-name: xquotient.test -*-

from zope.interface import Interface

class IMIMEDelivery(Interface):
    def createMIMEReceiver(source):
        """Create an object to accept a MIME message.

        @type source: C{unicode}
        @param source: A short string describing the means by which this
        Message came to exist. For example, u'mailto:alice@example.com' or
        u'pop3://bob@example.net'.

        @rtype: L{twisted.mail.smtp.IMessage}
        """



class IHamFilter(Interface):
    """
    Plugin for scoring messages based on their spaminess.
    """

    def score(message):
        """
        Score a message from [0.0..1.0]: lower is spammier.

        @type message: L{xquotient.exmess.Message}
        @param message: The message to score.
        """


    def train(spam, message):
        """
        Learn.

        @type spam: C{bool}
        @param spam: A flag indicating whether to train the given message as
        spam or ham.

        @type message: L{xquotient.exmess.Message}
        @param message: The message to train.
        """


    def forgetTraining():
        """
        Lose all stored training information.
        """



class IFilteringRule(Interface):
    """
    Defines a particular rule which defines items as either belonging to a
    particular category or being excluded from it.
    """

    def applyTo(item):
        """
        Determine if the indicated item is matched by this rule or not.

        @rtype: three-tuple of C{bool, bool, object}
        @return: The return value represents three pieces of information.
        The first boolean in the tuple indicates whether this rule matched.
        If it did not, the remaining two items are ignored.  If it did: the
        second boolean is interpreted as an indication of whether to proceed
        to subsequent rules or to stop rule processing here; the third value
        is treated as opaque and passed on through to the action stage of
        filtering.
        """


    def getAction():
        """
        Return the L{IFilteringAction} to take when this rule matches.
        """



class IFilteringAction(Interface):
    """
    Perform some action on an item which was matched by a rule.
    """

    def actOn(filteringPowerup, rule, item, extraData):
        """
        Actually perform some action.

        @param filteringPowerup: The powerup which is ostensibly in charge
        of this action.

        @param rule: The L{IFilteringRule} which matched the item being
        processed.

        @param item: The Item which was matched.

        @param extraData: The third element of the tuple returned by
        C{rule.applyTo}.
        """
