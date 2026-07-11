## `sillo`

<div align="left">

<a href="https://git.io/typing-svg"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&pause=1000&color=4CAF50&center=true&width=435&lines=sillo+ASGI+Framework;Fast%2C+Simple%2C+Flexible" alt="Typing SVG" /></a>

<p align="center">
    <img alt=Support height="350" src="https://sillolabs.com/logo.png">
    </p>
    <h1 align="center">sillo 3.x.x</h1>

   </a>
</p>

<!-- Badges Section -->
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/Downloads-10k/month-brightgreen" alt="Downloads">
  <img src="https://img.shields.io/badge/Contributions-Welcome-orange" alt="Contributions">
  <img src="https://img.shields.io/badge/Active Development-Yes-success" alt="Active Development">
</p>

<p align="center">
<a href="https://github.com/sillo-labs/sillo?tab=followers"><img title="Followers" src="https://img.shields.io/github/followers/sillo-labs?label=Followers&style=social"></a>
<a href="https://github.com/sillo-labs/sillo/stargazers/"><img title="Stars" src="https://img.shields.io/github/stars/sillo-labs/sillo?&style=social"></a>
<a href="https://github.com/sillo-labs/sillo/network/members"><img title="Fork" src="https://img.shields.io/github/forks/sillo-labs/sillo?style=social"></a>
<a href="https://github.com/sillo-labs/sillo/watchers"><img title="Watching" src="https://img.shields.io/github/watchers/sillo-labs/sillo?label=Watching&style=social"></a>

</br>

<h2 align="center"> Star the repo if u like it🌟</h2>

sillo is a utility-first Python web framework designed for developers who need powerful tooling and extensibility. Built with a modular architecture, sillo provides a comprehensive toolkit for building everything from simple APIs to complex distributed systems. The framework emphasizes developer productivity through its rich ecosystem of utilities, middleware, and community-contributed extensions. Whether you're building microservices, real-time applications, or enterprise-grade backends, sillo gives you the tools and flexibility to craft solutions that scale with your needs.

---

## `Installation` 📦

**Requirements:**

- Python 3.9 or higher
- pip (Python package manager)

To install **sillo**, you can use several methods depending on your environment and preferred package manager. Below are the instructions for different package managers:

### 1. **From `pip`** (Standard Python Package Manager)

```bash
# Ensure you have Python 3.9+
python --version

# Install sillo
pip install sillo

# Or install with specific version
pip install sillo == 3.4.0
```

## Utility-First Features ✨

### Core Utilities & Tooling

- [x] **Modular Architecture** - Mix and match components as needed
- [x] **Rich CLI Tooling** - Project scaffolding, code generation, and development tools
- [x] **Plugin System** - Extensible architecture for custom functionality
- [x] **Developer Utilities** - Debug toolbar, profiling, and development helpers
- [x] **Testing Framework** - Built-in testing utilities and fixtures

### Web Framework Essentials

- [x] **Powerful Routing** - Type-safe routing with parameter validation
- [x] **Automatic OpenAPI Documentation** - Self-documenting APIs
- [x] **Authentication Toolkit** - Multiple auth backends and strategies
- [x] **Middleware Pipeline** - Composable request/response processing
- [x] **WebSocket Support** - Real-time communication utilities
- [x] **Session Management** - Flexible session handling

### Community & Extensibility

- [x] **Community Contrib Package** - sillo-contrib with community extensions
- [x] **Custom Middleware Support** - Build and share your own middleware
- [x] **Event System** - Hook into framework events and signals
- [x] **Dependency Injection** - Clean, testable code architecture
- [x] **Security Utilities** - CORS, CSRF, secure headers, and more

### Quick Start - Utility-First Approach

```py
from sillo import silloApp
from sillo.http import Request, Response

# Create app with built-in utilities
app = silloApp(title="My Utility API")

@app.get("/")
async def basic(request: Request, response: Response):
    return {"message": "Hello from sillo utilities!"}
```

### Using Community Extensions

```py
from sillo import silloApp, Depend
from sillo_contrib.etag import ETagMiddleware
from sillo_contrib.trusted import TrustedHostMiddleware
from sillo.http import Request, Response

app = silloApp()

# Add community-contributed middleware
app.add_middleware(ETagMiddleware())
app.add_middleware(TrustedHostMiddleware(allowed_hosts=["example.com"]))

# Utility function with dependency injection
async def get_database():
    # Your database utility here
    return {"connection": "active"}

@app.get("/health")
async def health_check(request: Request, response: Response, db =  Depend(get_database)):
    return {"status": "healthy", "database": db}
```

Visit <http://localhost:8000/docs> to view the Swagger API documentation.

## See the full docs

👉 <a href="https://sillolabs.com">https://sillolabs.com</a>

## Contributors

<a href="https://github.com/sillo-labs/sillo/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=sillo-labs/sillo" />
</a>

---

## 🌟 Community-Driven Development

sillo thrives on community contributions and collaboration. We believe the best tools are built by developers, for developers.

### Get Involved

- **Contribute Code**: Submit PRs to the main framework or [sillo-contrib](https://github.com/sillo-labs/contrib)
- **Share Utilities**: Create and share your own middleware, plugins, and tools
- **Join Discussions**: Participate in [GitHub Discussions](https://github.com/sillo-labs/sillo/discussions)
- **Help Others**: Answer questions and help fellow developers

### Community Resources

- 📚 **Documentation**: [https://sillolabs.com](https://sillolabs.com)
- 🛠️ **Community Extensions**: [sillo-contrib package](https://github.com/sillo-labs/contrib)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/sillo-labs/sillo/discussions)
- 🐛 **Issues**: [Report bugs and request features](https://github.com/sillo-labs/sillo/issues)

### Support the Project

If sillo has helped you build something awesome, consider supporting its continued development:

👉 [**Buy Me a Coffee**](https://www.buymeacoffee.com/techwithdul) and help fuel the community-driven future of sillo.
