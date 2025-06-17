# Contributing Guide

Thank you for considering contributing to **Digitation V3**!

## Development workflow

1. Fork the repository and create a topic branch off **`main`**.
2. Set up a local dev environment:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e .
   pre-commit install
   ```

3. Make your changes, ensuring:

   * `ruff` reports **no errors** (`ruff .`)
   * `black` reformats code (`black .`)
   * `pytest` passes (`pytest`)

4. Commit using **conventional commits** (e.g. `feat: add ghost overlay option`).
5. Push and open a Pull Request (PR).
6. One of the maintainers will review, request changes, or merge.

## Code style

* **Black** (120‑char line length) is the source of truth.
* **Ruff** enforces the majority of PEP 8 & bug‑bear checks.
* Type hints are encouraged.

## Commit style

Follow the [Conventional Commits](https://www.conventionalcommits.org) spec.

## License

By contributing you agree that your work will be licensed under the MIT License.
