# Rendering Tracy for the framework figure

`tracy_idle.png` and `tracy_inserting.png` next to the figure are rendered from Tracy's own
description, not photographed. The board is the repository's `board.stl`, the pieces are built
from the sizes in `experiments.montessori.pieces`, the drawers stand where the montessori world
puts them, and the square hole's place on the lid was measured off the board mesh.

## Once: the description packages and the URDF

Tracy's xacro pulls two UR10e arms and two Robotiq 2F-85 grippers from ROS-Industrial packages.
Clone the three packages next to each other and put that directory on `ROS_PACKAGE_PATH`:

```bash
git clone --depth 1 https://github.com/code-iai/iai_tracy
git clone --depth 1 --branch melodic-devel https://github.com/ros-industrial/universal_robot
git clone --depth 1 --branch kinetic-devel https://github.com/ros-industrial/robotiq
export ROS_PACKAGE_PATH=$PWD
```

`tracy.urdf` here is the xacro's output with the UR10e default kinematics passed for both arms,
which Tracy's launch file normally supplies:

```bash
xacro iai_tracy/iai_tracy_description/urdf/tracy.urdf.xacro \
    kinematics_config_left:=$UR/config/ur10e/default_kinematics.yaml \
    kinematics_config_right:=$UR/config/ur10e/default_kinematics.yaml -o tracy.urdf
```

On a machine without ROS, the `$(find pkg)` lookups inside the xacro files have to be replaced
by the clone paths first (`sed -i 's|$(find ur_description)|/path/to/ur_description|g'` over
every `*.xacro`, and likewise for the other two packages).

## Rendering

```bash
pip install yourdfpy trimesh pyrender numpy scipy pillow
PYOPENGL_PLATFORM=osmesa python render_tracy.py idle
PYOPENGL_PLATFORM=osmesa python render_tracy.py inserting
```

`SHOTS` in `render_tracy.py` holds each shot's camera, size, crop and which piece the gripper
carries; `BOARD`, `DRAWERS` and `PIECES` place the scene on the table. The joint angles come from
`pose_idle.json` and `pose_inserting.json`. `python pose_search.py <shot>` solves new angles for
that shot's tool targets (`SHOT_TARGETS`), writes them to the shot's pose file and renders it.

pyrender 0.1.45 still says `np.infty`, which NumPy 2 removed; replace it with `np.inf` in the
installed package. osmesa comes from `apt install libosmesa6`.
