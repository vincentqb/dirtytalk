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

import yaml
from bs4 import BeautifulSoup


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


# Curated tails the legacy bash scripts appended after each scraped source.
# Kept inline so the whole pipeline lives in one file.
ACRONYMS_EXTRA: tuple[str, ...] = (
    "3DES", "APIs", "APK", "AXFR", "BSSID", "CAs", "CCMP", "CSPRNG", "CVSS",
    "CWE", "DMARC", "DNSSEC", "DSGVO", "ECB", "EDNS", "GC", "GDPR", "GNSS",
    "HKLM", "HMAC", "HSTS", "HTA", "IAM", "IBAN", "IBANs", "IDN", "JWT",
    "KDF", "LTS", "MD5", "MITM", "MTAs", "OCSP", "OSINT", "PEM", "R2",
    "RC4", "RCE", "SNI", "SSRF", "TKIP", "TOTP", "U2F", "XHR",
)  # fmt: skip

BRANDS_EXTRA: tuple[str, ...] = (
    "Acronis", "AMD64", "AngularJS", "Artifactory", "BitLocker", "Chromebook",
    "CloudFormation", "CloudTrail", "Coverity", "Cppcheck", "Defender",
    "DigiCert", "Duqu", "Entra", "FortiGate", "FOSSGIS", "Foxit", "GitLab's",
    "GlobalSign", "Hoek", "iPhones", "jsoup", "Karaf", "Log4j", "Lync",
    "Mailchimp", "MailHog", "Nessus", "Netgear", "Nvidia", "Office", "OkHttp",
    "OneDrive's", "OpenPhish", "OSTIF", "PKZIP", "PowerDNS", "PrivateLink",
    "Protection", "PRTG", "PSFTPd", "reCAPTCHA", "reCAPTCHA's", "Semgrep",
    "SendGrid", "Sophos", "Splashtop", "Threema's", "TinyMCE", "TopAccess",
    "Vertica", "Wazuh", "YubiKey", "YubiKey's", "YubiKeys",
)  # fmt: skip

UNIX_EXTRA: tuple[str, ...] = ("cron", "gpg", "podman", "rsync", "sudo", "tcpdump")

# Names of wordlists/<name>.words files that are hand-curated. `fetch` leaves
# them alone; `build` still concatenates them with everything else.
STATIC_WORDLISTS: frozenset[str] = frozenset({"comments", "jargon", "names"})


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


@source("acronyms")
def acronyms() -> list[str]:
    """Common IT acronyms from the Wikipedia list page, plus a curated tail."""
    soup = BeautifulSoup(
        http_get("https://en.wikipedia.org/wiki/List_of_computing_and_IT_abbreviations"),
        "html.parser",
    )
    out = [text for a in soup.select("li > a[title]") if re.fullmatch(r"[A-Za-z0-9.]+", text := a.get_text().strip())]
    out.extend(ACRONYMS_EXTRA)
    return out


@source("algorithms")
def algorithms() -> list[str]:
    """Algorithm and data-structure names from two Wikipedia list pages."""
    out: list[str] = []
    for url in (
        "https://en.wikipedia.org/wiki/List_of_algorithms",
        "https://en.wikipedia.org/wiki/List_of_data_structures",
    ):
        soup = BeautifulSoup(http_get(url), "html.parser")
        for a in soup.select(".mw-parser-output li > a[title]"):
            text = re.sub(r"\(.*\)$", "", a.get_text()).strip()
            out.extend(text.split())
    return out


@source("brands")
def brands() -> list[str]:
    """Popular IT-related brand names from simple-icons + curated tail."""
    data = json.loads(
        http_get("https://raw.githubusercontent.com/simple-icons/simple-icons/master/data/simple-icons.json")
    )
    # Schema: a flat list of {"title": "...", ...} (was {"icons": [...]} pre-2024).
    out = [w for icon in data for w in str(icon.get("title", "")).split() if re.search(r"[A-Za-z]", w)]
    out.extend(BRANDS_EXTRA)
    return out


@source("cpp")
def cpp_glossary() -> list[str]:
    """C++-related vocabulary from Stroustrup's glossary."""
    soup = BeautifulSoup(http_get("https://www.stroustrup.com/glossary.html"), "html.parser")
    return [w for b in soup.find_all("b") for w in b.get_text().split() if re.search(r"[A-Za-z]", w)]


@source("docker")
def docker_glossary() -> list[str]:
    """Docker-related vocabulary from docker/docs glossary.yaml top-level keys."""
    data = yaml.safe_load(http_get("https://raw.githubusercontent.com/docker/docs/main/data/glossary.yaml"))
    return list(data.keys()) if isinstance(data, dict) else []


@source("html")
def html_tags() -> list[str]:
    """HTML tag names from MDN's element index."""
    soup = BeautifulSoup(http_get("https://developer.mozilla.org/en-US/docs/Web/HTML/Element"), "html.parser")
    return [
        m.group(1)
        for code in soup.find_all("code")
        if (m := re.fullmatch(r"<([a-zA-Z][a-zA-Z0-9]*)>", code.get_text().strip()))
    ]


@source("nerd-fonts")
def nerd_fonts() -> list[str]:
    """Nerd Fonts codepoints, marked '/?' so :mkspell! treats them as rare."""
    soup = BeautifulSoup(http_get("https://www.nerdfonts.com/cheat-sheet"), "html.parser")
    script = soup.find("script")
    if script is None or not script.string:
        return []
    # The cheat-sheet embeds an array of '"abcd",' tuples — the 4-hex codepoint.
    return [chr(int(cp, 16)) + "/?" for cp in re.findall(r'"([0-9a-f]{4})",', script.string)]


@source("prometheus")
def prometheus_glossary() -> list[str]:
    """Prometheus-related vocabulary from the upstream glossary markdown."""
    md = http_get("https://raw.githubusercontent.com/prometheus/docs/main/docs/introduction/glossary.md")
    md = "\n".join(md.splitlines()[2:])  # drop front-matter
    md = re.sub(r"\]\([^)]*\)", "]", md)  # strip [text](url) link targets
    return [w for w in re.split(r"[^A-Za-z]+", md) if len(w) > 1]


@source("unix")
def unix_commands() -> list[str]:
    """UNIX command names from coreutils + POSIX utilities."""
    out: list[str] = []
    readme = http_get("https://git.savannah.gnu.org/cgit/coreutils.git/plain/README")
    if m := re.search(
        r"The programs that can be built with this package are:\s*\n(.+?)\n\s*See the file NEWS",
        readme,
        re.DOTALL,
    ):
        out.extend(re.findall(r"[a-z][a-z0-9]+", m.group(1)))
    soup = BeautifulSoup(
        http_get("https://pubs.opengroup.org/onlinepubs/9699919799.2018edition/idx/utilities.html"),
        "html.parser",
    )
    out.extend(text for a in soup.find_all("a") if re.fullmatch(r"[a-z][a-z0-9]*", text := a.get_text().strip()))
    out.extend(UNIX_EXTRA)
    return out


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
