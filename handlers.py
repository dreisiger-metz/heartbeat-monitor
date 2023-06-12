# ===========================================================================
import enum
import time
import json
from abc import ABC, abstractmethod

from response import Response




class STATUS(enum.Enum):
    UNDEFINED = 0
    VALID = 1
    EXPIRED = 2
    BEING_PROCESSED = 3
    EXPIRATION_HANDLED = 4
    EXPIRATION_HANDLING_FAILED = 5    # the WatchdogMonitor needs to create a SyslogHandler entry in this case


class KeepAlive:
    def __init__(self, validUntil: float, metadata: dict, handlers: dict):
        self.validUntil = round(validUntil)
        self.metadata = metadata
        self.handlers = handlers

        for h in self.handlers:
            h['keepalive'] = { 'status': STATUS.VALID, 'message': '' }






# https://plainenglish.io/blog/specifying-data-types-in-python-c182fda3bf43#specifying-types-of-lists--dictionaries
# https://stackoverflow.com/questions/2489669/how-do-python-functions-handle-the-types-of-parameters-that-you-pass-in
# https://docs.python.org/3/library/typing.html
class BaseHandler(ABC):
    """The abstract base class of our Handler classes"""

    name = "heartbeat-monitor.basehandler"

    def __init__(self):
        pass


    @abstractmethod
    def process(self, metadata: dict, body: dict):
        """This method must be implemented by a child class"""
        pass


    def validateKeepAlive(self, metadata: dict, body: dict):
        return [ False, 'validator not implimented' ]






# ===========================================================================
import logging
import logging.handlers
import os

class SyslogHandler(BaseHandler):
    name = "heartbeat-monitor.syslog"

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger('heartbeat-monitor')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.handlers.SysLogHandler(address = '/dev/log'))


    def debug(self, message):
        self.logger.debug(f"heartbeat-monitor[{os.getpid()}]: {message}")


    def process(self, metadata: dict, data: dict):
        self.logger.info(f"heartbeat-monitor[{os.getpid()}]: " + data['message'].format(**metadata))


    def validateKeepAlive(self, metadata: dict, data: dict):
        return Response(200, 'OK')






# ===========================================================================
import json
import requests


class CloudAPIHandler(BaseHandler):
    name = "com.ionos.api.cloud"
    api_url = "https://api.ionos.com/cloudapi/v6/"

    def __init__(self, CloudAPIConfig: dict):
        super().__init__()

        self.CloudAPIConfig = CloudAPIConfig
        self.session = requests.Session()


    #def testfn(d: dict) -> int:
    def process(self, metadata, data):
        validation = self.validateKeepAlive(metadata, data)

        if validation.statusCode == 200:
            self.session.headers = { 'Authorization': f'Bearer {self.CloudAPIConfig["tokens"][metadata["contract-number"]]}',
                                     'X-Contract-Number': metadata['contract-number'] }
            #res = self.session.post(self.api_url + data['endpoint'].format(**metadata))

            # to-do: wait for request to complete (or add the Request-ID to a monitoring loop)

            #return res
    
        else:
            print(validation)
            # body['keepalive']['status'] = STATUS.EXPIRATION_HANDLING_FAILED
            # body['keepalive']['message'] = validate[1]

        #print(f"{res.headers['Date']}: POST {DATACENTER_UUID}/servers, Status: {res.status_code}")


    def validateKeepAlive(self, metadata, body):
        # make sure metadata['contract-number'] is in self.CloudAPIConfig['tokens']
        if metadata['contract-number'] in self.CloudAPIConfig['tokens']:
            return Response(200, 'OK')
        else:
            return Response(404, 'Resource not found', f'Information about Contract-Number {metadata["contract-number"]} not contained in CloudAPIConfig')
    

    # as per https://github.com/ionos-cloud/sdk-python/blob/master/ionoscloud/api_client.py#L773
    def wait_for_completion(self, requestID, timeout=600, initial_wait=2, scaleup=10):
        timeout = time.time() + timeout
        wait_period = initial_wait
        scaleup = scaleup
        next_increase = time.time() + wait_period * scaleup

        request = "https://api.ionos.com/cloudapi/v6/requests/{request_id}/status"

        while True:
            res = self.session.get(requestID)
            status = json.loads(res._content)['metadata']['status']

            if status == 'DONE':
                print(f"Call for request {requestID} successfully completed")
                break

            elif status == 'FAILED':
                print(f"Call failed with error {json.loads(res._content)['metadata']['message']}")
                #sys.exit(2)
            
            current_time = time.time()
            if current_time > timeout:
                print(f"Call for request {requestID} has timed out")
                #sys.exit(3)

            if current_time > next_increase:
                wait_period *= 2
                next_increase = time.time() + wait_period * scaleup
                scaleup *= 2

            print(f"wait_period = {wait_period}, scaleup = {scaleup}, next_increase = {next_increase}")
            time.sleep(wait_period)






# ===========================================================================
from copy import copy
import smtplib
from email.message import EmailMessage


#    if not isinstance(element, dict):
class EmailHandler(BaseHandler):
    name = "heartbeat-monitor.email"

    def __init__(self, EmailHandlerConfig):
        super().__init__()
        self.EmailHandlerConfig = copy(EmailHandlerConfig)
        self.server = smtplib.SMTP('localhost')

        if 'from' not in EmailHandlerConfig:
            self.EmailHandlerConfig['from'] = 'Heartbeat Monitor <noreply@localhost>'
        if 'to' not in EmailHandlerConfig:
            self.EmailHandlerConfig['to'] = 'Heartbeat Monitor <root>'
        if 'subject' not in EmailHandlerConfig:
            self.EmailHandlerConfig['subject'] = "WARNING: Keep-alive expired for '{name}'"
        if 'content' not in EmailHandlerConfig:
            self.EmailHandlerConfig['content'] = "Keep-alive expired for '{name}' --- a possible failure has been detected."


    def process(self, metadata, data):
        message = EmailMessage()

        message['From'] = self.EmailHandlerConfig['from']
        message['To'] = self.EmailHandlerConfig['to']
        message['Subject'] = data['subject'].format(**metadata) if 'subject' in data else self.EmailHandlerConfig['subject'].format(**metadata)
        message.set_content(data['data']['content'].format(**metadata) if 'content' in data.get('data', {}) else self.EmailHandlerConfig['content'].format(**metadata))

        self.server.send_message(message)


    def validateKeepAlive(self, metadata, data):
        return Response(200, 'OK')
    





# ===========================================================================
if __name__ == '__main__':
    import json
    vm1 = json.load(open('server--subcontract-1--vm-1.json'))
    vm2 = json.load(open('server--subcontract-2--vm-1.json'))

    eh = EmailHandler({})
    eh.process(vm1['metadata'], vm1['handlers'][2])
