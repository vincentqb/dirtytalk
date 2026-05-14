#!/usr/bin/env python3
"""Build a programmer spellcheck dictionary from per-source wordlists."""

__all__ = ["SOURCES", "build", "dirtytalk_from_args", "fetch", "fetch_all"]

import json
import re
import shutil
import subprocess
import sys
import urllib.request
from argparse import ArgumentParser
from collections.abc import Callable, Iterable
from pathlib import Path


def __dir__():
    return __all__


# --- HTTP -------------------------------------------------------------------


def http_get(url: str, *, timeout: float = 30.0) -> str:
    """Fetch a URL and return decoded text."""
    req = urllib.request.Request(url, headers={"User-Agent": "dirtytalk"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# --- source registry --------------------------------------------------------

SOURCES: dict[str, Callable[[], Iterable[str]]] = {}


def source(name: str) -> Callable[[Callable[[], Iterable[str]]], Callable[[], Iterable[str]]]:
    """Decorator to register a fetcher under SOURCES[name]."""

    def deco(fn: Callable[[], Iterable[str]]) -> Callable[[], Iterable[str]]:
        SOURCES[name] = fn
        return fn

    return deco


# --- fetchers ---------------------------------------------------------------


@source("python")
def python_glossary() -> list[str]:
    """Python glossary terms from cpython's Doc/glossary.rst."""
    text = http_get("https://raw.githubusercontent.com/python/cpython/main/Doc/glossary.rst")
    # Glossary terms are indented by 3 spaces and start with a word character.
    return [
        word
        for line in text.splitlines()
        if re.match(r"^   \w", line)
        for word in line.split()
        if re.search(r"[A-Za-z]", word)
    ]


@source("kubernetes")
def kubernetes_kinds() -> list[str]:
    """Kinds of Kubernetes objects from the openapi swagger spec."""
    data = json.loads(
        http_get("https://raw.githubusercontent.com/kubernetes/kubernetes/master/api/openapi-spec/swagger.json")
    )
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            gvks = node.get("x-kubernetes-group-version-kind")
            if isinstance(gvks, list):
                out.extend(gvk["kind"] for gvk in gvks if isinstance(gvk, dict) and "kind" in gvk)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return out


@source("git")
def git_glossary() -> list[str]:
    """Git-related vocabulary from glossary-content.adoc."""
    text = http_get("https://raw.githubusercontent.com/git/git/master/Documentation/glossary-content.adoc")
    # AsciiDoc term lines look like:  [[def_foo]]foo bar::
    out: list[str] = []
    for match in re.finditer(r"^\[\[[^\]]+\]\](.+?)::\s*$", text, re.MULTILINE):
        out.extend(re.findall(r"[A-Za-z][\w-]*", match.group(1)))
    return out


@source("file-extensions")
def file_extensions() -> list[str]:
    """Common file extensions from vim-polyglot + file-extension-list."""
    polyglot = http_get("https://raw.githubusercontent.com/sheerun/vim-polyglot/master/autoload/polyglot/init.vim")
    exts = list(re.findall(r"\.[a-z]+", polyglot))
    list_data = json.loads(
        http_get("https://raw.githubusercontent.com/dyne/file-extension-list/master/pub/extensions.json")
    )
    exts.extend(f".{key}" for key in list_data)
    return exts


@source("lorem-ipsum")
def lorem_ipsum() -> list[str]:
    """Words used in the standard Lorem Ipsum passage."""
    text = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
        "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis "
        "nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. "
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu "
        "fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
        "culpa qui officia deserunt mollit anim id est laborum."
    )
    return [w.strip(".,").lower() for w in text.split()]


@source("versions")
def versions() -> list[str]:
    """Version numbers v0..v99."""
    return [f"v{i}" for i in range(100)]


# --- emit -------------------------------------------------------------------


def emit_words(words: Iterable[str]) -> str:
    """Sort/uniq a wordlist and apply the upstream slash-handling for compounds.

    Replicates the legacy `sort | uniq | grep -v '^$' | sed 's,/(.|$),,\\1,g'`
    pipeline from scripts/common.sh: words containing '/<char>' (e.g. 'a/b')
    become 'a,b' so :mkspell! treats them as comma-separated equivalents.
    Words ending with '/?' are kept verbatim (rare-word marker).
    """
    cleaned = sorted({w for w in (w.strip() for w in words) if w})
    return "\n".join(re.sub(r"/([^?]|$)", r",\1", w) for w in cleaned) + "\n"


def fetch(name: str) -> str:
    """Run the fetcher named `name` and return a sorted/uniqued wordlist text."""
    if name not in SOURCES:
        raise KeyError(f"Unknown source: {name!r}. Known: {sorted(SOURCES)}")
    return emit_words(SOURCES[name]())


def fetch_all(wordlists_dir: Path) -> dict[str, BaseException | None]:
    """Run every fetcher, write each to wordlists/<name>.words.

    Returns a dict of name -> None on success, or the exception that fired.
    Failures are logged and skipped; remaining sources still run.
    """
    wordlists_dir = Path(wordlists_dir).resolve()
    wordlists_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, BaseException | None] = {}
    for name in sorted(SOURCES):
        try:
            text = fetch(name)
            (wordlists_dir / f"{name}.words").write_text(text, encoding="utf-8")
            results[name] = None
            print(f"  ok    {name}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — one source failing must not kill all
            results[name] = exc
            print(f"  fail  {name}: {exc}", file=sys.stderr)
    return results


# --- build ------------------------------------------------------------------


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


# --- CLI --------------------------------------------------------------------


def dirtytalk_from_args(*, prog: str = "dirtytalk") -> None:
    parser = ArgumentParser(prog=prog, description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", description=build.__doc__)
    p_build.add_argument("--wordlists", type=Path, default=Path("wordlists"))
    p_build.add_argument("--output", type=Path, default=Path("."))

    p_fetch = sub.add_parser("fetch", description=fetch_all.__doc__)
    p_fetch.add_argument(
        "names",
        nargs="*",
        help="sources to fetch; default: all registered sources",
    )
    p_fetch.add_argument("--wordlists", type=Path, default=Path("wordlists"))

    p_list = sub.add_parser("list", description="List registered fetchers.")
    del p_list  # silence unused-var warnings

    args = parser.parse_args()

    if args.command == "build":
        spl = build(args.wordlists, args.output)
        print(spl, file=sys.stderr)
    elif args.command == "fetch":
        names = args.names or sorted(SOURCES)
        Path(args.wordlists).mkdir(parents=True, exist_ok=True)
        any_failed = False
        for name in names:
            try:
                text = fetch(name)
                (args.wordlists / f"{name}.words").write_text(text, encoding="utf-8")
                print(f"  ok    {name}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                any_failed = True
                print(f"  fail  {name}: {exc}", file=sys.stderr)
        raise SystemExit(1 if any_failed else 0)
    elif args.command == "list":
        for name in sorted(SOURCES):
            print(name)


if __name__ == "__main__":
    dirtytalk_from_args(prog="dirtytalk")
