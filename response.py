import json


class Response():
    def __init__(self, statusCode, reason = '', data = ''):
        self.statusCode = statusCode
        self.reason = reason
        self.data = data


    def __str__(self):
        return json.dumps({ 'statusCode': self.statusCode,
                             'reason': self.reason,
                             'data': self.data })
    