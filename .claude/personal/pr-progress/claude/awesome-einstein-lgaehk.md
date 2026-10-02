## PR #489 - robokudo test-data fetch race (bug)

Why: found while fixing #229's red CI (run 37040000560, head a635644d). That run's
`robokudo` job failed with "OpenCV couldn't read ...depth_image.png", and its
`giskardpy` job with `test_script_launch_and_kill` (exit 1 on SIGINT). Neither
is #229's: a re-run of the failed jobs went green. The PR head merged with
cram2/main also passes sdt, segmind, coraplex, experiments, giskardpy and
robokudo in the CI image (robokudo's only failures there were MongoDB being
absent locally).

Done:
- Failing test first: test/robokudo_test/test_utils_data_downloader.py
  (2 unpackings instead of 1, 5 out of 5 runs before the fix).
- Fix: FileLock around pooch.retrieve in robokudo/utils/data_downloader.py;
  filelock declared in robokudo/pyproject.toml. Test passes 5 out of 5, and
  test_full_ae_execution/test_query pass with a fresh cache.
- Draft PR #489 opened off main, labelled bug.

Not done / open:
- Not merged into #229 (its CI is already green, and it is ready for review).
- giskardpy flake not fixed: test_script_launch_and_kill sends SIGINT after a
  fixed 5s sleep. If imports are still running then, the handler isn't
  installed yet, so the script exits 1. A fix needs the script to signal
  readiness, so that's a separate bug PR if wanted.
