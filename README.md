# OpenBES-py

[![Unittest](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/unittest.yml/badge.svg)](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/unittest.yml)
[![ASHRAE 140 Suite](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/test_cases.yml/badge.svg)](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/test_cases.yml)
[![.github/workflows/package_test.yml](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/package_test.yml/badge.svg)](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/package_test.yml)
![PyPI - Downloads](https://img.shields.io/pypi/dm/openBES)
![PyPI - Version](https://img.shields.io/pypi/v/openBES)

OpenBES-py is an open-source building energy simulation tool written in Python. It is designed to provide transparent, reproducible, and extensible energy modeling for buildings, supporting research, education, and practical analysis.

## Features

- **Modular simulation engine**: Each energy category is implemented as a separate module for clarity and extensibility.
- **Comprehensive test suite**: All core modules are covered by unit and integration tests.
- **Standardized test cases**: Planned integration with ASHRAE Standard 140 test cases (see `cases_ashrae_std140_...` directory).
- **Modern dependency management**: Uses [UV](https://github.com/astral-sh/uv) for fast, reliable Python environment setup (`uv.lock` included).

## Installation

You can install OpenBES-py via pip:

```bash
pip install openBES[jit]
```

This will install the package along with optional JIT compilation support for improved performance (via Numba). 
If you do not need JIT support, you can install without the `[jit]` extra.

<details>
<summary>
<h3>Why doesn't the package default to JIT support?</h3>
</summary>
A major use-case for the package is in a web-based environment, using Pyodide. 
Pyodide does not currently support Numba, so to keep the package lightweight and compatible with such environments, JIT support is made optional.

At a later date we might custom-compile the project to WASM with Numba support, but for now this is not available.
</details>

## Usage

Here is a simple example of how to use OpenBES-py to run a building energy simulation:

```python
from openBES import BuildingSimulation, OpenBESSpecification

spec_file = "path/to/specification.toml"
spec = OpenBESSpecification.from_toml(spec_file)
simulation = BuildingSimulation(spec)  # the simulation is run upon initialization
total_annual_energy_used = simulation.energy_use.sum().sum()  # collaspse energy use DataFrame -> annual energy in kWh
```

## Development

1. Install [UV](https://github.com/astral-sh/uv) if you do not have it: `pip install uv`

2. Set up a virtual environment (recommended): `uv venv`

3. Install editable package: `uv pip install -e .[dev]`

4. Install dependencies: `uv sync`

5. Run tests to verify installation: `uv run python -m unittest discover -s tests`

## License

The license for this project is under consideration. 

## Credits

We use Pandas for data manipulation and NumPy for numerical calculations.

We use PVLib.iotools for reading EPW (energy plus weather) files.

    Jensen, A., Anderson, K., Holmgren, W., Mikofski, M., Hansen, C., Boeman, L., Loonen, R. “pvlib iotools — Open-source Python functions for seamless access to solar irradiance data.” Solar Energy, 266, 112092, (2023). DOI: 10.1016/j.solener.2023.112092.

