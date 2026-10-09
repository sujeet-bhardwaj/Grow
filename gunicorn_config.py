"""
Gunicorn Configuration for Groww Algo Trading Bot (Render / WSGI).
Ensures the background trading scanner loop starts properly inside the active worker process.
"""

import os

# Server socket
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Worker processes
workers = 1
threads = 4
worker_class = "gthread"
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"


def post_fork(server, worker):
    """
    Called just after a worker process has been forked in Gunicorn on Linux (Render).
    Guarantees that the background market scanner thread runs inside the worker process
    where all web requests are handled.
    """
    server.log.info(f"[GUNICORN POST-FORK] Worker spawned (PID: {worker.pid}). Initializing bot scanner thread...")
    try:
        from app import ensure_bot_running
        ensure_bot_running()
        server.log.info(f"[GUNICORN POST-FORK] Bot trading thread successfully initialized in worker PID: {worker.pid}")
    except Exception as e:
        server.log.error(f"[GUNICORN POST-FORK] Failed to initialize bot in worker PID {worker.pid}: {e}")
