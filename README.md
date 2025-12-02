# Cognitive Robot Abstract Machine (CRAM)

Monorepo for the CRAM cognitive architecture. 

## Installation 

To install the CRAM architecture, follow these steps:

Setup the Python venvironment:

```bash
python3 -m venv cram-env
source cram-env/bin/activate
```

We use poetry to manage dependencies. Install poetry if you haven't already:

```bash
pip install poetry
``` 

Install the CRAM package along with its dependencies:

```bash
cd cognitive_robot_abstract_machine
poetry install
```

## Contribution

Before committing any changes, please navigate into the project root and install pre-commit hooks:

```bash
sudo apt install pre-commit
pre-commit install
```

### Code of Conduct

(TBD)