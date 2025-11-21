# threading_utils.py
"""
Threading utilities.

In this version we don't strictly need a separate module because we use
Qt signals directly in the GUI, but this file demonstrates how you could
add reusable helpers if you want.
"""

import threading


def start_daemon_thread(target, args=(), name=None) -> threading.Thread:
    """Start a daemon thread with basic error isolation."""
    thread = threading.Thread(target=target, args=args, name=name, daemon=True)
    thread.start()
    return thread


class StoppableThread(threading.Thread):
    """A thread that can be signaled to stop."""

    def __init__(self, target=None, args=(), name=None):
        super().__init__(target=target, args=args, name=name, daemon=True)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self) -> bool:
        return self._stop_event.is_set()
