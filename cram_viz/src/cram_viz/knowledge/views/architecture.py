"""
Drill-down views of the CRAM architecture: packages, subpackages and classes.
"""

from __future__ import annotations

from typing_extensions import Any, Dict, List, TYPE_CHECKING

from cram_viz.knowledge.architecture_entities import Package, PythonClass, SubPackage
from cram_viz.knowledge.views.base import _view

if TYPE_CHECKING:
    from cram_viz.knowledge.knowledge_base import EpisodeKnowledgeBase

#: at most this many classes are drawn in one drill-down view
CLASS_CAP = 150

#: at most this many subclasses are drawn in a class inheritance view
SUBCLASS_CAP = 80


def _class_id(python_class: PythonClass) -> str:
    """
    Graph node id of a scanned class (module-qualified).
    """
    return python_class.module + "." + python_class.name


def _class_lines(python_class: PythonClass, drill_hint: bool = True) -> List[str]:
    """
    Detail lines shown for a class node.
    """
    lines = [
        "a PythonClass",
        "package: " + python_class.package,
        "module: " + python_class.module,
        "methods: %d" % python_class.methods,
    ]
    if python_class.bases:
        lines.append("bases: " + ", ".join(python_class.bases))
    if python_class.doc:
        lines.append(python_class.doc)
    if drill_hint:
        lines.append("double-click: inheritance view")
    return lines


def _add_classes(
    add: Any,
    edges: List[Dict[str, Any]],
    parent_id: str,
    shown: List[PythonClass],
    total: int,
) -> List[str]:
    """
    Add class nodes plus their on-screen inheritance edges to a view.

    :return: Extra detail lines for the parent (a truncation notice, if any).
    """
    name_to_id: Dict[str, str] = {}
    for python_class in shown:
        class_id = _class_id(python_class)
        add(class_id, python_class.name, "pyclass", _class_lines(python_class))
        edges.append(
            {"from": parent_id, "to": class_id, "kind": "prop", "label": "defines"}
        )
        name_to_id.setdefault(python_class.name, class_id)
    for python_class in shown:
        for base in python_class.bases:
            if base in name_to_id and name_to_id[base] != _class_id(python_class):
                edges.append(
                    {
                        "from": _class_id(python_class),
                        "to": name_to_id[base],
                        "kind": "type",
                        "label": "inherits",
                    }
                )
    if total > len(shown):
        return [
            "showing the %d largest of %d classes (by method count)"
            % (len(shown), total)
        ]
    return []


def _package_view(
    knowledge_base: EpisodeKnowledgeBase, package: Package
) -> Dict[str, Any]:
    """
    Inside view of a package: its subpackages and top-level classes.
    """
    nodes, edges, details, add = _view()
    subpackages = [
        entry for entry in knowledge_base.subpackages if entry.package == package.name
    ]
    top_level = sorted(
        (
            entry
            for entry in knowledge_base.classes
            if entry.package == package.name and entry.subpackage == package.name
        ),
        key=lambda entry: -entry.methods,
    )
    add(
        package.name,
        package.name,
        "concept",
        [
            "a Package",
            package.description,
            "%d modules · %d classes" % (package.module_count, package.class_count),
        ],
    )
    for subpackage in subpackages:
        add(
            subpackage.name,
            subpackage.name.split(".", 1)[1],
            "klass",
            [
                "a SubPackage of " + subpackage.package,
                "%d modules · %d classes"
                % (subpackage.module_count, subpackage.class_count),
                "double-click to open",
            ],
        )
        edges.append(
            {
                "from": package.name,
                "to": subpackage.name,
                "kind": "prop",
                "label": "contains",
            }
        )
    note = _add_classes(add, edges, package.name, top_level[:CLASS_CAP], len(top_level))
    if note:
        details[package.name]["lines"] += note
    return {
        "ok": True,
        "crumb": package.name,
        "nodes": nodes,
        "edges": edges,
        "details": details,
    }


def _subpackage_view(
    knowledge_base: EpisodeKnowledgeBase, subpackage: SubPackage
) -> Dict[str, Any]:
    """
    Inside view of a subpackage: its classes with inheritance edges.
    """
    nodes, edges, details, add = _view()
    classes = sorted(
        (
            entry
            for entry in knowledge_base.classes
            if entry.subpackage == subpackage.name
        ),
        key=lambda entry: -entry.methods,
    )
    add(
        subpackage.name,
        subpackage.name.split(".", 1)[1],
        "klass",
        [
            "a SubPackage of " + subpackage.package,
            "%d modules · %d classes"
            % (subpackage.module_count, subpackage.class_count),
        ],
    )
    note = _add_classes(add, edges, subpackage.name, classes[:CLASS_CAP], len(classes))
    if note:
        details[subpackage.name]["lines"] += note
    return {
        "ok": True,
        "crumb": subpackage.name.split(".", 1)[1],
        "nodes": nodes,
        "edges": edges,
        "details": details,
    }


def _class_view(
    knowledge_base: EpisodeKnowledgeBase, python_class: PythonClass
) -> Dict[str, Any]:
    """
    Inheritance view of one class: bases above, repo subclasses below.
    """
    nodes, edges, details, add = _view()
    class_id = _class_id(python_class)
    add(
        class_id,
        python_class.name,
        "pyclass",
        _class_lines(python_class, drill_hint=False),
    )
    # direct base classes: resolve inside the repo (same package preferred),
    # otherwise show them as external
    for base in python_class.bases:
        candidates = [entry for entry in knowledge_base.classes if entry.name == base]
        pick = next(
            (entry for entry in candidates if entry.package == python_class.package),
            candidates[0] if candidates else None,
        )
        if pick:
            base_id = _class_id(pick)
            if base_id not in details:
                add(base_id, pick.name, "pyclass", _class_lines(pick))
        else:
            base_id = "ext:" + base
            if base_id not in details:
                add(base_id, base, "upper", ["external base class (outside the repo)"])
        edges.append(
            {"from": class_id, "to": base_id, "kind": "type", "label": "inherits"}
        )
    # every subclass in the repo (matched by base name)
    subclasses = [
        entry
        for entry in knowledge_base.classes
        if python_class.name in entry.bases and _class_id(entry) != class_id
    ]
    for subclass in subclasses[:SUBCLASS_CAP]:
        subclass_id = _class_id(subclass)
        if subclass_id not in details:
            add(subclass_id, subclass.name, "pyclass", _class_lines(subclass))
        edges.append(
            {"from": subclass_id, "to": class_id, "kind": "type", "label": "inherits"}
        )
    if len(subclasses) > SUBCLASS_CAP:
        details[class_id]["lines"].append(
            "showing %d of %d subclasses" % (SUBCLASS_CAP, len(subclasses))
        )
    return {
        "ok": True,
        "crumb": python_class.name,
        "nodes": nodes,
        "edges": edges,
        "details": details,
    }
