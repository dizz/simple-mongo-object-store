import datetime
import os.path
import urllib
import json
import logging

from tornado import httpserver
from tornado import ioloop
from tornado import web

from pymongo.connection import Connection
from gridfs import GridFS

# Pre-req: have a pre-existing install of mongo db
# external install dependencies:
#  pip install tornado
#  pip install pymongo
#
# Test out with:
# curl -X GET http://localhost:8888/
# curl -X PUT http://localhost:8888/myapp/
# curl -X PUT -T task.py http://localhost:8888/myapp/task.py
# curl -X GET http://localhost:8888/myapp/
# curl -X GET http://localhost:8888/myapp/task.py
# curl -X DELETE http://localhost:8888/myapp/task.py
# curl -X GET http://localhost:8888/myapp/
# curl -X DELETE http://localhost:8888/myapp/
# curl -X GET http://localhost:8888/
#
# Note:
# 1. If you attempt curl -X PUT -T task.py http://localhost:8888/somethingsuper/woop.js
#    It will not work - this is something to be added if needed.
# 2. No authentication! Ah sure, security... who needs that :p
# 3. No multipart support for uploads


FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)
log = logging.getLogger('task.repo')
log.setLevel(logging.INFO)

def start(port, ssl_port, db_host='localhost'):
    """Starts the mock S3 server on the given port at the given path."""
    
    log.info("Starting task repo server...")
    log.info("\tMongo server at: " + db_host)
    application = RepoApplication(db_host)
    http_server = httpserver.HTTPServer(application)
    http_server.listen(port)
    
    import ssl
    
    https_server = httpserver.HTTPServer(application, ssl_options={
        "certfile": '/Users/andy/contacts.service.crt',
        "keyfile": '/Users/andy/contacts.service.nopwd.key',
        "cert_reqs": ssl.CERT_REQUIRED,
        "ca_certs":"/Users/andy/contacts.service.crt"
    })
    https_server.listen(ssl_port)
    
    ioloop.IOLoop.instance().start()


class RepoApplication(web.Application):
    def __init__(self, db_host='localhost'):     
        connection = Connection(db_host)
        self.bucket_db = connection.repo
        self.object_db = self.bucket_db
        self.gfs = GridFS(connection.files)
              
        web.Application.__init__(self, [
            (r"/", RootHandler),
            (r"/([^/]+)/", BucketHandler),
            (r"/([^/]+)/(.+)", ObjectHandler),
        ])


class BaseRequestHandler(web.RequestHandler):
    def render(self, value):
        assert isinstance(value, dict) and len(value) == 1
        self.set_header("Content-Type", "application/json; charset=UTF-8")       
        self.finish(json.dumps(value, indent=4))


class RootHandler(BaseRequestHandler):
    def get(self):

        log.info("Listing all buckets")
        buckets = []
        for bucket in self.application.bucket_db.buckets.find():
            buckets.append({
                "name": bucket['name'],
                "created": bucket['created']
            })
        self.render({"buckets": buckets})


class BucketHandler(BaseRequestHandler):
    def get(self, bucket_name):
        log.info("Listing all objects in bucket: " + bucket_name)
        
        obj = self.application.bucket_db.buckets.find_one({"name":bucket_name})
        if obj is None:
            log.error("Could not find specified bucket")
            raise web.HTTPError(404)
        
        objects = []
        for obj in self.application.object_db.objects.find({'bucket_name':bucket_name}):
            objects.append({
                "name": obj['name'], 
                "content_type":obj["content_type"], 
                "content":str(obj["content"]),
                "created":obj["created"]
            })
        self.render({"objects": objects})

    def put(self, bucket_name):
        log.info("Creating a bucket named: " + bucket_name)
        if self.application.bucket_db.buckets.find({'name':bucket_name}).count() > 1:
            log.error("Bucket already exists")
            raise web.HTTPError(409)
        
        self.application.bucket_db.buckets.save({
            "name":bucket_name, "created":str(datetime.datetime.utcnow())
        })
        self.set_status(200)
        self.finish()

    def delete(self, bucket_name):
        log.info("Deleting a bucket named: " + bucket_name)
        obj = self.application.bucket_db.buckets.find_one({"name":bucket_name})
        if obj is None:
            log.error("Could not find specified bucket")
            raise web.HTTPError(404)
                
        self.application.bucket_db.buckets.remove(obj)
        self.set_status(204)
        self.finish()


class ObjectHandler(BaseRequestHandler):
    def get(self, bucket, object_name):
        log.info("Retreiving content of an object named: " + object_name)
        object_name = urllib.unquote(object_name)
        
        # TODO refactor
        if self.application.bucket_db.buckets.find({'name':bucket}).count() <= 0:
            log.error("Couldn't find specified bucket")
            raise web.HTTPError(404)
        
        obj = self.application.object_db.objects.find_one({'name':object_name})
        if not obj:
            log.error("Couldn't find specified bucket")
            raise web.HTTPError(404)
        
        filein = self.application.gfs.get(obj['content'])
        
        self.set_header("Content-Type", obj['content_type'])
#        self.set_header("Last-Modified", datetime.datetime.utcfromtimestamp(info.st_mtime))

        self.finish(filein.read())

    def put(self, bucket, object_name):
        log.info("Creating an object named: " + object_name + " in bucket: " + bucket)
        
        if self.application.bucket_db.buckets.find({'name':bucket}).count() <= 0:
            log.error("Couldn't find specified bucket")
            raise web.HTTPError(404)
        
        object_name = urllib.unquote(object_name)

        if self.application.object_db.objects.find({'name':object_name}).count() > 1:
            log.error("Object already exists")
            raise web.HTTPError(409)
        
        #TODO if someone is so kind to supply the content-type header then use this
        fileid = self.application.gfs.put(self.request.body, content_type="application/unknown", original_user="andy")
        
        self.application.object_db.objects.save({
             "name":object_name, 
             "bucket_name":bucket, 
             "content_type":"application/unknown", 
             "content":fileid,
             "created":str(datetime.datetime.utcnow()) 
        })

        self.finish()

    def delete(self, bucket, object_name):
        log.info("Deleting an object named: " + object_name)
        object_name = urllib.unquote(object_name)
        
        #Delete the DB record first
        obj = self.application.object_db.objects.find_one({"name":object_name})
        if obj is None:
            log.error("The object specified could not be found")
            raise web.HTTPError(404)
                
        self.application.object_db.objects.remove(obj)
        
        #Delete the actual content
        self.application.gfs.delete(obj['content'])
        self.set_status(200)
        self.finish()

 
if __name__ == "__main__":
    start(8888, 8889, db_host='postie')