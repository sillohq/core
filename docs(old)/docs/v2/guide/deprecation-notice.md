---
icon: alert-triangle
title: ⚠️ Version 2 Deprecated
description: sillo v2 is no longer maintained. Please upgrade to the latest version.
head:
  - - meta
    - property: og:title
      content: sillo v2 Deprecated
  - - meta
    - property: og:description
      content: sillo v2 is no longer maintained. Please upgrade to the latest version.
---

# ⚠️ sillo v2 is Deprecated

::: danger Important Deprecation Notice
**sillo v2 has reached end-of-life and is no longer maintained.**

This documentation is provided for historical reference only. We strongly recommend upgrading to the latest version of sillo for:

-  **Security updates and patches**
-  **Performance improvements**
-  **New features and enhancements**
-  **Bug fixes and stability improvements**
-  **Active community support**

## Migration Path

### Current Status
- **v2.x**:  Deprecated (no longer maintained)
- **v3.x**:  Current stable version (recommended)

### How to Upgrade

1. **Check your current version**:
   ```bash
   pip show sillo
   ```

2. **Upgrade to latest version**:
   ```bash
   pip install --upgrade sillo
   ```

3. **Review migration guide**: See [Migration Guide](../../guide/migration-v2-to-v3) for detailed upgrade instructions.

4. **Test your application**: Ensure all functionality works as expected after upgrade.

### Breaking Changes in v3

While we've tried to minimize breaking changes, some updates were necessary for security and performance improvements:

- Updated dependency injection system
- Enhanced middleware architecture
- Improved WebSocket handling
- Updated authentication system
- Performance optimizations

### Need Help?

-  **Current Documentation**: [Latest Version Documentation](../../)
-  **Community Support**: [Join our Discord](https://discord.gg/sillo)
-  **Report Issues**: [GitHub Issues](https://github.com/sillo-labs/sillo/issues)
-  **Email Support**: support@sillo.dev

---

::: tip Thank You
Thank you for using sillo! We're committed to making the upgrade process as smooth as possible. If you encounter any issues during migration, please don't hesitate to reach out.
:::
