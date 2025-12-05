# VM Image Build Toolkit

This folder will contain every script required to build the in-browser VM
images for the v86-based lab. The current workflow is designed to run on any
host with Python 3.10+, `curl`, `tar`, and basic disk utilities (`dd`,
`mkfs.ext4`, `guestmount` or similar).

## Components

- `build_images.py` – orchestrates downloading the Alpine minirootfs, preparing
  per-role root filesystems, assembling raw disk images, and emitting gzipped
  artifacts plus a manifest for the web loader.
- `build/` – scratch space created automatically. Contains cached tarballs,
  unpacked rootfs trees, logs, and temporary mount points.
- `dist/` – output directory (configurable) containing compressed disk images
  and an `images.json` manifest.

## Quick Start

```bash
python tools/build_images.py --role attacker --role defender
```

> The script is currently scaffolded: some provisioning steps are placeholders
> and will be completed in subsequent phases.
