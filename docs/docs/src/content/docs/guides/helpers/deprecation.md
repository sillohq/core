---
title: Deprecation Helpers
description: Framework deprecation utilities — warnings, decorators, parameter deprecation.
---

# Deprecation (`sillo.helpers.deprecation`)

```python
from sillo.helpers import deprecation

deprecation.warn_deprecated(
    "old_method is deprecated",
    version="1.0",
    removed_in="2.0",
)

@deprecation.deprecated(
    since="1.0",
    removed_in="2.0",
    replacement="new_method",
)
def old_method():
    pass

@deprecation.deprecate_parameter(
    param_name="old_param",
    since="1.0",
    removed_in="2.0",
    replacement="new_param",
)
def my_func(new_param=None, old_param=None):
    pass
```
