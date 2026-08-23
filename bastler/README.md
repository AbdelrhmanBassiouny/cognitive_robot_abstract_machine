# bastler

The workflow tooling for this repository: the Python behind the stacked-pull-request
tooling, the plan dashboards, the personal-notes hooks and the upstream review reader.

The name is the German word for someone who builds things themselves, and shares its
first letters with the surname of the person who wrote it, Bassiouny.

## Importing it

`bastler` is a plain top-level directory on the repository root, so it imports from there
with no installation step - which is what a cloud session running on a fresh clone with
no `pip` step needs.

```python
from bastler.stack import load_configuration
```

The `pyproject.toml` beside this file is for installing it somewhere that is not such a
checkout:

```bash
pip install ./bastler                # the modules that need nothing but the standard library
pip install './bastler[rendering]'   # plus the dashboard build's Jinja2/markdown/nh3
```

## Running it

Every entry point is run as a module rather than by its file path:

```bash
python3 -m bastler.stack configuration
python3 -m bastler.maintenance run-report --json
python3 -m bastler.build_dashboard --help
```

By path, the interpreter puts *this* directory on `sys.path` in place of the repository
root, and a module's imports of its siblings stop resolving. The shell entry points under
`.claude/hooks/` and the skills that call them all use `python3 -m "${SOME_MODULE}"`, with
the module named once in `.claude/hooks/resolve-personal-notes-config.sh`.

## What needs what installed

`bastler/package_layout.py` declares, per module, how much of the dependency stack it
reaches. Two things read it: `pip install -r bastler/requirements.txt` installs what the
top tier needs, and `test/bastler_test/test_package_contract.py` checks each module really
does import within the tier it claims.

The point is not that any caller is forbidden to install something - `check-setup.sh`
reports a missing requirement and `/setup-personal-notes` installs it. It is that a caller
can tell, without running anything, which entry points work on a checkout where nothing
has been installed yet and which need the rendering extra first.

## What stays outside the package

`SKILL.md` files, `settings.json`, the bash entry points under `.claude/hooks/` and the
plan-dashboard `example/` all stay under `.claude/`, because Claude Code and its readers
find them by path.
