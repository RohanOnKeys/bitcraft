"""Build an air-gapped install bundle for a Linux machine with no network.

    python packages/offline_bundle.py [--out dist/offline] [--python 3.11]

Run on a connected machine. The bundle holds everything BitCraft downloads
at setup time:

    wheelhouse/      Linux wheels for the TUI, pipeline and API (+ bitcraft)
    images.tar       Docker images (ml, backend, postgres, redis), if Docker
                     is available and `docker compose build` has run
    datasets/        the dataset CSVs, generated metadata and GeoIP databases
    repo.tar.gz      this repository (git archive of HEAD)
    install.sh       offline installer for the target machine

Copy the folder across, then on the target: `bash install.sh`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IMAGES = ("bitcraft-ml", "bitcraft-backend", "postgres:16-alpine", "redis:7-alpine")
# No published wheels; pure Python, so a locally built wheel runs anywhere.
SOURCE_ONLY = ("python-louvain",)

INSTALL_SH = """#!/usr/bin/env bash
# BitCraft offline installer: no network access needed.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bitcraft && tar -xzf repo.tar.gz -C bitcraft
cp -r datasets/. bitcraft/datasets/

if [ -f images.tar ] && command -v docker >/dev/null; then
  echo "Loading Docker images ..."
  docker load -i images.tar
  echo "Start the full stack with:  cd bitcraft && docker compose up --no-build"
fi

echo "Installing Python packages from the local wheelhouse ..."
python3 -m venv bitcraft/.venv
bitcraft/.venv/bin/pip install --no-index --find-links wheelhouse \\
    -r bitcraft/requirements.txt -r bitcraft/backend/requirements.txt
bitcraft/.venv/bin/pip install --no-index --find-links wheelhouse --no-deps -e bitcraft
echo
echo "Done. Next:"
echo "  cd bitcraft && source .venv/bin/activate"
echo "  python -m ml.pipeline && (cd backend && python -m app.loader)"
echo "  bitcraft"
"""


def run(cmd: list[str], **kwargs) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, **kwargs)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build an offline install bundle for Linux")
    parser.add_argument("--out", type=Path, default=REPO / "dist" / "offline")
    parser.add_argument("--python", default="3.11", help="target Python version, e.g. 3.11")
    parser.add_argument("--platform", default="manylinux2014_x86_64")
    parser.add_argument("--no-images", action="store_true", help="skip saving Docker images")
    args = parser.parse_args(argv)

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    wheelhouse = out / "wheelhouse"
    wheelhouse.mkdir(parents=True)

    # Linux wheels for every dependency, built for the target interpreter.
    # Source-only packages (pure Python) are built into universal wheels here.
    requirements = [
        line.strip()
        for path in (REPO / "requirements.txt", REPO / "backend" / "requirements.txt")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    binary = [r for r in requirements if not r.startswith(SOURCE_ONLY)]
    source = [r for r in requirements if r.startswith(SOURCE_ONLY)]
    run([
        sys.executable, "-m", "pip", "download", "--dest", str(wheelhouse),
        "--only-binary=:all:", "--platform", args.platform,
        "--python-version", args.python, "--implementation", "cp",
        *binary, "textual>=5.0", "httpx>=0.27", "pillow>=10.0", "setuptools>=77", "wheel",
    ])
    if source:
        run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheelhouse), *source])
    run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse), str(REPO)])

    with open(out / "repo.tar.gz", "wb") as handle:
        run(["git", "archive", "--format=tar.gz", "HEAD"], cwd=REPO, stdout=handle)

    datasets = out / "datasets"
    shutil.copytree(REPO / "datasets", datasets, ignore=shutil.ignore_patterns(".gitkeep", "*.zip"))

    if not args.no_images and shutil.which("docker"):
        present = [
            image for image in IMAGES
            if subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode == 0
        ]
        if present:
            run(["docker", "save", "-o", str(out / "images.tar"), *present])
        missing = sorted(set(IMAGES) - set(present))
        if missing:
            print(f"note: images not found, run `docker compose build` first: {', '.join(missing)}")

    (out / "install.sh").write_text(INSTALL_SH, encoding="utf-8", newline="\n")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) / 1e9
    print(f"\nbundle ready: {out} ({size:.2f} GB). Copy it over, then run: bash install.sh")


if __name__ == "__main__":
    main()
