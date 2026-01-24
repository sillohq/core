## `NEXIOS`

<div align="left">

<a href="https://git.io/typing-svg"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&pause=1000&color=4CAF50&center=true&width=435&lines=Nexios+ASGI+Framework;Fast%2C+Simple%2C+Flexible" alt="Typing SVG" /></a>

<p align="center">
    <img alt=Support height="350" src="https://nexioslabs.com/logo.png">
    </p>
    <h1 align="center">Nexios 3.x.x</h1>

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
<a href="https://github.com/nexios-labs/Nexios?tab=followers"><img title="Followers" src="https://img.shields.io/github/followers/nexios-labs?label=Followers&style=social"></a>
<a href="https://github.com/nexios-labs/Nexios/stargazers/"><img title="Stars" src="https://img.shields.io/github/stars/nexios-labs/Nexios?&style=social"></a>
<a href="https://github.com/nexios-labs/Nexios/network/members"><img title="Fork" src="https://img.shields.io/github/forks/nexios-labs/Nexios?style=social"></a>
<a href="https://github.com/nexios-labs/Nexios/watchers"><img title="Watching" src="https://img.shields.io/github/watchers/nexios-labs/Nexios?label=Watching&style=social"></a>

</br>

<h2 align="center"> Star the repo if u like it🌟</h2>

Nexios is a utility-first Python web framework designed for developers who need powerful tooling and extensibility. Built with a modular architecture, Nexios provides a comprehensive toolkit for building everything from simple APIs to complex distributed systems. The framework emphasizes developer productivity through its rich ecosystem of utilities, middleware, and community-contributed extensions. Whether you're building microservices, real-time applications, or enterprise-grade backends, Nexios gives you the tools and flexibility to craft solutions that scale with your needs.

---

## `Installation` 📦

**Requirements:**

- Python 3.9 or higher
- pip (Python package manager)

To install **Nexios**, you can use several methods depending on your environment and preferred package manager. Below are the instructions for different package managers:

### 1. **From `pip`** (Standard Python Package Manager)

```bash
# Ensure you have Python 3.9+
python --version

# Install Nexios
pip install nexios

# Or install with specific version
pip install nexios == 3.4.0
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

- [x] **Community Contrib Package** - nexios-contrib with community extensions
- [x] **Custom Middleware Support** - Build and share your own middleware
- [x] **Event System** - Hook into framework events and signals
- [x] **Dependency Injection** - Clean, testable code architecture
- [x] **Security Utilities** - CORS, CSRF, secure headers, and more

### Quick Start - Utility-First Approach

```py
from nexios import NexiosApp
from nexios.http import Request, Response

# Create app with built-in utilities
app = NexiosApp(title="My Utility API")

@app.get("/")
async def basic(request: Request, response: Response):
    return {"message": "Hello from Nexios utilities!"}
```

### Using Community Extensions

```py
from nexios import NexiosApp, Depend
from nexios_contrib.etag import ETagMiddleware
from nexios_contrib.trusted import TrustedHostMiddleware
from nexios.http import Request, Response

app = NexiosApp()

# Add community-contributed middleware
app.add_middleware(ETagMiddleware())
app.add_middleware(TrustedHostMiddleware(allowed_hosts=["example.com"]))

# Utility function with dependency injection
async def get_database():
    # Your database utility here
    return {"connection": "active"}

@app.get("/health")
async def health_check(request: Request, response: Response, db: Depend(get_database)):
    return {"status": "healthy", "database": db}
```

Visit <http://localhost:8000/docs> to view the Swagger API documentation.

## See the full docs

👉 <a href="https://nexioslabs.com">https://nexioslabs.com</a>

## Contributors

<a href="https://github.com/nexios-labs/nexios/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=nexios-labs/nexios" />
</a>

---

## 🌟 Community-Driven Development

Nexios thrives on community contributions and collaboration. We believe the best tools are built by developers, for developers.

### Get Involved

- **Contribute Code**: Submit PRs to the main framework or [nexios-contrib](https://github.com/nexios-labs/contrib)
- **Share Utilities**: Create and share your own middleware, plugins, and tools
- **Join Discussions**: Participate in [GitHub Discussions](https://github.com/nexios-labs/nexios/discussions)
- **Help Others**: Answer questions and help fellow developers

### Community Resources

- 📚 **Documentation**: [https://nexioslabs.com](https://nexioslabs.com)
- 🛠️ **Community Extensions**: [nexios-contrib package](https://github.com/nexios-labs/contrib)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/nexios-labs/nexios/discussions)
- 🐛 **Issues**: [Report bugs and request features](https://github.com/nexios-labs/nexios/issues)

### Support the Project

If Nexios has helped you build something awesome, consider supporting its continued development:

👉 [**Buy Me a Coffee**](https://www.buymeacoffee.com/techwithdul) and help fuel the community-driven future of Nexios.
