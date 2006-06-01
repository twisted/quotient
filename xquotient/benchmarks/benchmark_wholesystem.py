
"""
Create an axiom database configured with Mantissa, add a user with a POP3
grabber, run the POP3 grabber against a POP3 server which we also start up, and
run until all messages have been retrieved.
"""

import os

from twisted.python import filepath
from twisted.internet import reactor

from epsilon import extime
from epsilon.scripts import benchmark

from axiom import item, attributes, scheduler

from xquotient import grabber, mail
from xquotient.benchmarks.benchmark_initialize import initializeStore

# Number of messages which will be downloaded before we shut down.
TOTAL_MESSAGES = 50

def main():
    s, userStore = initializeStore()
    g = grabber.POP3Grabber(
        store=userStore,
        username=u"testuser",
        password=u"password",
        domain=u"127.0.0.1",
        port=12345)
    scheduler.IScheduler(userStore).schedule(g, extime.Time())
    StoppingMessageFilter(store=userStore).installOn(userStore)

    pop3server = filepath.FilePath(__file__).sibling("pop3server.tac")
    os.system("twistd -y " + pop3server.path)
    benchmark.start()
    os.system("axiomatic -d wholesystem.axiom start -n")
    benchmark.stop()
    os.system("kill `cat twistd.pid`")


if __name__ != '__main__':
    class StoppingMessageFilter(item.Item):
        messageCount = attributes.integer(default=0)

        def installOn(self, other):
            self.store.findUnique(mail.MessageSource).addReliableListener(self)

        def processItem(self, item):
            self.messageCount += 1
            if self.messageCount == TOTAL_MESSAGES:
                reactor.stop()
else:
    from xquotient.benchmarks.benchmark_wholesystem import StoppingMessageFilter
    main()
