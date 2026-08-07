---
title: Installation
description: Learn how to install and set up sillo Contrib packages in your project.
---

# Installation

Learn how to install and set up sillo Contrib packages in your project.

## About sillo Contrib

The **sillo-contrib** package is a community-driven collection of extensions, middleware, and add-ons for the sillo framework. As an open source project, it welcomes contributions from developers worldwide who want to extend sillo's capabilities.

### What's Included

The contrib package provides independently versioned packages that you can install à-la-carte or together:

- **URL Normalization Middleware** (`sillo_contrib.slashes`) - Handles trailing slashes and URL normalization
- **Trusted Host Middleware** (`sillo_contrib.trusted`) - Validates Host headers for security
- **ETag Middleware** (`sillo_contrib.etag`) - Automatic ETag generation and conditional requests
- **JSON-RPC** (`sillo_contrib.jrpc`) - Complete JSON-RPC 2.0 implementation
- **Tortoise ORM Integration** (`sillo_contrib.tortoise`) - Async ORM integration with lifecycle management

## Meta Package Installation

Install all contrib packages at once:

```bash
uv add sillo-contrib
```

This installs the meta package that includes all available contrib packages, giving you access to the entire community-contributed ecosystem.


## Development Installation

For development or to use the latest features:

```bash
# Clone the contrib repository
git clone https://github.com/sillohq/sillo-contrib.git
cd sillo-contrib

# Install dependencies for development
uv sync
```

## Requirements

- **Python 3.10+**
- **sillo 0.0.1a1+**

Some contrib packages may have additional requirements:

- **Redis contrib**: Requires `redis-py`
- **Tortoise ORM contrib**: Requires `tortoise-orm`
- **JSON-RPC contrib**: No additional dependencies
- **Middleware packages**: No additional dependencies

### Optional Dependencies

You can install contrib packages with their optional dependencies:

```bash
# Install with Redis support
uv add "sillo-contrib[redis]"

# Install with Tortoise ORM support
uv add "sillo-contrib[tortoise]"

# Install with all optional dependencies
uv add "sillo-contrib[all]"
```

## Verification

Verify your installation:

```python
import sillo_contrib

# Check available packages
print(sillo_contrib.__version__)

# Import specific packages
import sillo_contrib.etag
import sillo_contrib.redis
import sillo_contrib.trusted
import sillo_contrib.tortoise
```

## Contributing to sillo Contrib

As an open source project, sillo-contrib thrives on community contributions! Here's how you can get involved:

### Ways to Contribute

- **Submit new middleware or extensions** - Have an idea for useful middleware? Create it and share it with the community
- **Improve existing packages** - Fix bugs, add features, or enhance documentation
- **Report issues** - Found a problem? Let us know on [GitHub Issues](https://github.com/sillohq/sillo-contrib/issues)
- **Share feedback** - Join discussions and help shape the future of contrib packages

### First Contribution

1. **Fork the repository**: [sillo-contrib on GitHub](https://github.com/sillohq/sillo-contrib)
2. **Set up development environment**:
   ```bash
   git clone https://github.com/your-username/sillo-contrib.git
   cd sillo-contrib
   uv sync
   ```
3. **Create your contribution** following our [contribution guidelines](/community/contribution-guide)
4. **Submit a pull request** with your changes

### Package Structure

Each contrib package follows a consistent structure:
```
sillo_contrib/
└── your_package/
    ├── __init__.py
    ├── README.md
    └── your_module.py
```

## Next Steps

- Browse the [middleware documentation](/community/middleware/etag/) to get started
- Check out the [integrations](/community/integrations/redis/) for advanced features
- See the [main overview](/community/) for a complete list of available packages
- Visit the [sillo-contrib repository](https://github.com/sillohq/sillo-contrib) to contribute
