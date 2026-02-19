import traceback
from threading import Thread
from time import sleep

import rclpy
from ament_index_python import get_package_share_directory
from rclpy import Future
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .my_multithreaded_executor import MyMultiThreadedExecutor
from .. import MiddlewareWrapper, set_middleware, get_middleware

node: Node = None
executor: MultiThreadedExecutor = None
spinner_thread: Thread = None


class ROS2Wrapper(MiddlewareWrapper):

    def loginfo(self, msg: str):
        global node
        node.get_logger().info(msg)

    def logwarn(self, msg: str):
        global node
        # node.get_logger().warn(msg)
        node.get_logger().warning(msg)

    def logerr(self, msg: str):
        global node
        node.get_logger().error(msg)

    def logdebug(self, msg: str):
        global node
        node.get_logger().debug(msg)

    def logfatal(self, msg: str):
        global node
        node.get_logger().fatal(msg)

    def resolve_iri(cls, path: str) -> str:
        """
        e.g. 'package://giskardpy/data'
        """
        if "package://" in path:
            split = path.split("package://")
            prefix = split[0]
            result = prefix
            for suffix in split[1:]:
                package_name, suffix = suffix.split("/", 1)
                real_path = get_package_share_directory(package_name)
                result += f"{real_path}/{suffix}"
            return result
        else:
            return path.replace("file://", "")


def heart():
    global node, executor
    executor = MyMultiThreadedExecutor(thread_name_prefix="giskard executor")
    executor.add_node(node)
    try:
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.1)
            sleep(0.001)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    except Exception:
        traceback.print_exc()
    # Avoid touching a destroyed node during shutdown
    try:
        if node is not None:
            node.get_logger().info("Giskard died.")
    except Exception:
        pass


def init_node(node_name: str) -> None:
    global node, spinner_thread, executor
    if node is not None:
        get_middleware().logwarn("ros node already initialized.")
        return
    rclpy.init()
    node = Node(node_name)
    spinner_thread = Thread(target=heart, daemon=True, name="rclpy spin")
    set_middleware(ROS2Wrapper())
    spinner_thread.start()


def wait_for_future_to_complete(future: Future) -> None:
    while rclpy.ok() and not future.done():
        sleep(0.01)


def shutdown() -> None:
    """
    Cleanly shutdown the ROS2 node, executor and spin thread between tests.
    This avoids InvalidHandle errors on subsequent initialisations.
    """
    global node, executor, spinner_thread

    executor.shutdown()
    spinner_thread.join(2.0)
    node.destroy_node()
    rclpy.shutdown()

    # Reset globals
    executor = None
    spinner_thread = None
    node = None
