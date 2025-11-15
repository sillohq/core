# Installation

Learn how to install and set up Nexios Contrib packages in your project.

## About Nexios Contrib

The **nexios-contrib** package is a community-driven collection of extensions, middleware, and add-ons for the Nexios framework. As an open source project, it welcomes contributions from developers worldwide who want to extend Nexios's capabilities.

### What's Included

The contrib package provides independently versioned packages that you can install à-la-carte or together:

- **URL Normalization Middleware** (`nexios_contrib.slashes`) - Handles trailing slashes and URL normalization
- **Trusted Host Middleware** (`nexios_contrib.trusted`) - Validates Host headers for security
- **ETag Middleware** (`nexios_contrib.etag`) - Automatic ETag generation and conditional requests
- **JSON-RPC** (`nexios_contrib.jrpc`) - Complete JSON-RPC 2.0 implementation

## Meta Package Installation

Install all contrib packages at once:

```bash
pip install nexios_contrib
```

This installs the meta package that includes all available contrib packages, giving you access to the entire community-contributed ecosystem.


## Development Installation

For development or to use the latest features:

```bash
# Clone the contrib repository
git clone https://github.com/nexios-labs/nexios-contrib.git
cd nexios-contrib

# Install in development mode
pip install -e .

# Or with uv
uv sync
```

## Requirements

- **Python 3.9+**
- **Nexios 2.11.3+** (or 3.0.0+ for latest features)

Some contrib packages may have additional requirements:

- **Redis contrib**: Requires `redis-py`
- **JSON-RPC contrib**: No additional dependencies
- **Middleware packages**: No additional dependencies

## Verification

Verify your installation:

```python
import nexios_contrib

# Check available packages
print(nexios_contrib.__version__)

# Import specific packages
import nexios_contrib.etag
import nexios_contrib.redis
import nexios_contrib.trusted
```

## Contributing to Nexios Contrib

As an open source project, nexios-contrib thrives on community contributions! Here's how you can get involved:

### Ways to Contribute

- **Submit new middleware or extensions** - Have an idea for useful middleware? Create it and share it with the community
- **Improve existing packages** - Fix bugs, add features, or enhance documentation
- **Report issues** - Found a problem? Let us know on [GitHub Issues](https://github.com/nexios-labs/nexios-contrib/issues)
- **Share feedback** - Join discussions and help shape the future of contrib packages

### Getting Started

1. **Fork the repository**: [nexios-contrib on GitHub](https://github.com/nexios-labs/nexios-contrib)
2. **Set up development environment**:
   ```bash
   git clone https://github.com/your-username/nexios-contrib.git
   cd nexios-contrib
   uv sync  # or pip install -e .
   ```
3. **Create your contribution** following our [contribution guidelines](/community/contribution-guide)
4. **Submit a pull request** with your changes

### Package Structure

Each contrib package follows a consistent structure:
```
nexios_contrib/
└── your_package/
    ├── __init__.py
    ├── README.md
    └── your_module.py
```

## Next Steps

- Browse the [middleware documentation](/contribs/middleware/etag) to get started
- Check out the [integrations](/contribs/integrations/redis) for advanced features
- See the [main overview](/contribs) for a complete list of available packages
- Visit the [nexios-contrib repository](https://github.com/nexios-labs/nexios-contrib) to contribute