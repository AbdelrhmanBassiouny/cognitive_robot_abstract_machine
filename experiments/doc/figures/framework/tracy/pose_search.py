"""Find joint angles that put each of Tracy's grippers at a chosen spot with the tool
pointing down, write them to the shot's pose file, and render the shot.

Run ``python pose_search.py idle`` or ``python pose_search.py inserting``. The idle shot
hovers both grippers over the table; the inserting shot puts the left tool above the
square hole, high enough for the fingers to clear the lid.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yourdfpy
from scipy.optimize import minimize

import render_tracy

# %% what a pose is asked to do

ARM_JOINTS = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)
TOOL_FRAMES = {"left": "l_gripper_tool_frame", "right": "r_gripper_tool_frame"}
# the arms are mounted mirrored, so the wrist turns the other way on the right
WRIST_SIGN = {"left": -1.0, "right": 1.0}
NOMINAL_ANGLES = np.array([0.0, -1.4, 1.8, -2.0, -1.57, 0.0])
DOWN = np.array([0.0, 0.0, -1.0])
CUBE_ABOVE_LID = 0.045
"""
How far above the lid the left tool is put for the inserting shot, so the fingers clear
the board with the cube hanging over its hole.
"""


@dataclass(frozen=True)
class ArmTarget:
    """
    Where one arm's tool frame is asked to be.
    """

    position: tuple[float, float, float]
    """
    The tool frame's position, in Tracy's frame.
    """

    finger_angle: float
    """
    The gripper's finger joint angle: 0 open, larger closed.
    """


SHOT_TARGETS = {
    "idle": {
        "left": ArmTarget((0.62, 0.22, 0.30), finger_angle=0.3),
        "right": ArmTarget((0.62, -0.22, 0.30), finger_angle=0.3),
    },
    "inserting": {
        "left": ArmTarget(
            tuple(
                render_tracy.BOARD.square_hole_position()
                + np.array([0.0, 0.0, CUBE_ABOVE_LID])
            ),
            finger_angle=0.5,
        ),
        "right": ArmTarget((0.50, -0.38, 0.45), finger_angle=0.3),
    },
}


# %% solving


def tool_pose(robot: yourdfpy.URDF, side: str, angles: np.ndarray) -> np.ndarray:
    """
    The tool frame's pose once the arm's joints stand at ``angles``.
    """
    configuration = dict(zip(robot.actuated_joint_names, robot.cfg))
    for joint, angle in zip(ARM_JOINTS, angles):
        configuration[f"{side}_{joint}"] = float(angle)
    robot.update_cfg(configuration)
    return robot.get_transform(TOOL_FRAMES[side], "world")


def solve(robot: yourdfpy.URDF, side: str, target: ArmTarget) -> np.ndarray:
    """
    Joint angles that reach the target with the tool pointing down, the elbow up and out
    to the arm's own side, and the fingers square to the board.

    :param robot: The robot to move.
    :param side: ``left`` or ``right``.
    :param target: Where the tool frame should be.
    """
    goal = np.asarray(target.position)
    sign = WRIST_SIGN[side]
    nominal = NOMINAL_ANGLES * np.array([1, 1, 1, 1, sign, 1])

    def cost(angles: np.ndarray) -> float:
        pose = tool_pose(robot, side, angles)
        position_error = np.sum((pose[:3, 3] - goal) ** 2)
        pointing_error = np.sum((pose[:3, 2] - DOWN) ** 2)
        elbow = robot.get_transform(f"{side}_forearm_link", "world")[:3, 3]
        wrist = robot.get_transform(f"{side}_wrist_1_link", "world")[:3, 3]
        elbow_up = (
            max(0.0, 0.62 - elbow[2]) ** 2
            + max(0.0, min(0.45, goal[2] + 0.14) - wrist[2]) ** 2
        )
        own_side = (
            max(0.0, 0.18 - (-sign) * elbow[1]) ** 2
            + max(0.0, 0.05 - (-sign) * wrist[1]) ** 2
        )
        forward = max(0.0, 0.05 - elbow[0]) ** 2 + max(0.0, elbow[0] - 0.5) ** 2
        squareness = 1.0 - max(abs(pose[0, 0]), abs(pose[1, 0]))
        regular = 0.02 * np.sum((angles - nominal) ** 2)
        return (
            200 * position_error
            + 4 * pointing_error
            + squareness
            + regular
            + 20 * (elbow_up + own_side + forward)
        )

    best = None
    for pan in (-1.0, -0.5, 0.0, 0.5, 1.0):
        start = nominal.copy()
        start[0] = pan
        result = minimize(
            cost,
            start,
            method="Powell",
            options=dict(maxiter=4000, xtol=1e-3, ftol=1e-5),
        )
        if best is None or result.fun < best.fun:
            best = result
    return best.x


def main(shot_name: str) -> None:
    robot = render_tracy.load_robot()
    robot.update_cfg({name: 0.0 for name in robot.actuated_joint_names})
    pose = {}
    for side, target in SHOT_TARGETS[shot_name].items():
        angles = solve(robot, side, target)
        for joint, angle in zip(ARM_JOINTS, angles):
            pose[f"{side}_{joint}"] = round(float(angle), 3)
        pose[f"{side}_finger_joint"] = target.finger_angle
        reached = tool_pose(robot, side, angles)
        print(
            side, np.round(reached[:3, 3], 3), "tool axis", np.round(reached[:3, 2], 2)
        )
    shot = render_tracy.SHOTS[shot_name]
    (render_tracy.HERE / shot.pose_file).write_text(json.dumps(pose, indent=2))
    render_tracy.render(
        shot, robot, pose, render_tracy.HERE.parent / f"tracy_{shot_name}.png"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "inserting")
