PR #523, item basstler-package/cram-basstler-removal (auto mode). Draft.

Plan
- Strip every basstler file and mention from CRAM; plugin is per-user.

Done
- Promotion link built + promotion-link-sent label.
- Review round 1 (f1d380d8c): settings.json, stack.toml, upstream-reviews.yml removed; README/.gitignore cleaned; PathEnumeration moved to krrood with tests. Upstream setting moved to personal stack.toml. 11 threads resolved.

Next
- Promotion link recorded on #523; user clicks Create upstream, then adds in-review. Open threads (upstream-reviews, stamps) now tracked as basstler items.

id: basstler-package
title: 'The basstler package: what is left of it in CRAM'
tracking_issue: 102
item:
  id: cram-basstler-removal
  title: Move CRAM onto the basstler plugin, keeping only its configuration
  branch: claude/compassionate-darwin-ek7d2u
  status: in progress
  track: extraction
  depends_on: []
  pull_request_number: 523
  session: https://claude.ai/code/session_01JtoHXNAfe5rxy2nN5e23fk
  notes: 'Draft PR #523: enables the basstler plugin in settings.json, adds .claude/basstler/stack.toml
    and an upstream-reviews.yml calling basstler@v0.1.5, and deletes basstler/, its tests,
    .claude/hooks|stack|SETUP.md, the plugin''s skills and the test_basstler job. Open PRs
    #488, #265, #202 relabelled to promotion-link-sent. Next: the user''s review; promote
    to cram2 only with their OK. Copy basstler#16''s stack-maintenance caller once released.

    '
  blockers:
  - 'Cross-repository dependency, not representable in depends_on: basstler-package/cram-uses-basstler-plugin
    and cram-basstler-removal in AbdelrhmanBassiouny/basstler''s notes track the same work
    there.'
<!-- END-PLAN-ITEM -->

# basstler-package

- Everything else about basstler, its items and its standing rules, lives in AbdelrhmanBassiouny/basstler's notes: its `claude/personal-notes` branch, `.claude/personal/plans/basstler-package/`.
