"""Scaffold a SQLite-backed review app for the Automated Sourcing workflow.

This script is the workflow's API-generation step. It copies the checked-in
`server-template/` (Express + better-sqlite3, modeled on
`ppl-ai/people-search-ui`) into a target directory, drops the rendered UI
bundle into the target's `public/` so it is served by the same host, and
prints the next-step commands the operator runs.

The output is a runnable review-app project:

  <output>/
    package.json          # from server-template
    README.md             # from server-template
    server/index.js       # Express + SQLite, /api/candidates + /api/general-feedback
    scripts/seed.js       # loads review_bundle.json into SQLite
    public/               # rendered UI bundle (recruiting_review_app.html/css/js)
      review_bundle.json  # initial bundle, also used by `npm run seed`

Usage:

    python3 scripts/scaffold_review_app.py \
        --bundle /path/to/review_bundle.json \
        --output /path/to/review-app/

If `--ui-bundle` is omitted, the script renders one from `--bundle` by calling
`formatting.py` itself, so a single command produces both the UI and the API.

Stdlib-only Python. No third-party deps to install before scaffolding; the
Node review-app installs its own deps with `npm install` after this script
runs.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "server-template"
FORMATTING_SCRIPT = SKILL_DIR / "formatting.py"
TEMPLATE_FILES: tuple[str, ...] = (
    "package.json",
    "README.md",
    "server/index.js",
    "scripts/seed.js",
)


def _copy_template(output: Path) -> None:
    for rel in TEMPLATE_FILES:
        src = TEMPLATE_DIR / rel
        if not src.is_file():
            raise FileNotFoundError(f"missing template file: {src}")
        dst = output / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def _copy_ui_bundle(ui_bundle: Path, output: Path) -> None:
    public_dir = output / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "recruiting_review_app.html",
        "recruiting_review_app.css",
        "tokens.css",
        "recruiting_review_app.js",
        "review_bundle.json",
    ):
        src = ui_bundle / name
        if not src.is_file():
            raise FileNotFoundError(f"missing rendered UI file: {src}")
        shutil.copyfile(src, public_dir / name)
    shutil.copyfile(ui_bundle / "recruiting_review_app.html", public_dir / "index.html")


def _render_ui(bundle: Path, output: Path) -> Path:
    ui_dir = output / ".automated-sourcing-ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(FORMATTING_SCRIPT),
            "--input",
            str(bundle),
            "--output",
            str(ui_dir),
        ],
        check=True,
    )
    return ui_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        required=True,
        help="Path to the ReviewBundle JSON exported from the workflow SQLite store.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Target directory to scaffold the review app into.",
    )
    parser.add_argument(
        "--ui-bundle",
        type=Path,
        help=(
            "Pre-rendered UI bundle directory (the renderer's --output). "
            "Omit to render from --bundle in one step."
        ),
    )
    args = parser.parse_args(argv)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    _copy_template(output)

    ui_bundle = (
        args.ui_bundle.resolve()
        if args.ui_bundle
        else _render_ui(args.bundle.resolve(), output)
    )
    _copy_ui_bundle(ui_bundle, output)

    print(f"scaffolded review app at {output}")
    print()
    print("Next steps:")
    print(f"  cd {output}")
    print("  npm install")
    print("  node scripts/seed.js public/review_bundle.json")
    print("  npm start  # http://localhost:3000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
