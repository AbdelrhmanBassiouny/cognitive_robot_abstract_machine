# general-video-production — standing rules

- The package lands on main first and must already produce a video on its own (a minimal narrated video rendered in a test), per the request that started the plan.
- Scope check: the package's files are extracted from unlanded #429, but the package stands on its own (a usable library with its own tests), so it is a separate item rather than folded into #429; #429 shrinks instead.

- The package is `crollywood` (renamed from `cramcorder` in the upstream review on cram2#742). Every later item imports `crollywood` and follows the API changes listed on #471.
