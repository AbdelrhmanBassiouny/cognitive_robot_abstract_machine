#!/usr/bin/env python

from __future__ import annotations

import os
import signal
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import rclpy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QGridLayout,
)

from giskardpy.middleware.ros2 import rospy
from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
    ShapeSource,
)
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import Body


@dataclass
class RobotSemanticAnnotationBuilderInterface:
    """
    Interface for managing robot semantic annotations.
    """

    world: World = field(init=False)
    """
    World instance for managing bodies.
    """

    def __post_init__(self):
        self.world = World()
        with self.world.modify_world():
            self.world.add_body(Body(name=PrefixedName("map")))
        VizMarkerPublisher(
            _world=self.world, node=rospy.node, shape_source=ShapeSource.COLLISION_ONLY
        ).with_tf_publisher()

    def load_urdf(self, urdf_path: str):
        """
        Loads a URDF file and merges it into the world.
        """
        robot_world = URDFParser.from_file(urdf_path).parse()
        with self.world.modify_world():
            self.world.clear()
            self.world.add_body(map_body := Body(name=PrefixedName("map")))
            self.world.merge_world(
                robot_world, FixedConnection(parent=map_body, child=robot_world.root)
            )

    def reset_body_colors(self):
        """
        Sets all body colors to white transparent.
        """
        with self.world.modify_world():
            for body in self.world.bodies_with_collision:
                for shape in body.collision.shapes:
                    shape.color = Color(1.0, 1.0, 1.0, 0.5)

    def highlight_body(self, body: Body):
        """
        Highlights the given body by changing its color.
        """
        highlight_color = Color(1.0, 0.0, 0.0, 1.0)
        self.reset_body_colors()
        with self.world.modify_world():
            body.collision.dye_shapes(highlight_color)

    @property
    def bodies(self) -> List[Body]:
        """
        Returns a sorted list of all bodies with collision.
        """
        return list(sorted(self.world.bodies_with_collision, key=lambda x: x.name.name))


@dataclass
class BodyButton(QPushButton):
    """
    A button representing a robot body.
    """

    body: Body
    interface: RobotSemanticAnnotationBuilderInterface

    def __post_init__(self):
        super().__init__(self.body.name.name)
        self.clicked.connect(self.on_click)
        self.setMinimumHeight(40)

    def on_click(self):
        """
        Callback for button click.
        """
        self.interface.highlight_body(self.body)


class ProgressBarWithText(QProgressBar):
    """
    A progress bar that displays text.
    """

    def set_progress(self, value: int, text: Optional[str] = None):
        """
        Sets the progress value and optional text.
        """
        value = int(min(max(value, 0), 100))
        self.setValue(value)
        if text is not None:
            self.setFormat(f"{text}: %p%")
        self.parent().repaint()


@dataclass
class Application(QMainWindow):
    """
    The main application for the robot semantic annotation builder tool.
    """

    interface: RobotSemanticAnnotationBuilderInterface = field(
        init=False, default_factory=RobotSemanticAnnotationBuilderInterface
    )
    """
    Reference to a RobotSemanticAnnotationBuilderInterface instance.
    """
    timer: QTimer = field(init=False, default_factory=QTimer)
    """
    Timer used to update the ui periodically.
    """

    def __post_init__(self):
        super().__init__()
        self.timer.start(1000)
        self.timer.timeout.connect(lambda: None)
        self.init_ui_components()

    def init_ui_components(self):
        """
        Initialize all ui components.
        """
        self.setWindowTitle("Robot Semantic Annotation Builder Tool")
        self.setMinimumSize(800, 600)

        self.urdf_progress = ProgressBarWithText(self)
        self.urdf_progress.set_progress(0, "No urdf loaded")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.body_buttons_widget = QWidget()
        self.body_buttons_layout = QGridLayout(self.body_buttons_widget)
        self.body_buttons_layout.setSpacing(0)
        self.body_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.body_buttons_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.body_buttons_widget)

        layout = QVBoxLayout()
        layout.addLayout(self._create_urdf_box_layout())
        layout.addWidget(self.scroll_area)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def _create_urdf_box_layout(self) -> QHBoxLayout:
        """
        Creates the layout for URDF loading.
        """
        self.load_urdf_file_button = QPushButton("Load urdf from file")
        self.load_urdf_file_button.clicked.connect(self._load_urdf_file_button_callback)
        urdf_section = QHBoxLayout()
        urdf_section.addWidget(self.load_urdf_file_button)
        urdf_section.addWidget(self.urdf_progress)
        return urdf_section

    def _load_urdf_file_button_callback(self):
        """
        Callback for the load URDF button.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        urdf_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select URDF File",
            "",
            "urdf files (*.urdf);;All files (*)",
            options=options,
        )
        if urdf_file:
            if not os.path.isfile(urdf_file):
                QMessageBox.critical(
                    self, "Error", f"File does not exist: \n{urdf_file}"
                )
                return

            self.interface.load_urdf(urdf_file)
            self.urdf_progress.set_progress(100, f"Loaded {urdf_file}")
            self.refresh_body_buttons()

    def refresh_body_buttons(self):
        """
        Refreshes the list of body buttons in a grid layout.
        """
        while self.body_buttons_layout.count():
            item = self.body_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        columns = 5
        for index, body in enumerate(self.interface.bodies):
            button = BodyButton(body=body, interface=self.interface)
            row = index // columns
            column = index % columns
            self.body_buttons_layout.addWidget(button, row, column)


def handle_sigint(sig, frame):
    """Handler for the SIGINT signal."""
    rospy.shutdown()
    QApplication.quit()


if __name__ == "__main__":
    rospy.init_node("robot_semantic_annotation_builder")
    signal.signal(signal.SIGINT, handle_sigint)

    app = QApplication(sys.argv)
    window = Application()
    window.show()
    exit_code = app.exec_()
    rospy.shutdown()
    sys.exit(exit_code)
