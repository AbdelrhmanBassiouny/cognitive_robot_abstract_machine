"""Base visualization interface for RoboKudo pipelines.

This module provides the base visualization interface and shared state management
for RoboKudo pipeline visualization. It implements:

* Observer pattern for state updates
* Shared visualization state
* Visualizer lifecycle management
* Pipeline data access
* Common visualization utilities

Dependencies
-----------
* logging for status messages
* py_trees for behavior tree integration
* robokudo.annotators for annotator access
* robokudo.pipeline for pipeline access

See Also
--------
* :mod:`robokudo.vis.cv_visualizer` : OpenCV-based visualization
* :mod:`robokudo.vis.o3d_visualizer` : Open3D-based visualization
* :mod:`robokudo.vis.ros_visualizer` : ROS-based visualization
"""

import logging

import py_trees

from robokudo.annotators.core import BaseAnnotator
import robokudo.pipeline


class Visualizer(object):
    """Base class for RoboKudo pipeline visualizers.

    This class provides the foundation for implementing pipeline visualizers. It includes:

    * Observer pattern for state updates
    * Shared visualization state
    * Visualizer lifecycle management
    * Pipeline data access
    * Common visualization utilities

    Parameters
    ----------
    pipeline : robokudo.pipeline.Pipeline
        Pipeline to visualize
    shared_visualizer_state : SharedState, optional
        Shared state object for coordinating between visualizers

    Attributes
    ----------
    pipeline : robokudo.pipeline.Pipeline
        Pipeline being visualized
    indicate_termination_var : bool
        Flag indicating if visualization should terminate
    shared_visualizer_state : SharedState
        Shared state object for coordinating between visualizers
    update_output : bool
        Flag indicating if display needs updating
    new_data : bool
        Flag indicating if new data is available
    rk_logger : logging.Logger
        Logger instance
    instances : list
        List of all active visualizer instances

    Notes
    -----
    Do not instantiate this class directly. Use :meth:`new_visualizer_instance`
    to properly register visualizers.
    """

    # Observer pattern from https://en.wikipedia.org/wiki/Observer_pattern
    class Observable:
        """Base class for objects that can be observed.

        This class implements the Observable part of the Observer pattern.
        """

        def __init__(self):
            """Initialize the observable object."""
            self._observers = []

        def register_observer(self, observer):
            """Register an observer to receive notifications.

            Parameters
            ----------
            observer : Observer
                The observer to register
            """
            self._observers.append(observer)

        def notify_observers(self, *args, **kwargs):
            """Notify all registered observers.

            Parameters
            ----------
            *args
                Variable length argument list passed to observers
            **kwargs
                Arbitrary keyword arguments passed to observers
            """
            for obs in self._observers:
                obs.notify(self, *args, **kwargs)

    class Observer:
        """Base class for objects that observe state changes.

        This class implements the Observer part of the Observer pattern.
        """

        def notify(self, observable, *args, **kwargs):
            """Handle notification of state changes.

            Parameters
            ----------
            observable : Observable
                The object that sent the notification
            *args
                Variable length argument list
            **kwargs
                Arbitrary keyword arguments

            Raises
            ------
            Exception
                If not implemented by subclass
            """
            print("Got", args, kwargs, "From", observable)
            # Show the passed data, but terminate. Make this an ABC in the future.
            raise Exception("You need to implement the notify method in your Visualizer to catch update requests.")

    class SharedState(Observable):
        """Shared state for single-view visualizers.

        This class manages state shared between visualizers, particularly for
        single-view visualizers that switch between annotators. It uses the
        Observer pattern to notify visualizers of state changes.

        Notes
        -----
        The Observer pattern is used for state changes, not for new data.

        Attributes
        ----------
        active_annotator : BaseAnnotator
            Currently active annotator
        active_annotator_i : int
            Index of currently active annotator
        """

        def __init__(self):
            """Initialize shared state."""
            super().__init__()
            self.active_annotator = None
            self.active_annotator_i = 0

    instances = []

    def __init__(self, pipeline: robokudo.pipeline.Pipeline, shared_visualizer_state=None):
        """Initialize the visualizer.

        Do not use this constructor directly. Use :meth:`new_visualizer_instance`
        to properly register visualizers.

        Parameters
        ----------
        pipeline : robokudo.pipeline.Pipeline
            Pipeline to visualize
        shared_visualizer_state : SharedState, optional
            Shared state object for coordinating between visualizers
        """
        self.pipeline = pipeline
        self.indicate_termination_var = False
        self.shared_visualizer_state = shared_visualizer_state
        self.update_output = True  # Indicate that the output of this Visualizer needs to be renewed/redrawn
        self.new_data = False

        # for now we assume that every annotator outputs an image
        if self.shared_visualizer_state and not self.shared_visualizer_state.active_annotator:
            self.shared_visualizer_state.active_annotator = self.pipeline.get_annotators()[0]
            self.shared_visualizer_state.active_annotator_i = 0

        self.rk_logger = logging.getLogger(robokudo.defs.PACKAGE_NAME)

    def identifier(self):
        """Get a unique identifier for this visualizer."""
        return "RoboKudo/" + self.pipeline.name

    def pre_tick(self):
        """Prepare for visualization update.

        Called before :meth:`tick`. Override to implement pre-update logic.
        """
        pass

    def tick(self):
        """Update the visualization display.

        This is the main method for visualizers. Override to implement
        visualization logic.
        """
        pass

    def post_tick(self):
        """Clean up after visualization update.

        Called after :meth:`tick`. Override to implement post-update logic.
        """
        pass

    @staticmethod
    def static_post_tick():
        """Perform static post-update operations.

        This method is called once per visualizer type, regardless of how many
        instances exist. Override to implement static post-update logic.
        """
        pass

    @classmethod
    def new_visualizer_instance(cls, pipeline: robokudo.pipeline.Pipeline, shared_visualizer_state=None):
        """Create and register a new visualizer instance.

        Parameters
        ----------
        pipeline : robokudo.pipeline.Pipeline
            Pipeline to visualize
        shared_visualizer_state : SharedState, optional
            Shared state object for coordinating between visualizers

        Returns
        -------
        Visualizer
            New visualizer instance
        """
        vis = cls(pipeline=pipeline, shared_visualizer_state=shared_visualizer_state)
        Visualizer.instances.append(vis)
        return vis

    @staticmethod
    def clear_visualizer_instances():
        """Remove all registered visualizer instances."""
        Visualizer.instances.clear()

    def insert_input(self):
        """Handle input insertion.

        Override to implement input handling logic.
        """
        pass

    def activate_update_output(self):
        """Mark visualizer for update.

        Sets the update flag to trigger a redraw.
        """
        self.update_output = True

    def new_data_available(self):
        """Signal that new data is available.

        Called by external code to indicate new data is ready for visualization.
        """
        self.new_data = True

    def indicate_termination(self):
        """Check if visualization should terminate.

        Returns
        -------
        bool
            True if visualization should terminate, False otherwise
        """
        return self.indicate_termination_var

    @staticmethod
    def get_unique_types_of_visualizer_instances():
        """Get set of unique visualizer types.

        Returns
        -------
        set
            Set of visualizer classes that have instances
        """
        return set([type(x) for x in Visualizer.instances])

    def update_output_flag_for_new_data(self) -> None:
        """Update flags when new data arrives.

        Sets update flag and clears new data flag when new data is available.
        """
        if self.new_data:
            self.update_output = True
            self.new_data = False

    def get_visualized_annotator_outputs_for_pipeline(self) -> robokudo.annotators.outputs.AnnotatorOutputs:
        """Get annotator outputs for visualization.

        Returns
        -------
        robokudo.annotators.outputs.AnnotatorOutputs
            Annotator outputs for the current pipeline

        Raises
        ------
        AssertionError
            If outputs are not of the expected type
        """
        blackboard = py_trees.blackboard.Blackboard()
        annotator_output_pipeline_map_visualized = blackboard.get("annotator_output_pipeline_map_visualized")
        annotator_outputs = annotator_output_pipeline_map_visualized.map[self.pipeline.name]
        assert (isinstance(annotator_outputs, robokudo.annotators.outputs.AnnotatorOutputs))

        return annotator_outputs
