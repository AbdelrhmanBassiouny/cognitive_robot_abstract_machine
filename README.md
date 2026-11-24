# basstler upstream reviews

Kept by basstler's `/upstream-reviews` skill. Each read pushes a branch of its own under
`basstler/upstream-reviews-requests/`, starting from this one, with a `request.json`. That push runs
`.github/workflows/upstream-reviews.yml`, which reads the upstream as the request asks and commits `result.json`
onto the same branch, where the session reads it. Each run also deletes the request
branches it made, by their `Basstler-request` trailer, whose last commit is over an hour
old. Nothing here is ever merged anywhere.

Install or update it with `/setup-personal-notes`, which runs
`python -m basstler.setup.steps install-upstream-reviews-action`.
