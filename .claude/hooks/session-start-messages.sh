#!/bin/bash
# The wording of session-start.sh's summary lines, defined once.
#
# Sourced by ./session-start.sh, which prints these, and called directly by the
# tests that assert on them - so a reworded message changes both sides at once
# instead of drifting apart from a second copy typed into an assertion.
#
# One function per outcome rather than one template string per outcome: the
# arguments are then named and positional in the same place the sentence is
# written, and a caller that passes the wrong number fails loudly here rather
# than rendering a half-substituted line.
#
# Deliberately holds no logic. Deciding *which* message applies is
# session-start.sh's business; this file only says how each one reads.

# %% the plan line

# plan_line_not_applicable: for a branch no plan item could ever track - the
# default branch, the notes branch, a detached HEAD.
plan_line_not_applicable() {
  printf 'not applicable (this branch never holds a plan item)'
}

# plan_line_no_plans_tracked: plans are not in use on the notes branch at all.
plan_line_no_plans_tracked() {
  local notes_branch="$1"
  printf "no plans tracked on '%s' yet" "${notes_branch}"
}

# plan_line_no_item_tracks_branch: plans are in use, and none holds an item for
# this branch. Even-handed on purpose: belonging to no plan is an ordinary
# state for most branches and must not read as a reprimand.
plan_line_no_item_tracks_branch() {
  local branch="$1"
  local tracked_plan_count="$2"
  printf "no item tracks branch '%s' (%s plan(s) tracked) - if this session's work belongs to one of them, add its item before starting; if it belongs to none, there is nothing to do" \
    "${branch}" "${tracked_plan_count}"
}

# plan_line_manifest_missing: the index names a plan whose manifest is not on
# the notes branch, so the two have drifted apart.
plan_line_manifest_missing() {
  local plan_id="$1"
  local manifest_path="$2"
  local notes_branch="$3"
  printf "'%s' tracks this branch, but %s is missing on '%s'" \
    "${plan_id}" "${manifest_path}" "${notes_branch}"
}

# plan_line_tracked: the branch is a tracked item of a plan that resolved.
plan_line_tracked() {
  local plan_id="$1"
  local tracking_issue="$2"
  printf "'%s' (tracking issue: %s)" "${plan_id}" "${tracking_issue}"
}

# %% the git identity line

# git_identity_line_not_recorded: the notes branch carries no identity at all,
# so there is nothing to write into this clone.
git_identity_line_not_recorded() {
  local notes_branch="$1"
  local identity_path="$2"
  printf "not recorded on '%s' (%s) - run ./save-git-identity.sh to record one" \
    "${notes_branch}" "${identity_path}"
}

# git_identity_line_incomplete: an identity is recorded but only half of it,
# and half an identity cannot author a commit.
git_identity_line_incomplete() {
  local identity_path="$1"
  local notes_branch="$2"
  printf "%s on '%s' needs both user.name and user.email - nothing written" \
    "${identity_path}" "${notes_branch}"
}

# git_identity_line_already_set: this clone has an identity of its own, which
# the hook only ever fills a gap around rather than overriding.
git_identity_line_already_set() {
  local identity="$1"
  printf 'already set in this clone: %s - left unchanged' "${identity}"
}

# git_identity_line_written: the recorded identity was written into this
# clone's repository-local config.
git_identity_line_written() {
  local notes_branch="$1"
  local identity_path="$2"
  local identity="$3"
  printf "set from '%s' (%s): %s" "${notes_branch}" "${identity_path}" "${identity}"
}

# %% the setup line

# setup_line_not_checked: check-setup.sh is not in this checkout, so there is
# no verdict to report rather than a passing one.
setup_line_not_checked() {
  local check_setup_script="$1"
  printf 'not checked - %s is not in this checkout' "${check_setup_script}"
}

# setup_line_ok: every check passed.
setup_line_ok() {
  printf 'ok'
}

# setup_line_needs_setup: the heading above the indented needs-setup rows,
# which check-setup.sh itself words.
setup_line_needs_setup() {
  local needs_setup_count="$1"
  printf '%s check(s) need setup - run /setup-personal-notes:' "${needs_setup_count}"
}

# %% the default branch line

# default_branch_line_not_synced: the script that does the syncing is not in
# this checkout, so there is no outcome to report rather than a clean one.
default_branch_line_not_synced() {
  local fast_forward_script="$1"
  printf 'not synced - %s is not in this checkout' "${fast_forward_script}"
}


# default_branch_line_not_configured: nothing in this checkout names the
# upstream repository the fork tracks, so there is no branch to catch up with.
default_branch_line_not_configured() {
  local stack_config_file="$1"
  printf 'not synced - %s is not in this checkout, so no upstream repository is named' \
    "${stack_config_file}"
}

# default_branch_line_upstream_unresolved: the configuration is there but this
# checkout's remotes do not resolve to a fork and an upstream, in the words the
# resolution itself refused with.
default_branch_line_upstream_unresolved() {
  local reason="$1"
  printf 'not synced - %s' "${reason}"
}

# default_branch_line_upstream_unreachable: the upstream is named but could not
# be fetched, so how stale this clone is stays unknown.
default_branch_line_upstream_unreachable() {
  local base_branch="$1"
  local upstream_repository="$2"
  printf "'%s' left as it is - %s is unreachable" \
    "${base_branch}" "${upstream_repository}"
}

# default_branch_line_current: the base every session starts from already
# carries the upstream's tip.
default_branch_line_current() {
  local base_branch="$1"
  local upstream_repository="$2"
  printf "'%s' already matches %s" "${base_branch}" "${upstream_repository}"
}

# default_branch_line_fast_forwarded: the base was behind and has been brought
# up to the upstream's tip in this clone.
default_branch_line_fast_forwarded() {
  local base_branch="$1"
  local commit_count="$2"
  local upstream_repository="$3"
  printf "'%s' fast-forwarded %s commit(s) to %s" \
    "${base_branch}" "${commit_count}" "${upstream_repository}"
}

# default_branch_line_diverged: the base carries commits the upstream does not,
# which a fast-forward cannot reconcile and a force push must never resolve.
default_branch_line_diverged() {
  local base_branch="$1"
  local upstream_repository="$2"
  printf "'%s' has commits %s does not - left as it is, nothing force-pushed" \
    "${base_branch}" "${upstream_repository}"
}

# default_branch_line_local_update_refused: the base is checked out and the
# working tree would lose changes, so git refused to move it.
default_branch_line_local_update_refused() {
  local base_branch="$1"
  local upstream_repository="$2"
  printf "'%s' is behind %s but is checked out with changes git will not overwrite - left as it is" \
    "${base_branch}" "${upstream_repository}"
}

# %% the rows under the default branch line

# default_branch_row_fork_pushed: the fork was behind too and now is not, so
# the clone the next session is cut from starts fresh.
default_branch_row_fork_pushed() {
  local fork_remote="$1"
  printf "pushed it to '%s', which was behind" "${fork_remote}"
}

# default_branch_row_fork_push_failed: this clone moved but the fork did not,
# which is what silently makes every later clone stale.
default_branch_row_fork_push_failed() {
  local fork_remote="$1"
  printf "pushing it to '%s' was refused - the fork is still behind, so the next clone starts stale" \
    "${fork_remote}"
}

# default_branch_row_current_branch_behind: the work this session has to do
# before planning against a base the fast-forward has moved out from under it.
default_branch_row_current_branch_behind() {
  local base_branch="$1"
  local commit_count="$2"
  printf "this branch is %s commit(s) behind '%s' - merge or rebase it before planning on a stale base" \
    "${commit_count}" "${base_branch}"
}
