# basstler upstream reviews

Kept by basstler's `/upstream-reviews` skill. Pushing a new `request.json` runs
`.github/workflows/upstream-reviews.yml`, which reads the upstream pull request it names and commits
`result.json`. Nothing on this branch is ever merged anywhere.

Install or update it with `/setup-personal-notes`, which runs
`python -m basstler.setup_steps install-upstream-reviews-action`.
