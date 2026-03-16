from dataclasses import dataclass, field

from typing_extensions import Tuple


@dataclass
class DepthComponent:
    depthOffset: int = 0
    depth_hints: str = "compressedDepth"
    topic_depth: str = field(init=False)


@dataclass
class ColorComponent:
    filterBlurredImages: bool = True
    color_hints: str = "compressed"
    topic_cam_info: str = field(init=False)
    topic_color: str = field(init=False)


@dataclass
class TfComponent:
    tf_from: str = field(init=False)
    tf_to: str = field(init=False)
    lookup_viewpoint: bool = True


@dataclass
class StableViewpointComponent:
    only_stable_viewpoints: bool = True
    max_viewpoint_distance: float = 0.01
    max_viewpoint_rotation: float = 1.0


@dataclass
class SemanticMapComponent:
    semantic_map: str = field(init=False)


@dataclass
class RGBDComponent(DepthComponent, ColorComponent):
    color2depth_ratio: Tuple[float, float] = (1.0, 1.0)
    hi_res_mode: bool = False
