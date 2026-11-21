# krrood static generic bindings
- The runtime and the static reader share one binding computation; neither re-implements it.
- Nothing in this plan imports, checks out or installs the code under review, and nothing generates stubs or binds a derived parameter a second time by hand.
- basstler's triage knows no krrood pattern: krrood plugs in through the triage's extension point.
