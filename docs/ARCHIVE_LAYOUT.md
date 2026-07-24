# Archive layout

```
C:\memorybox\archive\
  google-takeout-original\   # preferred: immutable Gmail Takeout zip snapshot
  google-takout-original\    # legacy misspelling — supported in git ignore/LFS rules
  checksums\                 # optional checksum manifests
```

Processing never writes into these folders. Use `C:\memorybox\working\` for extracts.
