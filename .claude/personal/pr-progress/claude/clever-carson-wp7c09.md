# network-limits-on-main (montessori-perception-split) - draft PR #487

Plan: land network_limits.py and its test off main as their own PR, reshaped per
review (EQL requirement query; no module-level constants or free functions).

Done: review round 1 (6 threads) addressed in 612f307b8 - SettingRequirement is an
EQL condition (operator.ge/le), LargeMessageReceiver owns machine, requirements,
unmet_requirements(), raise_limits_command(), check_messages_can_arrive(). 13/13
tests pass locally (venv also needs casadi). Threads replied and resolved; PR
description updated, still draft.
Next: CI on 612f307b8, then the reviewer. When #202 restacks onto this, its
perception/node.py call becomes LargeMessageReceiver().check_messages_can_arrive().
