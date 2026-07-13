---
title: File Helpers
description: File utilities — size formatting, extension detection, safe filenames, MIME types.
---

# Files (`sillo.helpers.files`)

```python
from sillo.helpers import files

files.format_size(1024)                      # "1.0 KB"
files.format_size(1536000)                   # "1.5 MB"
files.format_size_binary(1536000)            # "1.5 MiB"
files.parse_size("10 MB")                    # 10485760
files.get_extension("photo.jpg")             # ".jpg"
files.get_extension_clean("archive.tar.gz")  # "gz"
files.guess_mime_type("photo.png")           # "image/png"
files.is_dangerous_extension("script.exe")   # True
files.is_image_extension("photo.jpg")        # True
files.is_media_extension("song.mp3")         # True

files.safe_filename("user input: file?.txt") # "user_input_file_.txt"
files.unique_filename("/tmp", "log.txt")     # "log (1).txt" if exists
files.file_age("/var/log/app.log")           # seconds since modified
files.file_age_human("/var/log/app.log")     # "3h ago"
files.ensure_directory("/data/uploads")
files.list_files("/data", "*.csv", recursive=True)
```
