import os
import warnings
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Optional

from rclpy import Context
from rclpy.executors import MultiThreadedExecutor


class MyMultiThreadedExecutor(MultiThreadedExecutor):
    def __init__(
            self,
            num_threads: Optional[int] = None,
            *, context: Optional[Context] = None,
            thread_name_prefix: Optional[str] = None
    ) -> None:
        super().__init__(context=context)
        if num_threads is None:
            # On Linux, it will try to use the number of CPU this process has access to.
            # Other platforms, os.sched_getaffinity() doesn't exist so we use the number of CPUs.
            if hasattr(os, 'sched_getaffinity'):
                num_threads = len(os.sched_getaffinity(0))
            else:
                num_threads = os.cpu_count()
            # The calls above may still return None if they aren't supported
            if num_threads is None:
                num_threads = 2
        if num_threads == 1:
            warnings.warn(
                'MultiThreadedExecutor is used with a single thread.\n'
                'Use the SingleThreadedExecutor instead.')
        self._futures = []
        self._executor = ThreadPoolExecutor(num_threads, thread_name_prefix=thread_name_prefix)