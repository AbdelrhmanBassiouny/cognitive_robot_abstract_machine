"""Annotation writer classes for RoboKudo.

This module provides annotators for writing and publishing annotations.
"""

import os
import shutil
from timeit import default_timer

from std_msgs.msg import String
import rospy
from ..utils import serialization as serializer
from py_trees.common import Status
from . import core


class AnnotationStorageWriter(core.BaseAnnotator):
    """Annotator for writing annotations to storage in JSON format.

    This annotator writes the current CAS annotations to files in a specified
    directory, using JSON serialization.

    :ivar counter: Counter for generating sequential filenames
    :type counter: int
    """

    class Descriptor(core.BaseAnnotator.Descriptor):
        """Configuration descriptor for annotation storage writer."""

        class Parameters:
            """Parameters for configuring annotation storage."""

            def __init__(self):
                self.basic_path: str = "annotations"
                """Base directory for storing annotations, defaults to "annotations"""

                self.suffix: str = "json"
                """File extension for annotation files, defaults to "json"""

        parameters = (
            Parameters()
        )  # overwrite the parameters explicitly to enable auto-completion

    def __init__(
        self,
        name: str = "AnnotationStorageWriter",
        descriptor: Descriptor = Descriptor(),
    ):
        """Initialize the annotation storage writer. Minimal one-time init!

        :param name: Name of the annotator instance, defaults to "AnnotationStorageWriter"
        :param descriptor: Configuration descriptor, defaults to Descriptor()
        """
        super().__init__(name, descriptor)
        self.rk_logger.debug("%s.__init__()" % self.__class__.__name__)

        self.counter = -1
        """Counter for generating sequential filenames"""

    def update(self):
        """Write current CAS annotations to storage.

        Serializes the current annotations to JSON and writes them to a file
        in the configured directory. Files are numbered sequentially.

        :return: SUCCESS after writing annotations
        """
        start_timer = default_timer()

        # encode data as json string
        json_data_string = serializer.encode(self.get_cas().annotations)

        dir_path = os.path.join(self.descriptor.parameters.basic_path, self.name)

        # increase count
        self.counter += 1

        if self.counter == 0 and os.path.exists(dir_path):
            shutil.rmtree(dir_path)

        os.makedirs(dir_path, exist_ok=True)

        json_path = os.path.join(
            dir_path, "{}.{}".format(self.counter, self.descriptor.parameters.suffix)
        )
        with open(json_path, "w") as f:
            f.write(json_data_string)

        end_timer = default_timer()
        self.feedback_message = f"Processing took {(end_timer - start_timer):.4f}s"
        return Status.SUCCESS


class AnnotationPublisherWriter(core.BaseAnnotator):
    """Annotator for publishing annotations via ROS topics.

    This annotator publishes the current CAS annotations as JSON-encoded
    strings over a ROS topic.

    :ivar pub: ROS publisher for annotations
    :type pub: rospy.Publisher
    """

    class Descriptor(core.BaseAnnotator.Descriptor):
        """Configuration descriptor for annotation publisher."""

        class Parameters:
            """Parameters for configuring annotation publishing."""

            def __init__(self):
                self.topic_name: str = "/annotations"
                """Name of the ROS topic to publish on, defaults to "/annotations"""

        parameters = (
            Parameters()
        )  # overwrite the parameters explicitly to enable auto-completion

    def __init__(
        self,
        name: str = "AnnotationPublisherWriter",
        descriptor: "AnnotationPublisherWriter.Descriptor" = Descriptor(),
    ):
        """Initialize the annotation publisher. Minimal one-time init!

        :param name: Name of the annotator instance, defaults to "AnnotationPublisherWriter"
        :param descriptor: Configuration descriptor, defaults to Descriptor()
        """
        super().__init__(name, descriptor)
        self.rk_logger.debug("%s.__init__()" % self.__class__.__name__)

        self.pub = None

    def setup(self, timeout: float):
        """Set up the ROS publisher. Useful for delayed initialization. For example ROS pub/sub, drivers.

        :param timeout: Maximum time to wait for setup completion
        :return: True if setup was successful
        """
        self.rk_logger.debug("%s.setup()" % self.__class__.__name__)

        self.pub = rospy.Publisher(
            self.descriptor.parameters.topic_name, String, queue_size=10
        )

    def update(self) -> Status:
        """Publish current CAS annotations.

        Serializes the current annotations to JSON and publishes them
        on the configured ROS topic.

        :return: SUCCESS after publishing annotations
        """
        start_timer = default_timer()

        # encode data as json string
        json_data_string = serializer.encode(self.get_cas().annotations)

        # publish encoded data
        self.pub.publish(json_data_string)

        end_timer = default_timer()
        self.feedback_message = f"Processing took {(end_timer - start_timer):.4f}s"
        return Status.SUCCESS
