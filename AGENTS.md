# Repository Guidelines

## Project Structure & Module Organization
The reusable library code lives in `logurich/`, with `core.py` handling logging integration, `console.py` encapsulating rich rendering helpers, and `handler.py` providing custom Loguru handlers. Shared configuration defaults live in `conf.py`. Tests reside in `tests/` and mirror module names (`test_core.py`, `test_rich.py`, `test_mp.py`). Runnable walkthroughs live in `examples/` for quick validation of logging scenarios. Packaging metadata is in `pyproject.toml` alongside the dependency lockfile `uv.lock`.

## Environment Setup
Use uv to keep the development environment reproducible. From the repo root run:
- `uv venv` to create `.venv`
- `source .venv/bin/activate`
- `uv pip install -e ".[dev]"` to install runtime and pytest extras
Re-run the last command whenever dependencies change.

## Build, Test, and Development Commands
- `uv run pytest` executes the entire test suite with the active virtualenv.
- `uv run python examples/base.py` demonstrates the default logger output; adapt the script when validating new features.
- `uv run python examples/mp_example.py` stress-tests multi-process logging behaviour.
Publishing is orchestrated through the GitHub Actions workflows (`.github/workflows/`); manual builds use `python -m build` if you need a local wheel.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and `snake_case` for functions, module-level helpers, and test names. Classes such as `Formatter` stay in `PascalCase`. Prefer explicit imports from `logurich`'s public API via `__init__.py`, and include type hints for new parameters and return values. Use `ctx(...)` when binding contextual extras instead of the legacy `context__` key pattern. Keep log message strings formatted via Loguru's structured style (e.g., `logger.info("Value {}", value)`).

## Testing Guidelines
Write tests with pytest and place them under `tests/`, naming files `test_<module>.py` and functions `test_<behaviour>`. Reuse shared fixtures from `tests/conftest.py`. Ensure new log formatting paths have representative assertions, and extend the example scripts when manual verification is useful. Run `uv run pytest` before opening a PR; aim to cover both the standard and rich rendering paths.

## Commit & Pull Request Guidelines
Commits follow Conventional Commit syntax (`type(scope): summary`) as seen in `git log`. Keep changes scoped and mention relevant modules in the scope. Pull requests must include a short summary, linked issues if applicable, and notes on testing (`uv run pytest`). Attach before/after screenshots or logs when changing console output. CI runs the test matrix across Python 3.10–3.13; wait for green builds before merging.
