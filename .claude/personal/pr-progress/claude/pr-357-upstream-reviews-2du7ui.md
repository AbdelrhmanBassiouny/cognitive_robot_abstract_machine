## Read-only session: review state of PR #357 / upstream #642

**Task**: report the comments and reviews on fork PR #357 and on its upstream
pull request cram2#642. No code change is committed from this branch yet.

**Done**
- Fork PR #357 (`claude/polymorphic-enum-feature-domain-14xvqi`, base `main`,
  labels `bug`, `in-review`): no issue comments, no reviews, no review threads,
  no check runs on head `0741a16`. Everything is upstream.
- `/upstream-reviews 642` dispatched on the fork (run 35346727940, success).
  Upstream #642 carries 1 review thread, still unresolved, on
  `test/krrood_test/conftest.py:116`:
  - tomsch420 (changes requested): "I am unsure if this is a true problem.
    PolymorphicEnumType should always be used for enums in ORM anyways"
  - two replies from the user, the second asking why the type mappings were
    adjusted at all when this "should have just been a feature extractor fix".

**Next (not started, awaiting the user's call)**
- The conftest change is test-harness only: krrood's own test ORM was generated
  without the `enum.Enum -> PolymorphicEnumType` mapping, so its enum columns
  mapped natively and could not reproduce the bug. Registering it is what makes
  the new test fail before the fix. The production change really is only
  `FeatureExtractor._type_of_column_value`.
- If the user wants the thread answered, the reply has to be posted by them or
  from a fork context - AGENTS.md forbids commenting on upstream.
