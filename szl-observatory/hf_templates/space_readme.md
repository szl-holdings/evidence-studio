---
title: SZL Observatory
emoji: 📊
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
---

# SZL Observatory Space

This Space runs the same read-only FastAPI dashboard as the canonical GitHub repository. Mount or bake an immutable snapshot export into the image and set `SZL_SNAPSHOT_FILE` to serve that snapshot.

The Space is a presentation surface. It does not collect provider credentials and it does not recognize revenue. Every displayed metric must retain its source, timestamp, status, and evidence URL.
