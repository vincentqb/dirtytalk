#!/usr/bin/env python3
"""Build a programmer spellcheck dictionary from per-source wordlists."""

__all__ = ["build", "dirtytalk_from_args"]

import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path


def __dir__():
    return __all__


def build(wordlists_dir: Path, output_dir: Path) -> Path:
    """Concatenate wordlists/*.words into programming.words and compile to .spl.

    Returns the path to the compiled programming.utf-8.spl file. Requires
    `nvim` (or `vim`) on PATH for :mkspell!.
    """
    wordlists_dir = Path(wordlists_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(wordlists_dir.glob("*.words"))
    if not sources:
        raise FileNotFoundError(f"No *.words files in {wordlists_dir}")

    words_path = output_dir / "programming.words"
    words_path.write_bytes(b"".join(p.read_bytes() for p in sources))

    editor = shutil.which("nvim") or shutil.which("vim")
    if not editor:
        raise RuntimeError("nvim or vim is required for :mkspell!")

    # :mkspell! <output-basename> <input> writes <output-basename>.<encoding>.spl
    subprocess.run(
        [
            editor,
            "--headless",
            "--clean",
            "-c",
            f"mkspell! {output_dir / 'programming'} {words_path}",
            "-c",
            "qa",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    spl_path = output_dir / "programming.utf-8.spl"
    if not spl_path.exists():
        raise RuntimeError(f"{editor} :mkspell! did not produce {spl_path}")
    return spl_path


def dirtytalk_from_args(*, prog: str = "dirtytalk") -> None:
    parser = ArgumentParser(prog=prog, description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", description=build.__doc__)
    p_build.add_argument("--wordlists", type=Path, default=Path("wordlists"))
    p_build.add_argument("--output", type=Path, default=Path("."))

    args = parser.parse_args()
    if args.command == "build":
        spl = build(args.wordlists, args.output)
        print(spl, file=sys.stderr)


if __name__ == "__main__":
    dirtytalk_from_args(prog="dirtytalk")
