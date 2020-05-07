Swig - A truly micro Python web framework
=========================================

Swig is a monolithic, multithreaded, micro web framework designed for air-gapped intranet environments.

## Table of Contents
* [Features](#features)
* [Dependencies](#dependencies)
* [Installation](#installation)
* [Usage](#usage)
    * [Quick-Start Guide](#quick-start-guide)
    * [Configuration Options](#configuration-options)
    * [Registering Endpoints](#registering-endpoints)
    * [Starting the Server](#starting-the-server)
    * [Enabling HTTPS](#enabling-https)
* [Background and Motivation](#background-and-motivation)
* [License](#license)

## Features

* **No dependencies**. I wrote Swig in Python 3; it has no external dependencies.
* **Multithreaded execution**. Modern web browsers send multiple requests in parallel; Swig supports this with a default pool of eight threads.
* **IPv4 and IPv6**. Each instance of Swig can serve connections to either IPv4 or IPv6 addresses.
* **HTTP and HTTPS**. Swig supports both the HTTP and HTTPS protocols.
* **Streaming responses**. Returning a resource’s content with a generator rather than a function causes Swig to stream its response back to the client, rather than passing the response data to the TCP stack in a single operation for it to then transfer to the client with multiple packets.
* **gzip compression**. Swig allows you to minimize the time required to transfer data over the network by compressing it first using the popular gzip format.

## Dependencies

Swig does not rely on any third-party tools, code, or frameworks. It uses Python 3.

## Installation

Because Swig has no dependencies, installation is a breeze: just clone this repository. Open a shell and type the following commands:

```
$ git clone https://zjszewczyk@bitbucket.org/zjszewczyk/swig.git swig
```

That's it.

## Usage

### Quick-Start Guide

Start a web server by running the script:

```
$ python3 server.py
```

In its default configuration, running `server.py` creates a private IPv4 web server available to the local machine only, served over port 8000, that supports both the *GET* and *HEAD* HTTP methods for a single endpoint: `/`. Opening [http://localhost:8000](http://localhost:8000) in your browser will display a simple "Hello, world!" message. GET requests for all other endpoints will receive a `404: Not Found` response and return the contents of a basic 404 page, while using any other HTTP method will cause the server to send a `405: Not Allowed` response and return the contents of a basic 405 page.

### Configuration Options

Swig supports the following configuration options, passed as parameters to the `Server()` class at instantiation.

* **ip**: IP at which to serve web server. Default: 127.0.0.1 (String). Use this parameter to specify the interface on which to make the web server available, or use "0.0.0.0" or "::" to accept incoming connections on all IPv4 or IPv6 interfaces, respectively.
* **port**: Port at which to serve web server. Default: 8000 (Int). Swig requires that you use a port in the range 1024 to 65535 inclusive.
* **methods**: List of supported HTTP methods. Default: {"HEAD",GET"} (Set). All HTTP methods not included in this set, including invalid ones, will cause the server to send a `405: Not Allowed` response and return the contents of a basic 405 page.
* **threads**: Number of threads for request handling. Default: 8 (Int).
* **logfile**: Name of the logfile. Default: server.log (String). Swig will attempt to write its log file to the path you specify here.
* **gzip**: Flag to support gzip compression for clients that send the `Accept-Encoding: gzip` header. Default: None (Bool).
* **verbose**: Flag to print log messages to the terminal and write to the log file (True), or just write to the log file (False). Default: True (Bool).
* **background**: Flag to background server execution. Default: False (Bool). I recommend keeping the default value of False during development, so Swig will raise exceptions when it encounters problems. Once True, execution will take place in a different thread that will also consumes those helpful error messages.
* **https**: Flag to signal use of HTTPS instead of HTTP. Default: False (Bool). This requires you to have a `server.pem` X.509 certificate in the same directory as the server script. If Swig cannot find this file, *it will still start the server*, but it will use plaintext HTTP instead of HTTPS.

Check out these example configurations.

```
s = Server()
```

This creates a new instance of the web server, `s`, using the default configuration values described above. As I described earlier, this creates a private IPv4 web server available to the local machine only, served over port 8000, that supports the *HEAD* and *GET* HTTP methods for a single endpoint: `/`. Opening [http://localhost:8000](http://localhost:8000) in your browser will display a simple "Hello, world!" message. GET requests for all other endpoints will receive a `404: Not Found` response and return the contents of a basic 404 page, while using any other HTTP method will cause the server to send a `405: Not Allowed` response and return the contents of a basic 405 page.

```
s = Server(ip="::", port=8080, methods={"GET", "POST"}, background=True, threads=32)
```

This creates a public IPv6 web server available to the entire local area network, served over port 8080, that can handle multiple simultaneous connections using up to thirty-two threads. It supports both GET and POST HTTP methods, but not the default HEAD. In this case, opening the IPv6 version of localhost at port 8080--[http://[::]:8080](http://[::]:8000) or [http://[::1]:8080](http://[::1]:8000)--in your browser will display that simple "Hello, world!" message. Replace `[::]` or `[::1]` with the IPv6 address of your server to view these pages on any other device in the network. 

### Registering Endpoints

Once you have created an instance of the web server, you must associate endpoints with classes that expose the resource's [MIME type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types), the resource itself, and its size. These methods must be named `get_content_type`, `get_content`, and `get_size`, respectively. Each of these methods must accept two parameters: the class name space object, `self`, and the variably sized key-value dictionary `**kwargs`. Swig passes three key-value pairs via `kwargs` each time one of these methods is called: `kwargs["method"]`, the HTTP method used for the request, `kwargs["target"]`, the URI to which the request was made, and `kwargs["body"]`, the request body. Check out this example class, which would allow Swig to serve the README.md file in its base directory:

```
# Class: readme
# Purpose: Serve the README.md file in the current directory.
class readme():
    def __init__(self):
        from os.path import getsize
        self.content_type = "text/plain"
        self.size = getsize("./README.md")
    
    def get_content_type(self,**kwargs):
        return self.content_type

    def get_content(self,**kwargs):
        fd = open("./README.md", "rb")
        data = fd.read()
        fd.close()
        return data

    def get_size(self,**kwargs):
        return self.size
```

Swig could also stream the file's contents to the client using a generator. Check out the changed `get_content` method, below:

```
# Class: readme
# Purpose: Serve the README.md file in the current directory.
class readme():
    def __init__(self):
        from os.path import getsize
        self.content_type = "text/plain"
        self.size = getsize("./README.md")
    
    def get_content_type(self,**kwargs):
        return self.content_type

    def get_content(self,**kwargs):
        fd = open("./README.md", "rb")
        for i,line in enumerate(fd):
            yield line
        fd.close()

    def get_size(self,**kwargs):
        return self.size
```

Either way, associate the `readme` class with the `/readme` endpoint using Swig's `register()` method:

```
s.register("/readme", readme())
```

Swig's `register()` method creates endpoint-class associations. If a previous association exists, it will overwrite the old one--even for default endpoints, like "/". Combined with the helper `base_page` class, which allows you to inherit `get_content_type`, `get_content`, and `get_size` methods from `base_page` that return `self.content_type`, `self.content`, and `len(self.content)`, respectively, you can rapidly deploy static endpoints. Check out the full example below, which changes the "Hello, world!" message on the "/" endpoint:

```
class home(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.content = "Goodbye, cruel world."

s.register("/", home())
```

Although the examples above associated an endpoint string with a class, Swig also supports using regular expressions. This comes in handy when building a blog, for example: instead of hundreds of `s.register("/blog/first-post", first_post())`, `s.register("/blog/second-post", second_post())`, ... `s.register("/blog/n-post", n_post())` stanzas, you could use `s.register("/blog/.*", posts())` instead. The regular expression `"/blog/.*"` would match any URI that begins with "/blog/", which would cause Swig to call the `get_content_type`, `get_content`, and `get_size` methods in the `posts()` class with the `kwargs["method"]`, `kwargs["target"]`, and `kwargs["body"]` parameters. `kwargs["target"]` could then allow you to differentiate between `/blog/first-post` and `/blog/n-post`. Check out the short example below:

```
# Class: posts
# Purpose: Serve individual blog posts below the /blog/ endpoint.
class posts(base_page):
    def __init__(self):
        self.content_type = "text/html"

    def get_content(self,**kwargs):
        # Extract the target post as the portion of the string after /blog/
        uri = kwargs["target"][6:]

        # ... Read post identified in uri ... #

    def get_size(self,**kwargs):
        return "-"

s.register("/blog/.*", posts())
```

### Starting the Server

After instantiating a server and registering some endpoints, start it with `s.run()`. The web server will run until a keyboard interrupt causes it to gracefully shutdown. The graceful shutdown process entails joining any child threads, closing the socket, and then verifying it will no longer accept connections before exiting. The block below contains an entire script to start a private web server on port 8000, that uses the custom endpoint I defined above:

```
from server import *

class home(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.content = "Goodbye, cruel world."

s = Server()
s.register("/", home())
s.run()
```

Opening [http://localhost:8000](http://localhost:8000) will now present "Goodbye, cruel world."

### Enabling HTTPS

If you want to generate a self-signed certificate to support HTTPS connections, just move into the new `swig` directory and use `openssl` to create a new `server.pem` X.509 certificate. (H/t [dergachev](https://gist.github.com/dergachev/7028596))

```
$ cd swig
$ openssl req -new -x509 -keyout server.pem -out server.pem -days 365 -nodes
```

Pass the `https=True` flag to Swig during instantiation, and it will use `server.pem` to secure HTTPS connections. Note that although your browser will present a warning against trusting the certificate because it is self-signed, rather than signed by a trusted Certificate Authority, the connection is safe. Also note that if Swig cannot find this file, *it will still start the server*, but it will use plaintext HTTP instead of HTTPS. Check out the example below, which builds upon the previous one:

```
from server import *

class home(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.content = "Goodbye, cruel world."

class contact_me(base_page):
    def __init__(self):
        self.content_type = "text/html"
        self.content = "... Just kidding. Let's chat."

s = Server(ip="0.0.0.0",background=True,https=True)
s.register("/", home())
s.register("/contact", contact_me())
s.run()
```

[http://localhost:8000](http://localhost:8000) will now fail, since the server no longer supports plain HTTP connections. Try [**https**://localhost:8000](https://localhost:8000) instead--you will get "Goodbye, cruel world." after dismissing the browser warning, and going to [https://localhost:8000/contact](https://localhost:8000/contact) will yield "... Just kidding. Let's chat." You can now also view these pages from any device on the local network if you know the server's IP address. For example, if my local machine has an IPv4 address of 10.0.0.10, I can go to [https://10.0.0.10:8000](https://10.0.0.10:8000) on my phone to view the home page, and [https://10.0.0.10:8000/contact](https://10.0.0.10:8000/contact) on my iPad to see the invitation to chat.

## Background and Motivation

After fighting with [Flask](https://flask.palletsprojects.com/en/1.1.x/), [Bottle](http://bottlepy.org/docs/dev/), and then Python's own [http.server](https://docs.python.org/3/library/http.server.html) library, I decided to write my own web framework. I liked Flask, but it has far too many dependencies to work in my target environment. I liked Bottle even more, since it mirrors most of Flask's functionality without any dependencies, but it lacks the ability to handle concurrent connections. The surprisingly capable `http.server` library has zero dependencies and supports concurrent execution, but is ill-suited for building out an entire web application. I built *Swig*[^1] to solve all of these problems.

Swig uses the `socket` library to interface with TCP sockets at the lowest level feasible for a language as performant as Python. As Julia Evans pointed out quite some time ago, [it makes little sense to go any lower](https://jvns.ca/blog/2014/08/12/what-happens-if-you-write-a-tcp-stack-in-python/).

## License

This project is licensed under a [Creative Commons Attribution 4.0 International License](http://creativecommons.org/licenses/by/4.0/). Read more about the license, and my other disclaimers, [at my website](https://zacs.site/disclaimers.html). You may also view a local copy of the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License license in [LICENSE.md](./LICENSE.md).

[>1] Flask, Bottle, and Swig--are you getting it?
