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

Thank you for your interest in contributing to Nexios! This guide will help you get started with contributing to the project.

## Quick Start

1. **Fork the repository**: https://github.com/nexios-labs/nexios
2. **Clone your fork**: 
   ```bash
   git clone https://github.com/YOUR_USERNAME/nexios.git
   cd nexios
   ```
3. **Set up development environment**:
   ::: code-group

   ```bash [Using uv (Recommended)]
   # Create virtual environment and install dependencies
   uv venv
   uv pip install -e ".[dev]"
   ```

   ```bash [Using venv]
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install development dependencies
   pip install -e ".[dev]"
   ```

   :::
4. **Create a feature branch**: 
   ```bash
   git checkout -b feature/your-feature-name
   ```
5. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat: add your feature"
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request** to the v3 branch

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- A GitHub account
- **uv** (recommended) - Modern Python package installer. Install with: `pip install uv`

### Environment Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nexios-labs/nexios.git
   cd nexios
   ```

2. **Set up virtual environment**:
   ::: code-group

   ```bash [Using uv (Recommended)]
   # Create virtual environment
   uv venv
   ```

   ```bash [Using venv]
   # Create virtual environment
   python -m venv venv
   
   # On Unix/macOS
   source venv/bin/activate
   
   # On Windows
   venv\Scripts\activate
   ```

   :::

3. **Install dependencies**:
   ::: code-group

   ```bash [Using uv (Recommended)]
   # Install development dependencies
   uv pip install -e ".[dev]"
   ```

   ```bash [Using venv]
   # Install development dependencies
   pip install -e ".[dev]"
   ```

   :::

4. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
   pytest

# Run tests with coverage
   pytest --cov=nexios --cov-report=term-missing

# Run tests in parallel
   pytest -n auto
```

## Finding Issues to Work On

- **Good First Issues**: Look for issues labeled `good first issue` for beginner-friendly tasks
- **Help Wanted**: Issues with the `help wanted` label need community assistance
- **Bug Reports**: Help fix reported bugs
- **Feature Requests**: Contribute new features

## Submitting Changes

### Pull Request Process

1. **Before Submitting**:
   - Run tests: `pytest`
   - Check code style: `black --check .` and `isort --check-only .`
   - Ensure all tests pass locally
   - Update documentation if needed

2. **Creating the PR**:
   - Target the `v3` branch
   - Use a clear, descriptive title
   - Reference related issues using `#issue-number`
   - Include a detailed description of changes

3. **PR Description Template**:
   ```markdown
   ## Description
   Brief description of what this PR does.
   
   ## Changes
   - List of changes made
   
   ## Testing
   - How you tested the changes
   - Test cases added/modified
   
   ## Related Issues
   Closes #123
   ```

### Code Style

We follow strict code style guidelines:

- **Python**: Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- **Line length**: 88 characters (Black formatter standard)
- **Type hints**: Required for all public APIs
- **Docstrings**: Follow Google Python Style Guide

#### Code Formatting Tools

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .
```

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
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

## Creating Libraries for Nexios

Want to create a library that extends Nexios? We provide a project template to help you get started:

**Project Template**: https://github.com/nexios-labs/project-template

This template includes:
- Standard project structure
- CI/CD configuration
- Testing setup
- Documentation template
- Pre-commit hooks
- PyPI publishing configuration

### Getting Started with the Template

1. **Click "Use this template"** on the GitHub repository
2. **Clone your new repository**
3. **Customize the template**:
   - Update `pyproject.toml` with your project details
   - Modify README.md
   - Update package name and imports
4. **Install dependencies** and start developing

## Documentation

### Documentation Structure

```
docs/
├── guide/           # Tutorials and how-to guides
├── intro/           # Introduction and getting started
├── community/       # Community resources
└── .vitepress/      # Vitepress configuration
```

### Making Documentation Changes

1. **Small Fixes**:
   - Fix typos, broken links, or outdated information
   - Use the "Edit this page" link at the bottom of each doc

2. **New Content**:
   - Follow the existing documentation style
   - Add new Markdown files in the appropriate directory
   - Update navigation in the config file

3. **Running Documentation Locally**:
   ```bash
   # Install dependencies
   npm install
   
   # Start development server
   npm run docs:dev
   
   # Build for production
   npm run docs:build
   ```

### Documentation Guidelines

- Use clear, concise language
- Include code examples with proper syntax highlighting
- Add step-by-step instructions for complex procedures
- Include links to related documentation
- Keep documentation up-to-date with code changes

## Testing

### Test Structure

```
tests/
├── unit/                  # Unit tests
├── integration/          # Integration tests
├── conftest.py           # Shared fixtures
└── test_config.py        # Test configuration
```

### Writing Tests

1. **Test Naming**:
   - Test files: `test_<module_name>.py`
   - Test classes: `Test<ClassName>`
   - Test methods: `test_<method_name>_<condition>`

2. **Test Structure**:
   ```python
   import pytest
   from nexios.module import function_to_test
   
   def test_function_with_valid_input():
       """Test function with valid input returns expected result."""
       # Arrange
       input_data = {"key": "value"}
       expected = {"result": "success"}
       
       # Act
       result = function_to_test(input_data)
       
       # Assert
       assert result == expected
   ```

3. **Testing Best Practices**:
   - Write descriptive test names
   - Use fixtures for reusable test data
   - Test both success and failure cases
   - Mock external dependencies
   - Aim for high test coverage

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

1. **Clear Title**: e.g., "Fix: API returns 500 when X"
2. **Description**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages or logs (use code blocks)
3. **Environment Details**:
   ```bash
   OS: [e.g., Windows 11, macOS 13, Ubuntu 22.04]
   Python: [e.g., 3.9.7]
   Nexios Version: [e.g., 1.0.0]
   ```
4. **Screenshots/Videos**: For UI-related issues

### Feature Requests

For feature requests, include:

1. **Clear description** of the feature
2. **Use case** and why it's valuable
3. **Proposed implementation** (if you have ideas)
4. **Alternative approaches** considered

## Community

### Getting Help

- **Discord**: Join our [Discord community](https://discord.gg/nexios) for real-time help
- **GitHub Discussions**: Use [GitHub Discussions](https://github.com/nexios-labs/nexios/discussions) for longer conversations
- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/nexios-labs/nexios/issues)

### Code of Conduct

Please note that this project is governed by our [Code of Conduct](/community/code-of-conduct). By participating, you are expected to uphold this code.

## Release Management

### Versioning

We follow [Semantic Versioning](https://semver.org/):
- `MAJOR`: Incompatible API changes
- `MINOR`: Backward-compatible functionality
- `PATCH`: Backward-compatible bug fixes

### Branch Strategy

- `v3`: Latest stable release (main development branch)
- `next`: Next release candidate
- `release-x.y`: Maintenance branches for patch releases

## Recognition

Contributors are recognized in several ways:

- **Contributors list** in the repository
- **Release notes** mentioning significant contributions
- **Community recognition** in Discord and discussions
- **Maintainer opportunities** for consistent contributors

---

Thank you for contributing to Nexios! Your contributions help make the framework better for everyone. Whether you're fixing bugs, adding features, improving documentation, or helping others in the community, your efforts are greatly appreciated.
