"""ROS-based visualization for RoboKudo pipelines.

This module provides ROS-based visualization capabilities for RoboKudo pipelines.
It handles:

* Image publishing to ROS topics
* Single and multi-view visualization
* Pipeline state visualization
* Dynamic topic management
* Image format conversion

Dependencies
-----------
* rospy for ROS integration
* cv2 for image manipulation
* numpy for array operations
* cv_bridge for ROS/OpenCV conversion
* robokudo.annotators for annotator access
* robokudo.vis.visualizer for base visualization interface

See Also
--------
* :mod:`robokudo.vis.visualizer` : Base visualization interface
* :mod:`robokudo.vis.cv_visualizer` : OpenCV-based visualization
* :mod:`robokudo.vis.o3d_visualizer` : Open3D-based visualization
"""

import cv2
import numpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

from robokudo.annotators.core import BaseAnnotator
from robokudo.vis.visualizer import Visualizer


class SharedROSVisualizer(Visualizer, Visualizer.Observer, Node):
    """A single-view ROS Image Publisher. It publishes the active annotator from the SharedState.

    :ivar shared_visualizer_state: Shared state object for coordinating between visualizers
    :type shared_visualizer_state: Visualizer.SharedState
    :ivar ros_image_publisher: Publisher for the image topic
    :type ros_image_publisher: rospy.Publisher
    :ivar ros_image_cv_bridge: Bridge for converting between ROS and OpenCV image formats
    :type ros_image_cv_bridge: CvBridge
    :ivar update_output: Flag indicating if display needs updating
    :type update_output: bool
    """

    def __init__(self, *args, **kwargs):
        """Initialize the shared ROS visualizer."""
        Visualizer.__init__(self, *args, **kwargs)
        Node.__init__(self, 'shared_ros_visualizer')
        # This Visualizer works with a shared state and needs notifications
        self.shared_visualizer_state.register_observer(self)
        self.ros_image_publisher = self.create_publisher(Image, f"{self.pipeline.name}/output_image", 10)
        self.ros_image_cv_bridge = CvBridge()

    def tick(self):
        """Update the visualization display.

        This method:

        * Gets current annotator outputs
        * Updates display if needed
        * Renders annotator name overlay
        * Publishes image to ROS topic
        """
        annotator_outputs = self.get_visualized_annotator_outputs_for_pipeline()

        assert (self.shared_visualizer_state.active_annotator is not None)
        active_annotator_instance: BaseAnnotator = self.shared_visualizer_state.active_annotator

        self.update_output_flag_for_new_data()

        # Check if we have to render something
        if self.update_output:
            self.update_output = False
            # 2D imshow output
            img = None
            if active_annotator_instance.name not in annotator_outputs.outputs:
                # We do not yet have visual output set up for this annotator
                # This might happen in dynamic perception pipelines, where annotators have not been set up
                # during construction of the tree AND don't generate image outputs.
                # Create an empty image to show in the visualizer
                img = numpy.zeros((640, 480, 3), dtype="uint8")
            else:
                img = annotator_outputs.outputs[active_annotator_instance.name].image
            img_with_annotator_text = cv2.putText(img,
                                                  active_annotator_instance.name,
                                                  (15, 15),
                                                  cv2.FONT_HERSHEY_SIMPLEX,
                                                  0.5,
                                                  (0, 255, 0),
                                                  2)
            self.ros_image_publisher.publish(self.ros_image_cv_bridge.cv2_to_imgmsg(img_with_annotator_text))

    def notify(self, observable, *args, **kwargs):
        """Handle notification of state changes.

        :param observable: The object that sent the notification
        :type observable: object
        """
        self.update_output = True


class AllAnnotatorROSVisualizer(Visualizer, Node):
    """A ROS Image Publisher that publishes the output of all images in the given Pipeline.

    This class provides visualization of all annotator outputs in a pipeline
    through separate ROS image topics. It supports:

    * Multiple image topic publishing
    * Dynamic topic creation
    * Image format conversion
    * Per-annotator output streams

    :ivar ros_image_publishers: Mapping of annotator names to ROS publishers
    :type ros_image_publishers: dict
    :ivar ros_image_cv_bridge: Bridge for converting between ROS and OpenCV image formats
    :type ros_image_cv_bridge: CvBridge
    :type update_output: bool
    :ivar update_output: Flag indicating if display needs updating
    """

    def __init__(self, *args, **kwargs):
        """Initialize the multi-view ROS visualizer."""
        Visualizer.__init__(self, *args, **kwargs)
        Node.__init__(self, 'all_annotator_ros_visualizer')
        # This Visualizer works with a shared state and needs notifications
        self.ros_image_publishers = {}  # Dict of Publishers based on annotator name
        self.ros_image_cv_bridge = CvBridge()

    def update_ros_image_publishers(self):
        """Update ROS publishers for all annotators.

        This method:

        * Gets current list of annotators
        * Creates publishers for new annotators
        * Maintains existing publishers

        TODO: Consider removing publishers for non-existing annotators. May not be
         worth the cost if re-instantiation is frequent due to changing annotator lists.
        """
        annotator_list = self.pipeline.get_annotators()
        for annotator in annotator_list:
            if annotator.name not in self.ros_image_publishers:
                self.ros_image_publishers[annotator.name] = self.create_publisher(
                    Image, f"{self.pipeline.name}/{annotator.name}/output_image", 10)

    def tick(self):
        """Update all visualization displays.

        This method:

        * Gets current annotator outputs
        * Updates publishers if needed
        * Publishes all annotator images to ROS topics
        """
        annotator_outputs = self.get_visualized_annotator_outputs_for_pipeline()

        self.update_output_flag_for_new_data()

        # Check if we have to render something
        if self.update_output:
            self.update_output = False

            self.update_ros_image_publishers()

            for annotator_name, annotator_output in annotator_outputs.outputs.items():
                img = annotator_output.image
                self.ros_image_publishers[annotator_name].publish(self.ros_image_cv_bridge.cv2_to_imgmsg(img))

    def notify(self, observable, *args, **kwargs):
        """Handle notification of state changes.

        :param observable: The object that sent the notification
        :type observable: object
        """
        self.update_output = True
