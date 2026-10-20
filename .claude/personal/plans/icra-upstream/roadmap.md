# ICRA upstream: roadmap

- Every pull request holds exactly the ICRA tip's version of its layer's files (real-experiments-tracy-icra-2026), based on main or on the layer below, never an older lineage plus a top-up.
- A layer imports only from main and the layers below it; check the import graph before each cut, and assign shared datasets, fixtures and configuration to the item whose tests use them.
- Once an item merges, close every pull request it supersedes with a comment naming the replacement; the review history stays on those closed pull requests.
- Promote to cram2 in this order: probabilistic_model, giskardpy, segmind and semantic_digital_twin (#410, #409), krrood EQL, coraplex; experiments only once their libraries are there.
- The semantic_digital_twin numeric spatial types are not landed: CasADi is locked on main (CasadiLock), so segmind runs in its own thread without them. Cover that with a threaded stress test.
- Work other plans own stays there: RDR in rdr-core-engine and rdr-interface-and-decorator, ORMatic in ontomatic-port, perception in montessori-perception-split and review-reaches-main, #409 and #410 in montessori-eql-stack, the video in general-video-production.
- No video or other large binary goes into git; link to it.
