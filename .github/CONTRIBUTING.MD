# Contributing to Nexios

Thank you for your interest in contributing to Nexios! We're excited to have you on board. This guide will help you get started with contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Setting Up the Development Environment](#setting-up-the-development-environment)
- [Development Workflow](#development-workflow)
  - [Branching Strategy](#branching-strategy)
  - [Code Style and Formatting](#code-style-and-formatting)
  - [Testing](#testing)
  - [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
  - [Pull Request Guidelines](#pull-request-guidelines)
  - [Commit Message Format](#commit-message-format)
- [Project Structure](#project-structure)
- [Reporting Issues](#reporting-issues)
- [Asking Questions](#asking-questions)

## Code of Conduct

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- [UV](https://github.com/astral-sh/uv) (recommended) or pip
- Node.js (for documentation development)
- Git

### Setting Up the Development Environment

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/nexios.git
   cd nexios
   ```
3. **Set up a virtual environment** and install dependencies:
   ```bash
   # Using UV (recommended)
   uv venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
   uv pip install -e ".[dev]"
   
   # Or using pip
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
   pip install -e ".[dev]"
   ```
4. **Install Node.js dependencies** for documentation:
   ```bash
   npm install
   ```


## Development Workflow

### Branching Strategy

- `main` - The main branch. All production-ready code goes here.
- `develop` - The development branch. All feature branches should be merged here first.
- `feature/` - For new features.
- `bugfix/` - For bug fixes.
- `docs/` - For documentation improvements.

### Code Style and Formatting

Nexios follows strict code style guidelines. We use:

- **Black** for code formatting
- **isort** for import sorting
- **Ruff** for linting

Before committing, run:

```bash
black .
isort .
ruff check . --fix
```

### Testing

We use `pytest` and `tox` for testing. To run the test suite:

```bash
# Run tests with pytest directly
pytest

# Or use tox to test across multiple Python versions
tox
```

For test coverage:

```bash
coverage run -m pytest
coverage report -m
```

### Documentation

Documentation is built using VitePress. To work on the documentation:

1. Start the development server:
   ```bash
   npm run docs:dev
   ```
   This will start a local development server at `http://localhost:5173`

2. To build the documentation for production:
   ```bash
   npm run docs:build
   ```

3. To preview the production build locally:
   ```bash
   npm run docs:preview
   ```

## Submitting Changes

### Pull Request Guidelines

1. Create a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit them following the [commit message format](#commit-message-format).

3. Push your branch and create a Pull Request (PR) to the `develop` branch.

4. Ensure all tests pass and there are no linting errors.

5. Request a review from one of the maintainers.

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Example:
```
feat(router): add support for dynamic route parameters

- Added support for path parameters in route definitions
- Updated router to handle dynamic segments
- Added relevant tests
```

## Reporting Issues

If you find a bug or have a feature request, please [open an issue](https://github.com/nexios-labs/nexios/issues/new/choose). Be sure to include:

- A clear title and description
- Steps to reproduce the issue
- Expected vs. actual behavior
- Environment details (Python version, OS, etc.)
- Any relevant logs or error messages

## Asking Questions

For questions and discussions, please:

1. Check the [documentation](https://nexios-labs.github.io/nexios/)
2. Search the [existing issues](https://github.com/nexios-labs/nexios/issues)
3. If you still can't find an answer, open a new discussion or issue

## Development Tips

- **Using UV**: Nexios recommends using UV for faster dependency management. After installing UV, you can use it as a drop-in replacement for pip:
  ```bash
  uv pip install -e ".[dev]"
  ```

- **Running Tests with Tox**: To ensure compatibility across Python versions, use tox:
  ```bash
  # Run tests on all configured Python versions
  tox
  
  # Run tests for a specific Python version
  tox -e py39  # For Python 3.9
  ```

- **Documentation Development**: When working on documentation, the VitePress dev server provides hot-reloading. Just run `npm run docs:dev` and start editing the markdown files in the `docs` directory.

- **Pre-commit Hooks**: The project includes pre-commit hooks that automatically format and check your code. Install them with `pre-commit install`.

---

Thank you for contributing to Nexios! Your help makes the project better for everyone. 
