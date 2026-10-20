# network-limits-on-main (montessori-perception-split) - draft PR #487

Plan: land network_limits.py and its test off main as their own PR, reshaped per
review.

Done: review rounds 1 (612f307b8) and 2 (7ad177fe1) addressed, all 9 threads replied
and resolved. Requirements are a tuple of SettingValue on LargeMessageReceiver;
unmet_requirements() is one EQL query joining required and actual values (fragment
lifetime the only upper bound); sysctl_root renamed kernel_settings_root. 13/13 tests
pass locally. PR description current, still draft.
Next: CI on 7ad177fe1, then the reviewer. When #202 restacks onto this, its
perception/node.py call becomes LargeMessageReceiver().check_messages_can_arrive().
