"""
Running an object's shutdown when the interpreter exits.
"""

from __future__ import annotations

import atexit
import weakref
from dataclasses import dataclass, field

from typing_extensions import Callable, Optional


@dataclass
class ShutdownAtExit:
    """
    Runs one object's shutdown when the interpreter exits, for as long as the object is
    still in use.

    :mod:`atexit` keeps what it is handed until the process ends, so a bound method
    registered with it directly keeps its object -- and everything that object reaches
    -- alive for the rest of the run. This holds the method weakly instead, so an object
    nothing else uses is collected and its shutdown is dropped with it.
    """

    _shutdown: Optional[weakref.WeakMethod] = field(default=None, init=False)
    """
    The method to run at exit, held weakly through the object it is bound to.
    """

    @classmethod
    def register(cls, shutdown: Callable[[], None]) -> ShutdownAtExit:
        """
        Ask for a method to be run when the interpreter exits.

        :param shutdown: The bound method to run.
        :return: The registration, which :meth:`cancel` takes back.
        """
        registration = cls()
        registration._shutdown = weakref.WeakMethod(shutdown, registration._forget)
        atexit.register(registration)
        return registration

    def cancel(self) -> None:
        """
        Take the registration back, for an object that has shut down already.
        """
        atexit.unregister(self)

    def _forget(self, _collected: weakref.ref) -> None:
        """
        Take the registration back once the object it would shut down is gone.

        :param _collected: The dead reference, which :class:`weakref.WeakMethod` hands
            its callback.
        """
        self.cancel()

    def __call__(self) -> None:
        """
        Run the shutdown, unless its object has been collected in the meantime.
        """
        shutdown = self._shutdown()
        if shutdown is None:
            return
        shutdown()
