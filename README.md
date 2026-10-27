# AERA Recovery builder for Redmi Note 8 Pro (begonia)

This repository mirrors the AERA Recovery Project build setup without touching
the OrangeFox begonia work. It syncs the AERA Android 16 manifest and builds
`twrp_begonia-bp2a-eng` through GitHub Actions.

- AERA source: https://github.com/AERA-Recovery/android_manifest
- Device tree in this repo: `device/xiaomi/begonia`
- Lunch target: `twrp_begonia-bp2a-eng`
- Build target: `adbd recoveryimage`

The AERA source tree is large; the workflow frees runner disk space before
building and trims `.repo` after sync.  It also removes test-only source trees
before Soong scans the tree: on a 16 GB hosted runner the full AOSP 16 test
module graph does not fit in memory, even though none of those modules are
needed for `recoveryimage`.
