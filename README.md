# Cognitive Robot Abstract Machine (CRAM)

Monorepo for the CRAM cognitive architecture. 

### Using Lightning Ai

1. go to https://lightning.ai/
2. create an account (USE free plan (CPU), you have to verify identity using phone number)
3. create a studio and wait till it is ready

## Installation

### Install missing linux libraries
```bash
sudo apt install graphviz-dev
```

### Clone the repo
```bash
git clone https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine.git -b knowledge_acquisition_course
cd cognitive_robot_abstract_machine
```

### Install using UV 

To install the whole repo we use uv (https://github.com/astral-sh/uv), first to install uv:

```bash 
curl -LsSf https://astral.sh/uv/install.sh | sh
```

then install packages:

```bash
uv sync --active
```

### Install KRROOD

```bash
pip install -e krrood/
```
