# Pre-reqs
* Have a pre-existing install of mongo db

* External install dependencies:
  * `pip install tornado`
  * `pip install pymongo`

Test out with:

	curl -X GET http://localhost:8888/
	curl -X PUT http://localhost:8888/myapp/
	curl -X PUT -T task.py http://localhost:8888/myapp/task.py
	curl -X GET http://localhost:8888/myapp/
	curl -X GET http://localhost:8888/myapp/task.py
	curl -X DELETE http://localhost:8888/myapp/task.py
	curl -X GET http://localhost:8888/myapp/
	curl -X DELETE http://localhost:8888/myapp/
	curl -X GET http://localhost:8888/

# Notes
1. If you attempt `curl -X PUT -T task.py http://localhost:8888/somethingsuper/woop.js` it will not work - this is something to be added if needed.
2. No authentication! Ah sure, security... who needs that :p
3. No multipart support for uploads