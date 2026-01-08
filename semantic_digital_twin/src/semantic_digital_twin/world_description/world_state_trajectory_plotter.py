from dataclasses import dataclass, field
from uuid import UUID

from typing_extensions import List, Dict

import numpy as np
import matplotlib

# Force non-interactive backend to avoid GUI backend requirements in headless/test environments.
try:
    matplotlib.use("Agg", force=True)
except Exception:
    pass
import matplotlib.pyplot as plt

from ..spatial_types.derivatives import Derivatives
from .world_state import WorldStateTrajectory


@dataclass
class WorldStateTrajectoryPlotter:
    """
    Plot a trajectory of world states with one subplot per derivative.

    Subplots share the x axis (time in seconds, normalized so that the first time maps to 0).
    Physical x scaling matches the Gantt chart logic: inches_per_second = second_width_in_cm / 2.54.
    """

    derivatives_to_plot: List[Derivatives] = field(
        default_factory=lambda: list(Derivatives)
    )
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
            Derivatives.acceleration: "rad/s² or m/s²",
            Derivatives.jerk: "rad/s³ or m/s³",
        }
    )
    """Label of the y-axis."""

    center_positions: bool = False
    """
    If True, the position plots will be centered around 0.
    This may be useful if continues joints are used, because they can achieve very large values.
    """

    plot_0_lines: bool = False
    """
    If False, lines of degrees of freedom that are constant 0 will not be plotted to reduce clutter.
    For positions this suppresses lines that are always equal to the initial value.
    """

    color_map: Dict[UUID, str] | None = None
    """
    A color map to use for plotting the trajectory.
    Use can use matplotlib styles, like 'r:' for dotted red lines.
    It should map the UUIDs of degrees of freedom in the world state trajectory to colors. 
    If None, a default color map will be used.
    
    Each degree of freedom will have the same color in each subplot.
    """

    def _seconds_to_inches(self, seconds: float) -> float:
        """Return the drawable width in inches for a given duration."""
        return max(0.0, float(seconds)) * (self.second_width_in_cm / 2.54)

    def _build_figure(
        self, duration_s: float, n_subplots: int
    ) -> tuple[plt.Figure, list[plt.Axes]]:
        """Create a stacked subplot figure sized so the inner axes width matches duration_s in physical units."""
        # Inner drawable width must equal seconds-to-inches. Add margins around it in inches
        inner_w_in = max(0.0, self._seconds_to_inches(duration_s))
        # Margins tuned to avoid clipping of yticks, ylabel and to leave space for a bottom legend
        left_margin_in = 0.8
        right_margin_in = 2.0
        top_margin_in = 0.3
        bottom_margin_in = 1.0
        fig_w_in = inner_w_in + left_margin_in + right_margin_in
        # Stack subplots vertically: add top/bottom margins to the inner subplot heights
        inner_h_in = max(1.0, n_subplots * (self.subplot_height_in_cm / 2.54))
        fig_h_in = inner_h_in + top_margin_in + bottom_margin_in
        fig, axes = plt.subplots(
            nrows=n_subplots,
            ncols=1,
            sharex=True,
            figsize=(fig_w_in, fig_h_in),
            constrained_layout=False,
        )
        if n_subplots == 1:
            axes = [axes]
        # Set explicit normalized margins so that inner area keeps the intended physical width
        fig.subplots_adjust(
            left=left_margin_in / fig_w_in,
            right=1.0 - right_margin_in / fig_w_in,
            bottom=bottom_margin_in / fig_h_in,
            top=1.0 - top_margin_in / fig_h_in,
            hspace=0.2,
        )
        return fig, axes

    def _choose_ticks(self, duration_s: float) -> np.ndarray:
        """Choose semi-automatic tick spacing: either 0.5s or integer seconds with adaptive spacing."""
        if duration_s <= 0:
            return np.array([0.0])
        # Prefer 0.5 if it does not create too many ticks; otherwise use integers with adaptive step
        max_ticks = 12
        if duration_s / 0.5 <= max_ticks:
            step = 0.5
        else:
            # choose integer step so that count <= max_ticks
            step = max(1, int(np.ceil(duration_s / max_ticks)))
        return np.arange(0.0, duration_s + 1e-9, step)

    def _iter_dofs(self, traj: WorldStateTrajectory) -> List[UUID]:
        """Return DOF ids in requested order."""
        dof_ids = list(traj._ids)
        if self.sort_degrees_of_freedom:
            dof_ids.sort(
                key=lambda d: str(traj.world.get_degree_of_freedom_by_id(d).name)
            )
        return dof_ids

    def _should_plot_series(
        self, derivative: Derivatives, series: np.ndarray, initial_value: float
    ) -> bool:
        """Decide whether to plot a DOF series according to suppression rules."""
        if self.plot_0_lines:
            return True
        if derivative == Derivatives.position:
            # Suppress if always equal to initial value or exactly all zeros
            if np.all(series == initial_value):
                return False
            if np.all(series == 0.0):
                return False
            return True
        else:
            return not np.all(series == 0.0)

    def _style_for_dofs(self, dof_ids: List[UUID]) -> Dict[UUID, dict]:
        """Assign styles to DOFs, respecting an optional color_map of matplotlib format strings."""
        styles: Dict[UUID, dict] = {}
        if self.color_map is not None:
            for d in dof_ids:
                s = self.color_map.get(d)
                if s is not None:
                    styles[d] = {"fmt": s}
        # Default cycle without wrapping colors; then reuse with styles
        if len(styles) < len(dof_ids):
            prop_cycle = plt.rcParams.get("axes.prop_cycle")
            colors = list(prop_cycle.by_key().get("color", [])) if prop_cycle else []
            line_styles = ["-", "--", "-.", ":"]
            assigned = 0
            for ls in line_styles:
                for c in colors:
                    if assigned >= len(dof_ids):
                        break
                    d = dof_ids[assigned]
                    if d not in styles:
                        styles[d] = {"color": c, "linestyle": ls}
                        assigned += 1
                if assigned >= len(dof_ids):
                    break
        return styles

    def plot_trajectory(
        self, world_state_trajectory: WorldStateTrajectory, file_name: str
    ):
        """
        Plots the trajectory and saves the resulting plot to the specified file.

        :param world_state_trajectory: The trajectory to plot.
        :param file_name: The name of the file where the plot will be saved.
        """
        traj = world_state_trajectory
        if len(traj.times) == 0:
            return
        t0 = float(traj.times[0])
        t = traj.times - t0
        duration_s = float(t[-1])

        # Filter derivatives to those present in the trajectory's data rows
        available_rows = traj.data.shape[1]
        derivatives = [d for d in self.derivatives_to_plot if int(d) < available_rows]
        if not derivatives:
            return

        fig, axes = self._build_figure(duration_s, len(derivatives))

        dof_ids = self._iter_dofs(traj)
        styles = self._style_for_dofs(dof_ids)

        # Plot per derivative
        for ax, derivative in zip(axes, derivatives):
            ax.grid(True, axis="x")
            ax.grid(True, axis="y")
            # Collect series for all DOFs
            for dof_id in dof_ids:
                col = traj._index[dof_id]
                y = traj.data[:, derivative, col].astype(float)
                initial_val = float(y[0])
                if derivative == Derivatives.position and self.center_positions:
                    y = y - initial_val
                    initial_cmp = 0.0
                else:
                    initial_cmp = initial_val
                if not self._should_plot_series(derivative, y, initial_cmp):
                    continue
                style = styles.get(dof_id, {})
                name = str(traj.world.get_degree_of_freedom_by_id(dof_id).name)
                # Support format strings
                if "fmt" in style:
                    ax.plot(t, y, style["fmt"], label=name)
                else:
                    ax.plot(t, y, label=name, **style)
            # Axis formatting
            ax.set_title(str(derivative.name).capitalize())
            ax.set_ylabel(self.y_label.get(derivative, ""))

        # Shared x axis settings (apply to last axis)
        ticks = self._choose_ticks(duration_s)
        axes[-1].set_xlim(0.0, duration_s)
        axes[-1].set_xticks(ticks)
        axes[-1].set_xticklabels(
            [str(int(x)) if abs(x - int(x)) < 1e-9 else f"{x:.1f}" for x in ticks]
        )
        axes[-1].set_xlabel("Time [s]")
        for ax in axes[:-1]:
            ax.set_xlabel("")

        if self.legend:
            # Place a single shared legend at the top-right, outside the plotting area but inside the figure.
            handles, labels = axes[-1].get_legend_handles_labels()
            if handles:
                fig.legend(
                    handles,
                    labels,
                    loc="upper right",
                    bbox_to_anchor=(0.99, 0.99),
                    ncol=1,
                    frameon=True,
                    borderaxespad=0.0,
                )

        plt.savefig(file_name)
        plt.close()
