#!/usr/bin/env python3
"""
Scaffolding tool to build role-specific VM images for the v86-based lab.

Current implementation fetches the Alpine minirootfs, prepares per-role rootfs
trees with the lab assets, and packages them into gzipped tar archives named
*.img.gz. Future iterations will replace the tar-based packaging with actual
ext4 disk images suitable for direct boot in v86.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD_DIR = REPO_ROOT / "build"
DEFAULT_DIST_DIR = REPO_ROOT / "dist"
DEFAULT_IMAGE_SIZE_MB = 512
MINIROOTFS_URL = (
    "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/"
    "alpine-minirootfs-3.19.1-x86_64.tar.gz"
)

LAB_SHARED_FILES = {
    "attacker": [
        ("network-lab-final/attacker/attack_script.py", "opt/lab/attacker/attack_script.py"),
        ("network-lab-final/attacker/payloads.txt", "opt/lab/attacker/payloads.txt"),
    ],
    "defender": [
        ("network-lab-final/snort/flag_checker.py", "opt/lab/snort/flag_checker.py"),
        ("network-lab-final/snort/found", "opt/lab/snort/found"),
        ("network-lab-final/snort/motd", "opt/lab/snort/motd"),
    ],
}

COMMON_PACKAGES = ["bash", "coreutils", "nano", "iproute2", "procps-ng"]
ROLE_PACKAGES = {
    "attacker": COMMON_PACKAGES
    + [
        "python3",
        "py3-pip",
        "hping3",
        "iputils",
    ],
    "defender": COMMON_PACKAGES
    + [
        "python3",
        "snort",
        "tcpdump",
        "iputils",
    ],
}


@dataclass
class BuildConfig:
    roles: List[str]
    build_dir: Path
    dist_dir: Path
    cache_dir: Path
    force: bool
    keep_workdir: bool
    skip_packages: bool
    image_type: str
    image_size_mb: int
    minirootfs_url: str = MINIROOTFS_URL


class BuildError(RuntimeError):
    """Custom exception for build failures."""


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build v86-ready Alpine images for attacker and defender roles."
    )
    parser.add_argument(
        "--role",
        action="append",
        choices=("attacker", "defender"),
        help="Role(s) to build. Repeat the flag for multiple roles. Defaults to both.",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=DEFAULT_BUILD_DIR,
        help="Scratch directory for intermediate build artifacts.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST_DIR,
        help="Destination directory for final images and manifest.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate role rootfs even if it already exists.",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Do not delete per-role work directories after packaging.",
    )
    parser.add_argument(
        "--skip-packages",
        action="store_true",
        help="Skip running apk provisioning inside the rootfs.",
    )
    parser.add_argument(
        "--image-type",
        choices=("tar", "ext4"),
        default="tar",
        help="Output image format. ext4 requires mke2fs/genext2fs to be available.",
    )
    parser.add_argument(
        "--image-size-mb",
        type=int,
        default=DEFAULT_IMAGE_SIZE_MB,
        help="Raw image size when --image-type ext4 is selected.",
    )
    parser.add_argument(
        "--minirootfs-url",
        default=MINIROOTFS_URL,
        help="Override Alpine minirootfs download URL.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        format="[%(levelname)s] %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_command(cmd: List[str], cwd: Path | None = None) -> None:
    logging.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise BuildError(f"Command {' '.join(cmd)} failed with exit code {result.returncode}")


def download_file(url: str, destination: Path) -> Path:
    if destination.exists():
        logging.info("Using cached %s", destination.name)
        return destination

    logging.info("Downloading minirootfs from %s", url)
    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as out:
            shutil.copyfileobj(response, out)
    except Exception as exc:  # pragma: no cover - network dependent
        raise BuildError(f"Failed to download {url}: {exc}") from exc

    logging.info("Downloaded %s (%.1f MB)", destination.name, destination.stat().st_size / 1e6)
    return destination


def _handle_symlink(member: tarfile.TarInfo, tar: tarfile.TarFile, destination: Path) -> None:
    link_target = member.linkname.lstrip("/")
    target_path = destination / link_target
    member_path = destination / member.name
    ensure_directory(member_path.parent)

    if target_path.is_dir():
        if member_path.exists():
            return
        shutil.copytree(target_path, member_path, dirs_exist_ok=True)
    elif target_path.is_file():
        shutil.copy2(target_path, member_path)
    else:
        logging.debug(
            "Symlink target %s does not exist yet; creating empty placeholder for %s",
            target_path,
            member.name,
        )
        member_path.write_bytes(b"")


def extract_rootfs(tarball: Path, destination: Path, force: bool) -> None:
    if destination.exists():
        if force:
            shutil.rmtree(destination, onerror=_make_writable_and_retry)
        else:
            logging.info("Rootfs already exists at %s; reuse (use --force to rebuild).", destination)
            return

    logging.info("Extracting minirootfs into %s", destination)
    ensure_directory(destination)
    with tarfile.open(tarball, "r:gz") as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk():
                _handle_symlink(member, tar, destination)
                continue
            tar.extract(member, destination)


def copy_lab_files(role: str, rootfs_dir: Path) -> None:
    for src_rel, dst_rel in LAB_SHARED_FILES.get(role, []):
        src = REPO_ROOT / src_rel
        dst = rootfs_dir / dst_rel
        ensure_directory(dst.parent)
        shutil.copy2(src, dst)
        logging.debug("Copied %s -> %s", src_rel, dst_rel)

    ipc_dir = rootfs_dir / "opt" / "lab" / "ipc"
    ensure_directory(ipc_dir)
    for name in ("attack_info.txt", "stop_attack.txt"):
        target = ipc_dir / name
        target.write_text("" if name == "attack_info.txt" else "0\n")


def configure_hostname(role: str, rootfs_dir: Path) -> None:
    hostname = f"{role}-vm"
    (rootfs_dir / "etc" / "hostname").write_text(f"{hostname}\n")
    hosts_content = textwrap.dedent(
        f"""\
        127.0.0.1 localhost
        ::1       localhost
        127.0.1.1 {hostname}
        """
    ).strip()
    (rootfs_dir / "etc" / "hosts").write_text(hosts_content + "\n")


def write_apk_repositories(rootfs_dir: Path) -> None:
    repos = textwrap.dedent(
        """\
        https://dl-cdn.alpinelinux.org/alpine/v3.19/main
        https://dl-cdn.alpinelinux.org/alpine/v3.19/community
        """
    )
    repo_path = rootfs_dir / "etc" / "apk" / "repositories"
    ensure_directory(repo_path.parent)
    repo_path.write_text(repos.strip() + "\n")


def write_lab_init_script(role: str, rootfs_dir: Path) -> None:
    local_d = rootfs_dir / "etc" / "local.d"
    ensure_directory(local_d)
    script = local_d / "lab.start"
    role_body = {
        "attacker": textwrap.dedent(
            """\
            if [ -f /opt/lab/attacker/attack_script.py ]; then
                echo "[lab] Launching attack loop" >/dev/console
                python3 /opt/lab/attacker/attack_script.py >/var/log/attacker.log 2>&1 &
            fi
            """
        ),
        "defender": textwrap.dedent(
            """\
            if [ -f /opt/lab/snort/motd ]; then
                cat /opt/lab/snort/motd >/dev/console
            fi
            echo "[lab] Snort shell ready. Type 'found' to submit flag." >/dev/console
            """
        ),
    }.get(role, "echo '[lab] Unknown role' >/dev/console")

    contents = textwrap.dedent(
        f"""\
        #!/bin/sh
        ### Autogenerated init for {role}
        IPC_DIR="/opt/lab/ipc"
        mkdir -p "$IPC_DIR"
        chmod 777 "$IPC_DIR"
        {role_body}
        """
    )
    script.write_text(contents)
    script.chmod(0o755)

    runlevels = rootfs_dir / "etc" / "runlevels" / "default"
    ensure_directory(runlevels)
    (runlevels / "lab").write_text("/etc/local.d/lab.start\n")


def host_supports_chroot() -> bool:
    return os.name != "nt" and shutil.which("chroot") is not None


def run_chroot_command(rootfs_dir: Path, cmd: List[str]) -> None:
    if not host_supports_chroot():
        raise BuildError("chroot is not available on this host; cannot provision packages.")
    run_command(["chroot", str(rootfs_dir)] + cmd)


def provision_packages(role: str, rootfs_dir: Path, skip: bool) -> None:
    if skip:
        logging.info("Skipping package provisioning for %s (--skip-packages).", role)
        return

    packages = ROLE_PACKAGES.get(role, COMMON_PACKAGES)
    if not host_supports_chroot():
        logging.warning(
            "Package provisioning requires chroot. Run on Linux or pass --skip-packages. "
            "Continuing without installing packages for %s.",
            role,
        )
        return

    logging.info("Installing packages for %s: %s", role, ", ".join(packages))
    run_chroot_command(rootfs_dir, ["apk", "update"])
    run_chroot_command(rootfs_dir, ["apk", "add", "--no-cache"] + packages)


def prepare_role_rootfs(role: str, rootfs_src: Path, work_dir: Path, force: bool) -> Path:
    role_rootfs = work_dir / role / "rootfs"
    tarball_symlink = work_dir / "cache_rootfs.tar.gz"
    ensure_directory(tarball_symlink.parent)
    if not tarball_symlink.exists():
        shutil.copy2(rootfs_src, tarball_symlink)

    extract_rootfs(tarball_symlink, role_rootfs, force)
    copy_lab_files(role, role_rootfs)
    configure_hostname(role, role_rootfs)
    write_apk_repositories(role_rootfs)
    write_lab_init_script(role, role_rootfs)
    return role_rootfs


def package_rootfs(role: str, rootfs_dir: Path, dist_dir: Path, image_type: str, size_mb: int) -> Path:
    if image_type == "ext4":
        return package_rootfs_ext4(role, rootfs_dir, dist_dir, size_mb)
    return package_rootfs_tar(role, rootfs_dir, dist_dir)


def package_rootfs_tar(role: str, rootfs_dir: Path, dist_dir: Path) -> Path:
    ensure_directory(dist_dir)
    raw_img = dist_dir / f"{role}.img"
    logging.info("Packaging %s rootfs into %s", role, raw_img)
    with tarfile.open(raw_img, "w") as tar:
        tar.add(rootfs_dir, arcname=".")

    gz_path = raw_img.with_suffix(".img.gz")
    logging.debug("Compressing %s -> %s", raw_img.name, gz_path.name)
    with raw_img.open("rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    raw_img.unlink()
    logging.info("%s packaged (%.1f MB)", gz_path.name, gz_path.stat().st_size / 1e6)
    return gz_path


def package_rootfs_ext4(role: str, rootfs_dir: Path, dist_dir: Path, size_mb: int) -> Path:
    if shutil.which("mke2fs") is None:
        raise BuildError("mke2fs not found; install e2fsprogs or use --image-type tar.")

    ensure_directory(dist_dir)
    raw_img = dist_dir / f"{role}.img"
    size_bytes = size_mb * 1024 * 1024
    logging.info("Creating %s ext4 image (%d MB)", raw_img, size_mb)
    with raw_img.open("wb") as f:
        f.truncate(size_bytes)

    blocks = size_bytes // 4096
    run_command(
        [
            "mke2fs",
            "-t",
            "ext4",
            "-d",
            str(rootfs_dir),
            "-L",
            f"{role}-lab",
            "-m",
            "0",
            str(raw_img),
            str(blocks),
        ]
    )

    gz_path = raw_img.with_suffix(".img.gz")
    logging.debug("Compressing %s -> %s", raw_img.name, gz_path.name)
    with raw_img.open("rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    raw_img.unlink()
    logging.info("%s packaged (%.1f MB)", gz_path.name, gz_path.stat().st_size / 1e6)
    return gz_path


def compute_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def update_manifest(dist_dir: Path, artifacts: Dict[str, Path]) -> None:
    manifest_path = dist_dir / "images.json"
    entries = []
    for role, artifact_path in artifacts.items():
        entries.append(
            {
                "role": role,
                "file": artifact_path.name,
                "size_bytes": artifact_path.stat().st_size,
                "sha256": compute_sha256(artifact_path),
            }
        )

    manifest = {"images": entries}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logging.info("Wrote manifest to %s", manifest_path)


def build_images(config: BuildConfig) -> None:
    ensure_directory(config.build_dir)
    ensure_directory(config.cache_dir)
    ensure_directory(config.dist_dir)

    minirootfs_tar = download_file(
        config.minirootfs_url, config.cache_dir / Path(config.minirootfs_url).name
    )

    artifacts: Dict[str, Path] = {}
    for role in config.roles:
        logging.info("==== Building role: %s ====", role)
        role_rootfs = prepare_role_rootfs(role, minirootfs_tar, config.build_dir, config.force)
        provision_packages(role, role_rootfs, config.skip_packages)
        artifact = package_rootfs(
            role,
            role_rootfs,
            config.dist_dir,
            config.image_type,
            config.image_size_mb,
        )
        artifacts[role] = artifact
        if not config.keep_workdir:
            shutil.rmtree(role_rootfs.parent, onerror=_make_writable_and_retry)
            logging.debug("Removed workdir %s", role_rootfs.parent)

    update_manifest(config.dist_dir, artifacts)


def _make_writable_and_retry(func, path, exc_info):
    del exc_info
    os.chmod(path, stat.S_IWRITE)
    func(path)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)
    roles = args.role or ["attacker", "defender"]
    cache_dir = args.build_dir / "cache"

    config = BuildConfig(
        roles=roles,
        build_dir=args.build_dir,
        dist_dir=args.dist_dir,
        cache_dir=cache_dir,
        force=args.force,
        keep_workdir=args.keep_workdir,
        skip_packages=args.skip_packages,
        image_type=args.image_type,
        image_size_mb=args.image_size_mb,
        minirootfs_url=args.minirootfs_url,
    )

    try:
        build_images(config)
    except BuildError as exc:
        logging.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logging.warning("Build interrupted by user.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
