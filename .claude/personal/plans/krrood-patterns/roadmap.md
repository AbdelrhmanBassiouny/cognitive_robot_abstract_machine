# krrood patterns: standing rules

- A pattern lives in `krrood.patterns`, imports no other workspace package, and lands with krrood-internal mimics in `test/krrood_test/dataset` before any site migrates to it.
- Each site migration is its own item and pull request, off `main`, after the pattern it adopts has landed.
