#!/usr/local/bin/python3

# This work is licensed by Zachary J. Szewczyk under the Creative Commons
# Attribution-NonCommercial-ShareAlike 4.0 International License. See
# http://creativecommons.org/licenses/by-nc-sa/4.0/ for more information.

# Imports
from socket import socket, has_ipv6, AF_INET, AF_INET6, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR # Socket interface.
from multiprocessing.pool import ThreadPool # Service requests concurrently.
from threading import Thread # Enable the web server to run in the background.
from signal import signal, SIGINT # Handle keyboard interrupts in a multithreaded environment.
from inspect import ismethod, isgeneratorfunction # Differentiate between typical methods and generator functions.
from zlib import compressobj, DEFLATED # Enable gzip response compression.
import datetime # Timestamp logs.
from re import fullmatch # Supporting regex endpoints.
from time import sleep # Debugging
from ssl import wrap_socket as wrap_socket_ssl # HTTPS support
from os.path import isfile # Checking for server certificate.
from ipaddress import ip_address # Bounds checking

# Class: Server
# Purpose: Provide a high-level interface for simple, multi-threaded web servers
class Server():
    # Method: __init__
    # Purpose: Initialize the web server.
    # Parameters: 
    # - self: Class reference (Object)
    # - ip: IP at which to serve web server. Default: 127.0.0.1 (String)
    # - port: Port at which to serve web server. Default: 8000 (Int)
    # - methods: List of supported HTTP methods. Default: {"HEAD",GET"} (Set)
    # - threads: Number of threads for request handling. Default: 8 (Int)
    # - logfile: Name of the logfile. Default: server.log (String)
    # - gzip: Flag to support gzip compression. Default: None (Bool)
    # - verbose: Flag to print log messages to the terminal and write to the log
    #   file (True), or just write to the log file (False). Default: True (Bool)
    # - background: Flag to background server execution. Default: False (Bool)
    # - https: Flag to signal use of HTTPS over HTTP. Default: False (Bool)
    # Return: None.
    def __init__(self, ip="127.0.0.1", port=8000, methods={"HEAD","GET"}, threads=8, logfile="server.log", gzip=None, verbose=True, background=False, https=False):
        # Configure the server's IP address, and the port at which to serve it
        # If the user makes the web server available at localhost or 127.0.0.1,
        # create a private web server accessible from the local machine only.
        # Note: the IPv6 equivalent of a private web server at localhost or
        # 127.0.0.1 is [::1].
        # If the user makes the web server available at a different IP address,
        # such as the IP address for its LAN interface, create a web server
        # accessible by any machine on the local network. Note: the IPv6
        # equivalent of a web server available to any machine on the LAN (IPv4
        # 0.0.0.0) is [::]
        if (ip == "localhost"): ip = "127.0.0.1"
        # Ensure the user provided a valid IPv4 address on which to serve the
        # web server, and a port in the range 1024 to 65535.
        assert ip_address(ip)
        assert port > 1023 and port < 65536, "Please use a port in the range 1024 to 65535."
        # Store the IP and port at which to serve the web server.
        self.IP,self.PORT = ip,port

        # Store the list of valid supported HTTP methods. First ensure the user
        # provided a set of supported methods, then intersect the supported
        # methods with a set of valid HTTP methods. This makes it impossible to
        # use invalid HTTP methods.
        assert type(methods) == set, "Please provide a list of valid HTTP methods as a set, using the {\"METHOD\", \"METHOD\", ...} syntax."
        self.allowed_methods = {"GET","HEAD","POST","PUT","DELETE","CONNECT","OPTIONS","TRACE","PATCH"}.intersection(methods)

        # If the server's execution is to be backgrounded, define a pool of
        # threads with which to handle connections, and store the background
        # execution boolean. If the server is to be run in the foreground,
        # explicitly set the background execution boolean to False.
        if (background == True):
            assert type(threads) == int, "Please use an integer to specify the number of threads for request handling."
            self.pool = ThreadPool(threads)
            self.background = True
        else: self.background = False

        # Bounds check the provided log file name.
        # https://stackoverflow.com/questions/9532499/check-whether-a-path-is-valid-in-python-without-creating-a-file-at-the-paths-ta
        assert type(logfile) == str, "Please provide a log file name as a string."
        assert '\x00' not in logfile, "Please enter a valid log file name, that does not include a null byte."
        assert all([len(x) < 256 for x in logfile.split("/")]) if "/" in logfile else len(logfile) < 256, "Please enter a valid log file path, that does not include paths components above 255 bytes."
        # Store the log file's name for future writes, then clear it.
        self.logfile = logfile
        open(f"{self.logfile}", "w").close()

        # Set the gzip compression flag. If the user does not specifically tell
        # the server to support gzip compression by passing a "gzip" parameter
        # with a value other than None, the flag defaults to None and the server
        # will NOT compress its responses. If the user desires to support gzip
        # compression and indicates this by passing "gzip" with a value other
        # than None, the server will support it on a connection-by-connection
        # basis by defaulting self.gzip to False and setting it to True based on
        # the request header for each connection.
        if (gzip != None): self.gzip = False
        else: self.gzip = None

        # Store the verbose flag for controlling logging ouput
        if (verbose == True): self.verbose = True
        else: self.verbose = False

        # Create a new socket handle, s, for the address and port combination
        # defined above. This operation supports both IPv4 and IPv6 addresses.
        if (":" in self.IP): 
            assert has_ipv6, "You specified an IPv6 address, but this platform does not support IPv6."
            self.s = socket(family=AF_INET6)
        else: 
            self.s = socket()
        
        # If the user wants to use HTTPS, wrap it in an SSL context; otherwise,
        # use plain HTTP.
        if (https == True):
            if (isfile("./server.pem")):
                self.s = wrap_socket_ssl(self.s, certfile='./server.pem', server_side=True)
            else:
                print("Error: No server certificate found. Serving over HTTP.")
        
        # Do not error out if the system thinks the socket is already in use.
        # Set a timeout for 1 second to facilitate non-blocking execution.
        self.s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.s.settimeout(1)

        if (":" in self.IP):
            self.s.bind((self.IP, self.PORT, 0, 0))
        else:
            self.s.bind((self.IP,self.PORT))

        # Define the number of unaccepted connections the system will allow
        # before refusing new connections.
        self.s.listen(10)
        
        # Define a dictionary of endpoints and the associated class that
        # provides the data for that page.
        self.endpoints = {}

        # Store the keep_running flag, which--while True--keeps the server 
        # running indefinitely. Once False, the server automatically shuts down.
        self.keep_running = True

        # Define the handler function for keyboard interrupts. Since the web
        # server executes asynchronously, this handler must be defined here.
        def keyboardInterruptHandler(signal, frame):
            self.shutdown() # Signal a server shutdown

        # Register the signal handler.
        signal(SIGINT, keyboardInterruptHandler)

    # Method: run
    # Purpose: Start the web server, in a new child thread if appropriate.
    # Parameters: 
    # - self: Class reference (Object)
    # Return: None
    def run(self):
        if (self.background == True): self.t = Thread(target=self.__run__); self.t.start()
        else: self.__run__()

    # Method: __run__
    # Purpose: Serve the web server until the thread owner signals a shutdown.
    # Parameters: 
    # - self: Class reference (Object)
    # Return: 
    # - Port still open: False (Bool)
    # - Port closed: True (Bool)
    def __run__(self):
        if (self.verbose): self.log(f"Serving web server at port {self.PORT} on host {self.IP}")

        # Serve the web server until the "keep_running" flag changes to False.
        # If the web server is running in the background, that signal will come
        # in the form of a new threat attribute, self.t.keep_running. If the web
        # server is running in the foreground, that signal is stored in the
        # class's local self.keep_running variable.
        if (self.background == True):
            while getattr(self.t, "keep_running", True):
                try:
                    conn = self.s.accept() # Timeout to allow refresh.
                    self.pool.apply_async(self.handle,(conn,)) # Asynchronous
                except OSError as e: pass

        else:
            while self.keep_running == True:
                try:
                    conn = self.s.accept() # Timeout to allow refresh
                    self.handle(conn) # Blocking
                except OSError as e: pass

    # Method: shutdown
    # Purpose: Signal a shutdown and close the server's socket.
    # Parameters: 
    # - self: Class reference (Object)
    # Return:
    # - True: Server shutdown and port closed (Bool)
    # - False: Server not shutdown, or port not closed (Bool)
    def shutdown(self):
        # If the server's execution was backgrounded, signal a shutdown by 
        # adding an attribute "keep_running" to the thread with the value False,
        # then wait for the child thread to join. If the server's was executing
        # in the foreground, just set the local keep_running variable to False
        # to signal a shutdown.
        if (self.background == True):
            self.t.keep_running = False
            self.t.join()
        else:
            self.keep_running = False

        # Try to close the port, and return False (failure) if it remains open.
        if (self.close() == 0):
            if (self.verbose): print(f"\nError: failed to close port {self.PORT} on host {self.IP}.")
            return False

        # If the server was running in the background, make sure the server's
        # thread stopped. Return False (failure) if it's still running.
        if (self.background == True):
            if (self.t.is_alive()):
                if (self.verbose): print(f"\nError: failed to shutdown child server process.")
                return False

        # If the port closed and the server shutdown, optionally print a message
        # to the user, then return True (success)
        if (self.verbose): print(f"\nSuccess: closed port {self.PORT} on host {self.IP} and shutdown server.")
        return True

    # Method: close
    # Purpose: Close the socket, then test to make sure it actually closed.
    # Parameters: 
    # - self: Class reference (Object)
    # Return: 
    # - Port still open: 0 (Int)
    # - Port closed: !0 (Int)
    def close(self):
        self.s.close() # Close the port.

        # Attempt to connect to the port, and record an integer return value
        # based on whether the port is still open (0) or now closed (!0).
        # Specify 127.0.0.1 (or ::1) as the origin IP because otherwise the
        # server will try to connect to itself from the same IP:PORT it was 
        # served on, which may not yet have been released by the kernel.
        if (":" in self.IP):
            sock = socket(AF_INET6, SOCK_STREAM)
            code = sock.connect_ex(("::1",self.PORT))
        else:
            sock = socket(AF_INET, SOCK_STREAM)
            code = sock.connect_ex(("127.0.0.1",self.PORT))

        # Log server termination
        self.log(f"{self.IP} [ident] sys [{datetime.datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] \"server shutdown\" {'success' if code != 0 else 'fail'} -")
        
        # Return success (!0) or failure (0) of the port close operation.
        return code
        
    # Method: handle
    # Purpose: Handle connection.
    # Parameters: 
    # - self: Class reference (Object)
    # - args: Passed argument list (List)
    # Return: 
    # - HTTP response code (Int)
    def handle(self,args):
        # Read the gzip flag set during class initialization. 
        gzip = self.gzip

        # Extract the socket connection from the arguments provided.
        c = args[0]

        # Read and parse request headers up to 4096 bytes. Turn into a key-value
        # dictionary.
        request = self.parse_request(c.recv(4096))

        # Extract the HTTP method and target from the request line
        method = request["request_line"].split()[0]
        target = request["request_line"].split()[1]

        # Make sure client is using an allowable HTTP method. Redirect to an
        # error page if not.
        if (method not in self.allowed_methods):
            msg = "405 Not Allowed"
            target = "/405.html"
        # If the HTTP request method is supported, and if requested resource is
        # in the list of valid endpoints, use the 200 OK response. If the HTTP
        # method is POST, and the POST payload was not already captured, check 
        # for a body payload (as indicated by the "Content-Length" header); if
        # it's present, read the POST payload.
        elif (any([fullmatch(x,target) for x in self.endpoints.keys()])):
            msg = "200 OK"
            if ("POST" in request["request_line"]):
                if ("body" not in request.keys()):
                    if ("Content-Length" in request.keys()):
                        body = c.recv(int(request["Content-Length"]))
                else:
                    body = request["body"]
        # If the client requested an unregistered endpoint, use the 404 Not
        # Found response and set the target page to the error page.
        else:
            msg = "404 Not Found"
            target = "/404.html"

        # Store the target page's data in an easy-to-access variable
        for x in self.endpoints.keys():
            if (fullmatch(x,target)):
                resource = self.endpoints[x]

        # If the HTTP request "body" variable was not set earlier, define it as
        # an empty byte string here to minimize redundant tests later.
        if ("body" not in locals()): body = b""

        # Log the connection
        self.log(f"{c.getpeername()[0]} [ident] [user] [{datetime.datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] \"{request['request_line']}\" {msg.split()[0]} {resource.get_size(method=method,target=target,body=body)}")

        # Determine if gzip compression is appropriate.
        # A value of None indicates the user did not set gzip flag during
        # initialization, so gzip compression is never appropriate. A value of
        # False indicates the user did set the gzip flag during initialization,
        # and that therefore gzip compression is appropriate on a case-by-case
        # basis, depending on the request header.
        if (gzip == False): 
            # Check for the "Accept-Encoding" header.
            if ("Accept-Encoding" in request.keys()):
                # If the "Accept-Encoding" hedaer exists, see if the client
                # support gzip compression
                if ("gzip" in request["Accept-Encoding"]):
                    # The server permits gzip compression, the client specified
                    # acceptable encoding formats, and that list of formats 
                    # included gzip, so set the gzip flag to true. The response
                    # for this connection will be gzip compressed.
                    gzip = True

                    # Instantiate a compression object to handle the gzip
                    # compression.
                    z = compressobj(-1,DEFLATED,31)

        # Start sending basic response headers.
        # - HTTP protocol and status
        # - Content-Type: {based on resource}
        # - Connection: close
        self.send_header(c,f"HTTP/1.1 {msg}")
        self.send_header(c,f"Content-Type: {resource.get_content_type()}")
        self.send_header(c,"Connection: close")

        # Send the "Allow" header if the client used an unsupported HTTP method.
        if (target == "/405.html"): self.send_header(c,f"Allow: {', '.join(self.allowed_methods)}")

        # Determine how the class will provide the server data for its endpoint,
        # so the server can choose the appropriate header to send to the client,
        # and the manner to transmit that data.
        # If the class provides endpoint data with a generator function, stream
        # the data to the client. If the client provides endpoint data with a
        # function via its return value, capture it and send it back to the
        # client in a single operation. Send the appropriate header now.
        if (isgeneratorfunction(resource.get_content) == True):
            # Signal a streaming response with the Transfer-Encoding header
            self.send_header(c,"Transfer-Encoding: chunked")
            # If using gzip compression for this connection, send the gzip
            # header, read the data in from the generator function, compress it,
            # and stream it back to the client.
            if (gzip == True):
                self.send_header(c,"Content-Encoding: gzip")
                self.end_header(c)
                if (method != "HEAD"): 
                    data = ""
                    for chunk in resource.get_content(method=method,target=target,body=body):
                        data += chunk

                    compressed_data = z.compress(bytes(data,"utf-8")) + z.flush()
                    transmitted = self.stream(c,compressed_data)
            # If not using gzip compression, close the header block and stream
            # the response data back to the client.
            else:
                self.end_header(c)
                if (method != "HEAD"): 
                    transmitted = 0
                    for chunk in resource.get_content(method=method,target=target,body=body):
                        transmitted += self.stream(c,chunk)
            # End the stream
            self.end_stream(c)
        elif (ismethod(resource.get_content) == True):
            # If using gzip compression for this connection, compress the
            # response data, calculate its length, and send that value in the
            # Content-Length header. Signal the end of the header block, then
            # transmit the compressed data.
            if (gzip == True):
                compressed_data = z.compress(bytes(resource.get_content(method=method,target=target,body=body),"utf-8")) + z.flush()
                self.send_header(c,f"Content-Length: {len(compressed_data)}")
                self.send_header(c,"Content-Encoding: gzip")
                self.end_header(c)
                if (method != "HEAD"): transmitted = self.transmit(c,compressed_data)
            # If not using gzip compression, send the appropriate Content-Length
            # header, close the header block, and transmit the data.
            else:
                self.send_header(c,f"Content-Length: {resource.get_size(method=method,target=target,body=body)}")
                self.end_header(c)
                if (method != "HEAD"): transmitted = self.transmit(c,resource.get_content(method=method,target=target,body=body))

        # Close the connection
        c.close()

        # Return a tuple of [HTTP response code, bytes transmitted]
        return [msg.split()[0], transmitted]

    # Method: stream
    # Purpose: Stream data to the client.
    # Parameters: 
    # - c: Connection over which to stream the data.
    # - d: Data to stream (Bytes/String)
    # Return: Number of bytes streamed to the client.
    def stream(self,c,d):
        if (type(d) != bytes): d = bytes(f"{format(len(d.encode('utf-8')), 'x')}\r\n{d}\r\n","utf-8")
        else: d = bytes(f"{format(len(d), 'x')}\r\n","utf-8")+d+bytes("\r\n","utf-8")
        return self.transmit(c,d)

    # Method: end_stream
    # Purpose: Signal the end of a data stream to the client.
    # Parameters:
    # - c: Connection over which to signal the end of the data stream.
    # Return: Number of bytes streamed to the client.
    def end_stream(self,c):
        return c.send(bytes("0\r\n\r\n", "utf-8"))

    # Method: register
    # Purpose: Associate a URL endpoint with a class that provides the data for,
    # and date type of, that page.
    # Parameters: 
    # - self: Class reference (Object)
    # - endpoint: Target endpoint (String)
    # - cls: Class that stores the data and data type for the endpoint. (Class)
    # Return: None
    def register(self,endpoint,cls):
        self.endpoints[endpoint] = cls

    ############################################################################
    # Helper methods: the methods in this section help streamline the request
    # handling code above.

    # Method: parse_request
    # Purpose: Turn request into a key-value dictionary.
    # Parameters: 
    # - self: Class reference (Object)
    # - data: Header block (Byte string)
    # Return: 
    # - Request as a key-value dictionary (Dict)
    def parse_request(self,data):
        d = {}
        # Capture lines and strip off carriage returns and newlines.
        data = [x.strip() for x in data.decode("utf-8").split('\r\n')]

        # If there are more lines than just the request line, test the last line
        # of the request. If it's not empty, this is the request body; capture
        # it in the request dictionary.
        if (len(data) > 1):
            if (data[-1] != ''):
                d["body"] = data.pop(-1)

        # At a minimum, extract the request line.
        d["request_line"] = data[0]
        if (len(data) == 1): return d

        # If there are more headers, parse them and add them to the dictionary
        # until reaching the newline that delineates the request header from its
        # body.
        for each in data[1:]:
            if (len(each) == 0): break
            each = each.strip().split(":",1)
            d[each[0]] = each[1]

        # Return the request headers, parsed as a key-value dictionary        
        return d

    # Method: send_header
    # Purpose: Parse a string-formatted header line and send it to the client.
    # Parameters: 
    # - self: Class reference (Object)
    # - c: Connection over which to send the header. (Socket)
    # - header: Header to send (String)
    # Return: None
    def send_header(self,c,header):
        c.sendall(bytes(header+"\r\n", "utf-8"))
    
    # Method: end_header
    # Purpose: Signal the end of the header block to the client.
    # Parameters: 
    # - self: Class reference (Object)
    # - c: Connection over which to send the termination signal. (Socket)
    # Return: None
    def end_header(self,c):
        c.sendall(b"\n")

    # Method: transmit
    # Purpose: Send data to the client.
    # Parameters: 
    # - self: Class reference (Object)
    # - c: Connection over which to send the string. (Socket)
    # - d: Data to parse and send to the client. (*)
    # Return:
    # - sent: Number of bytes send to client (Int)
    def transmit(self,c,d):
        # Convert the data to a byte string if necessary
        if (type(d) != bytes): d = bytes(d,"utf-8")
        
        # Track the number of bytes sent to ensure all the data is transmitted.
        sent = 0
        while sent < len(d): sent += c.send(d[sent:])
        
        # Return the number of bytes transmitted.
        return sent

    # Method: log
    # Purpose: Print a message to the console and a write it to a log file.
    # Parameters: 
    # - self: Class reference (Object)
    # - msg: Message to log. (String)
    # Return: None
    def log(self,msg):
        fd = open(self.logfile, "a")
        fd.write(msg+"\n")
        fd.close()
        if (self.verbose): print(msg)

# Class: template
# Purpose: Define the opening and closing HTML tags that constitute a page, and
# the size of each block. Note: this can be overridden with a custom template as
# long as it uses the same "opening", and "closing" variables.
class template():
    opening = f"<html>\n{' '*4}<head>\n{' '*6}<title>{{title}}</title>\n{' '*4}</head>\n{' '*4}<body>\n"
    closing = f"\n{' '*4}</body>\n</html>"

# Class: base_page
# Purpose: Define basic, generic, required methods for getting endpoint info.
# Note: this can be overridden for all pages, or on a case-by-case basis, to
# support more complex or dynamic pages as long as the new class exposes the
# get_content_type(**kwargs), get_content(**kwargs), and get_size(**kwargs)
# methods for the server to access endpoint information. To override these 
# methods for all pages, edit this class; to override these methods for
# individual pages, define new methods in the individual page classes, an 
# example of which is included below.
class base_page():
    # Method: get_content_type
    # Purpose: Return media type for the endpoint.
    # Parameters:
    # - self: Class reference (Object)
    # Return: Media type for the endpoint.
    def get_content_type(self):
        return self.content_type

    # Method: get_content
    # Purpose: Return content for the endpoint.
    # Parameters:
    # - self: Class reference (Object)
    # - kwargs: Key-value dictionary that supplies request endpoint with key
    #   "target" and request body with key "body" (Dictionary)
    # Return: Content for the endpoint.
    def get_content(self,**kwargs):
        return template.opening.format(title=self.title) + self.content + template.closing

    # Method: get_size
    # Purpose: Return resource size for the endpoint.
    # Parameters:
    # - self: Class reference (Object)
    # - kwargs: Key-value dictionary that supplies request endpoint with key
    #   "target" and request body with key "body" (Dictionary)
    # Return: Size of content at the endpoint.
    def get_size(self,**kwargs):
        return len(self.get_content(kwargs=kwargs))

# Class: home
# Inherits: base_page
# Purpose: Define a basic static page to illustrate proper structure and make 
# the server usable. Note: to support a more complex or dynamic page by 
# overriding the methods defined in base_page, simply define them as new methods
# here after the __init__ definition.
class home(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.title = "Home"
        self.content = "Hello, world!"

# Class: not_found
# Inherits: base_page
# Purpose: Define a basic error page to illustrate proper structure and make the
# server usable. Note: to support a more complex or dynamic page by overriding
# the methods defined in base_page, simply define them as new methods here
# after the __init__ definition.
class not_found(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.title = "404: Resource Not Found"
        self.content = "Error: The requested resource cannot be found."

# Class: not_allowed
# Inherits: base_page
# Purpose: Define an error page for handling unsupported HTTP methods. Note: to
# support a more complex or dynamic page by overriding the methods defined in
# base_page, simply define them as new methods here after __init__.
class not_allowed(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.title = "405: Method Not Allowed"
        self.content = "Error: The request method is not supported by the server and cannot be handled."

# If run as a standalone program, start a simple HTTP server with a single valid
# endpoint, /, and error pages for 404 and 405 methods.
if (__name__ == "__main__"):
    s = Server(background=True)
    s.register("/", home())
    s.register("/404.html", not_found())
    s.register("/405.html", not_allowed())
    s.run()