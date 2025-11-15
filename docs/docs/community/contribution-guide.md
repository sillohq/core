---
title: Contribution Guide
icon: contribution
description: >
    Contribution Guide
head:
  - - meta
    - property: og:title
      content: Contribution Guide
    - property: og:description
      content: Contribution Guide
---

If you have any comments or suggestions, please report an [issue](https://github.com/nexios-labs/nexios/issues),
or make changes and submit a [pull request](https://github.com/nexios-labs/nexios/pulls).

## Quick Start

1. Fork the repository: `https://github.com/nexios-labs/nexios`
2. Clone your fork: `git clone https://github.com/nexios-labs/nexios.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Make changes and commit: `git commit -m "feat: add your feature"`
5. Push to your fork: `git push origin feature/your-feature`
6. Open a Pull Request to the main repository

## Reporting New Issues

- Please specify what kind of issue it is.
- Before you report an issue, please search for related issues to avoid duplicates.
- Explain your purpose clearly in tags (see **Useful Tags**), title, or content.

### Issue Guidelines

1. **Title**: Clear and descriptive (e.g., "Fix: API returns 500 when X")
2. **Description**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages or logs (use code blocks)
   - Environment details:
     ```bash
     OS: [e.g., Windows 11, macOS 13, Ubuntu 22.04]
     Python: [e.g., 3.9.7]
     Nexios Version: [e.g., 1.0.0]
     ```
3. **Screenshots/Videos**: For UI-related issues

## Useful Tags

We use tags to categorize issues and pull requests. Tags are divided into two groups:

### Type
- `bug`: Confirmed bug reports
- `feature`: New feature requests
- `documentation`: Documentation improvements
- `performance`: Performance-related issues
- `support`: Help needed from maintainers

### Scope
- `core:xx`: Core framework issues (e.g., `core:loader`)
- `plugin:xx`: Plugin-specific issues
- `deps:xx`: Dependency-related issues
- `test`: Test-related issues
- `chore`: Maintenance tasks

### Special Labels
- `good first issue`: Great for new contributors
- `help wanted`: Extra attention needed
- `priority:high`: High priority issues
- `status:blocked`: Blocked on other work

## Documentation

All features must be submitted with documentation. The documentation should:

- Clearly explain what the feature is, why it's useful, and how it works
- Include step-by-step instructions when applicable
- Provide code examples with proper syntax highlighting
- Include links to related documentation
- Be kept up-to-date with code changes

### Documentation Structure

```
docs/
├── guide/           # Tutorials and how-to guides
├── intro/           # Introduction and getting started
├── community/       # Community resources
└── .vitepress/      # Vitepress configuration
```

### Making Documentation Changes

1. **Small Fixes**
   - Fix typos, broken links, or outdated information
   - Use the "Edit this page" link at the bottom of each doc

2. **New Content**
   - Follow our [Documentation Style Guide](/community/docs-style-guide)
   - Add new Markdown files in the appropriate directory
   - Update `config.mjs` to include the new page in the sidebar

3. **Running Locally**
   ```bash
   # Install dependencies
   npm install
   
   # Start development server
   npm run docs:dev
   
   # Build for production
   npm run docs:build
   ```

### Code Examples

Include clear, concise code examples that demonstrate the feature or fix. For example:

```python
# Example: Initializing the Nexios client
from nexios import Nexios

# Create a new client instance
client = Nexios(api_key="your-api-key")

# Make API requests
response = client.get("/users")
print(response.json())
```
   
## Submitting Code

### Pull Request Guide

1. **Before Submitting**
   - Run tests: `npm test`
   - Ensure your code follows our style guide
   - Update documentation if needed
   - Add tests for new features

2. **Creating a Pull Request**
   ```bash
   # Create a new branch
   git checkout -b fix/some-bug
   
   # Make your changes
   git add .
   git commit -m "fix(core): fix some bug"
   
   # Push to your fork
   git push origin fix/some-bug
   ```
   Then create a Pull Request from your fork to the main repository.

3. **PR Description**
   - Reference related issues using `#123`
   - Explain the changes and why they're needed
   - Include any relevant screenshots or test results
   - Update documentation if necessary

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code
- Ensure code is well-documented
- Keep lines under 88 characters (Black formatter standard)
- Document all public APIs with docstrings
- Write tests for new functionality

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types**:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Code style/formatting
- `refactor`: Code changes that don't add features
- `test`: Adding tests
- `chore`: Maintenance tasks

**Example**:
```
feat(auth): add OAuth2 support

- Add OAuth2 authentication flow
- Update documentation
- Add tests for new functionality

Closes #123
```

## Release Management

### Versioning

We follow [Semantic Versioning](https://semver.org/) (SemVer):
- `MAJOR` version for incompatible API changes
- `MINOR` version for backward-compatible functionality
- `PATCH` version for backward-compatible bug fixes

### Branch Strategy

- `main`: Latest stable release
- `next`: Next release candidate
- `release-x.y`: Maintenance branches for patch releases
### Documentation Style

- Use active voice
- Be concise but thorough
- Follow proper heading hierarchy
- Include a table of contents for long documents
- Use admonitions for notes, warnings, and tips

### Building Documentation Locally

```bash
# Install dependencies
npm install

# Start development server
npm run docs:dev

# Build for production
npm run docs:build
```

## Getting Help

- Join our [Discord community](https://discord.gg/nexios) for real-time help
- Check our [FAQ](/community/faq) for common questions
- Open a [GitHub Discussion](https://github.com/nexios-labs/nexios/discussions) for longer conversations

## Code of Conduct

Please note that this project is governed by our [Code of Conduct](/community/code-of-conduct). By participating, you are expected to uphold this code.
   

We welcome and appreciate all contributions to Nexios! Whether you're fixing bugs, adding new features, or improving documentation, your help makes Nexios better for everyone.

### Quick Start

1. **Set up your development environment**
   ```bash
   # Clone the repository
   git clone https://github.com/nexios-labs/nexios.git
   cd nexios
   
   # Create and activate a virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install development dependencies
   pip install -e ".[dev]"
   ```

2. **Find an issue to work on**
   - Check the [Good First Issues](https://github.com/organization/nexios/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22) for beginner-friendly tasks
   - Look for issues with the `help wanted` label
   - Comment on the issue to let us know you're working on it

3. **Make your changes**
   - Follow our [Code Style Guide](#code-style-guide)
   - Write tests for your changes
   - Update relevant documentation

4. **Submit a Pull Request**
   - Follow our [PR Guidelines](#pull-request-guide)
   - Reference any related issues using `#issue-number`
   - Ensure all tests pass before requesting review

### Need Help?

- Join our [Discord/Slack community](#) for real-time help
- Check our [FAQ](#) for common questions
- Open a [GitHub Discussion](#) for longer conversations

## Submitting Code

### Pull Request Guide

Before submitting a Pull Request, please ensure you've completed the following steps:

1. **Pre-PR Checklist**
   ```bash
   # Run tests
   pytest tests/
   
   # Check code style
   black --check .
   isort --check-only .
   flake8 .
   ```

2. **Creating the PR**
   - Target the `main` branch
   - Use the PR template (automatically loaded when creating a PR)
   - Include a clear description of changes
   - Reference related issues using `#issue-number`
   - Add screenshots for UI changes
   - Update the `CHANGELOG.md` if applicable

3. **After Submission**
   - Wait for CI to complete
   - Address any review comments
   - Keep your PR up-to-date with the target branch
   ```bash
   git fetch upstream
   git rebase upstream/main
   git push --force-with-lease
   ```

1. **Fork the Repository**
   - Click the 'Fork' button on the top-right corner of the repository page
   - Clone your forked repository locally: `git clone https://github.com/nexios-labs/nexios.git`
   - Add the upstream repository: `git remote add upstream https://github.com/organization/nexios.git`

2. **Create a Feature Branch**
   - Always create a new branch for your changes: `git checkout -b feature/your-feature-name`
   - Use descriptive branch names (e.g., `fix/header-bug`, `feature/user-authentication`)
   - Keep your branch up-to-date with main: `git pull --rebase upstream main`

3. **Making Changes**
   - Make small, focused commits that are easy to review
   - Each commit should represent a single logical change
   - Write clear commit messages following our commit message format
   - Test your changes thoroughly

4. **Testing**
   - Write unit tests for all new functionality
   - Update existing tests if your changes affect them
   - Run all tests locally before submitting: `pytest tests/`
   - Ensure test coverage doesn't decrease

5. **Documentation**
   - Update relevant documentation for your changes
   - Ensure code is well-documented
   - Update README.md if you're adding new features or changing behavior

6. **Submitting a Pull Request**
   - Push your changes to your fork: `git push origin your-branch-name`
   - Open a Pull Request against the `main` branch
   - Use the PR template to provide detailed information
   - Reference any related issues using `#issue-number`
   - Wait for CI to pass before requesting review

### Code Style Guide

#### Python Code Style

We enforce strict code style guidelines to maintain consistency across the codebase. Here's how to ensure your code meets our standards:

1. **Code Formatting**
   - Use [Black](https://black.readthedocs.io/) for automatic code formatting
   - Line length: 88 characters
   - Use `isort` for import sorting
   - Configure your editor to format on save:
     ```json
     // VS Code settings.json
     {
       "editor.formatOnSave": true,
       "python.formatting.provider": "black",
       "python.formatting.blackArgs": ["--line-length", "88"],
       "editor.codeActionsOnSave": {
         "source.organizeImports": true
       },
       "python.sortImports.args": ["--profile", "black"]
     }
     ```

2. **Linting**
   - We use `flake8` with the following configuration:
     ```ini
     [flake8]
     max-line-length = 88
     exclude = .git,__pycache__,.venv,venv,build,dist
     select = E9,F63,F7,F82
     ignore = 
         E203,  # Allow whitespace before ':' in slices (conflicts with Black)
         E501,  # Line too long (handled by black)
         W503   # Line break before binary operator (PEP 8 compliant)
     ```

     ```

3. **Pre-commit Hooks**
   We use `pre-commit` to automatically check code quality before each commit. Install it with:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

   Example `.pre-commit-config.yaml`:
   ```yaml
   repos:
   -   repo: https://github.com/psf/black
       rev: 22.3.0
       hooks:
       - id: black
         language_version: python3.8
   -   repo: https://github.com/PyCQA/isort
       rev: 5.10.1
       hooks:
       -   id: isort
   -   repo: https://github.com/PyCQA/flake8
       rev: 4.0.1
       hooks:
       - id: flake8
   ```

#### Type Hints

We use Python's type hints throughout the codebase to improve code quality and developer experience. Here's a comprehensive guide:

1. **Basic Type Hints**
   ```python
   # Variable annotations
   name: str = "Nexios"
   version: tuple[int, int, int] = (1, 0, 0)
   
   # Function annotations
   def greet(name: str, age: int | None = None) -> str:
       return f"Hello {name}" + (f", you're {age} years old" if age else "")
   ```

2. **Advanced Types**
   ```python
   from typing import Any, Dict, List, Optional, Union, TypedDict, Callable
   from pathlib import Path
   
   # Collections
   def process_users(users: list[dict[str, Any]]) -> list[str]:
       return [user["name"] for user in users if "name" in user]
   
   # Callables
   Callback = Callable[[str, int], bool]
   
   # Type aliases
   UserDict = Dict[str, Union[str, int, bool]]
   
   # Typed dictionaries
   class User(TypedDict):
       id: int
       name: str
       email: str
       is_active: bool = True
   ```

3. **When to use `# type: ignore`**
   ```python
   # Only use when absolutely necessary with an explanation
   import some_legacy_module  # type: ignore[import]
   
   def process(data: Any) -> None:
       # type: (Any) -> None  # For Python 2 compatibility if needed
       result = some_legacy_module.function(data)  # type: ignore[attr-defined]
   ```

#### Docstrings

We follow the Google Python Style Guide for docstrings. Here's a comprehensive guide:

1. **Module Docstrings**
   ```python
   """Nexios - A high-performance Python framework for building APIs.
   
   This module provides core functionality for the Nexios framework,
   including request handling, routing, and response generation.
   
   Example:
       >>> from nexios import NexiosApp
       >>> app = NexiosApp()
       >>> @app.route("/")
       ... def home(req,res):
       ...     return "Hello, World!"
   
   Note:
       This module is not thread-safe. For concurrent applications,
       use appropriate synchronization mechanisms.
   """
   ```

2. **Function/Method Docstrings**
   ```python
   def process_data(data: list[dict], *, validate: bool = True) -> dict[str, int]:
       """Process input data and return aggregated statistics.
   
       This function takes a list of data dictionaries, processes them,
       and returns aggregated statistics. The function can optionally
       validate the input data before processing.
   
       Args:
           data: A list of dictionaries containing the data to process.
               Each dictionary must have 'id' and 'value' keys.
           validate: If True, validate input data before processing.
               Defaults to True.
   
       Returns:
           A dictionary containing aggregated statistics with the
           following keys:
               - 'total': Total number of items processed
               - 'sum': Sum of all values
               - 'avg': Average of all values
   
       Raises:
           ValueError: If validation fails or data is malformed.
           TypeError: If input types are incorrect.
   
       Example:
           >>> data = [{"id": 1, "value": 10}, {"id": 2, "value": 20}]
           >>> process_data(data)
           {'total': 2, 'sum': 30, 'avg': 15.0}
   
       Note:
           This function is performance-critical. Avoid calling it in a tight loop
           with large datasets. Consider batching if needed.
       """
   ```

3. **Class Docstrings**
   ```python
   class DataProcessor:
       """A class for processing and analyzing data.
   
       This class provides methods for loading, processing, and analyzing
       data from various sources. It includes caching and validation
       mechanisms to ensure data integrity.
   
       Attributes:
           cache (dict): A cache for storing processed data.
           options (dict): Configuration options for the processor.
   
       Example:
           >>> processor = DataProcessor()
           >>> processor.load_data("data.csv")
           >>> result = processor.analyze()
   
       Note:
           This class is not thread-safe. For concurrent access, use one
           instance per thread or implement proper synchronization.
       """
   
       def __init__(self, options: dict | None = None):
           """Initialize the DataProcessor with optional configuration.
   
           Args:
               options: Optional configuration dictionary. Valid keys are:
                   - max_cache_size (int): Maximum number of items to cache.
                   - validate (bool): Whether to validate input data.
           """
   ```
  ```

#### Testing Standards

We take testing seriously to ensure code quality and prevent regressions. Here's our comprehensive testing guide:

1. **Test Structure**
   ```python
   # tests/test_module.py
   """Tests for the module functionality."""
   
   import pytest
   from unittest.mock import Mock, patch
   
   from nexios.module import process_data
   
   
   class TestProcessData:
       """Test suite for the process_data function."""
   
       @pytest.fixture
       def sample_data(self) -> list[dict]:
           """Provide sample test data."""
           return [
               {"id": 1, "value": 10, "active": True},
               {"id": 2, "value": 20, "active": False},
               {"id": 3, "value": 30, "active": True},
           ]
   
       def test_process_data_with_valid_input(self, sample_data: list[dict]) -> None:
           """Test processing valid data returns expected results."""
           # Arrange
           expected = {"total": 3, "sum": 60, "avg": 20.0}
           
           # Act
           result = process_data(sample_data)
           
           # Assert
           assert result == expected
   
       @pytest.mark.parametrize("invalid_input, expected_exception", [
           (None, TypeError),
           ("not a list", TypeError),
           ([{"invalid": "data"}], ValueError),
       ])
       def test_process_data_with_invalid_input(
           self, 
           invalid_input: Any,
           expected_exception: type[Exception]
       ) -> None:
           """Test processing invalid data raises appropriate exceptions."""
           with pytest.raises(expected_exception):
               process_data(invalid_input)
   ```

2. **Test Naming Conventions**
   - Test files: `test_<module_name>.py`
   - Test classes: `Test<ClassName>`
   - Test methods: `test_<method_name>_<condition>[_when_<scenario>]`
   - Examples:
     - `test_user_creation_succeeds_with_valid_data()`
     - `test_login_fails_with_invalid_credentials()`
     - `test_process_data_handles_empty_list()`

3. **Test Organization**
   ```
   tests/
   ├── unit/                  # Unit tests
   │   ├── __init__.py
   │   ├── test_models.py
   │   └── test_utils.py
   ├── integration/          # Integration tests
   │   ├── __init__.py
   │   └── test_api.py
   ├── conftest.py           # Shared fixtures
   └── test_config.py        # Test configuration
   ```

4. **Fixtures and Mocks**
   ```python
   # tests/conftest.py
   import pytest
   from typing import Generator
   from unittest.mock import MagicMock
   
   @pytest.fixture(scope="module")
   def mock_database() -> Generator[MagicMock, None, None]:
       """Mock database connection for testing."""
       with patch('nexios.db.Database') as mock_db:
           yield mock_db()
   
   @pytest.fixture
   def sample_user() -> dict:
       """Provide a sample user dictionary."""
       return {
           "id": 1,
           "username": "testuser",
           "email": "test@example.com",
           "is_active": True
       }
   ```

5. **Testing Best Practices**
   - **Arrange-Act-Assert**: Clearly separate test phases
   - **One Assert Per Test**: Test one behavior per test method
   - **Descriptive Names**: Make test names self-documenting
   - **Test Edge Cases**: Include boundary values and error conditions
   - **Use Parametrization**: For testing multiple inputs
   - **Keep Tests Fast**: Mock external dependencies
   - **Test Coverage**: Aim for at least 80% coverage

6. **Running Tests**
   ```bash
   # Run all tests
   pytest
   
   # Run specific test file
   pytest tests/unit/test_models.py
   
   # Run tests with coverage
   pytest --cov=nexios --cov-report=term-missing
   
   # Run tests in parallel
   pytest -n auto
   
   # Run tests matching a pattern
   pytest -k "test_user"
   
   # Run failed tests only
   pytest --lf
   ```

7. **Test Configuration**
   Add a `pytest.ini` file to your project root:
   ```ini
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = -v --cov=nexios --cov-report=term-missing
   norecursedirs = .git .venv venv build dist
   ```

8. **Integration with CI/CD**
   Example GitHub Actions workflow (`.github/workflows/tests.yml`):
   ```yaml
   name: Tests
   
   on: [push, pull_request]
   
   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python-version: ["3.8", "3.9", "3.10", "3.11"]
   
       steps:
       - uses: actions/checkout@v3
       - name: Set up Python ${{ matrix.python-version }}
         uses: actions/setup-python@v4
         with:
           python-version: ${{ matrix.python-version }}
       - name: Install dependencies
         run: |
           python -m pip install --upgrade pip
           pip install -e ".[dev]"
       - name: Run tests
         run: |
           pytest --cov=nexios --cov-report=xml
       - name: Upload coverage to Codecov
         uses: codecov/codecov-action@v3
   ```

9. **Property-Based Testing**
   For complex logic, consider using `hypothesis` for property-based testing:
   ```python
   from hypothesis import given
   from hypothesis import strategies as st
   
   @given(st.lists(st.integers(min_value=1), min_size=1))
   def test_process_data_positive_numbers(numbers):
       data = [{"id": i, "value": x} for i, x in enumerate(numbers)]
       result = process_data(data)
       assert result["sum"] == sum(numbers)
       assert result["avg"] == sum(numbers) / len(numbers)
   ```

#### Code Review Process
1. Automated checks (CI) must pass
2. At least one maintainer must approve
3. All discussions must be resolved
4. Code must be up-to-date with the target branch
5. All new code must be covered by tests
6. Documentation must be updated
- Write unit tests for new features

### Commit Message Format

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes
- refactor: Code changes that neither fix bugs nor add features
- test: Adding missing tests or correcting existing tests
- chore: Changes to the build process or auxiliary tools

## Release Management

### Release Strategy

- We follow [Semantic Versioning](https://semver.org/)
- Major releases may include breaking changes
- Minor releases add functionality in a backward-compatible manner
- Patch releases include backward-compatible bug fixes

### Preparation Before Release

1. Ensure all tests are passing
2. Update version numbers
3. Update changelog
4. Verify documentation is up-to-date
5. Create a release branch

### During Release

1. Create a signed tag for the release
2. Push the tag to trigger the release pipeline
3. Wait for CI/CD to complete
4. Verify the release on PyPI
5. Update documentation for the new version

### After Release

1. Merge the release branch back to main
2. Create a GitHub release with release notes
3. Announce the release on relevant channels
4. Update any dependencies that depend on this release

---

Thank you for contributing to Nexios! Your contributions are greatly appreciated.
