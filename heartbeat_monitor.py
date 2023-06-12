from handlers import STATUS, KeepAlive, SyslogHandler, CloudAPIHandler, EmailHandler
from response import Response


# ===========================================================================
import threading
import time



# This class should probably 'own' the KeepAlives dict and just expose a method
# that the API server can call to add a new KeepAlive object (this method should
# also perform the (delegated) KA validation and let the API server know what
# to tell the calling clients...
class HeartbeatMonitor(threading.Thread):
    TickInterval = 10
    Handlers = { }
    KeepAlives = { }
    TimeFormats = [ '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S' ]


    def __init__(self):
        threading.Thread.__init__(self)

        self.syslog = SyslogHandler()
        self.registerHandler(self.syslog)


    def run(self):
        while True:
            # take the time to process tick() into account
            self.tick()
            time.sleep(self.TickInterval)


    def registerHandler(self, h):
        self.Handlers[h.name] = h


    def registerKeepAlive(self, endpoint, ka):
        #print(f"ka.metadata = '{ka.metadata}'")
        if 'disabled-until' in ka.metadata:
            for fmt in self.TimeFormats:
                try:
                    ka.validUntil = max(ka.validUntil, int(time.mktime(time.strptime(ka.metadata['disabled-until'], fmt))))
                except:
                    pass
        # print(f"expires in {round(ka.validUntil - time.time())} seconds")

        unsupportedKAHandlers = []
        for h in ka.handlers:
            if h['handler'] not in self.Handlers:
                unsupportedKAHandlers.append(h['handler'])
                self.syslog.debug(f"HeartbeatMonitor.registerKeepAlive() : ignoring unsupported handler {h}")
                ka.handlers.remove(h)

        # validation = self.Handlers[h['handler']].validateKeepAlive(ka)
        # if validation.statusCode == 200:
        self.KeepAlives[endpoint] = ka
        # else:
        #     print(validation)

        print(f"{unsupportedKAHandlers}")
        return unsupportedKAHandlers


    def tick(self):
        # Go through self.KeepAlives, and place any items that have 'expired'
        # into __ExpiredKeepAlives so they can be processed in the next section
        self.__ExpiredKeepAlives = {}
        for key, keepalive in self.KeepAlives.items():
            if time.time() > keepalive.validUntil:
                self.__ExpiredKeepAlives[key] = keepalive
                self.syslog.debug(f"HeartbeatMonitor.tick() : KeepAlive {key} has expired")

        # And pass each expired KeepAlive to their respective handlers; note
        # that we don't need to check if i['handler'] is in self.Handlers, as
        # this was already done by registerKeepAlive()...
        for key, keepalive in self.__ExpiredKeepAlives.items():
            for i in keepalive.handlers:
                self.syslog.debug(f"HeartbeatMonitor.tick() : about to call handler {i['handler']} for {key} with arguments ({keepalive.metadata}, {i['data']})")
                i['keepalive']['status'] = STATUS.BEING_PROCESSED
                # should probably define (and save) return value and set i['keepalive'] accordingly
                self.Handlers[i['handler']].process(keepalive.metadata, i['data'])
                i['keepalive']['status'] = STATUS.EXPIRATION_HANDLED
                i['keepalive']['message'] = ''

            # Should probably also pop the KeepAlive from __ExpiredKeepAlives
            # iff all of their handlers could be successfully processed, and
            # log any issues 
            self.KeepAlives.pop(key)


    def printKeepAlives(self):
        for k, v in self.KeepAlives.items():
            if v.validUntil > time.time():
                print(f"{k} (valid for another {v.validUntil - round(time.time())} seconds) -->")
            else:
                print(f"{k} (expired {round(time.time()) - v.validUntil} seconds ago) -->")
            for i in v.handlers:
                print(f"    {i}")







# ===========================================================================
if __name__ == '__main__':
    import time
    import json
    import os


    vm1 = json.load(open('server--subcontract-1--vm-1.json'))
    vm2 = json.load(open('server--subcontract-2--vm-1.json'))
    vm3 = json.load(open('server--invalid-contract--vm.json'))

    HandlerConfigs = json.load(open('handler-configs.json'))


    HM = HeartbeatMonitor() 
    HM.registerHandler(CloudAPIHandler(HandlerConfigs[CloudAPIHandler.name] if CloudAPIHandler.name in HandlerConfigs else {}))
    HM.registerHandler(EmailHandler(HandlerConfigs[EmailHandler.name] if EmailHandler.name in HandlerConfigs else {}))

    HM.start()

    def pushKA(d, timeOffset = 15):
        HM.registerKeepAlive('server/{uuid}'.format(**d['metadata']), KeepAlive(time.time() + timeOffset, d['metadata'], d['handlers']))
