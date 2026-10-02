"""Build the pip and Chocolatey packages from one version number.

    python packages/build_package.py

1. Builds the wheel and sdist into dist/ (python -m build).
2. Copies the wheel and LICENSE into packages/chocolatey/tools/ and syncs
   the nuspec <version> with tui/__init__.py.
3. Runs `choco pack` into dist/ when Chocolatey is installed.

Publish afterwards with:
    python -m twine upload dist/bitcraft-<version>*.whl dist/bitcraft-<version>.tar.gz
    choco push dist/bitcraft.<version>.nupkg --source https://push.chocolatey.org/
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
CHOCO = REPO / "packages" / "chocolatey"
TOOLS = CHOCO / "tools"
NUSPEC = CHOCO / "bitcraft.nuspec"


def version() -> str:
    text = (REPO / "tui" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', text)
    if not match:
        raise SystemExit("tui/__init__.py has no __version__")
    return match.group(1)


def build_python(ver: str) -> Path:
    for stale in DIST.glob(f"bitcraft-{ver}*"):
        stale.unlink()
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(DIST), str(REPO)], check=True)
    return DIST / f"bitcraft-{ver}-py3-none-any.whl"


def stage_chocolatey(ver: str, wheel: Path) -> None:
    for old in TOOLS.glob("bitcraft-*.whl"):
        old.unlink()
    shutil.copy2(wheel, TOOLS / wheel.name)
    shutil.copy2(REPO / "LICENSE", TOOLS / "LICENSE.txt")
    nuspec = NUSPEC.read_text(encoding="utf-8")
    NUSPEC.write_text(
        re.sub(r"<version>[^<]+</version>", f"<version>{ver}</version>", nuspec, count=1),
        encoding="utf-8",
    )


def pack_chocolatey(ver: str) -> Path | None:
    choco = shutil.which("choco")
    if not choco:
        print("choco not found: skipped `choco pack` (staged files are ready in packages/chocolatey).")
        return None
    subprocess.run([choco, "pack", str(NUSPEC), "--outputdirectory", str(DIST)], check=True)
    return DIST / f"bitcraft.{ver}.nupkg"


def main() -> None:
    ver = version()
    wheel = build_python(ver)
    stage_chocolatey(ver, wheel)
    nupkg = pack_chocolatey(ver)
    print(f"\nbitcraft {ver}")
    for path in sorted(DIST.glob(f"bitcraft*{ver}*")):
        print(f"  {path.relative_to(REPO)}")
    if nupkg is None:
        print("  (Chocolatey package: run `choco pack packages/chocolatey/bitcraft.nuspec` on Windows)")


if __name__ == "__main__":
    main()
