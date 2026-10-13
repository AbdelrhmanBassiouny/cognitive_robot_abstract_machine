## Next
- Nothing on this branch. The remaining work belongs to the other items: the
  five downstream stack branches and #175 are all still based on the pre-merge
  `30bd734f` and need restacking onto `6d944c52`.
- Two CI failures are deliberately left for the developer, both pre-existing
  and unrelated to the merge: `PickUpAction`'s commented-out `AttachNode`
  (8cc3cf69) makes main's `test_node_expansion` see three children where it
  asserts four, and `test_warehouse_storage_layout` /
  `test_wind_farm_service_layout` (08257863) test two demo directories that
  were never committed.
- CI on `6d944c52` had not reported yet when this session ended.


## Plan
1. Merge `origin/main` into the #169 tip and resolve the seven conflicts. - done
2. Verify the result statically (the container has no cram environment). - done
3. Push to this branch, then fast-forward `montessori_fast_inline_monitor`. - done
4. Record the resolution in the plan's manifest/roadmap and republish the
   dashboard. - done
