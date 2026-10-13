# montessori-eql-stack — standing rules

- Per-branch working detail (test baselines, environment landmines, round notes) lives in `.claude/personal/pr-progress/<branch>.md` on the personal-notes branch — notably `pr-progress/cramera_eql_autocomplete.md`, which carries the full Round 1–4 history for #170 including the local-environment fixes (lark rename, semantic_digital_twin ORM duplicate table, costmaps inflation OOM, detector-test…
- Every PR in this plan is a draft, per the draft-until-told-otherwise convention in the personal notes.
- Landing order is the stack order; nothing here is parallelizable, which is why the plan is one wave / one track with a chained `depends_on`.
