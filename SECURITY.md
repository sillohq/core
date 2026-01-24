# Security Policy

## Supported Versions

Nexios takes security seriously. Below are the versions currently receiving security updates:

| Version | Supported |
| ------- | --------- |
| 3.7.x   | ✅        |
| 3.x     | ✅        |
| < 3.0   | ❌        |

## Reporting a Vulnerability

If you discover a security vulnerability within Nexios, please help us by reporting it responsibly. **Do not create a public issue for security-related reports.**

Instead, please send an email to [techwithdunamix@gmail.com](mailto:techwithdunamix@gmail.com) with the following details:

- A brief description of the vulnerability.
- Steps to reproduce the issue.
- Potential impact of the vulnerability.

We will acknowledge your report within 48 hours and provide a timeline for a fix if applicable. Once a fix is verified, we will release a security advisory and a patched version.

## Security Best Practices

When using Nexios, we recommend following these security practices:

1. **Keep Nexios Updated:** Always use the latest stable version to benefit from the latest security patches.
2. **Secure Your Secret Key:** Ensure your `secret_key` is strong and kept confidential (e.g., loaded from environment variables).
3. **Validate All Input:** Use Nexios's built-in Pydantic integration to validate and sanitize user input.
4. **Enable Security Middleware:** Use `SecurityMiddleware`, `CORSMiddleware`, and `CSRFMiddleware` as appropriate for your application.
