# network-limits-on-main (montessori-perception-split) - draft PR #487

Plan: land network_limits.py and its test off main as their own PR, reshaped per
review, then promote upstream.

Done: review rounds 1-3 (612f307b8, 7ad177fe1, a4b815ce4), all 10 threads replied and
resolved. unmet_requirements() returns an unevaluated EQL query (Entity[SettingValue]);
check_messages_can_arrive() evaluates it. 13/13 tests pass locally. Promotion link
built, recorded under "## Promote" in #487's description, labelled promotion-link-sent.
Next: CI on a4b815ce4; the developer clicks Create on the promotion link. When #202
restacks onto this, node.py calls LargeMessageReceiver().check_messages_can_arrive().
