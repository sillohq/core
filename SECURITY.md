# Security Policy

## Supported Versions

Security fixes ship on the latest minor of the 1.x line. That line is 1.2.
The current release is 1.2.1. It requires Python 3.10 or newer.

| Version | Supported |
| ------- | --------- |
| 1.2.x   | Yes       |
| 1.0.x   | No        |
| < 1.0   | No        |

1.0.x and the 0.x releases do not receive patches. Upgrade to 1.2.x.

## Reporting a Vulnerability

If you discover a security vulnerability within sillo, please help us by reporting it responsibly. **Do not create a public issue for security-related reports.**

Instead, please send an email to [techwithdunamix@gmail.com](mailto:techwithdunamix@gmail.com) with the following details:

- A brief description of the vulnerability.
- Steps to reproduce the issue.
- Potential impact of the vulnerability.

We will acknowledge your report within 48 hours and provide a timeline for a fix if applicable. Once a fix is verified, we will release a security advisory and a patched version.

## Security Best Practices

When using sillo, we recommend following these security practices:

1. **Keep sillo Updated:** Always use the latest stable version to benefit from the latest security patches.
2. **Secure Your Secret Key:** Ensure your `secret_key` is strong and kept confidential (e.g., loaded from environment variables).
3. **Validate All Input:** Use sillo's built-in Pydantic integration to validate and sanitize user input.
4. **Enable Security Middleware:** Use `SecurityMiddleware`, `CORSMiddleware`, and `CSRFMiddleware` as appropriate for your application.
