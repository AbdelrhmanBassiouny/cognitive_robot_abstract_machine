"""Visualization management for RoboKudo pipelines.

This module provides a behavior tree node that manages visualization of pipeline data
using different visualization backends. It coordinates:

* OpenCV-based visualization
* Open3D visualization
* ROS visualization
* Shared visualization state
* Pipeline data synchronization

Dependencies
-----------
* py_trees for behavior tree functionality
* cv2 for OpenCV visualization
* robokudo.pipeline for pipeline access
* robokudo.vis.* for visualization backends

See Also
--------
* :mod:`robokudo.vis.visualizer` : Base visualization interface
* :mod:`robokudo.vis.cv_visualizer` : OpenCV-based visualization
* :mod:`robokudo.vis.o3d_visualizer` : Open3D-based visualization
* :mod:`robokudo.vis.ros_visualizer` : ROS-based visualization
"""

import copy
import logging
from timeit import default_timer

import py_trees
from py_trees.behaviour import Behaviour

import robokudo.defs
import robokudo.pipeline
import robokudo.vis.cv_visualizer
import robokudo.vis.o3d_visualizer
import robokudo.vis.ros_visualizer
import robokudo.vis.visualizer


class VisualizationManager(Behaviour):
    """Behavior tree node for managing pipeline visualizations.

    This class coordinates visualization of pipeline data across multiple
    visualization backends. It handles:

    * Pipeline data buffering and synchronization
    * Visualizer creation and lifecycle management
    * Shared visualization state
    * Visualization timing and performance monitoring

    Parameters
    ----------
    name : str
        Name of the behavior tree node

    Attributes
    ----------
    pipelines : dict
        Mapping of pipeline names to Pipeline objects
    rk_logger : logging.Logger
        Logger instance for this class
    visualizer_types : list
        List of available visualizer classes
    visualizers : dict
        Mapping of pipeline names to lists of active visualizers

    Notes
    -----
    The manager operates in three phases:

    1. Pre-tick: Prepare visualizers for new data
    2. Tick: Update visualizations
    3. Post-tick: Cleanup and synchronization
    """

    def __init__(self, name):
        """Initialize the visualization manager.

        Parameters
        ----------
        name : str
            Name of the behavior tree node
        """
        super().__init__(name=name)
        self.pipelines = {}
        self.rk_logger = logging.getLogger(robokudo.defs.PACKAGE_NAME)
        self.visualizer_types = [
            robokudo.vis.cv_visualizer.CVVisualizer,
            robokudo.vis.o3d_visualizer.O3DVisualizer,
            robokudo.vis.ros_visualizer.SharedROSVisualizer,
            robokudo.vis.ros_visualizer.AllAnnotatorROSVisualizer,
        ]
        self.visualizers = {}  # key pipeline name to list of Visualizers

    def create_visualizers_for_pipeline(self, pipeline: robokudo.pipeline.Pipeline):
        """Create visualizer instances for a pipeline.

        Parameters
        ----------
        pipeline : robokudo.pipeline.Pipeline
            Pipeline to create visualizers for

        Notes
        -----
        Creates one instance of each visualizer type and associates them
        with the pipeline. All visualizers share a common visualization state.
        """
        # TODO Handle shared visualization context - Not all Visualizers need one!
        shared_state = robokudo.vis.visualizer.Visualizer.SharedState()
        visualizers = [visclass.new_visualizer_instance(pipeline=pipeline, shared_visualizer_state=shared_state) for
                       visclass in
                       self.visualizer_types]
        self.visualizers[pipeline.name] = visualizers

    @staticmethod
    def visualizer_instances():
        """Get all active visualizer instances.

        Returns
        -------
        list
            List of all active Visualizer instances
        """
        return robokudo.vis.visualizer.Visualizer.instances

    def initialise(self):
        """Initialize the behavior tree node.

        This method:

        * Clears existing pipeline references
        * Finds all Pipeline nodes in the behavior tree
        * Stores references to found pipelines

        Notes
        -----
        The VisualizationManager should be placed one level below the top node
        (Parallel) in the behavior tree.
        """
        self.rk_logger.debug("%s.initialise()" % self.__class__.__name__)
        self.pipelines = {}
        # The GUIManager should live one level below the top-node (Parallel)
        # Initially fill a list of all Pipelines
        for node in self.parent.iterate():
            if isinstance(node, robokudo.pipeline.Pipeline):
                self.pipelines[node.name] = node

    def update(self):
        """Update visualizations for all pipelines.

        This method:

        1. Copies new data from buffer to visualization map
        2. Creates visualizers for new pipelines
        3. Notifies visualizers of new data
        4. Executes pre-tick, tick, and post-tick phases
        5. Checks for termination signals

        Returns
        -------
        py_trees.common.Status
            FAILURE if any visualizer indicates termination, RUNNING otherwise

        Notes
        -----
        The update cycle ensures synchronized visualization across all backends
        while maintaining separation between data buffers and visualization state.
        """
        self.rk_logger.debug("%s.update()" % self.__class__.__name__)
        start_timer = default_timer()

        blackboard = py_trees.blackboard.Blackboard()
        annotator_output_pipeline_map_buffer = blackboard.get("annotator_output_pipeline_map_buffer")  # Working buffer
        annotator_output_pipeline_map_visualized = blackboard.get(
            "annotator_output_pipeline_map_visualized")  # Vis only

        # Create Visualized Buffer if new data is available
        for pipeline_name in annotator_output_pipeline_map_buffer.map:
            if annotator_output_pipeline_map_buffer.map[pipeline_name].redraw:
                self.rk_logger.debug("%s.update(): Redraw flag on Pipeline %s is true. Copying data"
                                     % (self.__class__.__name__, pipeline_name))

                annotator_output_pipeline_map_visualized.map[pipeline_name] = \
                    copy.deepcopy(annotator_output_pipeline_map_buffer.map[pipeline_name])

                annotator_output_pipeline_map_buffer.map[pipeline_name].redraw = False

        # Create new Visualizers based on the visualization data
        for pipeline_name in annotator_output_pipeline_map_visualized.map:
            assert (pipeline_name in self.pipelines)

            if pipeline_name not in self.visualizers:
                self.create_visualizers_for_pipeline(self.pipelines[pipeline_name])

            # Ping Visualizers if there is new data for this Pipeline
            if annotator_output_pipeline_map_visualized.map[pipeline_name].redraw:
                for visualizer in self.visualizers[pipeline_name]:
                    visualizer.new_data_available()

                # Visualizers have been informed
                annotator_output_pipeline_map_visualized.map[pipeline_name].redraw = False

        # Pre-tick
        for pipeline_name, visualizer_list in self.visualizers.items():
            for visualizer in visualizer_list:
                visualizer.pre_tick()

        # Tick
        for pipeline_name, visualizer_list in self.visualizers.items():
            for visualizer in visualizer_list:
                visualizer.tick()
        # Post Tick
        for pipeline_name, visualizer_list in self.visualizers.items():
            for visualizer in visualizer_list:
                visualizer.post_tick()

        # Static Post Tick
        for visualizer_type in self.visualizer_types:
            visualizer_type.static_post_tick()

        # Check if one Visualizer returned a termination signal
        for vis in VisualizationManager.visualizer_instances():
            if vis.indicate_termination():
                return py_trees.common.Status.FAILURE

        end_timer = default_timer()
        self.feedback_message = f'Processing took {(end_timer - start_timer):.4f}s'

        return py_trees.common.Status.RUNNING
