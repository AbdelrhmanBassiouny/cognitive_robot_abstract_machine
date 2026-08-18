"""
Keeping a thread joinable across module loads.

The interpreter releases one lock per thread when that thread's state is deleted, and
:meth:`threading.Thread.join` and :meth:`threading.Thread.is_alive` are built on it.
Registering such a lock always registers it for the calling thread, so a module that
registers one of its own while being imported takes the registration away from whichever
thread ran the import.
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass, field

# %% the lock join() waits on


@dataclass
class ThreadExitSentinel:
    """
    The registration that lets a thread be joined once it ends.

    A thread whose registration was taken over keeps its own lock locked for the life of the
    process: it reports itself alive after its target has returned, and joining it blocks
    forever.
    """

    thread: threading.Thread = field(default_factory=threading.current_thread)
    """
    The thread the sentinel belongs to.
    """

    @property
    def is_registered(self) -> bool:
        """
        Whether the interpreter still holds this thread's lock and will release it when
        the thread ends.

        The interpreter keeps a weak reference to the lock it will release, so a lock
        nothing refers to weakly is one no longer registered for anybody.
        """
        lock = self.thread._tstate_lock
        return lock is not None and weakref.getweakrefcount(lock) > 0

    def ensure_registered(self):
        """
        Register a fresh lock for the thread if its own is no longer registered.

        The abandoned lock stays locked for the life of the process, so it is also
        dropped from the set :func:`threading._shutdown` waits on; left there it would
        hang interpreter shutdown on a thread that has long since ended.
        """
        if self.is_registered:
            return
        abandoned_lock = self.thread._tstate_lock
        self.thread._set_tstate_lock()
        with threading._shutdown_locks_lock:
            threading._shutdown_locks.discard(abandoned_lock)
