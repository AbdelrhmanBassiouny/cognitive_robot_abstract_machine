import numpy as np
import threading
import rclpy

from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Table,
    Sofa,
    TrashCan,
    Fridge,
    Counter_Top,
    Wall,
    Cabinet,
    Cupboard,
    ShelfLayer,
    Hinge,
    Door,
    Handle,
    DiningTable,
    Leg,
    Drawer,
    Desk,
)
from semantic_digital_twin.world_description.degree_of_freedom import (
    DegreeOfFreedomLimits,
    DegreeOfFreedom,
)
from semantic_digital_twin.spatial_types.derivatives import DerivativeMap
from semantic_digital_twin.world_description.connections import (
    FixedConnection,
    RevoluteConnection,
    PrismaticConnection,
)
from semantic_digital_twin.spatial_types.spatial_types import Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import Room, Floor
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world_description.geometry import Box, Scale, Color
from semantic_digital_twin.world_description.geometry import Cylinder
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body


class KitchenEnvironment:
    """
    Manages the Kitchen Environment world with walls, furniture, and room layouts.
    """

    def get_world(self) -> World:
        """
        Constructs and returns a new World instance, setting up its environment,
        including walls, furniture, and rooms.

        :return: A new world instance with the initialized environment.
        """
        world = World()
        root = Body(name=PrefixedName("root"))
        with world.modify_world():
            world.add_body(root)

        self._build_environment_walls(world)
        self._build_environment_furniture(world)
        self._build_environment_rooms(world)

        return world

    def _build_environment_walls(self, world: World):
        """
        Builds and configures the environment walls for a given world. This involves creating
        various walls with predefined dimensions, transformation matrices, and connections.

        :param world: An instance representing the environment world where walls are to be
        configured and added.

        :return: The modified world instance with configured walls and connections.
        """
        root = world.root
        root_transformation = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.33, y=0.28, yaw=0.10707963267
        )

        with world.modify_world():
            south_wall1 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall1"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    y=-2.01
                ),
                scale=Scale(x=0.05, y=1.00, z=3.00),
            )

            south_wall2 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall2"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-0.145, y=-1.45, yaw=np.pi / 2
                ),
                scale=Scale(x=0.05, y=0.29, z=3.00),
            )

            south_wall3 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall3"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-0.29, y=-0.9925
                ),
                scale=Scale(x=0.05, y=1.085, z=1.00),
            )

            south_wall4 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall4"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-0.145, y=-0.45, yaw=np.pi / 2
                ),
                scale=Scale(x=0.05, y=0.29, z=1.00),
            )

            south_wall5 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall5"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-0.145, y=0.45, yaw=np.pi / 2
                ),
                scale=Scale(0.05, 0.29, 1.00),
            )

            south_wall6 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall6"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-0.29025, y=1.80
                ),
                scale=Scale(0.05, 2.75, 1.00),
            )

            south_wall7 = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("south_wall7"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-0.29025, y=5.16
                ),
                scale=Scale(0.05, 2.27, 1.00),
            )

            east_wall = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("east_wall"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=2.462, y=-2.535, yaw=np.pi / 2
                ),
                scale=Scale(0.05, 4.924, 3.00),
            )

            middle_wall = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("middle_wall"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=2.20975, y=5.00
                ),
                scale=Scale(0.05, 2.67, 1.00),
            )

            west_wall = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("west_wall"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=1.9345, y=6.32, yaw=np.pi / 2
                ),
                scale=Scale(0.05, 4.449, 3.00),
            )

            north_wall = Wall.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("north_wall"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=4.949, y=1.51
                ),
                scale=Scale(0.05, 8.04, 3.00),
            )

        north_west_wall = Cylinder(width=1.53, height=3.00)
        shape_geometry = ShapeCollection([north_west_wall])
        north_west_wall_body = Body(
            name=PrefixedName("north_west_wall_body"),
            collision=shape_geometry,
            visual=shape_geometry,
        )

        root_C_north_west_wall = FixedConnection(
            parent=root,
            child=north_west_wall_body,
            parent_T_connection_expression=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                x=4.924, y=6.295, z=1.50
            ),
        )

        with world.modify_world():
            world.add_connection(root_C_north_west_wall)
            return world

    def _build_environment_furniture(self, world: World):
        """
        Adds furniture items and room layouts (kitchen, living room, bedroom, office) to the scene graph.
        Connects furniture bodies and room structures hierarchically under the main root.
        Returns the updated World object with furniture integrated.
        """
        root = world.root
        root_transformation = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.33, y=0.28, yaw=0.10707963267
        )

        with world.modify_world():
            # --- REFINED TRASH CAN ---
            tc_l, tc_w, tc_h = 0.30, 0.30, 0.40
            tc_root_T = root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=0.416, y=5.5, z=tc_h / 2)

            trash_can = TrashCan.create_with_new_body_in_world(
                world=world, name=PrefixedName("trash_can"),
                world_root_T_self=tc_root_T, scale=Scale(tc_l, tc_w, tc_h), wall_thickness=0.02)
            for s in trash_can.root.visual.shapes: s.color = Color.GRAY()

            # Bin Body is now the trash_can.root
            bin_body = trash_can.root

            # Lid
            lid_h = 0.02
            lid_body = Body(name=PrefixedName("trash_lid_body"))
            lid_geom = ShapeCollection([Box(scale=Scale(tc_l, tc_w, lid_h), color=Color.BLACK())], reference_frame=lid_body)
            lid_geom.transform_all_shapes_to_own_frame()
            lid_body.collision, lid_body.visual = lid_geom, lid_geom

            lid_hinge = Body(name=PrefixedName("trash_lid_hinge_body"))
            world.add_connection(RevoluteConnection.create_with_dofs(world=world, parent=bin_body, child=lid_hinge,
                                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                                         x=-tc_l / 2, z=tc_h / 2),
                                                                     axis=Vector3.Y(), dof_limits=DegreeOfFreedomLimits(
                    lower=DerivativeMap[float](position=-np.pi / 2), upper=DerivativeMap[float](position=0.0))))
            world.add_connection(FixedConnection(parent=lid_hinge, child=lid_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=tc_l / 2, z=lid_h / 2)))

            # --- DETAILED REFRIGERATOR (Standing on floor & correctly rotated) ---
            fridge_l, fridge_w, fridge_h = 0.60, 0.658, 1.49

            # Use the Fridge factory which automatically creates a hollow case (HasCaseAsRootBody)
            # Position z = fridge_h / 2 to stand on floor (since geometry is centered)
            # Rotation yaw = -np.pi/2 to face away from the wall
            refrigerator = Fridge.create_with_new_body_in_world(
                name=PrefixedName("refrigerator"),
                world=world,
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=0.537, y=-2.181,
                                                                                                     z=fridge_h / 2,
                                                                                                     yaw=-np.pi / 2),
                scale=Scale(fridge_l, fridge_w, fridge_h),
                wall_thickness=0.02
            )
            for s in refrigerator.root.visual.shapes: s.color = Color.GRAY()

            # 1. Door (75% height)
            door_h = (fridge_h - 0.08) * 0.75
            door_body = Body(name=PrefixedName("fridge_door_body"))
            door_geom = ShapeCollection([Box(scale=Scale(0.02, fridge_w, door_h), color=Color.WHITE())],
                                        reference_frame=door_body)
            door_geom.transform_all_shapes_to_own_frame()
            door_body.collision, door_body.visual = door_geom, door_geom
            fridge_door = Door(root=door_body, name=PrefixedName("fridge_door"))

            # Hinge for Door (Front -fridge_l/2, Right edge +fridge_w/2)
            hinge_body = Body(name=PrefixedName("fridge_hinge_body"))
            world.add_connection(
                RevoluteConnection.create_with_dofs(world=world, parent=refrigerator.root, child=hinge_body,
                                                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                        x=-fridge_l / 2, y=-fridge_w / 2, z=fridge_h / 2 - door_h / 2),
                                                    axis=Vector3.Z(), dof_limits=DegreeOfFreedomLimits(
                        lower=DerivativeMap[float](position=0.0), upper=DerivativeMap[float](position=np.pi / 2))))
            world.add_connection(FixedConnection(parent=hinge_body, child=door_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     y=fridge_w / 2)))
            world.add_semantic_annotation(fridge_door)

            # 2. Lower Drawer (25% height, Modular with White Front and Gray Case)
            drawer_h = (fridge_h - 0.08) * 0.25
            fridge_drawer = Drawer.create_with_new_body_in_world(
                world=world, name=PrefixedName("fridge_drawer"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=0.537, y=-2.181,
                                                                                                     z=fridge_h / 2) @ HomogeneousTransformationMatrix.from_xyz_rpy(
                    yaw=-np.pi / 2) @ HomogeneousTransformationMatrix.from_xyz_rpy(x=-fridge_l / 2 + 0.25,
                                                                                   z=-fridge_h / 2 + 0.08 + drawer_h / 2),
                scale=Scale(0.5, fridge_w - 0.04, drawer_h - 0.01),
                active_axis=Vector3.NEGATIVE_X(),
                connection_limits=DegreeOfFreedomLimits(lower=DerivativeMap[float](position=0.0),
                                                        upper=DerivativeMap[float](position=0.5)))
            for s in fridge_drawer.root.visual.shapes: s.color = Color.GRAY()

            # Attach a white front plate
            dr_front_body = Body(name=PrefixedName("fridge_drawer_front_body"))
            dr_front_geom = ShapeCollection([Box(scale=Scale(0.02, fridge_w, drawer_h), color=Color.WHITE())],
                                            reference_frame=dr_front_body)
            dr_front_geom.transform_all_shapes_to_own_frame()
            dr_front_body.collision, dr_front_body.visual = dr_front_geom, dr_front_geom
            world.add_connection(FixedConnection(parent=fridge_drawer.root, child=dr_front_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.25)))

            # Correct hierarchy
            drawer_conn = fridge_drawer.root.parent_connection
            world.remove_connection(drawer_conn)
            drawer_conn.parent = refrigerator.root
            drawer_conn.parent_T_connection_expression = HomogeneousTransformationMatrix.from_xyz_rpy(
                x=-fridge_l / 2 + 0.25, z=-fridge_h / 2 + 0.08 + drawer_h / 2)
            world.add_connection(drawer_conn)

            # 3. Handles
            # 3.1 Door Handle (U-Shape with hollow space)
            ha_door_body = Body(name=PrefixedName("fridge_door_handle_body"))
            h_bar_l = 0.5
            h_thick = 0.02
            h_depth = 0.04

            # Main bar
            bar_geom = Box(scale=Scale(h_thick, h_thick, h_bar_l), color=Color.GRAY())
            bar_geom.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
            # Connection pieces (top/bottom)
            conn_top = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            conn_top.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, z=h_bar_l / 2 - h_thick / 2)
            conn_bot = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            conn_bot.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, z=-h_bar_l / 2 + h_thick / 2)

            ha_door_geom = ShapeCollection([bar_geom, conn_top, conn_bot], reference_frame=ha_door_body)
            ha_door_geom.transform_all_shapes_to_own_frame()
            ha_door_body.collision, ha_door_body.visual = ha_door_geom, ha_door_geom

            world.add_connection(FixedConnection(parent=door_body, child=ha_door_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.02, y=fridge_w / 2 - 0.03)))
            world.add_semantic_annotation(Handle(root=ha_door_body, name=PrefixedName("fridge_door_handle")))

            # 3.2 Drawer Handle
            ha_dr_body = Body(name=PrefixedName("fridge_drawer_handle_body"))
            ha_dr_geom = ShapeCollection([Box(scale=Scale(0.04, 0.5, 0.02), color=Color.GRAY())],
                                         reference_frame=ha_dr_body)
            ha_dr_geom.transform_all_shapes_to_own_frame()
            ha_dr_body.collision, ha_dr_body.visual = ha_dr_geom, ha_dr_geom
            world.add_connection(FixedConnection(parent=fridge_drawer.root, child=ha_dr_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.26, z=drawer_h / 2 - 0.03)))
            world.add_semantic_annotation(Handle(root=ha_dr_body, name=PrefixedName("fridge_drawer_handle")))

            # --- KITCHEN COUNTER  ---
            ct_l, ct_d, ct_h = 2.044, 0.658, 0.6
            ct_root_T = root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=1.887, y=-2.181, z=ct_h / 2,
                                                                                           yaw=-np.pi / 2)

            # Place the plate on top of the modules (z = ct_h + plate_thickness/2)
            counterTop = Counter_Top.create_with_new_body_in_world(
                world=world, name=PrefixedName("counterTop"),
                world_root_T_self=ct_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(z=ct_h / 2 + 0.02),
                scale=Scale(ct_d, ct_l, 0.04))
            for s in counterTop.root.visual.shapes: s.color = Color.BEIGE()

            # 0. Sink
            sink_body = Body(name=PrefixedName("sink_body"))
            sink_geom = ShapeCollection([Box(scale=Scale(0.4, 0.6, 0.005), color=Color.BLACK())], reference_frame=sink_body)
            sink_geom.transform_all_shapes_to_own_frame()
            sink_body.collision, sink_body.visual = sink_geom, sink_geom
            for s in sink_body.visual.shapes: s.color = Color.BLACK()
            world.add_connection(FixedConnection(parent=counterTop.root, child=sink_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     y=-0.7, z=0.025)))

            m1_w, m2_w = 0.60, 0.55
            m3_w = ct_l - m1_w - m2_w
            h_thick, h_depth = 0.02, 0.04

            # 1. Module 1: Cabinet (Drehtür)
            m1_y = -ct_l / 2 + m1_w / 2
            m1_anno = Cabinet.create_with_new_body_in_world(
                world=world, name=PrefixedName("ct_mod1"),
                world_root_T_self=ct_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(y=m1_y),
                scale=Scale(ct_d, m1_w, ct_h), wall_thickness=0.02)
            for s in m1_anno.root.visual.shapes: s.color = Color.GRAY()

            m1_door_body = Body(name=PrefixedName("ct_mod1_door_body"))
            m1_door_geom = ShapeCollection([Box(scale=Scale(0.02, m1_w, ct_h), color=Color.WHITE())],
                                           reference_frame=m1_door_body)
            m1_door_geom.transform_all_shapes_to_own_frame()
            m1_door_body.collision, m1_door_body.visual = m1_door_geom, m1_door_geom
            m1_hinge = Body(name=PrefixedName("ct_mod1_hinge_body"))
            world.add_connection(RevoluteConnection.create_with_dofs(world=world, parent=m1_anno.root, child=m1_hinge,
                                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                                         x=-ct_d / 2, y=-m1_w / 2, z=0),
                                                                     axis=Vector3.Z(), dof_limits=DegreeOfFreedomLimits(
                    lower=DerivativeMap[float](position=0.0), upper=DerivativeMap[float](position=np.pi / 2))))
            world.add_connection(FixedConnection(parent=m1_hinge, child=m1_door_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     y=m1_w / 2)))

            # Horizontal U-Handle for M1
            ha1_body = Body(name=PrefixedName("ct_mod1_handle_body"))
            bar1 = Box(scale=Scale(h_thick, m1_w - 0.06, h_thick), color=Color.GRAY())
            bar1.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
            cl1 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cl1.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=-(m1_w - 0.06) / 2 + h_thick / 2)
            cr1 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cr1.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=(m1_w - 0.06) / 2 - h_thick / 2)
            ha1_geom = ShapeCollection([bar1, cl1, cr1], reference_frame=ha1_body)
            ha1_geom.transform_all_shapes_to_own_frame()
            ha1_body.collision, ha1_body.visual = ha1_geom, ha_door_body.visual  # Reuse some visual if needed
            ha1_body.visual = ha1_geom
            world.add_connection(FixedConnection(parent=m1_door_body, child=ha1_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.02, z=ct_h / 2 - 0.05)))
            world.add_semantic_annotation(Handle(root=ha1_body, name=PrefixedName("ct_mod1_handle")))
            world.add_semantic_annotation(Door(root=m1_door_body, name=PrefixedName("ct_mod1_door")))

            # 2. Module 2: Dishwasher (Klapptür)
            m2_y = -ct_l / 2 + m1_w + m2_w / 2
            m2_anno = Cabinet.create_with_new_body_in_world(
                world=world, name=PrefixedName("ct_dishwasher"),
                world_root_T_self=ct_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(y=m2_y),
                scale=Scale(ct_d, m2_w, ct_h), wall_thickness=0.02)
            for s in m2_anno.root.visual.shapes: s.color = Color.GRAY()

            dw_door_body = Body(name=PrefixedName("ct_dw_door_body"))
            dw_door_geom = ShapeCollection([Box(scale=Scale(0.02, m2_w, ct_h), color=Color.WHITE())],
                                           reference_frame=dw_door_body)
            dw_door_geom.transform_all_shapes_to_own_frame()
            dw_door_body.collision, dw_door_body.visual = dw_door_geom, dw_door_geom
            dw_hinge = Body(name=PrefixedName("ct_dw_hinge_body"))
            world.add_connection(RevoluteConnection.create_with_dofs(world=world, parent=m2_anno.root, child=dw_hinge,
                                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                                         x=-ct_d / 2, z=-ct_h / 2),
                                                                     axis=Vector3.NEGATIVE_Y(),
                                                                     dof_limits=DegreeOfFreedomLimits(
                                                                         lower=DerivativeMap[float](position=0.0),
                                                                         upper=DerivativeMap[float](position=np.pi / 2))))
            world.add_connection(FixedConnection(parent=dw_hinge, child=dw_door_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     z=ct_h / 2)))

            # Horizontal U-Handle for DW (at Top)
            ha2_body = Body(name=PrefixedName("ct_dw_handle_body"))
            bar2 = Box(scale=Scale(h_thick, m2_w - 0.06, h_thick), color=Color.GRAY())
            bar2.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
            cl2 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cl2.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=-(m2_w - 0.06) / 2 + h_thick / 2)
            cr2 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cr2.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=(m2_w - 0.06) / 2 - h_thick / 2)
            ha2_geom = ShapeCollection([bar2, cl2, cr2], reference_frame=ha2_body)
            ha2_geom.transform_all_shapes_to_own_frame()
            ha2_body.collision, ha2_body.visual = ha2_geom, ha2_geom
            world.add_connection(FixedConnection(parent=dw_door_body, child=ha2_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.02, z=ct_h / 2 - 0.03)))
            world.add_semantic_annotation(Handle(root=ha2_body, name=PrefixedName("ct_dw_handle")))
            world.add_semantic_annotation(Door(root=dw_door_body, name=PrefixedName("ct_dishwasher_door")))

            # 3. Module 3: Hollow Cabinet with Drawers (40/40/20)
            m3_y = ct_l / 2 - m3_w / 2
            m3_anno = Cabinet.create_with_new_body_in_world(
                world=world, name=PrefixedName("ct_mod3_body"),
                world_root_T_self=ct_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(y=m3_y),
                scale=Scale(ct_d, m3_w, ct_h), wall_thickness=0.02)
            for s in m3_anno.root.visual.shapes: s.color = Color.GRAY()

            # Correct hierarchy
            m3_conn = m3_anno.root.parent_connection
            world.remove_connection(m3_conn)
            m3_conn.parent = counterTop.root
            # Move module down relative to the plate (plate is at +0.32 relative to module center)
            m3_conn.parent_T_connection_expression = HomogeneousTransformationMatrix.from_xyz_rpy(y=m3_y,
                                                                                                  z=-(ct_h / 2 + 0.02))
            world.add_connection(m3_conn)

            h_bot, h_mid, h_top = ct_h * 0.4, ct_h * 0.4, ct_h * 0.2
            z_pos = [-ct_h / 2 + h_bot / 2, -ct_h / 2 + h_bot + h_mid / 2, ct_h / 2 - h_top / 2]
            h_list = [h_bot, h_mid, h_top]
            for i, (h, z) in enumerate(zip(h_list, z_pos)):
                dr_id = f"ct_drawer_{i}"
                drawer = Drawer.create_with_new_body_in_world(
                    world=world, name=PrefixedName(dr_id),
                    world_root_T_self=ct_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(x=-ct_d / 2 + 0.15, y=m3_y,
                                                                                               z=z),
                    scale=Scale(0.3, m3_w - 0.04, h - 0.01),
                    active_axis=Vector3.NEGATIVE_X(),
                    connection_limits=DegreeOfFreedomLimits(lower=DerivativeMap[float](position=0.0),
                                                            upper=DerivativeMap[float](position=0.25)))
                for s in drawer.root.visual.shapes: s.color = Color.WHITE()

                # Attach front plate
                fr_body = Body(name=PrefixedName(f"{dr_id}_front"))
                fr_geom = ShapeCollection([Box(scale=Scale(0.02, m3_w, h), color=Color.WHITE())], reference_frame=fr_body)
                fr_geom.transform_all_shapes_to_own_frame()
                fr_body.collision, fr_body.visual = fr_geom, fr_geom
                world.add_connection(FixedConnection(parent=drawer.root, child=fr_body,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         x=-0.15)))

                # Correct hierarchy
                drawer_conn = drawer.root.parent_connection
                world.remove_connection(drawer_conn)
                drawer_conn.parent = m3_anno.root
                drawer_conn.parent_T_connection_expression = HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-ct_d / 2 + 0.15, z=z)
                world.add_connection(drawer_conn)

                # Handle
                ha3_body = Body(name=PrefixedName(f"{dr_id}_handle_body"))
                h_bar_w3 = m3_w - 0.06
                bar3 = Box(scale=Scale(h_thick, h_bar_w3, h_thick), color=Color.GRAY())
                bar3.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
                cl3 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
                cl3.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=-h_bar_w3 / 2 + h_thick / 2)
                cr3 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
                cr3.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=h_bar_w3 / 2 - h_thick / 2)
                ha3_geom = ShapeCollection([bar3, cl3, cr3], reference_frame=ha3_body)
                ha3_geom.transform_all_shapes_to_own_frame()
                ha3_body.collision, ha3_body.visual = ha3_geom, ha3_geom
                world.add_connection(FixedConnection(parent=drawer.root, child=ha3_body,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         x=-0.16, z=h / 2 - 0.03)))
                handle = Handle(root=ha3_body, name=PrefixedName(f"{dr_id}_handle"))
                world.add_semantic_annotation(handle)
                drawer.add_handle(handle)
            # --- OVEN TOWER (Final Corrected Framework Implementation) ---
            ot_w, ot_d, ot_h = 1.20, 0.658, 1.49
            ot_root_T = root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=3.51, y=-2.181, z=ot_h / 2,
                                                                                           yaw=-np.pi / 2)

            ovenTower = Cupboard.create_with_new_body_in_world(
                world=world, name=PrefixedName("oven_tower"),
                world_root_T_self=ot_root_T, scale=Scale(ot_d, ot_w, ot_h), wall_thickness=0.02)
            for s in ovenTower.root.visual.shapes: s.color = Color.GRAY()

            m_center_w, m_side_w = 0.60, 0.30
            h_cabinet, h_drawer = 0.60, 0.15
            h_oven = ot_h - h_cabinet - h_drawer
            h_thick, h_depth = 0.02, 0.04

            # 2.1 Side Drawers (Left & Right)
            for side in [-1, 1]:
                s_n = "left" if side == -1 else "right"
                dr_anno = Drawer.create_with_new_body_in_world(
                    world=world, name=PrefixedName(f"ot_side_drawer_{s_n}"),
                    world_root_T_self=ot_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(
                        y=side * (m_center_w / 2 + m_side_w / 2)),
                    scale=Scale(ot_d, m_side_w, ot_h), active_axis=Vector3.NEGATIVE_X())
                for s in dr_anno.root.visual.shapes: s.color = Color.WHITE()

                # Vertical U-Handle
                ha_body = Body(name=PrefixedName(f"ot_side_handle_{s_n}_body"))
                h_bar_l = ot_h - 0.08
                bar = Box(scale=Scale(h_thick, h_thick, h_bar_l), color=Color.GRAY())
                bar.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
                ct = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
                ct.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, z=h_bar_l / 2 - h_thick / 2)
                cb = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
                cb.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, z=-h_bar_l / 2 + h_thick / 2)
                ha_geom = ShapeCollection([bar, ct, cb], reference_frame=ha_body)
                ha_geom.transform_all_shapes_to_own_frame()
                ha_body.collision, ha_body.visual = ha_geom, ha_geom
                world.add_connection(FixedConnection(parent=dr_anno.root, child=ha_body,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         x=-ot_d / 2)))
                world.add_semantic_annotation(Handle(root=ha_body, name=PrefixedName(f"ot_side_handle_{s_n}")))

            # 2.2 Center Section: Bottom Cabinet
            cab_body = Body(name=PrefixedName("ot_cab_body"))
            cab_front = ShapeCollection([Box(scale=Scale(0.02, m_center_w, h_cabinet), color=Color.WHITE())],
                                        reference_frame=cab_body)
            cab_front.transform_all_shapes_to_own_frame()
            cab_body.collision, cab_body.visual = cab_front, cab_front
            cab_hinge = Body(name=PrefixedName("ot_cab_hinge_body"))
            world.add_connection(RevoluteConnection.create_with_dofs(world=world, parent=ovenTower.root, child=cab_hinge,
                                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                                         x=-ot_d / 2, y=m_center_w / 2,
                                                                         z=-ot_h / 2 + h_cabinet / 2),
                                                                     axis=Vector3.Z(), dof_limits=DegreeOfFreedomLimits(
                    lower=DerivativeMap[float](position=0.0), upper=DerivativeMap[float](position=np.pi / 2))))
            world.add_connection(FixedConnection(parent=cab_hinge, child=cab_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     y=-m_center_w / 2)))

            # Horizontal U-Handle for Cabinet
            ha_cab_body = Body(name=PrefixedName("ot_cab_handle_body"))
            h_bar_w = m_center_w - 0.06
            bar = Box(scale=Scale(h_thick, h_bar_w, h_thick), color=Color.GRAY())
            bar.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
            cl = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cl.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=-h_bar_w / 2 + h_thick / 2)
            cr = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cr.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=h_bar_w / 2 - h_thick / 2)
            ha_cab_geom = ShapeCollection([bar, cl, cr], reference_frame=ha_cab_body)
            ha_cab_geom.transform_all_shapes_to_own_frame()
            ha_cab_body.collision, ha_cab_body.visual = ha_cab_geom, ha_cab_geom
            world.add_connection(FixedConnection(parent=cab_body, child=ha_cab_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.02, z=h_cabinet / 2 - 0.05)))
            world.add_semantic_annotation(Handle(root=ha_cab_body, name=PrefixedName("ot_cab_handle")))
            world.add_semantic_annotation(Door(root=cab_body, name=PrefixedName("ot_cab_door")))

            # 2.3 Center Section: Middle Drawer
            ot_drawer = Drawer.create_with_new_body_in_world(
                world=world, name=PrefixedName("ot_center_drawer"),
                world_root_T_self=ot_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(x=-ot_d / 2 + 0.15,
                                                                                           z=-ot_h / 2 + h_cabinet + h_drawer / 2),
                scale=Scale(0.3, m_center_w - 0.04, h_drawer - 0.01),
                active_axis=Vector3.NEGATIVE_X(),
                connection_limits=DegreeOfFreedomLimits(lower=DerivativeMap[float](position=0.0),
                                                        upper=DerivativeMap[float](position=0.25)))
            for s in ot_drawer.root.visual.shapes: s.color = Color.WHITE()

            # Attach front plate
            ot_fr_body = Body(name=PrefixedName("ot_center_drawer_front"))
            ot_fr_geom = ShapeCollection([Box(scale=Scale(0.02, m_center_w, h_drawer), color=Color.WHITE())],
                                         reference_frame=ot_fr_body)
            ot_fr_geom.transform_all_shapes_to_own_frame()
            ot_fr_body.collision, ot_fr_body.visual = ot_fr_geom, ot_fr_geom
            world.add_connection(FixedConnection(parent=ot_drawer.root, child=ot_fr_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.15)))

            # Correct hierarchy
            drawer_conn = ot_drawer.root.parent_connection
            world.remove_connection(drawer_conn)
            drawer_conn.parent = ovenTower.root
            drawer_conn.parent_T_connection_expression = HomogeneousTransformationMatrix.from_xyz_rpy(x=-ot_d / 2 + 0.15,
                                                                                                      z=-ot_h / 2 + h_cabinet + h_drawer / 2)
            world.add_connection(drawer_conn)

            # 2.4 Center Section: Oven (Top)
            oven_door_body = Body(name=PrefixedName("ot_oven_door_body"))
            oven_frame_geom = Box(scale=Scale(0.02, m_center_w, h_oven), color=Color.WHITE())
            oven_glass_geom = Box(scale=Scale(0.005, 0.35, 0.35), color=Color.BLACK())
            oven_glass_geom.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-0.011)
            oven_door_geom = ShapeCollection([oven_frame_geom, oven_glass_geom], reference_frame=oven_door_body)
            oven_door_geom.transform_all_shapes_to_own_frame()
            oven_door_body.collision, oven_door_body.visual = oven_door_geom, oven_door_geom
            oven_hinge = Body(name=PrefixedName("ot_oven_hinge_body"))
            world.add_connection(RevoluteConnection.create_with_dofs(world=world, parent=ovenTower.root, child=oven_hinge,
                                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                                         x=-ot_d / 2, z=ot_h / 2 - h_oven),
                                                                     axis=Vector3.NEGATIVE_Y(),
                                                                     dof_limits=DegreeOfFreedomLimits(
                                                                         lower=DerivativeMap[float](position=0.0),
                                                                         upper=DerivativeMap[float](position=np.pi / 2))))
            world.add_connection(FixedConnection(parent=oven_hinge, child=oven_door_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     z=h_oven / 2)))

            # Horizontal U-Handle for Oven
            ha_ov_body = Body(name=PrefixedName("ot_oven_handle_body"))
            bar_ov = Box(scale=Scale(h_thick, h_bar_w, h_thick), color=Color.GRAY())
            bar_ov.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
            cl3 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cl3.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=-h_bar_w / 2 + h_thick / 2)
            cr3 = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
            cr3.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=h_bar_w / 2 - h_thick / 2)
            ha_ov_geom = ShapeCollection([bar_ov, cl3, cr3], reference_frame=ha_ov_body)
            ha_ov_geom.transform_all_shapes_to_own_frame()
            ha_ov_body.collision, ha_ov_body.visual = ha_ov_geom, ha_ov_geom
            world.add_connection(FixedConnection(parent=oven_door_body, child=ha_ov_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     x=-0.02, z=h_oven / 2 - 0.05)))
            world.add_semantic_annotation(Handle(root=ha_ov_body, name=PrefixedName("ot_oven_handle")))
            world.add_semantic_annotation(Door(root=oven_door_body, name=PrefixedName("ot_oven_door")))

            # --- SIDEBOARD / KITCHEN ISLAND ---
            sb_l, sb_w, sb_h = 2.45, 0.796, 0.845
            sb_thick = 0.04
            # Position z=sb_h/2, yaw=-np.pi/2. Moved y=0.2 to avoid sofa intersection
            # Local -X is now facing into the room (+Y in world)
            sb_root_T = root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=3.545, y=0.2, z=sb_h / 2,
                                                                                           yaw=np.pi / 2)

            # 1. Top Plate (Root)
            sideboard = Table.create_with_new_body_in_world(
                world=world, name=PrefixedName("sideboard"),
                world_root_T_self=sb_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(z=sb_h / 2 - sb_thick / 2),
                scale=Scale(sb_w, sb_l, sb_thick))
            for s in sideboard.root.visual.shapes: s.color = Color.WHITE()

            # 2. Main Body (Hollow Cabinet, Open towards local -X)
            sb_anno = Cabinet.create_with_new_body_in_world(
                world=world, name=PrefixedName("sb_main_body"),
                world_root_T_self=sb_root_T, scale=Scale(sb_w, sb_l, sb_h), wall_thickness=0.02)
            for s in sb_anno.root.visual.shapes: s.color = Color.WHITE()

            # 3. Cooktop (Ceran-Feld) on the Top Plate (on the right side in world coordinates)
            ct_body = Body(name=PrefixedName("sb_cooktop_body"))
            ct_geom = ShapeCollection([Box(scale=Scale(0.5, 0.6, 0.005), color=Color.BLACK())], reference_frame=ct_body)
            ct_geom.transform_all_shapes_to_own_frame()
            ct_body.collision, ct_body.visual = ct_geom, ct_geom
            # Position at the 'right' end of sideboard (local +Y)
            world.add_connection(FixedConnection(parent=sideboard.root, child=ct_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     y=-0.7, z=sb_thick / 2 + 0.001)))

            # 4. Drawer Layout (3x2 Grid on local -X face)
            w_outer, w_mid = sb_l * 0.3, sb_l * 0.4
            widths = [w_outer, w_mid, w_outer]
            y_offs = [-sb_l / 2 + w_outer / 2, 0, sb_l / 2 - w_outer / 2]
            dr_h = (sb_h - 0.15) / 2
            z_offs = [-sb_h / 2 + 0.05 + dr_h / 2, -sb_h / 2 + 0.05 + 3 * dr_h / 2]
            h_thick, h_depth = 0.02, 0.04

            for c_idx, (w, y_off) in enumerate(zip(widths, y_offs)):
                for r_idx, z_off in enumerate(z_offs):
                    dr_id = f"sb_drawer_{c_idx}_{r_idx}"
                    drawer = Drawer.create_with_new_body_in_world(
                        world=world, name=PrefixedName(dr_id),
                        world_root_T_self=sb_root_T @ HomogeneousTransformationMatrix.from_xyz_rpy(x=-sb_w / 2 + 0.2,
                                                                                                   y=y_off, z=z_off),
                        scale=Scale(0.4, w - 0.01, dr_h - 0.01),
                        active_axis=Vector3.NEGATIVE_X(),
                        connection_limits=DegreeOfFreedomLimits(lower=DerivativeMap[float](position=0.0),
                                                                upper=DerivativeMap[float](position=0.25)))
                    for s in drawer.root.visual.shapes: s.color = Color.WHITE()

                    # Reconnect to sideboard body for hierarchy
                    drawer_conn = drawer.root.parent_connection
                    world.remove_connection(drawer_conn)
                    drawer_conn.parent = sb_anno.root
                    # Set the connection pose relative to the new parent (sideboard body)
                    drawer_conn.parent_T_connection_expression = HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=-sb_w / 2 + 0.2, y=y_off, z=z_off)
                    world.add_connection(drawer_conn)
                    # Horizontal U-Handle
                    ha_body = Body(name=PrefixedName(f"{dr_id}_handle_body"))
                    h_bar_w = w - 0.1
                    bar = Box(scale=Scale(h_thick, h_bar_w, h_thick), color=Color.GRAY())
                    bar.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth)
                    cl = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
                    cl.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=-h_bar_w / 2 + h_thick / 2)
                    cr = Box(scale=Scale(h_depth, h_thick, h_thick), color=Color.GRAY())
                    cr.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-h_depth / 2, y=h_bar_w / 2 - h_thick / 2)
                    ha_geom = ShapeCollection([bar, cl, cr], reference_frame=ha_body)
                    ha_geom.transform_all_shapes_to_own_frame()
                    ha_body.collision, ha_body.visual = ha_geom, ha_geom
                    world.add_connection(FixedConnection(parent=drawer.root, child=ha_body,
                                                         parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                             x=-0.2, z=dr_h / 2 - 0.05)))
                    handle = Handle(root=ha_body, name=PrefixedName(f"{dr_id}_handle"))
                    world.add_semantic_annotation(handle)
                    drawer.add_handle(handle)

            sofa = Sofa.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("sofa"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=3.60, y=1.20, z=0.34,
                                                                                                     yaw=4.7124),
                scale=Scale(x=0.94, y=1.68, z=0.68),
            )
            for color in sofa.bodies[0].visual.shapes:
                color.color = Color.BEIGE()

            # --- REFINED COFFEE TABLE (White, Front-Closed, with Floor) ---
            ct_l, ct_w, ct_h = 0.37, 0.91, 0.44
            ct_thick = 0.02
            ct_color = Color.WHITE()
            ct_root_T = root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=4.22, y=2.22, z=ct_h,
                                                                                           yaw=np.pi)

            coffeeTable = Table.create_with_new_body_in_world(
                world=world, name=PrefixedName("coffee_table"),
                world_root_T_self=ct_root_T, scale=Scale(ct_l, ct_w, ct_thick))
            for s in coffeeTable.bodies[0].visual.shapes: s.color = ct_color

            # Middle Shelf
            shelf_body = Body(name=PrefixedName("coffee_table_shelf_body"))
            shelf_geom = ShapeCollection([Box(scale=Scale(ct_l, ct_w, 0.01), color=ct_color)], reference_frame=shelf_body)
            shelf_geom.transform_all_shapes_to_own_frame()
            shelf_body.collision, shelf_body.visual = shelf_geom, shelf_geom
            world.add_connection(FixedConnection(parent=coffeeTable.root, child=shelf_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     z=-ct_h / 2)))

            # Bottom Plate (Floor)
            floor_body = Body(name=PrefixedName("coffee_table_floor_body"))
            floor_geom = ShapeCollection([Box(scale=Scale(ct_l, ct_w, ct_thick), color=ct_color)],
                                         reference_frame=floor_body)
            floor_geom.transform_all_shapes_to_own_frame()
            floor_body.collision, floor_body.visual = floor_geom, floor_geom
            world.add_connection(FixedConnection(parent=coffeeTable.root, child=floor_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     z=-ct_h + ct_thick / 2)))

            # Walls (Supporting structure) - Both short sides closed
            for i, y_dir in enumerate([-1, 1]):
                side_wall = Body(name=PrefixedName(f"coffee_table_wall_short_{i}_body"))
                side_wall_geom = ShapeCollection([Box(scale=Scale(ct_l, ct_thick, ct_h), color=ct_color)],
                                                 reference_frame=side_wall)
                side_wall_geom.transform_all_shapes_to_own_frame()
                side_wall.collision, side_wall.visual = side_wall_geom, side_wall_geom
                world.add_connection(FixedConnection(parent=coffeeTable.root, child=side_wall,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         y=y_dir * (ct_w / 2 - ct_thick / 2), z=-ct_h / 2)))

            # 2. Long Sides (1/3 closed at the front, 2/3 open at the back)
            wall_len = ct_w / 3
            for side in [-1, 1]:
                s_n = "left" if side == -1 else "right"
                long_wall_body = Body(name=PrefixedName(f"coffee_table_wall_long_{s_n}_body"))
                long_wall_geom = ShapeCollection([Box(scale=Scale(ct_thick, wall_len, ct_h), color=ct_color)],
                                                 reference_frame=long_wall_body)
                long_wall_geom.transform_all_shapes_to_own_frame()
                long_wall_body.collision, long_wall_body.visual = long_wall_geom, long_wall_geom
                # Positioned at +y side (front)
                world.add_connection(FixedConnection(parent=coffeeTable.root, child=long_wall_body,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         x=side * (ct_l / 2 - ct_thick / 2), y=ct_w / 2 - wall_len / 2,
                                                         z=-ct_h / 2)))

            # --- Cupboard (tall cabinet with doors) ---
            cupboard_scale = Scale(0.43, 0.80, 2.02)

            cupboard = Cupboard.create_with_new_body_in_world(
                name=PrefixedName("cupboard_annotation"),
                world=world,
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=4.55, y=4.72,
                                                                                                     z=1.01),
                scale=cupboard_scale,
                wall_thickness=0.02,
            )
            # Connect the cupboard tp 'root' , to ensure that the coordinates are relative to the room
            cupboard_connection = cupboard.root.parent_connection
            world.remove_connection(cupboard_connection)
            cupboard_connection.parent = root
            world.add_connection(cupboard_connection)

            # create shelflayers manually and attach them directly to the cupboard
            shelf_scale = Scale(0.40, 0.76, 0.02)

            # Shelf 1
            shelf_1_geom = ShapeCollection([Box(scale=shelf_scale, color=Color.WHITE())])
            shelf_1_body = Body(
                name=PrefixedName("cupboard_shelf_1_body"),
                collision=shelf_1_geom,
                visual=shelf_1_geom,
            )
            shelf_1 = ShelfLayer(root=shelf_1_body, name=PrefixedName("cupboard_shelf_1"))

            cupboard_C_shelf_1 = FixedConnection(
                parent=cupboard.root,
                child=shelf_1_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0, y=0, z=-0.5
                ),
            )
            world.add_connection(cupboard_C_shelf_1)
            world.add_semantic_annotation(shelf_1)
            cupboard.add_shelf_layer(shelf_1)

            # Shelf 2
            shelf_2_geom = ShapeCollection([Box(scale=shelf_scale, color=Color.WHITE())])
            shelf_2_body = Body(
                name=PrefixedName("cupboard_shelf_2_body"),
                collision=shelf_2_geom,
                visual=shelf_2_geom,
            )
            shelf_2 = ShelfLayer(root=shelf_2_body, name=PrefixedName("cupboard_shelf_2"))

            cupboard_C_shelf_2 = FixedConnection(
                parent=cupboard.root,
                child=shelf_2_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0, y=0, z=0.5
                ),
            )
            world.add_connection(cupboard_C_shelf_2)
            world.add_semantic_annotation(shelf_2)
            cupboard.add_shelf_layer(shelf_2)

            # Creating doors manually and attaching them directly to the cupboard
            # Door height 105.5 cm (1.055 m)
            door_height = 1.055
            # Position Z: Bottom of cupboard is at -cupboard_scale.z / 2.
            # Door center should be at Bottom + door_height / 2
            door_z_rel = -(cupboard_scale.z / 2) + (door_height / 2)

            door_x_rel = -(cupboard_scale.x / 2) - 0.01
            door_scale = Scale(0.02, 0.40, door_height)

            # Define limits for doors
            # Left door opens outwards (0 to +90 degrees)
            left_lower = DerivativeMap[float](position=0.0)
            left_upper = DerivativeMap[float](position=np.pi / 2)
            left_door_limits = DegreeOfFreedomLimits(lower=left_lower, upper=left_upper)

            # Right door opens outwards (-90 to 0 degrees)
            right_lower = DerivativeMap[float](position=-np.pi / 2)
            right_upper = DerivativeMap[float](position=0.0)
            right_door_limits = DegreeOfFreedomLimits(lower=right_lower, upper=right_upper)

            # Left Door (Open via Hinge)
            # Create Hinge for the left door
            hinge_left_body = Body(name=PrefixedName("cupboard_hinge_left_body"))
            hinge_left = Hinge(
                root=hinge_left_body,
                name=PrefixedName("cupboard_hinge_left"),
            )

            cupboard_C_hinge_left = RevoluteConnection.create_with_dofs(
                world=world,
                parent=cupboard.root,
                child=hinge_left_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=door_x_rel, y=-0.40, z=door_z_rel
                ),
                axis=Vector3.Z(),
                dof_limits=left_door_limits,
            )
            world.add_connection(cupboard_C_hinge_left)
            world.add_semantic_annotation(hinge_left)

            # Create left door
            door_left_geom = ShapeCollection([Box(scale=door_scale, color=Color.WHITE())])
            door_left_body = Body(
                name=PrefixedName("cupboard_door_left_body"),
                collision=door_left_geom,
                visual=door_left_geom,
            )
            door_left = Door(root=door_left_body, name=PrefixedName("cupboard_door_left"))

            # Connect Door to Hinge (Fixed)
            # Door center is at y=+0.20 relative to hinge (hinge at -0.40, door center at -0.20)
            hinge_left_C_door_left = FixedConnection(
                parent=hinge_left_body,
                child=door_left_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0, y=0.20, z=0
                ),
            )
            world.add_connection(hinge_left_C_door_left)
            world.add_semantic_annotation(door_left)
            door_left.add_hinge(hinge_left)

            # Handle for Left Door
            handle_scale = Scale(0.04, 0.04, 0.04)
            handle_left_geom = ShapeCollection([Box(scale=handle_scale, color=Color.GRAY())])
            handle_left_body = Body(name=PrefixedName("cupboard_handle_left_body"), collision=handle_left_geom,
                                    visual=handle_left_geom)
            handle_left = Handle(root=handle_left_body, name=PrefixedName("cupboard_handle_left"))

            # Position: near the opening edge (+y for left door) and centered vertically
            door_left_C_handle_left = FixedConnection(
                parent=door_left_body,
                child=handle_left_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(x=-0.03, y=0.15, z=0)
            )
            world.add_connection(door_left_C_handle_left)
            world.add_semantic_annotation(handle_left)

            # Right Door (Closed via Hinge)
            hinge_right_body = Body(name=PrefixedName("cupboard_hinge_right_body"))
            hinge_right = Hinge(
                root=hinge_right_body,
                name=PrefixedName("cupboard_hinge_right"),
            )

            cupboard_C_hinge_right = RevoluteConnection.create_with_dofs(
                world=world,
                parent=cupboard.root,
                child=hinge_right_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=door_x_rel, y=0.40, z=door_z_rel
                ),
                axis=Vector3.Z(),
                dof_limits=right_door_limits,
            )
            world.add_connection(cupboard_C_hinge_right)
            world.add_semantic_annotation(hinge_right)

            door_right_geom = ShapeCollection([Box(scale=door_scale, color=Color.WHITE())])
            door_right_body = Body(
                name=PrefixedName("cupboard_door_right_body"),
                collision=door_right_geom,
                visual=door_right_geom,
            )
            door_right = Door(root=door_right_body, name=PrefixedName("cupboard_door_right"))

            hinge_right_C_door_right = FixedConnection(
                parent=hinge_right_body,
                child=door_right_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0, y=-0.20, z=0
                ),
            )
            world.add_connection(hinge_right_C_door_right)
            world.add_semantic_annotation(door_right)
            door_right.add_hinge(hinge_right)

            # Handle for Right Door
            handle_right_geom = ShapeCollection([Box(scale=handle_scale, color=Color.GRAY())])
            handle_right_body = Body(name=PrefixedName("cupboard_handle_right_body"), collision=handle_right_geom,
                                     visual=handle_right_geom)
            handle_right = Handle(root=handle_right_body, name=PrefixedName("cupboard_handle_right"))

            # Position: near the opening edge (-y for right door) and centered vertically
            door_right_C_handle_right = FixedConnection(
                parent=door_right_body,
                child=handle_right_body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(x=-0.03, y=-0.15, z=0)
            )
            world.add_connection(door_right_C_handle_right)
            world.add_semantic_annotation(handle_right)

            # Detailed White Desk Construction
            desk_l, desk_w, desk_h = 0.60, 1.20, 0.75
            desk_color = Color.WHITE()
            desk_plate_thick = 0.03

            desk = Desk.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("desk"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=0.05, y=1.28,
                                                                                                     z=desk_h),
                scale=Scale(desk_l, desk_w, desk_plate_thick),
            )
            for shape in desk.root.visual.shapes: shape.color = desk_color

            leg_scale = Scale(0.04, 0.04, desk_h - desk_plate_thick)
            x_off = (desk_l / 2) - 0.02
            y_off = (desk_w / 2) - 0.02
            z_pos = -(desk_plate_thick / 2) - (leg_scale.z / 2)

            for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
                l_body = Body(name=PrefixedName(f"desk_leg_{i}_body"))
                l_geom = ShapeCollection([Box(scale=leg_scale, color=desk_color)], reference_frame=l_body)
                l_geom.transform_all_shapes_to_own_frame()
                l_body.collision, l_body.visual = l_geom, l_geom
                leg = Leg(root=l_body, name=PrefixedName(f"desk_leg_{i}"))
                world.add_connection(FixedConnection(
                    parent=desk.root,
                    child=l_body,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(x=sx * x_off, y=sy * y_off,
                                                                                                z=z_pos)
                ))
                world.add_semantic_annotation(leg)
                # desk.add_leg(leg) # Generic Desk might not have add_leg, using semantic annotation is enough

            # --- MODULAR COOKING TABLE ---
            ct_l, ct_d, ct_h, ct_thick = 1.75, 0.64, 0.71, 0.04
            # 1. Top Layer (The Worktop)
            cooking_table = Table.create_with_new_body_in_world(world=world, name=PrefixedName("cooking_table"),
                                                                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(
                                                                    x=1.28, y=5.99, z=ct_h),
                                                                scale=Scale(ct_l, ct_d, ct_thick))
            for s in cooking_table.bodies[0].visual.shapes: s.color = Color.BEIGE()

            # Ceran Field
            cooktop_body = Body(name=PrefixedName("cooktop_body"))
            cooktop_geom = ShapeCollection([Box(scale=Scale(0.5, 0.5, 0.01), color=Color.BLACK())],
                                           reference_frame=cooktop_body)
            cooktop_geom.transform_all_shapes_to_own_frame()
            cooktop_body.collision, cooktop_body.visual = cooktop_geom, cooktop_geom
            world.add_connection(FixedConnection(parent=cooking_table.root, child=cooktop_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     z=ct_thick / 2 + 0.005)))

            # 2. Bottom Layer (The Support)
            ct_bottom_body = Body(name=PrefixedName("cooking_table_bottom_body"))
            ct_bottom_geom = ShapeCollection([Box(scale=Scale(ct_l, ct_d, ct_thick), color=Color.BEIGE())],
                                             reference_frame=ct_bottom_body)
            ct_bottom_geom.transform_all_shapes_to_own_frame()
            ct_bottom_body.collision, ct_bottom_body.visual = ct_bottom_geom, ct_bottom_geom
            world.add_connection(FixedConnection(parent=cooking_table.root, child=ct_bottom_body,
                                                 parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                     z=-ct_h + ct_thick)))

            # 3. Side Modules (Cupboards with Drawers)
            mod_w = (ct_l - 0.60) / 2
            dr_limits = DegreeOfFreedomLimits(lower=DerivativeMap[float](position=0.0),
                                              upper=DerivativeMap[float](position=0.40))
            for side in [-1, 1]:
                s_n = "left" if side == -1 else "right"
                # Module Cupboard
                mod_cupboard = Cupboard.create_with_new_body_in_world(name=PrefixedName(f"cooking_mod_{s_n}"), world=world,
                                                                      scale=Scale(mod_w, ct_d, ct_h - 2 * ct_thick))
                for s in mod_cupboard.bodies[0].visual.shapes: s.color = Color.BEIGE()
                world.remove_connection(mod_cupboard.root.parent_connection)
                world.add_connection(FixedConnection(parent=cooking_table.root, child=mod_cupboard.root,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         x=side * (0.265 + mod_w / 2), z=-ct_h / 2 + ct_thick, yaw=1.5708)))

                # Drawer in Module
                drawer = Drawer.create_with_new_body_in_world(
                    world=world, name=PrefixedName(f"cooking_drawer_{s_n}"),
                    world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=1.325, y=5.99,
                                                                                                         z=ct_h) @ HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=side * (0.265 + mod_w / 2), z=-ct_h / 2 + ct_thick,
                        yaw=1.5708) @ HomogeneousTransformationMatrix.from_xyz_rpy(y=0.2),
                    scale=Scale(mod_w - 0.04, ct_d - 0.02, 0.18),
                    active_axis=Vector3.NEGATIVE_X(),
                    connection_limits=dr_limits)
                for s in drawer.root.visual.shapes: s.color = Color.BEIGE()

                # Correct hierarchy
                drawer_conn = drawer.root.parent_connection
                world.remove_connection(drawer_conn)
                drawer_conn.parent = mod_cupboard.root
                drawer_conn.parent_T_connection_expression = HomogeneousTransformationMatrix.from_xyz_rpy(z=0.2)
                world.add_connection(drawer_conn)

                # Drawer Handle (Rectangular)
                ha_body = Body(name=PrefixedName(f"cooking_drawer_handle_{s_n}_body"))
                ha_geom = ShapeCollection([Box(scale=Scale(0.02, mod_w / 3, 0.04), color=Color.GRAY())],
                                          reference_frame=ha_body)
                ha_geom.transform_all_shapes_to_own_frame()
                ha_body.collision, ha_body.visual = ha_geom, ha_geom
                handle = Handle(root=ha_body, name=PrefixedName(f"cooking_drawer_handle_{s_n}"))
                world.add_connection(FixedConnection(parent=drawer.root, child=ha_body,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         x=-mod_w / 2 + 0.02)))
                world.add_semantic_annotation(handle)
                drawer.add_handle(handle)

                # Shelf below Drawer
                sh_body = Body(name=PrefixedName(f"cooking_shelf_{s_n}_body"))
                sh_geom = ShapeCollection([Box(scale=Scale(mod_w - 0.04, ct_d - 0.02, 0.02), color=Color.WHITE())],
                                          reference_frame=sh_body)
                sh_geom.transform_all_shapes_to_own_frame()
                sh_body.collision, sh_body.visual = sh_geom, sh_geom
                shelf = ShelfLayer(root=sh_body, name=PrefixedName(f"cooking_shelf_{s_n}"))
                world.add_connection(FixedConnection(parent=mod_cupboard.root, child=sh_body,
                                                     parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                                                         z=-0.1)))
                world.add_semantic_annotation(shelf)
                mod_cupboard.add_shelf_layer(shelf)

            # Dining Table Construction
            dt_length, dt_width, dt_height = 0.73, 1.18, 0.76
            dt_color = Color.BEIGE()
            dt_plate_thickness = 0.04

            dining_table = DiningTable.create_with_new_body_in_world(
                world=world,
                name=PrefixedName("dining_table"),
                world_root_T_self=root_transformation @ HomogeneousTransformationMatrix.from_xyz_rpy(x=2.59975, y=5.705,
                                                                                                     z=0.76),
                scale=Scale(dt_length, dt_width, dt_plate_thickness),
            )
            for shape in dining_table.root.visual.shapes: shape.color = dt_color

            leg_scale = Scale(0.06, 0.06, dt_height - dt_plate_thickness)
            x_offset = (dt_length / 2) - 0.03
            y_offset = (dt_width / 2) - 0.03
            z_pos = -(dt_plate_thickness / 2) - (leg_scale.z / 2)

            for i, (sign_x, sign_y) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
                l_body = Body(name=PrefixedName(f"dining_table_leg_{i}_body"))
                leg = Leg(root=l_body, name=PrefixedName(f"dining_table_leg_{i}"))
                l_geom = ShapeCollection([Box(scale=leg_scale, color=dt_color)], reference_frame=l_body)
                l_geom.transform_all_shapes_to_own_frame()
                l_body.collision = l_geom
                l_body.visual = l_geom
                # Create connection and add to world
                world.add_connection(FixedConnection(
                    parent=dining_table.root,
                    child=l_body,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(x=sign_x * x_offset,
                                                                                                y=sign_y * y_offset,
                                                                                                z=z_pos)
                ))
                world.add_semantic_annotation(leg)
                dining_table.add_leg(leg)

        return world

    def _build_environment_rooms(self, world: World):
        room_annotations = []

        root_transformation = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.33, y=0.28, yaw=0.10707963267
        )

        with world.modify_world():
            kitchen_floor_polytope = [
                Point3(0, 0, 0),
                Point3(0, 3.334, 0),
                Point3(5.214, 3.334, 0),
                Point3(5.214, 0, 0),
            ]

            living_room_floor_polytope = [
                Point3(0, 0, 0),
                Point3(0, 2.971, 0),
                Point3(5.214, 2.971, 0),
                Point3(5.214, 0, 0),
            ]

            bed_room_floor_polytope = [
                Point3(0, 0, 0),
                Point3(0, 2.67, 0.0),
                Point3(2.50, 2.67, 0.0),
                Point3(2.50, 0, 0.0),
            ]

            office_floor_polytope = [
                Point3(0, 0, 0),
                Point3(0, 2.67, 0),
                Point3(2.71, 2.67, 0),
                Point3(2.71, 0, 0),
            ]

            kitchen_floor = Floor.create_with_new_body_from_polytope_in_world(
                name=PrefixedName("kitchen_floor"),
                world=world,
                floor_polytope=kitchen_floor_polytope,
                world_root_T_self=root_transformation
                                  @ HomogeneousTransformationMatrix.from_xyz_rpy(x=2.317, y=-0.843),
            )
            kitchen = Room(floor=kitchen_floor, name=PrefixedName("kitchen"))
            room_annotations.append(kitchen)

            living_room_floor = Floor.create_with_new_body_from_polytope_in_world(
                name=PrefixedName("living_room_floor"),
                world=world,
                floor_polytope=living_room_floor_polytope,
                world_root_T_self=root_transformation
                                  @ HomogeneousTransformationMatrix.from_xyz_rpy(x=2.317, y=2.3095),
            )
            living_room = Room(floor=living_room_floor, name=PrefixedName("living_room"))
            room_annotations.append(living_room)

            bed_room_floor = Floor.create_with_new_body_from_polytope_in_world(
                name=PrefixedName("bed_room_floor"),
                world=world,
                floor_polytope=bed_room_floor_polytope,
                world_root_T_self=root_transformation
                                  @ HomogeneousTransformationMatrix.from_xyz_rpy(x=0.96, y=4.96),
            )
            bed_room = Room(floor=bed_room_floor, name=PrefixedName("bed_room"))
            room_annotations.append(bed_room)

            office_floor = Floor.create_with_new_body_from_polytope_in_world(
                name=PrefixedName("office_floor"),
                world=world,
                floor_polytope=office_floor_polytope,
                world_root_T_self=root_transformation
                                  @ HomogeneousTransformationMatrix.from_xyz_rpy(x=3.56, y=4.96),
            )
            office = Room(floor=office_floor, name=PrefixedName("office"))
            room_annotations.append(office)

            world.add_semantic_annotations(room_annotations)

        return world
