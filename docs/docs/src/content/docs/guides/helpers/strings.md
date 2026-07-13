---
title: String Helpers
description: String utilities — slugify, camel/snake conversion, masking, random generation.
---

# Strings (`sillo.helpers.strings`)

```python
from sillo.helpers import strings

strings.slugify("Hello World!")           # "hello-world"
strings.camel_to_snake("camelCase")       # "camel_case"
strings.snake_to_camel("snake_case")      # "snakeCase"
strings.pascal_case("snake_case")         # "SnakeCase"
strings.kebab_case("camelCase")           # "camel-case"
strings.strip_accents("café")             # "cafe"
strings.is_camel_case("myVar")            # True
strings.is_snake_case("my_var")           # True

strings.mask_string("abcdefghij", 2, 2)   # "ab******ij"
strings.mask_email("john@example.com")    # "j**n@example.com"

strings.random_string(12)                 # "aB3dEfGhIjKl"
strings.random_digits(6)                  # "847291"
strings.random_token()                    # base64 URL-safe token
```
