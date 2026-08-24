# Repository Guidelines

## Project Structure & Module Organization
The reusable library code lives in `src/logurich/`, with `core.py` handling stdlib logging integration, the `LogurichLogger` adapter and queue setup, `console.py` encapsulating Rich console helpers, `handler.py` providing custom Rich and console handlers, `context.py` holding bound and ambient context, `serialize.py` converting Rich renderables to structured JSON, `premarkup.py` implementing the premarkup tags, `user_input.py` offering prompt helpers, and `opt_click.py` exposing the optional Click decorator. Shared state lives in `struct.py`. Tests reside in `tests/` and mirror module names (`test_core.py`, `test_rich.py`, `test_mp.py`). Runnable walkthroughs live in `examples/` for quick validation of logging scenarios. Packaging metadata is in `pyproject.toml` alongside the dependency lockfile `uv.lock`.

## Environment Setup
Use uv to keep the development environment reproducible. From the repo root run:
- `uv sync --all-extras --all-groups` to create `.venv` and install runtime, optional and dev dependencies
- `source .venv/bin/activate` if you prefer an activated shell over `uv run`
Re-run the sync command whenever dependencies change. `dev` is a dependency group, not an extra, so `uv pip install -e ".[dev]"` does not work.

## Build, Test, and Development Commands
- `uv run pytest` executes the entire test suite with the active virtualenv.
- `uv run ruff check .` and `uv run ruff format --check .` mirror the lint gate.
- `uv run python examples/base.py` demonstrates the default logger output; adapt the script when validating new features.
- `uv run python examples/mp_example.py` stress-tests multi-process logging behaviour.
Publishing is orchestrated through the GitHub Actions workflows (`.github/workflows/`); pushing a `v*.*.*` tag builds and publishes to PyPI. Use `uv build` if you need a local wheel.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and `snake_case` for functions, module-level helpers, and test names. Classes such as `Formatter` stay in `PascalCase`. Prefer explicit imports from `logurich`'s public API via `__init__.py`, and include type hints for new parameters and return values. Pass context as plain call keywords (`logger.info("Login", user=ctx("alice"))`) and use `ctx(...)` for styled values; the 0.9 `extra={"context": ...}` and `extra={"renderables": ...}` payloads were removed and now raise. Keep log message strings formatted via stdlib logging style (e.g., `logger.info("Value %s", value)`).

## Testing Guidelines
Write tests with pytest and place them under `tests/`, naming files `test_<module>.py` and functions `test_<behaviour>`. Reuse shared fixtures from `tests/conftest.py`. Ensure new log formatting paths have representative assertions, and extend the example scripts when manual verification is useful. Run `uv run pytest` before opening a PR; aim to cover both the standard and rich rendering paths.

## Commit & Pull Request Guidelines
Commits follow Conventional Commit syntax (`type(scope): summary`) as seen in `git log`. Keep changes scoped and mention relevant modules in the scope. Pull requests must include a short summary, linked issues if applicable, and notes on testing (`uv run pytest`). Attach before/after screenshots or logs when changing console output. CI runs the test matrix across Python 3.9–3.14; wait for green builds before merging.
