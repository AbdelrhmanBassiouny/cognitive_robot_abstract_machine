from dataclasses import dataclass, field
from uuid import UUID

from typing_extensions import List, Dict

from ..spatial_types.derivatives import Derivatives
from .world_state import WorldStateTrajectory


@dataclass
class WorldStateTrajectoryPlotter:
    """
    This class will use matplot lib to create a plot for a trajectory of world states.
    It will have subplots for each derivative.
    """

    derivatives_to_plot: List[Derivatives]
    """A plot will be generated for each entry in this list."""

    subplot_height_in_cm: float = 6.0
    """Height of each derivative subplot in cm."""

    legend: bool = True
    """If True, a legend will be added to the plot."""

    sort_degrees_of_freedom: bool = True
    """If True, the degrees of freedom will be sorted by name before plotting."""

    second_width_in_cm: float = 2.0
    """Width of a second in cm."""

    y_label: Dict[Derivatives, str] = field(
        default_factory=lambda: {
            Derivatives.position: "rad or m",
            Derivatives.velocity: "rad/s or m/s",
            Derivatives.acceleration: "rad/s**2 or m/s**2",
            Derivatives.jerk: "rad/s**3 or m/s**3",
        }
    )
    """Label of the y-axis."""

    center_positions: bool = False
    """
    If True, the position plots will be centered around 0.
    This may be useful if continues joints are used, because they can achieve very large values.
    """

    plot_0_lines: bool = True
    """
    If False, lines of degrees of freedom that are constant 0 will not be plotted to reduce clutter.
    """

    color_map: Dict[UUID, str] | None = None
    """
    A color map to use for plotting the trajectory.
    Use can use matplotlib styles, like 'r:' for dotted red lines.
    It should map the UUIDs of degrees of freedom in the world state trajectory to colors. 
    If None, a default color map will be used.
    
    Each degree of freedom will have the same color in each subplot.
    """

    def plot_trajectory(
        self, world_state_trajectory: WorldStateTrajectory, file_name: str
    ):
        """
        Plots the trajectory and saves the resulting plot to the specified file.

        :param world_state_trajectory: The trajectory to plot.
        :param file_name: The name of the file where the plot will be saved.
        """
