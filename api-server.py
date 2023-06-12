from flask import Flask
from flask_restful import request, reqparse, abort, Api, Resource

from handlers import STATUS, KeepAlive, SyslogHandler, CloudAPIHandler, EmailHandler
from response import Response
from heartbeat_monitor import HeartbeatMonitor






# ===========================================================================
class ServerKeepAlive(Resource):
    def put(self):
        """Given a suitably-formatted json file, a KeepAlive can be created and registered via the command:
           curl -X PUT -H "Content-Type: application/json" -d @server-ka.json http://localhost:5000/server"""
        req = request.get_json()

        if 'uuid' in req['metadata']:
            HM.registerKeepAlive(f"server/{req['metadata']['uuid']}", KeepAlive(time.time() + 15, req['metadata'], req['handlers']))
        else:
            pass

        return { }, 201
    

    def delete(self):
        pass






# ===========================================================================
if __name__ == '__main__':
    import time
    import json
    import os


    app = Flask(__name__)
    api = Api(app)

    api.add_resource(ServerKeepAlive, '/server')
    # api.add_resource(ServerKeepAlive, '/server/<server_uuid>')


    HandlerConfigs = json.load(open('handler-configs.json'))


    HM = HeartbeatMonitor() 
    HM.registerHandler(CloudAPIHandler(HandlerConfigs[CloudAPIHandler.name] if CloudAPIHandler.name in HandlerConfigs else {}))
    HM.registerHandler(EmailHandler(HandlerConfigs[EmailHandler.name] if EmailHandler.name in HandlerConfigs else {}))


    HM.start()

    app.run(debug=False)
