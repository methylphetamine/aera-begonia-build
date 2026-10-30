# AERA Recovery builder for Redmi Note 8 Pro (begonia)

This repository mirrors the AERA Recovery Project build setup without touching
the OrangeFox begonia work. It syncs the AERA Android 16 manifest and builds
`twrp_begonia-bp2a-eng` through GitHub Actions.

- AERA source: https://github.com/AERA-Recovery/android_manifest
- Device tree in this repo: `device/xiaomi/begonia`
- Lunch target: `twrp_begonia-bp2a-eng`
- Build target: `adbd recoveryimage`

The AERA source tree is large; the workflow frees runner disk space before
building and trims `.repo` after sync.

## Decryption

Decryption mirrors the verified OrangeFox begonia bring-up. Before compiling,
the workflow runs `scripts/patch_vold_dynamic_fbe.py` on `system/vold/FsCrypt.cpp`
so vold:

- prefers the installed ROM's `/etc/additional.fstab` for the `/data` crypto
  options instead of the recovery fallback fstab;
- reads the policy actually installed on `/data/misc` and normalises the
  kernel value (FBE v1 is `0` in the kernel UAPI but `1` in vold);
- refuses hardware-wrapped keys and `IV_INO_LBLK_32` for v1 data, including
  the wrapped-key retry path;
- creates `/data/misc` and `/data/misc/vold` before `user_keys`, which
  recovery needs because init has not created those parents when vold starts.

The step fails the build if the anchors change upstream, so an image is never
silently produced without the patch.
