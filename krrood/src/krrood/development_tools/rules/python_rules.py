"""
The rules for any Python repository.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import PythonRule, RuleCatalogue, RuleSection


class PythonRules(RuleCatalogue):
    """
    The rules for any Python repository, one member per rule.
    """

    LEAVE_UNTOUCHED_CODE_ALONE = PythonRule(
        RuleSection.APPLYING_THESE_RULES,
        (
            "Existing code that breaks these rules stays as it is unless a change "
            "touches it or the user asks for the cleanup. When you modify a function "
            "or class, bring that function or class in line with these rules as part "
            "of the change, and leave code the change does not otherwise modify alone. "
            "If the cleanup renames a method and so changes the API, ask the user "
            "first"
        ),
    )

    ASK_BEFORE_DEPARTING_FROM_A_RULE = PythonRule(
        RuleSection.APPLYING_THESE_RULES,
        (
            "When a rule seems wrong for the case at hand - a failing test that is "
            "itself wrong, an exception that has to be caught, a value that genuinely "
            "has to live at module level - ask the user before departing from it; "
            "never decide the exception on your own"
        ),
    )

    ASK_INSTEAD_OF_INVENTING_REASONS = PythonRule(
        RuleSection.ASK_THE_DEVELOPER,
        (
            "When you are unsure why something was done or why a specific number was "
            "chosen, ask; never invent a reason and write it down as a comment"
        ),
    )

    ASK_ABOUT_TEST_ONLY_METHODS = PythonRule(
        RuleSection.ASK_THE_DEVELOPER,
        "When a method is never used outside of tests, ask whether it can be removed",
    )

    ASK_BEFORE_ADDING_DEPENDENCIES = PythonRule(
        RuleSection.ASK_THE_DEVELOPER,
        "Before adding a new dependency, ask",
    )

    WRITE_TESTS_WITH_PYTEST = PythonRule(
        RuleSection.WRITING_TESTS,
        (
            "Write tests with pytest: plain test functions or classes, pytest "
            "fixtures, `pytest.raises` and plain `assert`; never `unittest.TestCase` "
            "or its assertion methods"
        ),
    )

    REUSE_FIXTURES = PythonRule(
        RuleSection.WRITING_TESTS,
        "Reuse the existing fixtures in `conftest.py`",
    )

    WORK_TEST_DRIVEN = PythonRule(
        RuleSection.WRITING_TESTS,
        (
            "Work test-driven: prove a bug with a meaningful, failing test before "
            "fixing it. Every new feature and fix is covered by tests"
        ),
    )

    NEVER_MODIFY_A_FAILING_TEST = PythonRule(
        RuleSection.WRITING_TESTS,
        "When fixing a failing test, never modify the test itself",
    )

    NAME_TEST_CLASSES_AFTER_BEHAVIOUR = PythonRule(
        RuleSection.WRITING_TESTS,
        (
            "Name test classes, and the mimic classes tests use, after the pattern or "
            "behaviour they exercise, not after the external class they stand in for"
        ),
    )

    KEEP_SNIPPETS_IN_FILES = PythonRule(
        RuleSection.WRITING_TESTS,
        (
            "Keep code snippets in separate files of the correct type and import or "
            "read them into the test; never embed them as strings"
        ),
    )

    ASSERT_EXACT_EXPECTED_VALUES = PythonRule(
        RuleSection.ASSERTIONS,
        (
            "Assert equality to the expected value whenever it can be determined, "
            "never only a weaker check such as not-None or not-empty"
        ),
    )

    ASSERT_AGAINST_THE_DEFINITION = PythonRule(
        RuleSection.ASSERTIONS,
        (
            "Assert against the definition, not a retyped copy of it: the enum member, "
            "the `classproperty`, or the value from the fixture the code under test "
            "consumed. Where a type distinguishes the case - a distinct exception "
            "class, an enum member - assert the type instead of matching message text. "
            "A retyped literal keeps passing when the original changes"
        ),
    )

    TEST_ONE_BEHAVIOUR = PythonRule(
        RuleSection.ASSERTIONS,
        (
            "Each test checks the one behaviour it names and fails only for its own "
            "reason: assert exactly the values that behaviour determines, not "
            "incidental output such as the wording of an error message the test is not "
            "about. Where another test already asserts a value exactly, derive the "
            "expected value from the production code that computes it instead of "
            "hardcoding a second copy. Tests are independent of each other"
        ),
    )

    EVERY_TEST_RUNS_IN_CI = PythonRule(
        RuleSection.EXTERNAL_SERVICES_AND_CI,
        (
            "Every added test is part of the CI suite. A test that needs live external "
            "calls or credentials CI does not have is skipped there (or removed, if "
            "new) so it cannot break the pipeline"
        ),
    )

    APPROVE_CI_CREDENTIALS = PythonRule(
        RuleSection.EXTERNAL_SERVICES_AND_CI,
        (
            "A test that needs credentials in CI must be approved by the user and have "
            "those credentials available in CI; otherwise it is skipped there"
        ),
    )

    MOCK_EXTERNAL_APIS = PythonRule(
        RuleSection.EXTERNAL_SERVICES_AND_CI,
        "Mock external APIs; call one live only to download a dataset other tests need",
    )

    PAIR_LIVE_TESTS_WITH_MOCKED_ONES = PythonRule(
        RuleSection.EXTERNAL_SERVICES_AND_CI,
        (
            "A test that calls an external API live must have a skip condition so it "
            "does not run in CI, and must be paired with an equivalent mocked test "
            "that does"
        ),
    )

    RUN_TESTS_WITH_PYTEST = PythonRule(
        RuleSection.RUNNING_TESTS,
        "Run tests with pytest",
    )

    RUN_THE_SUITE_IN_PARTS = PythonRule(
        RuleSection.RUNNING_TESTS,
        (
            "Never run the whole test suite in one invocation: run one package or a "
            "few test directories at a time, and wait for each run to finish before "
            "starting the next"
        ),
    )

    CAP_TEST_MEMORY = PythonRule(
        RuleSection.RUNNING_TESTS,
        (
            "Make sure a test run can never exhaust the machine's working memory: "
            "check the free memory before starting, cap the run's memory so the run is "
            "killed rather than the machine, and account for other test runs already "
            "going on the same machine"
        ),
    )

    USE_DATACLASSES = PythonRule(
        RuleSection.CODE_STYLE,
        "Always use dataclasses",
    )

    DIVIDE_FILES_INTO_SECTIONS = PythonRule(
        RuleSection.CODE_STYLE,
        (
            "Divide every file, source and test, into sections with `# %% <short "
            "description>` headers (e.g. `# %% same-noun disambiguation`), never "
            "decorative box-drawing dividers"
        ),
    )

    GROUP_PRIMITIVES_INTO_DATACLASSES = PythonRule(
        RuleSection.CODE_STYLE,
        (
            "A group of primitives that travels together, or a return type that keeps "
            "being repeated, becomes a dataclass"
        ),
    )

    NEVER_DUPLICATE_CODE = PythonRule(
        RuleSection.CODE_STYLE,
        (
            "Never duplicate code. Never put methods in a catch-all module such as "
            "`utils.py`; move them onto the class that owns the behaviour"
        ),
    )

    ACCESS_ATTRIBUTES_DIRECTLY = PythonRule(
        RuleSection.CODE_STYLE,
        (
            "Access attributes with `.`, never with `getattr`, and never wrap "
            "attribute access in try-except"
        ),
    )

    NO_MUTABLE_DEFAULT_ARGUMENTS = PythonRule(
        RuleSection.CODE_STYLE,
        "Never use mutable objects as default arguments",
    )

    NEVER_REIMPLEMENT = PythonRule(
        RuleSection.CODE_STYLE,
        (
            "Never reimplement what the codebase or an existing dependency already "
            "provides. When searching for it, never cut off the output of grep or "
            "other searches; narrow the search instead"
        ),
    )

    CORRECT_SIMPLE_DESCRIPTIVE_NAMES = PythonRule(
        RuleSection.NAMING,
        (
            "Names are technically correct, simple and descriptive, in that order. An "
            "inaccurate name is worse than a vague one, because a reader who trusts it "
            "stops reading"
        ),
    )

    NAMES_READ_ON_THEIR_OWN = PythonRule(
        RuleSection.NAMING,
        (
            "A name stays correct and understandable when read on its own, without its "
            "class or a keyword argument next to it - after `value = "
            "instance.attribute`, in a log line, in a traceback, or when passed on "
            "positionally. A `Pipe` field `size` says nothing once it leaves the "
            "class; `inner_diameter` does. A generic word that would fit anything "
            "never passes this test"
        ),
    )

    USE_PLAIN_WORDS = PythonRule(
        RuleSection.NAMING,
        (
            "Use the plain word every reader already knows. Use a specialist, "
            "metaphorical or in-house term only where it is genuinely the precise "
            "word, never as shorthand between the people who were in the discussion"
        ),
    )

    USE_THE_DOMAIN_WORD = PythonRule(
        RuleSection.NAMING,
        (
            "Where the domain or file format already has a word for something, use "
            "that word"
        ),
    )

    NEVER_ABBREVIATE = PythonRule(
        RuleSection.NAMING,
        "Never abbreviate an identifier",
    )

    NAME_WHAT_NOT_HOW = PythonRule(
        RuleSection.NAMING,
        (
            "A name says *what* a thing is or does - never *how* it does it, *when* it "
            "runs, or the layer or mechanism it is built on. Keep it short"
        ),
    )

    NO_FOREIGN_VOCABULARY = PythonRule(
        RuleSection.NAMING,
        (
            "A name whose meaning has to be looked up elsewhere is wrong. Never adopt "
            "another system's vocabulary as an identifier of ours: name the thing for "
            "what it is here, and explain a foreign shape in the docstring"
        ),
    )

    VERB_AND_NOUN_PHRASES = PythonRule(
        RuleSection.NAMING,
        (
            "Methods are verb phrases for what they do; classes and attributes are "
            "noun phrases for what they are. Name a field for its subject, not for the "
            "shape of its value"
        ),
    )

    ONE_NAME_PER_OPERATION = PythonRule(
        RuleSection.NAMING,
        (
            "One operation has one name throughout a module. Where callers depend on "
            "that name, declare it in a base class instead of leaving it a convention "
            "each class is trusted to follow"
        ),
    )

    NAME_ENUM_MEMBERS_FOR_THEIR_SITUATION = PythonRule(
        RuleSection.NAMING,
        (
            "Name an enum member for the situation it means, not for the function it "
            "dispatches to or the text it renders"
        ),
    )

    NO_REPEATED_WORDS = PythonRule(
        RuleSection.NAMING,
        (
            "Never repeat the enclosing type's name in its members, or the same word "
            "twice within one name"
        ),
    )

    NEVER_SHADOW_BOUND_NAMES = PythonRule(
        RuleSection.NAMING,
        (
            "Never take an identifier the language or something in scope already "
            "binds: `Enum` reserves `name`, a parameter `field` shadows "
            "`dataclasses.field`, a field shadows a method of the same name. These "
            "fail at runtime or silently, not at import"
        ),
    )

    FINISH_RENAMES = PythonRule(
        RuleSection.NAMING,
        (
            "A rename is finished only when every reader of the old name, docstrings "
            "and comments included, uses the new one and the tests pass. A mechanical "
            "rename across a file is exactly where a method and a field converge on "
            "one name"
        ),
    )

    SUSPECT_VAGUE_CODE = PythonRule(
        RuleSection.NAMING,
        (
            "When no honest specific name exists, suspect the code, not your "
            "vocabulary: a thing that can only be described vaguely usually has no "
            "single subject (a container for whatever its caller passed, a function "
            "doing two jobs). Remove it instead of hunting for a better word"
        ),
    )

    ABSOLUTE_IMPORTS = PythonRule(
        RuleSection.IMPORTS,
        (
            "Imports are absolute. Exception: a test imports another test module (a "
            "shared mimic or fixture from the test datasets) relatively"
        ),
    )

    IMPORTS_AT_THE_TOP = PythonRule(
        RuleSection.IMPORTS,
        (
            "Imports go at the top of the module; fix an import cycle by restructuring "
            "the modules, never with a local import"
        ),
    )

    GUARD_TYPE_ONLY_IMPORTS = PythonRule(
        RuleSection.IMPORTS,
        "Guard type-only imports with `TYPE_CHECKING`",
    )

    OBJECT_ORIENTED_AND_SOLID = PythonRule(
        RuleSection.DESIGN_PRINCIPLES,
        "Use strictly object-oriented design and always apply the SOLID principles:",
        (
            (
                "Single Responsibility: each class and method does one thing. If a "
                "method has cyclomatic complexity in the hundreds, refactor"
            ),
            "Open/Closed: open for extension, closed for modification",
            (
                "Liskov Substitution: subtypes are substitutable for their base types "
                "without breaking behaviour"
            ),
            (
                "Interface Segregation: many small interfaces over one large one. An "
                "interface is an explicit superclass or mixin, never a `Protocol`"
            ),
            (
                "Dependency Inversion: depend on abstractions, not concrete "
                "implementations"
            ),
        ),
    )

    MODULAR_AND_DECOUPLED = PythonRule(
        RuleSection.DESIGN_PRINCIPLES,
        "Keep code modular and decoupled",
    )

    NO_YAGNI = PythonRule(
        RuleSection.DESIGN_PRINCIPLES,
        "Eliminate YAGNI smells",
    )

    HARD_TO_MISUSE_INTERFACES = PythonRule(
        RuleSection.DESIGN_PRINCIPLES,
        "Make interfaces hard to misuse",
    )

    EXTRACT_METHODS_THAT_EARN_THEIR_ABSTRACTION = PythonRule(
        RuleSection.METHODS,
        (
            "Every method hides what actually runs from the reader, so extract one "
            "only when its abstraction is worth more than reading the executed code in "
            "place"
        ),
    )

    ONE_LEVEL_OF_ABSTRACTION = PythonRule(
        RuleSection.METHODS,
        (
            "Keep every statement in a method on the same level of abstraction: a "
            "method either strings together named steps or carries out one step's "
            "detail, never both"
        ),
    )

    NO_FORWARDING_METHODS = PythonRule(
        RuleSection.METHODS,
        (
            "Never write a method that only forwards to or renames another call. A "
            "one-line method is allowed only when it implements an abstract method or "
            "a `classproperty`, caches its result, or removes duplication - and in the "
            "last case, first try to abstract the duplicated code itself"
        ),
    )

    INLINE_SINGLE_CALLER_METHODS = PythonRule(
        RuleSection.METHODS,
        (
            "A method with a single caller must earn its place under these rules; "
            "otherwise inline it"
        ),
    )

    GUARD_CLAUSES = PythonRule(
        RuleSection.METHODS,
        (
            "Reduce nesting and complexity with guard clauses: handle alternative "
            "outputs first by inverting conditions and returning early, so the main "
            "branch holds the main output and the biggest compute. A single level of "
            "abstraction never justifies deep nesting; split the method instead"
        ),
    )

    NEVER_TRY_EXCEPT = PythonRule(
        RuleSection.ERRORS,
        (
            "Never use try-except; a program in an illegal state raises an appropriate "
            "exception"
        ),
    )

    DATACLASS_EXCEPTIONS = PythonRule(
        RuleSection.ERRORS,
        "Create meaningful custom exceptions as dataclasses",
    )

    EXCEPTIONS_IN_THE_CLOSEST_MODULE = PythonRule(
        RuleSection.ERRORS,
        "Put each exception in the `exceptions.py` closest to the code that raises it:",
        (
            (
                "An exception raised only within one subpackage goes in that "
                "subpackage's `exceptions.py`; create the file if the subpackage has "
                "none"
            ),
            (
                "An exception raised across several subpackages goes in the "
                "`exceptions.py` of their nearest common package"
            ),
        ),
    )

    NO_ASSERT_OUTSIDE_TESTS = PythonRule(
        RuleSection.ERRORS,
        (
            "Never use `assert` outside tests: Python drops it when run with `-O`, so "
            "the check silently disappears. Raise a custom exception instead"
        ),
    )

    NO_GLOBAL_OR_CLASS_VARIABLES = PythonRule(
        RuleSection.CONSTANTS_AND_CLASS_LEVEL_VALUES,
        "Never use global variables, module-level constants or `ClassVar`. Instead:",
        (
            "A fixed set of related values is a module-level enum",
            (
                "A default a caller may want to change is a parameter of the method "
                "that uses it if only that method does, otherwise a dataclass field "
                "with that default. For example, a `Heater` takes `target_temperature: "
                "float = 20.0` as a field instead of declaring "
                "`DEFAULT_TARGET_TEMPERATURE: ClassVar[float] = 20.0`"
            ),
            "A constant that belongs to a class is a `classproperty`",
            (
                "`ClassVar` is allowed only for state that explicitly has to be shared "
                "and mutable across every instance of a class. This almost never "
                "applies"
            ),
        ),
    )

    PREFER_STRUCTURED_DATA = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "Structured data is the default over bare strings, hardcoded values and "
            "meaningless numbers: reach for the structured form first and justify the "
            "literal, never the other way round"
        ),
    )

    NAMED_STRINGS_ARE_ENUMS = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "A string that names a fixed thing - a payload key, a state, a label, a "
            "filename, an environment variable, a command flag, a status - is a "
            "`StrEnum` member. A value spelled in two places has no single source to "
            "rename, and nothing fails when the two drift apart"
        ),
    )

    TYPED_ENUM_VALUES = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "When the values are more than text - paths, numbers - give the enum "
            "values of that type, mixing the type in (`IntEnum`, `StrEnum`)"
        ),
    )

    NO_MAGIC_NUMBERS = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "A magic number becomes an enum member, a field default or a "
            "`classproperty`; a bare literal that carries meaning is unreadable where "
            "it is used and unsearchable everywhere else"
        ),
    )

    MIRROR_FOREIGN_DATA = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "Data whose shape someone else controls - an API response, a configuration "
            "file - is mirrored in dataclasses and parsed by a `from_json` "
            "classmethod, so the field names and the access path into the payload are "
            "written once"
        ),
    )

    NO_POSITIONAL_TUPLES = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "A tuple whose positions carry meaning becomes a dataclass, or an enum "
            "when the positions are a fixed set of alternatives rather than fields"
        ),
    )

    LONG_LITERALS_IN_FILES = PythonRule(
        RuleSection.STRUCTURED_DATA,
        (
            "A long literal document - a query, a template, a schema - lives in a file "
            "of its own type and is read in, never embedded as a string"
        ),
    )

    ANNOTATE_EVERYTHING = PythonRule(
        RuleSection.TYPE_HINTS,
        (
            "Every parameter and return value has an accurate type hint, `Any` and `-> "
            "None` included"
        ),
    )

    BUILTIN_GENERICS = PythonRule(
        RuleSection.TYPE_HINTS,
        (
            "Use builtin generics and `X | None` (`list[int]`, `Pose | None`), never "
            "`typing.List`, `Dict`, `Optional` or `Union`; import every other typing "
            "construct from `typing_extensions`, never from `typing`"
        ),
    )

    FUTURE_ANNOTATIONS = PythonRule(
        RuleSection.TYPE_HINTS,
        "Use `from __future__ import annotations` instead of wrapping types in strings",
    )

    BOUND_GENERIC_PARAMETERS = PythonRule(
        RuleSection.TYPE_HINTS,
        (
            "When each class in a family declares the type it handles, carry that type "
            "as a bound generic parameter, not a `ClassVar`, so it is part of the "
            "signature and cannot disagree with a separate attribute: bind it in each "
            "member (`class MemberOfFamily(Family[ConcreteType])`)"
        ),
    )

    DOCUMENT_EVERYTHING = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "Every class and method has meaningful, non-trivial documentation in "
            "reStructuredText. Every field has its own docstring directly below it, "
            "not a description in the class docstring"
        ),
    )

    OVERRIDES_INHERIT_DOCSTRINGS = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "An override that keeps its base contract has no docstring and inherits "
            "the base one. One that changes the contract documents only the difference "
            "and references the overridden method with `:meth:`"
        ),
    )

    DOCSTRINGS_STATE_THE_CONTRACT = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "A docstring states what the code does and its contract, short and to the "
            "point. It never contains:"
        ),
        (
            "how the code does it",
            (
                "the ways a caller can supply a value (for example, that it may also "
                "be given as a query instead of a concrete object)"
            ),
            (
                'the current callers or consumers ("used by X and Y") - that goes '
                "stale and reads as exhaustive"
            ),
            (
                "justification of design decisions, comparison with rejected or "
                "hypothetical designs, or review and implementation history"
            ),
            "type information - the type hints carry it",
        ),
    )

    SHORT_COMMENTS = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "Keep docstrings and comments short and never write walls of text. "
            "Comments are meaningful and DRY; remove comments that restate the code"
        ),
    )

    SPHINX_ROLES = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "Reference code with Sphinx roles (`:func:`, `:class:`, `:attr:`, "
            "`:meth:`), never with plain backticks, and use directives such as `.. "
            "note::` and `.. warning::` for notes and warnings"
        ),
    )

    NO_CAPITALS_FOR_EMPHASIS = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "Never use all-caps words for emphasis in docstrings or comments; use RST "
            "emphasis (`*word*`). Genuine identifiers, acronyms and enum/constant "
            "names (`UUID`, `WHERE`, `Definiteness.DEFINITE`) are exempt"
        ),
    )

    FORMAT_WITH_THE_HOOK = PythonRule(
        RuleSection.DOCUMENTATION,
        (
            "Always format modified Python files with ruff followed by docformatter, "
            "through the repository's pre-commit hook"
        ),
    )

    AUTHOR_AS_THE_HUMAN = PythonRule(
        RuleSection.VERSION_CONTROL,
        (
            "Author commits as the human user running the tool, with their own "
            "configured git `user.name` and `user.email`. Never author or amend a "
            "commit as an assistant, and never credit one as author or co-author: no "
            "`Co-Authored-By:` trailer for an assistant, no `noreply@anthropic.com` or "
            "similar as author or committer"
        ),
    )

    ACKNOWLEDGE_ASSISTANCE_PLAINLY = PythonRule(
        RuleSection.VERSION_CONTROL,
        (
            "A short plain line in the commit message body acknowledging assistant "
            "help, such as `Made with AI assistance`, is encouraged. Never name the "
            "model or the AI service"
        ),
    )

    RULES_APPLY_TO_EVERYONE = PythonRule(
        RuleSection.VERSION_CONTROL,
        "These rules apply to every contributor and every tool",
    )

    NEVER_PUSH_UPSTREAM = PythonRule(
        RuleSection.VERSION_CONTROL,
        (
            "When you work in a fork, never push to the upstream repository - no "
            "branch, no tag, whatever the reason. Push only to the fork; work reaches "
            "upstream only through a pull request opened from the fork. Before any "
            "push, read the full, untruncated `git remote -v` output and confirm the "
            "target remote is the fork"
        ),
    )

    LEAVE_UPSTREAM_PULL_REQUESTS_ALONE = PythonRule(
        RuleSection.VERSION_CONTROL,
        (
            "Never comment on or modify pull requests on the upstream repository "
            "unless the user has explicitly allowed it - through existing personal "
            "notes or instructions, or by accepting when you ask"
        ),
    )

    USE_THE_PROJECT_INTERPRETER = PythonRule(
        RuleSection.MISC,
        "Always use the project's configured Python interpreter for tests and commands",
    )

    SUGGEST_MORE_POWERFUL_PACKAGES = PythonRule(
        RuleSection.MISC,
        "If a package could be replaced by a more powerful one, tell us",
    )
