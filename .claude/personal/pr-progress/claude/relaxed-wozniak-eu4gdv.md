## Plan
- Skip uninstalled top-level packages (find_spec) only for imports under `if TYPE_CHECKING:`; runtime imports keep raising (developer decision)

## Done
- Implementation + tests pushed to #545 (draft); krrood test_utils, test_class_diagram green; RDR suite matches main
- PR description, labels `bug-fix` + `bug`, plan notes updated

## Next
- Developer review of #545; CI result (local runs used --noconftest, no ROS/libEGL in container)
