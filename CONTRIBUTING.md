# Contributing to RecoverX

## Getting Started

1. Fork the repository.
2. Create a feature branch from `main`.
3. Install in editable mode: `pip install -e ".[dev,test,static]"`
4. Make your changes.
5. Run tests: `pytest -q`
6. Run linters: `black --check src/ tests/ && isort --check-only src/ tests/ && flake8 src/ tests/ && mypy src/`

## Code Standards

- Line length: 100 characters
- Formatter: Black (default profile)
- Import order: isort with Black profile
- Type hints required for all public APIs
- Tests required for new functionality

## Branch Strategy

- `main` — stable, release-ready
- Feature branches from `main`, merged via PR
- Tags follow `vMAJOR.MINOR.PATCH`

## Pull Request Process

1. Ensure all tests pass and linting is clean.
2. Update CHANGELOG.md if applicable.
3. PRs require at least one review.

## Reporting Issues

Use the GitHub issue tracker. Include:
- Python version and OS
- Steps to reproduce
- Expected vs actual behavior
- Sample input if applicable
