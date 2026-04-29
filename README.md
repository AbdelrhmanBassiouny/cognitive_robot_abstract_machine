# Cognitive Robot Abstract Machine (CRAM)

Monorepo for the CRAM cognitive architecture. 

### Using Lightning Ai

1. go to https://lightning.ai/
2. create an account (USE free plan (CPU), you have to verify identity using a phone number)
3. create a studio (USE Python and the IDE option (VSCode)) and wait till it is ready

## Installation

### 1. Install missing linux libraries
```bash
sudo apt install graphviz-dev
```

### 2. Clone the repo
```bash
git clone https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine.git -b knowledge_acquisition_course
cd cognitive_robot_abstract_machine
```

### 3. Install using UV 

To install the whole repo we use uv (https://github.com/astral-sh/uv), first to install uv:

```bash 
curl -LsSf https://astral.sh/uv/install.sh | sh
```

then install packages:

```bash
uv sync --active
```

### 4. Install KRROOD

```bash
pip install -e krrood/
```

### 5. Install requirements for Exercises

```bash
cd Exercises
pip install -r requirements.txt
```

### 6. Open Exercises

The exercises are in the `Exercises` folder in the root of the repository.
Exercise 1 (Algebra using EQL):
https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/blob/knowledge_acquisition_course/Exercises/ex_01_algebra_eql.ipynb

Exercise 2 (Uncertainty):
https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/blob/knowledge_acquisition_course/Exercises/ex_02_uncertainty.ipynb
