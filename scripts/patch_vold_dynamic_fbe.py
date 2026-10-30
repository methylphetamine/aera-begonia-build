#!/usr/bin/env python3
"""Patch AERA's system/vold for runtime FBE v1/v2 decryption on begonia.

AERA's vold is Android 16 based, while the begonia device tree is shared with
the OrangeFox tree whose FBE bring-up predates it.  TWRP copies the installed
ROM's vendor fstab to /etc/additional.fstab; that file describes the crypto
layout that actually encrypted this ROM's /data (FBE v1 vs v2, metadata and
wrapped-key flags).  vold must use it, and it must trust the policy that is
really present on /data/misc rather than the recovery fallback fstab.

This is the AERA counterpart of orangefox-begonia-build's
scripts/patch_vold_dynamic_fbe.py.  The OrangeFox script targets the older
TWRP-12.1 FsCrypt.cpp (per-mount options argument); AERA moved the /data
options into the s_data_options global, so the anchors below are different.

What it changes in system/vold/FsCrypt.cpp:

  * init_data_file_encryption_options() prefers /etc/additional.fstab over
    the recovery fallback fstab.
  * the installed /data policy is read from /data/misc (with the legacy
    comma-vs-base64url dirent fallback) and overrides the fstab version.
    The kernel UAPI FSCRYPT_POLICY_V1 is 0, while EncryptionOptions::version
    uses 1, so the raw value is normalised; handing 0 to installKey() is the
    "Invalid encryption policy version: 0" failure seen before.
  * a detected v1 policy never uses hardware-wrapped keys or
    IV_INO_LBLK_32, and the wrapped-key retry is not attempted for v1.
    Upstream's retry toggled an unrelated local `options`, so the retry now
    toggles the `s_data_options` global that is actually installed.
  * /data/misc and /data/misc/vold are created before user_keys, because
    recovery mounts /data without init having made the parents (the same
    fix OrangeFox carries for its recovery vold).

Run it on a clean AOSP/AERA checkout before building:

    python3 scripts/patch_vold_dynamic_fbe.py aosp/system/vold/FsCrypt.cpp
"""

import sys
from pathlib import Path


FSTAB_OLD = """    if (fstab_default.empty()) {
        if (!ReadDefaultFstab(&fstab_default)) {
            PLOG(ERROR) << "Failed to open default fstab";
            return false;
        }
    }
    auto entry = GetEntryForMountPoint(&fstab_default, DATA_MNT_POINT);
"""

FSTAB_NEW = """    // TWRP copies the installed ROM's vendor fstab to /etc/additional.fstab.
    // That entry describes the crypto layout that actually encrypted /data,
    // so it must win over the recovery fallback fstab.
    android::fs_mgr::Fstab rom_fstab;
    if (access("/etc/additional.fstab", R_OK) == 0 &&
        android::fs_mgr::ReadFstabFromFile("/etc/additional.fstab", &rom_fstab) &&
        !rom_fstab.empty()) {
        fstab_default = rom_fstab;
        LOG(INFO) << "FBE: using installed ROM fstab /etc/additional.fstab";
    } else if (fstab_default.empty()) {
        if (!ReadDefaultFstab(&fstab_default)) {
            PLOG(ERROR) << "Failed to open default fstab";
            return false;
        }
    }
    auto entry = GetEntryForMountPoint(&fstab_default, DATA_MNT_POINT);
"""

PARSE_OLD = """    if (!ParseOptions(entry->encryption_options, &s_data_options)) {
        LOG(ERROR) << "Unable to parse encryption options for " << DATA_MNT_POINT ": "
                   << entry->encryption_options;
        return false;
    }
"""

PARSE_NEW = PARSE_OLD + """    // A ROM update can change the fstab version without reformatting /data.
    // Trust the policy that is actually installed on /data/misc instead.
    // Note: the kernel UAPI defines FSCRYPT_POLICY_V1 as 0 and
    // FSCRYPT_POLICY_V2 as 2, while EncryptionOptions::version uses 1 and 2.
    bool detected_v1 = false;
    int installed_version = -1;
    static int cached_installed_version = -1;
    if (cached_installed_version == 1 || cached_installed_version == 2) {
        installed_version = cached_installed_version;
    } else {
#ifdef USE_FSCRYPT_POLICY_V1
        struct fscrypt_policy_v1 installed_policy {};
#else
        struct fscrypt_policy_v2 installed_policy {};
#endif
        if (fscrypt_policy_get_struct("/data/misc", &installed_policy)) {
            const int kernel_version = installed_policy.version;
            if (kernel_version == 0 || kernel_version == 1) {
                installed_version = 1;
            } else if (kernel_version == 2) {
                installed_version = 2;
            }
            cached_installed_version = installed_version;
        } else {
            DIR* dir = opendir("/data/misc");
            if (dir != nullptr) {
                struct dirent* de;
                while ((de = readdir(dir)) != nullptr) {
                    if (de->d_name[0] == '.') continue;
                    // Legacy v1 encrypted dirents contain a comma; v2
                    // base64url names do not.
                    installed_version = std::strchr(de->d_name, ',') != nullptr ? 1 : 2;
                    cached_installed_version = installed_version;
                    break;
                }
                closedir(dir);
            }
        }
    }
    if (installed_version != -1) {
        if (static_cast<int>(s_data_options.version) != installed_version) {
            LOG(INFO) << "FBE: installed /data policy is v" << installed_version
                      << "; overriding fstab policy v"
                      << static_cast<int>(s_data_options.version);
        }
        s_data_options.version = installed_version;
        detected_v1 = installed_version == 1;
    }
    if (detected_v1) {
        // Hardware-wrapped keys and IV_INO_LBLK_32 are v2-only features.
        s_data_options.use_hw_wrapped_key = false;
        s_data_options.flags &= ~FSCRYPT_POLICY_FLAG_IV_INO_LBLK_32;
    }
"""

WRAPPED_OLD = """    if (s_data_options.version == 1 || !retry) {
        s_data_options.use_hw_wrapped_key =
            GetEntryForMountPoint(&fstab_default, DATA_MNT_POINT)->fs_mgr_flags.wrapped_key;
    }
"""

WRAPPED_NEW = """    if (s_data_options.version == 1 || !retry) {
        s_data_options.use_hw_wrapped_key = entry->fs_mgr_flags.wrapped_key;
    }
    if (detected_v1) {
        s_data_options.use_hw_wrapped_key = false;
    }
"""

RETRY_OLD = """        if (retry) {
            printf("Trying %s wrappedkey\\n", options.use_hw_wrapped_key ? "without" : "with");
            GetEntryForMountPoint(&fstab_default, DATA_MNT_POINT)->fs_mgr_flags.wrapped_key =
                options.use_hw_wrapped_key = !options.use_hw_wrapped_key;
"""

RETRY_NEW = """        if (retry && s_data_options.version != 1) {
            printf("Trying %s wrappedkey\\n",
                   s_data_options.use_hw_wrapped_key ? "without" : "with");
            GetEntryForMountPoint(&fstab_default, DATA_MNT_POINT)->fs_mgr_flags.wrapped_key =
                s_data_options.use_hw_wrapped_key = !s_data_options.use_hw_wrapped_key;
"""

PARENT_OLD = """    if (IsFbeEnabled()) {
        if (!prepare_dir(user_key_dir, 0700, AID_ROOT, AID_ROOT)) return false;
"""

PARENT_NEW = """    if (IsFbeEnabled()) {
        // Recovery mounts /data before vold starts, so Android's init has not
        // created /data/misc/vold yet.  fs_prepare_dir() only creates the final
        // path component; create the parents first, otherwise user_keys cannot
        // be created and FBE DE decryption never completes.
        if (!prepare_dir("/data/misc", 01771, AID_SYSTEM, AID_MISC)) return false;
        if (!prepare_dir("/data/misc/vold", 0700, AID_ROOT, AID_ROOT)) return false;
        if (!prepare_dir(user_key_dir, 0700, AID_ROOT, AID_ROOT)) return false;
"""


def replace_once(path: Path, src: str, old: str, new: str, marker: str) -> str:
    if marker in src:
        return src
    if old not in src:
        raise SystemExit(f"{path}: expected block not found ({marker!r})")
    return src.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_vold_dynamic_fbe.py <path/to/FsCrypt.cpp>")

    path = Path(sys.argv[1])
    if not path.is_file():
        raise SystemExit(f"{path}: not a file")
    src = path.read_text()

    if '#include "fscrypt_policy.h"' not in src:
        anchor = '#include "FsCrypt.h"'
        if anchor not in src:
            raise SystemExit(f"{path}: expected FsCrypt.h include")
        src = src.replace(anchor, anchor + '\n#include "fscrypt_policy.h"', 1)

    if "#include <cstring>" not in src:
        anchor = "#include <string>"
        if anchor not in src:
            raise SystemExit(f"{path}: expected <string> include")
        src = src.replace(anchor, anchor + "\n#include <cstring>", 1)

    src = replace_once(path, src, FSTAB_OLD, FSTAB_NEW,
                       "FBE: using installed ROM fstab")
    src = replace_once(path, src, PARSE_OLD, PARSE_NEW,
                       "FBE: installed /data policy is v")
    src = replace_once(path, src, WRAPPED_OLD, WRAPPED_NEW,
                       "s_data_options.use_hw_wrapped_key = entry->fs_mgr_flags.wrapped_key;")
    src = replace_once(path, src, RETRY_OLD, RETRY_NEW,
                       "if (retry && s_data_options.version != 1)")
    src = replace_once(path, src, PARENT_OLD, PARENT_NEW,
                       'prepare_dir("/data/misc/vold"')

    path.write_text(src)
    print(f"patched {path}: additional fstab, installed-policy detection, "
          "v1 wrapped-key handling, /data/misc parents")


if __name__ == "__main__":
    main()
