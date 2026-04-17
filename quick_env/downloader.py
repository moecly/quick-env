"""Download utilities."""

import hashlib
import os
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Optional

import requests

MAX_RETRIES = 3


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> bool:
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            if dest.exists():
                dest.unlink()
            if attempt < MAX_RETRIES - 1:
                time.sleep(1 * (attempt + 1))
                continue
            print(f"Download failed: {e}")
            return False
    return False


def download_with_progress(url: str, dest: Path, desc: str = "Downloading") -> bool:
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            dest.parent.mkdir(parents=True, exist_ok=True)

            with open(dest, "wb") as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            percent = (downloaded / total_size) * 100
                            print(f"\r{desc}: {percent:.1f}%", end="", flush=True)
            print()
            return True
        except Exception as e:
            if dest.exists():
                dest.unlink()
            if attempt < MAX_RETRIES - 1:
                time.sleep(1 * (attempt + 1))
                continue
            print(f"Download failed: {e}")
            return False
    return False


def verify_checksum(file: Path, expected: str, algorithm: str = "sha256") -> bool:
    if not file.exists():
        return False
    h = hashlib.new(algorithm)
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    actual = h.hexdigest()
    return actual.lower() == expected.lower()


def extract_tarball(archive: Path, dest: Path) -> Optional[Path]:
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:*") as tf:
            members = tf.getmembers()
            if len(members) == 1 and members[0].isdir():
                tf.extractall(dest)
            else:
                for member in members:
                    if "/" in member.name:
                        parts = member.name.split("/")
                        if parts[0] != members[0].name.split("/")[0]:
                            member.name = members[0].name.split("/")[0] + "/" + member.name
                tf.extractall(dest)
        return dest / members[0].name
    except Exception as e:
        print(f"Extract failed: {e}")
        return None


def extract_zip(archive: Path, dest: Path) -> Optional[Path]:
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "r") as zf:
            members = zf.namelist()
            if len(members) == 1 and members[0].endswith("/"):
                zf.extractall(dest)
            else:
                base = members[0].split("/")[0]
                for member in members:
                    if not member.startswith(base):
                        fixed = base + "/" + member
                        zf.extract(member, dest)
            return dest / base
    except Exception as e:
        print(f"Extract failed: {e}")
        return None


def find_executable_in_dir(directory: Path, name: str) -> Optional[Path]:
    for p in directory.rglob(name):
        if p.is_file():
            return p
    for suffix in ["", ".exe"]:
        p = directory / f"{name}{suffix}"
        if p.exists() and p.is_file():
            return p
    return None


def make_executable(file: Path) -> None:
    file.chmod(file.stat().st_mode | 0o111)


def run_command(cmd: str, shell: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=shell, check=check, capture_output=True, text=True)


if __name__ == "__main__":
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
        print(f"Test file: {f.name}")
