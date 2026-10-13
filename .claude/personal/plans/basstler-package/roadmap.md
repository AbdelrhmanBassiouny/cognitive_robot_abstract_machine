# basstler-package — standing rules

- Whichever lands second rebases. The migration moves files nearly every open tooling pull request touches. A pull request already through review may instead land just before the migration's final merge, which folds it in on the migration side - cheaper, and the user decides per pull request at merge time.
- The conversion items must follow the in-flight bash-touching pull requests, not lead them: a wholesale body rewrite cannot be merged by the whichever-lands-second convention.
- Two carriers are unreachable from the migration branch and stay with `basstler-github-api-unification`, whose two remaining carriers live on other plans' branches.
