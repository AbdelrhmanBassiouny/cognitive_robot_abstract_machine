#!/usr/bin/env python3
"""
bundle_urdf.py — make a URDF (or xacro) self-contained for the web viewer.

Resolves every mesh reference (package://, file://, absolute or relative),
copies the meshes plus their side assets (textures for .dae, .mtl + textures
for .obj) into <out>/meshes/..., rewrites the references to those relative
paths, and writes <out>/<name>.urdf. The result loads in the browser with no
ROS installed.

Standalone use:
    python3 tools/bundle_urdf.py path/or/package://...  --name apartment \
        --out static/scenes/my_scene

It is also imported by tools/onboard_demo.py, which feeds it the exact
uri->path resolutions recorded while the demo ran.
"""

import argparse
import glob
import logging
import os
import re
import shutil
import subprocess
import sys

MESH_EXTS = (".dae", ".stl", ".obj")


# ------------------------------------------------------------ resolution ----
def _search_root_candidates():
    """
    Likely ROS install prefixes to search for a package:// URI: env vars first,
    then common workspace layouts under the home directory and /opt/ros.
    """
    roots = []
    for env in ("AMENT_PREFIX_PATH", "ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH"):
        roots += [p for p in os.environ.get(env, "").split(":") if p]
    home = os.path.expanduser("~")
    roots += glob.glob(os.path.join(home, "*_ws", "install"))
    roots += glob.glob(os.path.join(home, "*", "install"))
    roots += glob.glob("/opt/ros/*")
    return roots


def resolve_uri(uri, hints=None, base_dir=None):
    """
    Resolve a mesh/urdf reference to an absolute file path (or None).
    """
    if hints and uri in hints:
        return hints[uri]
    if uri.startswith("package://"):
        rest = uri[len("package://") :]
        pkg, _, rel = rest.partition("/")
        # 1. the CRAM stack's own resolver (ament index), if importable
        try:
            from semantic_digital_twin.adapters.package_resolver import (
                PackageUriResolver,
            )

            p = PackageUriResolver().resolve(uri)
            if os.path.isfile(p):
                return p
        except Exception:
            pass
        # 2. ament index directly
        try:
            from ament_index_python.packages import get_package_share_directory

            p = os.path.join(get_package_share_directory(pkg), rel)
            if os.path.isfile(p):
                return p
        except Exception:
            pass
        # 3. filesystem heuristics over common workspace layouts
        for root in _search_root_candidates():
            for cand in (
                os.path.join(root, pkg, "share", pkg, rel),
                os.path.join(root, "share", pkg, rel),
                os.path.join(root, pkg, rel),
            ):
                if os.path.isfile(cand):
                    return cand
        return None
    if uri.startswith("file://"):
        p = uri[len("file://") :]
        return p if os.path.isfile(p) else None
    if os.path.isabs(uri):
        return uri if os.path.isfile(uri) else None
    if base_dir:
        p = os.path.join(base_dir, uri)
        return p if os.path.isfile(p) else None
    return None


def _ref_to_relpath(uri):
    """
    Where a reference lands inside <out>/meshes/.
    """
    if uri.startswith("package://"):
        rest = uri[len("package://") :]
        pkg, _, rel = rest.partition("/")
        return os.path.join(pkg, rel)
    name = uri[len("file://") :] if uri.startswith("file://") else uri
    return os.path.join("_local", os.path.basename(name))


# ------------------------------------------------------------ side assets ---
def _copy_file(src, dst, copied, missing):
    """
    Copy src to dst once; record it in copied (memo) or missing on failure.
    """
    if src in copied:
        return True
    if not src or not os.path.isfile(src):
        missing.append(src or "<unresolved>")
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    copied[src] = dst
    return True


def _copy_side_assets(src_mesh, dst_mesh, copied, missing):
    """
    Textures referenced by a .dae, or .mtl + its textures for a .obj.
    """
    d_src, d_dst = os.path.dirname(src_mesh), os.path.dirname(dst_mesh)
    ext = src_mesh.lower().rsplit(".", 1)[-1]
    try:
        txt = open(src_mesh, "rb").read().decode("utf-8", "replace")
    except Exception:
        return
    refs = set()
    if ext == "dae":
        refs |= set(re.findall(r"[\w./\-]+\.(?:png|jpg|jpeg|tga|tif)", txt, re.I))
    elif ext == "obj":
        for m in re.findall(r"mtllib\s+(.+)", txt):
            refs.add(m.strip())
        for mtl in list(refs):
            msrc = os.path.join(d_src, mtl)
            if os.path.isfile(msrc):
                _copy_file(msrc, os.path.join(d_dst, mtl), copied, missing)
                mt = open(msrc, "rb").read().decode("utf-8", "replace")
                for tm in re.findall(r"map_\w+\s+(.+)", mt):
                    refs.add(tm.strip())
    for r in refs:
        r = r.strip().lstrip("./")
        src = os.path.join(d_src, r)
        if os.path.isfile(src):
            _copy_file(src, os.path.join(d_dst, r), copied, missing)


# ---------------------------------------------------------------- xacro -----
def xacro_to_urdf_text(path):
    """
    Run the xacro CLI (needs a sourced ROS environment on PATH).
    """
    out = subprocess.run(["xacro", path], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("xacro failed for %s:\n%s" % (path, out.stderr[-2000:]))
    return out.stdout


# ------------------------------------------------------------------ main ----
def bundle_urdf(source, name, out_dir, hints=None):
    """
    Bundle one URDF/xacro.

    Returns a report dict.
    """
    src_path = resolve_uri(source, hints=hints) or source
    if not os.path.isfile(src_path):
        raise FileNotFoundError(
            "URDF source not found: %s (from %s)" % (src_path, source)
        )
    if src_path.endswith(".xacro"):
        txt = xacro_to_urdf_text(src_path)
    else:
        txt = open(src_path, encoding="utf-8", errors="replace").read()
    base_dir = os.path.dirname(src_path)

    os.makedirs(out_dir, exist_ok=True)
    copied, missing, rewritten = {}, [], 0
    for ref in sorted(set(re.findall(r'filename="([^"]+)"', txt))):
        if not ref.lower().endswith(MESH_EXTS):
            continue  # plugins (.so) etc.
        src = resolve_uri(ref, hints=hints, base_dir=base_dir)
        rel = _ref_to_relpath(ref)
        dst = os.path.join(out_dir, "meshes", rel)
        if _copy_file(src, dst, copied, missing):
            _copy_side_assets(src, dst, copied, missing)
        txt = txt.replace('"%s"' % ref, '"meshes/%s"' % rel.replace(os.sep, "/"))
        rewritten += 1

    urdf_out = os.path.join(out_dir, "%s.urdf" % name)
    open(urdf_out, "w").write(txt)
    links = re.findall(r'<link\s+name="([^"]+)"', txt)
    joints = re.findall(r'<joint\s+name="([^"]+)"\s+type="([^"]+)"', txt)
    exts = sorted({os.path.splitext(p)[1].lower() for p in copied})
    return {
        "name": name,
        "urdf": urdf_out,
        "source": src_path,
        "links": links,
        "joints": [j[0] for j in joints],
        "movable_joints": [j[0] for j in joints if j[1] not in ("fixed",)],
        "meshes_copied": len(copied),
        "mesh_exts": exts,
        "refs_rewritten": rewritten,
        "missing": missing,
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("source", help="URDF/xacro path or package:// URI")
    ap.add_argument("--name", help="output model name (default: source basename)")
    ap.add_argument("--out", default="static/sim", help="output directory")
    a = ap.parse_args()
    name = a.name or os.path.splitext(os.path.basename(a.source))[0]
    rep = bundle_urdf(a.source, name, a.out)
    logging.info(
        "wrote %s  (%d links, %d joints, %d meshes %s)"
        % (
            rep["urdf"],
            len(rep["links"]),
            len(rep["joints"]),
            rep["meshes_copied"],
            rep["mesh_exts"],
        )
    )
    if rep["missing"]:
        logging.warning("MISSING %d assets:" % len(rep["missing"]))
        for m in rep["missing"][:20]:
            logging.warning("   %s", m)
        sys.exit(2)


if __name__ == "__main__":
    main()
