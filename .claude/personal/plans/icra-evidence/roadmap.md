# icra-evidence — standing rules

- The evaluation frame is Bloom's taxonomy at three levels: Remembering (the store is queried and facts come back, against a vision-language model given the same episodes; Experiment D), Understanding (answering the question set; Experiment A) and Applying (the demo with parts of the representation removed; Experiment C).
- Inferring new knowledge, or any question needing several facts combined into a conclusion not already represented, is explicitly out of scope and stated so in the paper ("what objects can you pick up, and why or why not" is above Understanding).
- Working memory has no Bloom level, which is a finding, not a gap: questions such as "did anything recently move, did you move it" need a store persisting across time; icra-mechanism's snapshot-working-memory supplies it.
- Cost is reported beside correctness for every system compared.
