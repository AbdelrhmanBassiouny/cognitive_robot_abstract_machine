"""Stage 3: render every object under every setting and summarize the results into report/."""
import json, statistics, sys

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from common import CATEGORIES, CONFIGS, OUT, objects
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.spatial_computations.mesh_rendering import CameraRing

TILE = 240
FONT = ImageFont.load_default(size=15)
SMALL = ImageFont.load_default(size=13)
HANDLE = np.array([232, 89, 12])
HANDLE_HULLS = np.array([[232, 89, 12], [245, 140, 60], [200, 70, 20], [250, 175, 95]])
REST_HULLS = np.array([[70, 120, 190], [95, 165, 150], [140, 140, 200], [80, 150, 200], [120, 170, 110], [160, 120, 170]])
ring = CameraRing()
REPORT = OUT / "report"
(REPORT / "renders").mkdir(parents=True, exist_ok=True)


def asset_names():
    loader = RoboCasaDatasetLoader(); directory = loader.directory / "objects"; names = {}
    for name, (category, _, count) in CATEGORIES.items():
        files = sorted(f for g in loader.self_contained_object_groups for f in (directory / g).glob(f"{category}/**/model.xml"))
        for index, f in enumerate(files[:count]):
            names[f"{name}_{index}"] = str(f.parent.relative_to(directory))
    return names


def tile(image, colors, title, subtitle):
    """image: gray render; colors: per pixel rgb or None (gray)."""
    rgb = np.repeat(image[..., None], 3, 2).astype(float)
    if colors is not None:
        mask = colors[..., 0] >= 0
        rgb[mask] = colors[mask] * (rgb[mask] / 240.0) * 0.85 + rgb[mask] * 0.15
    hit = image < 255
    ys, xs = np.nonzero(hit) if hit.any() else (np.array([0, 447]), np.array([0, 447]))
    pad = 10
    crop = Image.fromarray(rgb.astype(np.uint8)).crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, 447), min(ys.max() + pad, 447)))
    side = max(crop.size); square = Image.new("RGB", (side, side), (255, 255, 255))
    square.paste(crop, ((side - crop.size[0]) // 2, (side - crop.size[1]) // 2))
    canvas = Image.new("RGB", (TILE, TILE + 44), (255, 255, 255))
    canvas.paste(square.resize((TILE, TILE)), (0, 44))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 4), title, fill=(30, 30, 30), font=FONT); draw.text((6, 24), subtitle, fill=(90, 90, 90), font=SMALL)
    return canvas


def render(mesh, view, face_colors):
    views = CameraRing(directions=[ring.directions[view]]).render(mesh)
    image, faces = views.images[0], views.faces[0]
    colors = np.full(image.shape + (3,), -1.0)
    hit = faces >= 0
    if face_colors is not None:
        colors[hit] = face_colors[faces[hit]]
    return image, colors


def main():
    names = asset_names(); rows = []
    short = {"threshold": "t", "max_convex_hull": "max", "preprocess_resolution": "pre", "max_convex_hulls": "max", "voxel_size": "voxel", "preprocess": "pre"}
    labels = {"original": "RoboCasa collision"} | {c: f"{CONFIGS[c][0]}" + (" boxes" if CONFIGS[c][1].get("hulls") == "boxes" else "") + " " + " ".join(f"{short.get(k, k)}={v}" for k, v in CONFIGS[c][1].items() if k != "hulls") for c in CONFIGS}
    for key in sys.argv[1:] or objects():
        located_path = OUT / "located" / f"{key}.json"
        if not located_path.exists():
            continue
        located = json.loads(located_path.read_text())
        data = np.load(OUT / "located" / f"{key}.npz")
        visual = trimesh.Trimesh(data["vertices"], data["faces"], process=False)
        handle = np.zeros(len(visual.faces), bool)
        kept = [part for part in located["parts"] if part["confidence"] >= 0.5]  # AnnotationPartFinder.minimum_confidence
        for part in kept:
            handle[part["faces"]] = True
        views = ring.render(visual)
        shown = [((f >= 0) & handle[np.maximum(f, 0)]).sum() for f in views.faces]
        view = int(np.argmax(shown)) if max(shown) > 0 else 1
        face_colors = np.where(handle[:, None], HANDLE, np.array([175, 175, 175]))
        confidence = (", ".join(f"{p['confidence']:.2f}" for p in kept) + (f" (+{len(located['parts']) - len(kept)} dropped)" if len(located["parts"]) > len(kept) else "")) or "no handle found"
        tiles = [tile(*render(visual, view, face_colors.astype(float)), "Handle faces (VLM)", f"confidence {confidence}")]
        results = {}
        for config in ["original", *CONFIGS]:
            path = OUT / "results" / key / f"{config}.json"
            result = json.loads(path.read_text()) if path.exists() else {"status": "not run"}
            result.pop("trace", None); results[config] = result
            hull_path = OUT / "hulls" / key / f"{config}.npz"
            if result.get("status") == "ok" and hull_path.exists():
                hulls = np.load(hull_path)
                mesh = trimesh.Trimesh(hulls["vertices"], hulls["faces"], process=False)
                palette = np.where(hulls["is_part"][:, None], HANDLE_HULLS[hulls["hull"] % len(HANDLE_HULLS)], REST_HULLS[hulls["hull"] % len(REST_HULLS)])
                subtitle = (f"{result['part_hulls']} + {result['rest_hulls']} hulls · {result['seconds']:.0f} s" if config != "original" else f"{result['rest_hulls']} hulls")
                tiles.append(tile(*render(mesh, view, palette.astype(float)), labels[config], subtitle))
            else:
                blank = np.full((448, 448), 255, np.uint8)
                tiles.append(tile(blank, None, labels[config], result.get("status", "")[:34]))
        columns = 7
        strip = Image.new("RGB", (TILE * columns, (TILE + 44) * ((len(tiles) + columns - 1) // columns)), (255, 255, 255))
        for i, t in enumerate(tiles):
            strip.paste(t, ((i % columns) * TILE, (i // columns) * (TILE + 44)))
        strip.save(REPORT / "renders" / f"{key}.png", optimize=True)
        rows.append({"object": key, "asset": names.get(key, key), "faces": located["faces"], "server_seconds": located["server_seconds"],
                     "handle_found": bool(kept), "confidence": [p["confidence"] for p in kept], "dropped_pieces": len(located["parts"]) - len(kept),
                     "handle_faces": int(handle.sum()), "results": results})
        print("rendered", key, flush=True)
    summary = {}
    for config in ["original", *CONFIGS]:
        rs = [r["results"][config] for r in rows if r["handle_found"]]
        ok = [r for r in rs if r.get("status") == "ok"]
        med = lambda k: statistics.median(r[k] for r in ok) if ok else None
        summary[config] = {"label": labels[config], "family": CONFIGS[config][0] if config in CONFIGS else "Reference",
                           "parameters": CONFIGS[config][1] if config in CONFIGS else {}, "objects": len(rs), "ok": len(ok),
                           "failed": sorted({r.get("status", "?")[:80] for r in rs if r.get("status") != "ok"}),
                           "median_seconds": med("seconds"), "max_seconds": max((r["seconds"] for r in ok), default=None),
                           "median_part_hulls": med("part_hulls"), "median_rest_hulls": med("rest_hulls"),
                           "max_hulls": max((r["part_hulls"] + r["rest_hulls"] for r in ok), default=None),
                           "median_visual_to_hull_p95_mm": med("visual_to_hull_p95_mm"), "median_hull_to_visual_p95_mm": med("hull_to_visual_p95_mm")}
    (REPORT / "summary.json").write_text(json.dumps({"configs": summary, "objects": rows}, indent=1))
    print("REPORT DONE")


main()
