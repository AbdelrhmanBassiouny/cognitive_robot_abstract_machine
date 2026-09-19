# Basstler package plan refactor (no PR — plan-data work only)

Session task (2026-08-20): refactor the workflow-unification plan so the
.claude Python migration into its own package is the priority now, with the
package renamed to `basstler` (Bas- from Bassiouny + German *Basstler*, a
tinkerer). Motivation: duplication carriers keep multiplying and reviewers
keep flagging them.

## Done

- plan.yaml refactored (decision 13): new `basstler` track in the upstream
  wave; `dev-tooling-*` item ids renamed `basstler-*`; `basstler-package`
  re-scoped to create the package off `main` itself, dependency on
  `shared-pr-state-chips` dropped and inverted (#111 now rebases onto the
  basstler branch); rebase-cost of the move measured per open PR and the
  crossing doctrine recorded in the item notes.
- roadmap.md: decision-13 entry appended (name, evidence, structural
  changes, cost, what decisions 8/12 keep).
- Saved via save-plan.sh (notes commit 05b70777f, after re-applying onto a
  concurrent #154-notes save), dashboard republished (same artifact URL),
  structural record posted on tracking issue #102.

## Next

- Kick off `basstler-package` (`/plan-item-kickoff workflow-unification
  basstler-package`) — it shows as ready-to-start on the dashboard. This
  session wrote no code and opened no PR; the designated branch
  claude/bastler-package-refactor-2r07er carries nothing, since plan data
  lives only on the personal-notes branch.
