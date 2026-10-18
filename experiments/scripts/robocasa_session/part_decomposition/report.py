"""Stage 3: render every object that is done and summarize the run into report/summary.json.

Renders an object only once, unless its result is newer than its render.
"""
import json, statistics, time

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from common import CATEGORIES, OUT, objects
from semantic_digital_twin.spatial_computations.mesh_rendering import CameraRing

TILE = 260
FONT = ImageFont.load_default(size=15)
SMALL = ImageFont.load_default(size=13)
HANDLE = np.array([232, 89, 12])
HANDLE_HULLS = np.array([[232, 89, 12], [245, 140, 60], [200, 70, 20], [250, 175, 95]])
REST_HULLS = np.array([[70, 120, 190], [95, 165, 150], [140, 140, 200], [80, 150, 200], [120, 170, 110], [160, 120, 170]])
ring = CameraRing()
REPORT = OUT / "report"
(REPORT / "renders").mkdir(parents=True, exist_ok=True)


def tile(image, colors, title, subtitle):
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


def render(mesh, direction, face_colors):
    views = CameraRing(directions=[direction]).render(mesh)
    image, faces = views.images[0], views.faces[0]
    colors = np.full(image.shape + (3,), -1.0)
    hit = faces >= 0
    colors[hit] = face_colors[faces[hit]]
    return image, colors


def draw(key, located, result):
    data = np.load(OUT / "located" / f"{key}.npz")
    visual = trimesh.Trimesh(data["vertices"], data["faces"], process=False)
    handle = np.zeros(len(visual.faces), bool)
    for part in located["parts"]:
        if part["confidence"] >= 0.5:
            handle[part["faces"]] = True
    views = ring.render(visual)
    shown = [((f >= 0) & handle[np.maximum(f, 0)]).sum() for f in views.faces]
    view = int(np.argmax(shown)) if max(shown) > 0 else 1
    front, back = ring.directions[view], ring.directions[(view + 4) % 8 if view < 8 else 1]
    face_colors = np.where(handle[:, None], HANDLE, np.array([175, 175, 175])).astype(float)
    tiles = [tile(*render(visual, front, face_colors), "Handle faces (VLM)", f"{int(handle.sum()):,} of {len(visual.faces):,} faces")]
    hull_path = OUT / "hulls" / f"{key}.npz"
    if result.get("status") == "ok" and hull_path.exists():
        hulls = np.load(hull_path)
        mesh = trimesh.Trimesh(hulls["vertices"], hulls["faces"], process=False)
        palette = np.where(hulls["is_part"][:, None], HANDLE_HULLS[hulls["hull"] % len(HANDLE_HULLS)], REST_HULLS[hulls["hull"] % len(REST_HULLS)]).astype(float)
        subtitle = f"{result['part_hulls']} + {result['rest_hulls']} hulls · {result['seconds']:.0f} s"
        tiles.append(tile(*render(mesh, front, palette), "Collision hulls", subtitle))
        tiles.append(tile(*render(mesh, back, palette), "Collision hulls, other side", f"gap p95 {result['gap_p95_mm']:.1f} mm"))
    else:
        blank = np.full((448, 448), 255, np.uint8)
        tiles.append(tile(blank, None, "Not split", result.get("status", "")[:36]))
    strip = Image.new("RGB", (TILE * len(tiles), TILE + 44), (255, 255, 255))
    for i, t in enumerate(tiles):
        strip.paste(t, (i * TILE, 0))
    strip.save(REPORT / "renders" / f"{key}.png", optimize=True)


def main():
    rows = []
    keys = objects()
    for path in sorted((OUT / "results").glob("*__*.json")) + sorted((OUT / "located").glob("*__*.json")):
        keys.setdefault(path.stem, path.stem)
    for key, asset in keys.items():
        row = {"object": key, "category": key.rsplit("_", 1)[0], "asset": asset, "state": "waiting"}
        if "__" in key:
            meta = json.loads(located_path.read_text()) if (located_path := OUT / "located" / f"{key}.json").exists() else json.loads((OUT / "results" / f"{key}.json").read_text())
            row.update(category=meta.get("category", key.split("__")[0]), asset=meta.get("asset", key))
        located_path, error_path, result_path = (OUT / "located" / f"{key}.json", OUT / "located" / f"{key}.error.json", OUT / "results" / f"{key}.json")
        if error_path.exists():
            row.update(state="locate failed", error=json.loads(error_path.read_text())["error"][:200])
        if located_path.exists():
            located = json.loads(located_path.read_text())
            kept = [p for p in located["parts"] if p["confidence"] >= 0.5]
            row.update(state="splitting", faces=located["faces"], server_seconds=located["server_seconds"],
                       confidence=[p["confidence"] for p in kept], dropped_pieces=len(located["parts"]) - len(kept))
            if result_path.exists():
                result = json.loads(result_path.read_text()); result.pop("trace", None)
                row.update(result=result, state="done" if result.get("status") == "ok" else ("no handle" if result.get("status") == "no part split off" else "failed"))
                render_path = REPORT / "renders" / f"{key}.png"
                if not render_path.exists() or render_path.stat().st_mtime < result_path.stat().st_mtime:
                    draw(key, located, result)
                    print("rendered", key, flush=True)
        elif result_path.exists():
            row.update(state="failed", error=json.loads(result_path.read_text()).get("status", "")[:200])
        rows.append(row)
    categories = {}
    for name in dict.fromkeys([*CATEGORIES, *(r["category"] for r in rows)]):
        rs = [r for r in rows if r["category"] == name]
        ok = [r["result"] for r in rs if r["state"] == "done"]
        med = lambda k: statistics.median(x[k] for x in ok) if ok else None
        categories[name] = {"objects": len(rs), **{s: sum(r["state"] == s for r in rs) for s in ("done", "no handle", "failed", "locate failed", "splitting", "waiting")},
                            "median_seconds": med("seconds"), "median_gap_p95_mm": med("gap_p95_mm"), "median_bloat_p95_mm": med("bloat_p95_mm"),
                            "median_part_hulls": med("part_hulls"), "median_rest_hulls": med("rest_hulls")}
    (REPORT / "summary.json").write_text(json.dumps({"updated": time.strftime("%d %b %Y %H:%M UTC", time.gmtime()), "categories": categories, "objects": rows}, indent=1))
    print("REPORT DONE", {k: (v["done"], v["objects"]) for k, v in categories.items()})


main()
