import multiprocessing
import os

# Gunicorn configuration
bind = "0.0.0.0:10000"
workers = 2  # Reduced number of workers for free tier
worker_class = "sync"
worker_connections = 50
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "daily-tv-serials"

# Worker processes
preload_app = False  # Important: Don't preload to avoid MongoDB fork issues
max_requests = 100
max_requests_jitter = 10

# Prevent zombie processes
daemon = False

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    pass

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")
