## PR #185 - basstler package extraction

### 2026-10-02 - cram2#659 third round (session_01GzsB6xE8CwrBApLvwSbGjD)

`/plan-item-resolve` (auto mode). The fork PR was green, clean and out of draft. What it was
actually waiting on was upstream: two new tomsch420 threads on cram2#659 from 2026-10-02 that
nothing on the fork had recorded.

Done, in `be0ed435f`:
- `dependencies.py:83`: `Dependency.CONSTRAINT_START` became the field `constraint_start`.
- `plan_model.py:56`: `ItemStatus` values are now `not started` / `in progress`. The user chose to
  change the values and migrate. The underscore spelling is still read (`_missing_`,
  `accepted_spellings`). `display_label` and the `status_label` filter are deleted. The CSS class
  comes from the member name, and the sync status-line regex accepts spaces. The docs use the new
  spelling.
- 705 tests pass on 3.11. The PR description is updated. The fork thread on the `status_label`
  assertion was replied to and resolved.
- The PR is left ready, not draft: its un-draft is the promotion approval.

### 2026-10-02 later - LucaKro round four, one Repository

Done:
- `c61a734d9`: one `Repository` in `basstler/repository.py`. `setup_steps`'s GitHub-host rule now
  lives in `resolve_repository`, and `labels_url` is on `ForkLabels`.
- `4cdd39318`: every print goes through logging via `basstler/standard_streams.py`
  (`StandardStreamHandler`, bare messages, stdout for info and stderr for warnings and up). A
  `__main__` module resolves to its spec name. `dependencies.main` returns an `ExitCode`.
- 710 tests pass. PR description updated.

Open: "dataclass exception gaming" (`dependencies.py:54`). The user asked whether the krrood
dependency is in the plan. Decision 14 intends it, but no item schedules it.

### 2026-10-02 evening - fork review of 4cdd39318

- `105de6379`: `StandardStreamHandler` is `@dataclass(eq=False)` (setup in `__post_init__`), its
  format is `BARE_MESSAGE_FORMAT`; the stream tests use a `LoggedMessage` StrEnum and
  `NOTHING_WRITTEN`; `test_repository.py` builds everything from one `REPOSITORY` and `Host`.
  710 pass. Three fork threads replied and resolved.
- `37e8cf887`: "no global constants" (two fork threads, 17:11) - `standard_streams.py` has none
  left: `message_format` is a handler field, the package logger is `__package__`, and
  `import_name` always reads the spec. 710 pass. Both threads replied and resolved.
- Upstream (16:55 read): only the "fields / and no classvar" thread is unresolved; it is met by
  `be0ed435f`. The user replied on the others at 16:14.

Next:
- The user replies on (and resolves) the "and no classvar" upstream thread.
- After #185 lands: rewrite the notes-branch manifests to the spaced spelling, then drop the
  underscore reading.
- Landing hazard until then: this branch's writers produce `in progress`, which `main`'s tooling
  rejects.
