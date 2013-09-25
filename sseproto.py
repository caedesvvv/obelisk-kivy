from twisted.internet.protocol import ClientFactory, Protocol
from twisted.protocols.basic import LineReceiver
import json
import traceback

class PlnClient(LineReceiver):
    def __init__(self, cookies, event_cb):
        self.cookies = cookies
        self.event_cb = event_cb
        self._headers = ""
        self._data = ""
        self.last_size = 0

    def connectionMade(self):
        print "Connecting", self.cookies
        self.transport.write("GET /sse/ HTTP/1.1\r\n")
        self.transport.write("Host: pbx.lorea.org\r\n")
        for key, val in self.cookies.iteritems():
            # should be packed in one line.. Cookie: name=value; name2=value2
            self.transport.write("Cookie: %s=%s\r\n" % (key, val))
        self.transport.write("\r\n")
        self._data = ""

    def got_event(self, event_name, event_data):
        self.event_cb(event_name, event_data)

    def parse(self, data):
        eventline = False
        for line in data.split('\n'):
            if eventline:
                payload = line.split(':', 1)[-1].strip()
                try:
                    self.got_event(eventline, json.loads(payload))
                except:
                    print "error decoding event", eventline, len(payload)
                    """
                    f = open("/tmp/payload", "w")
                    f.write(payload)
                    f.close()
		    f = open("/tmp/all", "w")
		    f.write(self._data)
		    f.close()
                    """
                    traceback.print_exc()
            if line.startswith("event:"):
                eventline = line.split(':', 1)[-1].strip()
            else:
                creditline = False
                eventline = False
                
    def lineReceived(self, data):
        if self._headers:
            # getting data
            if self.last_size:
                self._data += data
            self.last_size = not self.last_size

            while "\n\n" in self._data:
                idx = self._data.find("\n\n")
                self.parse(self._data[:idx])
                self._data = self._data[idx+2:]
        else:
            # getting headers
            self._data += data

            if not data:
                self._headers = self._data
                self._data = ""

class PlnClientFactory(ClientFactory):
    protocol = PlnClient

    def __init__(self, cookies, event_cb):
        self.cookies = cookies
        self.event_cb = event_cb

    def clientConnectionFailed(self, connector, reason):
        print "Connection failed!"
        self.event_cb('disconnected', {})

    def clientConnectionLost(self, connector, reason):
        print "Connection lost!"
        self.event_cb('disconnected', {})

    def buildProtocol(self, addr):
        return PlnClient(self.cookies, self.event_cb)

