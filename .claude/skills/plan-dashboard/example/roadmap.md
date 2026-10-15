# Notification Retry Overhaul — standing rules

- This is a fictional example plan, written to accompany
  example-walkthrough.md; nothing here describes a real initiative.
- Retries use exponential backoff with jitter, not a fixed delay.
- Every item in the retry-logic track stacks its branch directly on
  retry-backoff-strategy's branch once that pull request is ready for review.
- A message that exhausts its retries goes to a dead-letter queue rather than
  being dropped silently.
