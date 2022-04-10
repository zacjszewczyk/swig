#!/usr/local/bin/python3

# This work is licensed by Zachary J. Szewczyk under the Creative Commons
# Attribution-NonCommercial-ShareAlike 4.0 International License. See
# http://creativecommons.org/licenses/by-nc-sa/4.0/ for more information.

# Imports
from web import Web # Web client library.
from server import * # Server library.
from time import sleep # Waiting for child process to quit.
from os import system # Sterilize the environment prior to running the tests.

# Class: file
# Purpose: Test the web server's ability to serve a single file.
class file(base_page):
    # Method: __init__
    # Purpose: Instantiate the file-serving class.
    # Parameters:
    # - self: Class reference (Object)
    # Return: none
    def __init__(self):
        from os.path import getsize
        self.content_type = "text/plain"
        self.size = getsize("./README.md")

    # Method: get_content
    # Purpose: Read the contents of the README file.
    # Parameters:
    # - self: Class reference (Object)
    # Return: 
    # - Contents of the READ me file (String)
    def get_content(self,**kwargs):
        fd = open("./README.md", "rb")
        data = fd.read()
        fd.close()
        return data

# Class: stream
# Purpose: Test the web server's ability to stream a single file.
class stream(base_page):
    # Method: __init__
    # Purpose: Instantiate the streaming endpoint class.
    # Parameters:
    # - self: Class reference (Object)
    # Return: none
    def __init__(self):
        self.content_type = "text/plain"
    
    # Method: get_size
    # Purpose: Return a dummy value for the server log.
    # Parameters:
    # - self: Class reference (Object)
    # Return: "-"
    def get_size(self,**kwargs): return "-"

    # Method: get_content
    # Purpose: Return a generator object to stream the contents of the 
    # README file to the client.
    # Parameters:
    # - self: Class reference (Object)
    # Return: <generator object>
    def get_content(self,**kwargs):
        fd = open("./README.md", "r")
        for i,line in enumerate(fd):
            yield line
        fd.close()

# Class: regex_endpoint
# Purpose: Test the web server's ability to handle endpoints expressed
# as regular expressions.
class regex_endpoint(home):
    def __init__(self):
        super().__init__()
        self.content = "Regex endpoint."

# Class: post
# Purpose: Test the web server's ability to handle post requests.
class post():
    def get_content_type(self): return "text/plain"
    def get_size(self,**kwargs): return "-"
    def get_content(self,**kwargs):
        if (kwargs["body"]): yield kwargs["body"]
        else: yield "error"

def test_endpoints(base_url):
    # Track the test cases.
    total_tests = 0
    passed_tests = 0

    # Test the default home page.
    total_tests += 1
    web.get(f"{base_url}/")
    if (web.get_data() == "<html>\n    <head>\n      <title>Home</title>\n    </head>\n    <body>\nHello, world!\n    </body>\n</html>"): passed_tests += 1
    else: print(f"Failure: Failed to return proper default home page at {base_url}/ endpoint")

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET / HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for / endpoint incorrect.")
    fd.close()

    # Test a nonexistent endpoint. This query should cause the web server
    # to serve the default 404 page.
    total_tests += 1
    web.get(f"{base_url}/does/not/exist")
    if (web.get_data() == "<html>\n    <head>\n      <title>404: Resource Not Found</title>\n    </head>\n    <body>\nError: The requested resource cannot be found.\n    </body>\n</html>"): passed_tests += 1
    else: print(f"Failure: Failed to return proper default 404 page at {base_url}/does/not/exist endpoint")

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET /does/not/exist HTTP/1.1" 404' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for /does/not/exist endpoint incorrect.")
    fd.close()

    # Test the server's ability to filter out unsupported HTTP methods.
    total_tests += 1
    web.retrieve(f"{base_url}/",{"Content-Length": 3},"PUT",b"Hi!")
    if (web.get_data() == "<html>\n    <head>\n      <title>405: Method Not Allowed</title>\n    </head>\n    <body>\nError: The request method is not supported by the server and cannot be handled.\n    </body>\n</html>"): passed_tests += 1
    else: print(f"Failure: Failed to return proper default 405 page at {base_url}/ endpoint with POST method")

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"PUT / HTTP/1.1" 405' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for PUT / incorrect.")
    fd.close()

    # Test the server's ability to handle POST payloads by echoing the POST
    # message back to the client.
    total_tests += 1
    web.post(f"{base_url}/post",{"Content-Length": 5},b"hello")
    if (web.get_data() == "hello"): passed_tests += 1
    else: print(f"Failure: Failed to return proper POST body at {base_url}/post endpoint with POST method")

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"POST /post HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for POST /post incorrect.")
    fd.close()

    # Test the server's ability to transmit single files by serving the
    # README at /file, querying that endpoint, and comparing the response to
    # the contents of README.md on the disk.
    total_tests += 1
    fd = open("./README.md", "r")
    data = fd.read()
    fd.close()
    web.get(f"{base_url}/file")
    if (web.get_data() == data): passed_tests += 1
    else: print(f"Failure: Failed to return entire README from {base_url}/file")

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET /file HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for /file endpoint incorrect.")
    fd.close()

    # In part two of the single file test, read a part of the README file
    # from disk, then make sure this partial file does NOT match the 
    # response from the server. They should not match.
    total_tests += 1
    fd = open("./README.md", "r")
    web.get(f"{base_url}/file")
    if (web.get_data() != fd.readline()): passed_tests += 1
    else: print(f"Failure: Partial README read from disk matched server response at {base_url}/file")
    fd.close()

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET /file HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for /file endpoint incorrect.")
    fd.close()

    # Test the server's ability to stream a file by serving the README at
    # /stream, querying that endpoint, and comparing the entire response to
    # the contents of README.md on the disk.
    total_tests += 1
    fd = open("./README.md", "r")
    web.get(f"{base_url}/stream")
    if (web.get_data() == fd.read()): passed_tests += 1
    else: print(f"Failure: Failed to stream entire README from {base_url}/stream")
    fd.close()

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET /stream HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for /stream endpoint incorrect.")
    fd.close()

    # In part two of the single file stream test, read a part of the README
    # file from disk, then make sure this partial file does NOT match the 
    # streamed response from the server. They should not match.
    total_tests += 1
    fd = open("./README.md", "r")
    web.get(f"{base_url}/stream")
    if (web.get_data() != fd.readline()): passed_tests += 1
    else: print(f"Failure: Partial README read from disk matched streamed server response at {base_url}/stream")
    fd.close()

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET /stream HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for /stream endpoint incorrect.")
    fd.close()

    # Test the web server's ability to service endpoints defined as a 
    # regular expression.
    total_tests += 1
    web.get(f"{base_url}/asd")
    if (web.get_data() == "<html>\n    <head>\n      <title>Home</title>\n    </head>\n    <body>\nRegex endpoint.\n    </body>\n</html>"): passed_tests += 1
    else: print(f"Failure: Failed to serve proper page at regex endpoint {base_url}/asd (regex: /\w{3}")

    # Test the log message
    fd = open("./server.log")
    total_tests += 1
    if ('"GET /asd HTTP/1.1" 200' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for /asd regex endpoint incorrect.")
    fd.close()

    return total_tests,passed_tests

# If run as a standlone program, run the tests.
if (__name__ == "__main__"):
    # Kill any processes using port 8000
    system("kill -9 $(lsof -i -P -n | grep 8000 | awk '{print $2}') 2> /dev/null")

    # Track tests.
    total_tests = 0
    passed_tests = 0
    
    # Instantiate a web client to test the server endpoints.
    web = Web()

    # Set the base URL for the first round of tests, which tests a private HTTP
    # server that supports the GET and POST methods, and instantiate the server.
    base_url = "http://localhost:8000"
    s = Server(verbose=True,background=True,methods={"GET","POST"})

    # Start a web server with a home page (/) and a 404 page (/404.html),
    # that also serves the README streamed to the client (/stream) and
    # served as a unit /file). Also test regular expression endpoints, and
    # POST handling.
    s.register("/", home())
    s.register("/404.html", not_found())
    s.register("/405.html", not_allowed())
    s.register("/file", file())
    s.register("/stream", stream())
    s.register("/\w{3}", regex_endpoint())
    s.register("/post", post())
    s.run()

    # Update the test count trackers
    total_tests,passed_tests = test_endpoints(base_url)

    # Stop serving the web server, and give it time to shutdown before checking
    # the server log. This is, unfortunately, a race condition.
    s.shutdown()
    del s
    sleep(2)

    # Test the server shutdown log message
    fd = open("./server.log")
    total_tests += 1
    if ('"server shutdown" success' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for server shutdown incorrect.")
    fd.close()

    # Print the number of successful tests versus the number of total tests.
    print(f"Basic HTTP server via localhost: {passed_tests}/{total_tests} passed.")

    # Set the base URL for the second round of tests, which tests an IPv6 HTTP
    # server that supports the GET and POST methods, and instantiate the server.
    base_url = "http://[::1]:8000"
    s = Server(ip="::1",verbose=True,background=True,methods={"GET","POST"})

    # Start a web server with a home page (/) and a 404 page (/404.html),
    # that also serves the README streamed to the client (/stream) and
    # served as a unit /file). Also test regular expression endpoints, and
    # POST handling.
    s.register("/", home())
    s.register("/404.html", not_found())
    s.register("/405.html", not_allowed())
    s.register("/file", file())
    s.register("/stream", stream())
    s.register("/\w{3}", regex_endpoint())
    s.register("/post", post())
    s.run()

    # Update the test count trackers
    total_tests,passed_tests = test_endpoints(base_url)

    # Stop serving the web server, and give it time to shutdown before checking
    # the server log. This is, unfortunately, a race condition.
    s.shutdown()
    del s
    sleep(2)

    # Test the server shutdown log message
    fd = open("./server.log")
    total_tests += 1
    if ('"server shutdown" success' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for server shutdown incorrect.")
    fd.close()

    # Print the number of successful tests versus the number of total tests.
    print(f"Basic HTTP server via IPv6: {passed_tests}/{total_tests} passed.")

    # Set the base URL for the third round of tests, which tests an IPv6 HTTPS
    # server that supports the GET and POST methods, and instantiate the server.
    base_url = "https://[::]:8000"
    s = Server(ip="::",verbose=True,background=True,methods={"GET","POST"},https=True)

    # Start a web server with a home page (/) and a 404 page (/404.html),
    # that also serves the README streamed to the client (/stream) and
    # served as a unit /file). Also test regular expression endpoints, and
    # POST handling.
    s.register("/", home())
    s.register("/404.html", not_found())
    s.register("/405.html", not_allowed())
    s.register("/file", file())
    s.register("/stream", stream())
    s.register("/\w{3}", regex_endpoint())
    s.register("/post", post())
    s.run()

    # Update the test count trackers
    total_tests,passed_tests = test_endpoints(base_url)

    # Stop serving the web server, and give it time to shutdown before checking
    # the server log. This is, unfortunately, a race condition.
    s.shutdown()
    del s
    sleep(2)

    # Test the server shutdown log message
    fd = open("./server.log")
    total_tests += 1
    if ('"server shutdown" success' in fd.readlines()[-1]): passed_tests += 1
    else: print("Failure: Log message for server shutdown incorrect.")
    fd.close()

    # Print the number of successful tests versus the number of total tests.
    print(f"Basic HTTPS server via IPv6: {passed_tests}/{total_tests} passed.")