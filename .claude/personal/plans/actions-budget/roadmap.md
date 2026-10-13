# actions-budget — standing rules

- Draft pull requests run the changed libraries plus their dependents. The full matrix runs on ready for review, a `full-ci` label or dispatch.
- The integration pipeline is event-only: no `schedule` anywhere.
- Plan it here, take the fastest route to unblocking, and keep it clean. Prevent a repeat, and add monitors and warnings that fire when rates are being exceeded.
