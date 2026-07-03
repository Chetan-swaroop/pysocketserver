# PySocketServer: A High-Performance HTTP/1.1 Server

A production-grade **HTTP/1.1 web server** built entirely from scratch in Python using raw TCP sockets. This project implements the core networking stack—including socket management, HTTP protocol parsing, request handling, and concurrent client processing—without using web frameworks such as Flask or Django.

---

## Overview

Modern web frameworks abstract away networking details, making it difficult to understand how HTTP and TCP operate internally.

PySocketServer was built to gain a deeper understanding of:

* TCP socket programming
* HTTP/1.1 protocol internals
* Concurrent server architecture
* Request parsing and response generation
* Secure file serving
* Resource management

The project demonstrates systems programming concepts commonly used in networking and backend infrastructure.

---

## Features

### HTTP/1.1 Support

* GET request handling
* Persistent connections (Keep-Alive)
* Proper status codes
* HTTP header parsing
* Content-Length handling

### Concurrent Architecture

* ThreadPoolExecutor-based worker pool
* Bounded concurrency model
* Efficient handling of multiple clients
* Controlled resource usage

### Caching Support

* Conditional GET support
* If-Modified-Since handling
* 304 Not Modified responses

### Security

* Path traversal prevention
* Document root isolation
* Header size limits
* Request body limits
* Safe filesystem mapping

### File Serving

* Static HTML pages
* CSS files
* JavaScript files
* Images and assets
* Custom 404 pages

---

## Architecture

```text
Client Browser
       │
       ▼
TCP Socket Server
       │
       ▼
Request Parser
       │
       ▼
Request Handler
       │
       ▼
Response Builder
       │
       ▼
HTTP Response
```

### Module Structure

```text
.
├── main.py
├── server.py
├── request.py
├── handler.py
├── response.py
└── static/
```

| File        | Responsibility                        |
| ----------- | ------------------------------------- |
| server.py   | TCP socket management and thread pool |
| request.py  | HTTP request parsing                  |
| handler.py  | Route handling and file access        |
| response.py | HTTP response generation              |
| main.py     | Application entry point               |

---

## Technical Highlights

### TCP Socket Programming

* bind()
* listen()
* accept()
* recv()
* send()

### HTTP Parsing

* Request line parsing
* Header extraction
* Content-Length handling
* Connection management

### Concurrency

* Thread pool architecture
* Worker scheduling
* Connection handling

### Security

* Path traversal protection
* Request validation
* Resource limits

---

## Running the Server

### Default Configuration

```bash
python main.py
```

Default:

* Port: 8080
* Workers: 32
* Docroot: ./static

### Custom Configuration

```bash
python main.py --port 9000 --workers 64 --docroot ./my_files
```

---

## Example Request

```http
GET /index.html HTTP/1.1
Host: localhost:8080
Connection: keep-alive
```

---

## Example Response

```http
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 1245
Connection: keep-alive
```

---

## Performance Features

* Persistent connections
* Reduced connection overhead
* Thread-pooled workers
* Efficient I/O handling
* Conditional caching

---

## Skills Demonstrated

* Computer Networks
* Operating Systems
* Socket Programming
* HTTP Protocol
* Multithreading
* Concurrency
* Systems Programming
* Backend Engineering

---

## Future Improvements

* HTTPS/TLS support
* Gzip compression
* Reverse proxy support
* Access logging
* Rate limiting
* Thread-safe caching
* HTTP/2 support

---
