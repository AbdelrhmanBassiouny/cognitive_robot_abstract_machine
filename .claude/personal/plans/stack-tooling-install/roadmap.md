# stack-tooling-install — standing rules

- The upstream promotion is a separate manual step from the fork-internal merge, so a gate phrased as "on upstream main and fork main fast-forwarded" is not met by a fork merge alone.
- A cross-fork pull request's base-repository CI run has only one remote, pointing at the upstream, so there are zero fork candidates and a configuration load that treats that as an error fails in CI and nowhere else.
- Live label creation is unverified across this whole track. This environment's token is a fine-grained installation token, so the create call is exercised only through a stub.
- The package extraction carries these files. One bug fix here is duplicated verbatim at the moved path, so it lands first and is picked up in the re-merge that branch already needs.
