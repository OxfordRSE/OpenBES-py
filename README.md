# OpenBES-py

[![Unittest](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/unittest.yml/badge.svg)](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/unittest.yml)
[![.github/workflows/package_test.yml](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/package_test.yml/badge.svg)](https://github.com/OxfordRSE/OpenBES-py/actions/workflows/package_test.yml)

OpenBES-py is an open-source building energy simulation tool written in Python. It is designed to provide transparent, reproducible, and extensible energy modeling for buildings, supporting research, education, and practical analysis.

## Features

- **Modular simulation engine**: Each energy category is implemented as a separate module for clarity and extensibility.
- **Comprehensive test suite**: All core modules are covered by unit and integration tests.
- **Standardized test cases**: Planned integration with ASHRAE Standard 140 test cases (see `cases_ashrae_std140_...` directory).
- **Modern dependency management**: Uses [UV](https://github.com/astral-sh/uv) for fast, reliable Python environment setup (`uv.lock` included).

## Current Status

The following simulation categories are implemented and tested:
- [x] Others
- [x] Building standby
- [x] Lighting
- [x] Hot water
- [x] Ventilation

The following categories are planned and under development:
- [ ] Cooling
- [ ] Heating

## Installation

1. Install [UV](https://github.com/astral-sh/uv) if you do not have it: `pip install uv`

2. Set up a virtual environment (recommended): `uv venv`

3. Install dependencies: `uv sync`

4. Run tests to verify installation: `uv run python -m unittest discover -s tests`

## License

The license for this project is under consideration. 
