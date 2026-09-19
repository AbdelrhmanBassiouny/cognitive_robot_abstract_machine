# PR #211 - integration branch CI verdict

## Done, 2026-09-19

- **Restacked onto #185's head, through #154.** #154 had merged #185 at
  `5b332d6a59`, one commit before `213ad791c7` renamed the package there, so
  neither it nor this branch carried `basstler` over the modules they added.
  The same case-preserving substitution was applied to each branch's whole
  tree first and #185's head merged second, so each conflict was the two
  sides renaming to a target they already agree on: 128 conflicting paths
  straight off, 18 on #154 and 7 here that way.
- **#425 folded in as `b9de8d0200` and closed.** Eleven files, byte-identical
  to #425's. The candidate's own checks are told apart by the workflow GitHub
  says produced each run, rather than by job names read out of a checkout
  that does not carry the workflow being judged.
- 1165 tests pass here, 910 on #154. Manifest and roadmap saved
  (`e06fcd8bf6..f3815bc406`); both descriptions updated.

## Deliberately not done

- **Neither #211 nor #154 was re-drafted.** Both were taken out of draft by
  you, and #211's own record says it stays out deliberately, since a draft is
  excluded from every integration build.
- CI left unwatched, nothing subscribed, no check-in armed.

## Outstanding

- Merging #280 into this stack conflicts on six files (the `.claude/stack/`
  to `basstler/` relocation). Belongs to an integration triage pass.
- The reporting gap recorded on the item: `RefreshPipeline._act_on` returns
  `None` on a settling that succeeded without printing `settled.output`, so
  the one run that publishes says nothing about having published. Not fixed.
