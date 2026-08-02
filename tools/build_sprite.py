#!/usr/bin/env python3
"""APEXFIN inline SVG sprite builder  (O-02 / ADR-007).

Downloads the 27 SEMANTIC-LOCKED Lucide icons from lucide-static@<version>,
emits a single inline SVG sprite (one ``<symbol id="icon-<name>">`` per icon),
and writes a SHA-256 lock file mapping each icon name to its content hash.

Outputs (two copies of the same sprite, by design):
  * static/sprite.svg          -- committed baseline, used by CI comparison
  * templates/_sprite.svg.html -- Jinja fragment inlined via
                                  ``{% include "_sprite.svg.html" %}`` so the
                                  dashboard has ZERO network requests for icons
                                  and works under file:// (external <use
                                  href=".../sprite.svg#x"> is blocked cross-
                                  document by Chrome/Safari under file://).

FAIL-LOUD (exit 3) on:
  * any icon name returns HTTP != 200 (404 / silent rename / version drift)
  * lucide_version in config/icons.yaml != "1.28.0"
  * any output file (sprite / fragment / lock) cannot be written
"""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NoReturn

UA = "APEXFIN-build-sprite/1.0 (+https://github.com/apexfin/apexfin)"

ROOT = Path(__file__).resolve().parent.parent
ICONS_YAML = ROOT / "config" / "icons.yaml"
SPRITE_OUT = ROOT / "static" / "sprite.svg"
SPRITE_FRAGMENT = ROOT / "templates" / "_sprite.svg.html"
LOCK_OUT = ROOT / "config" / "icons.lock"

REQUIRED_VERSION = "1.28.0"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def fail(msg: str) -> NoReturn:
    print(f"[build_sprite] FATAL: {msg}", file=sys.stderr)
    sys.exit(3)


def load_icons() -> tuple[str, list[str]]:
    """Read config/icons.yaml. Prefer pyyaml; fall back to a minimal parser
    because a contributor may run this before installing project deps."""
    text = ICONS_YAML.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(text)
        version = str(cfg.get("lucide_version", ""))
        names = [str(n) for n in cfg.get("icons", [])]
        return version, names
    except ImportError:
        pass
    # Minimal parser for our controlled, comment-heavy YAML.
    version = ""
    names: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("lucide_version:"):
            version = s.split(":", 1)[1].strip().strip('"').strip("'")
        elif s.startswith("- ") and not s.startswith("- " + "-"):
            name = s[2:].split("#", 1)[0].strip()
            if name:
                names.append(name)
    return version, names


def fetch_svg(name: str, version: str) -> bytes:
    url = f"https://unpkg.com/lucide-static@{version}/icons/{name}.svg"
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            # https-only build-time fetcher: pinned lucide-static version + the
            # semantic-locked whitelist in config/icons.yaml. Not a server.
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                if resp.status != 200:
                    fail(f"{name}: HTTP {resp.status} from {url}")
                return resp.read()
        except urllib.error.HTTPError as exc:
            fail(f"{name}: HTTP {exc.code} from {url}")
        except Exception as exc:  # noqa: BLE001 - retry transient SSL EOF
            last = exc
            if attempt < 3:
                time.sleep(1.5 * attempt)
    fail(f"{name}: download failed after 3 attempts: {last}")


def to_symbol(name: str, raw: bytes) -> str:
    try:
        # Parses SVG bodies fetched from the pinned lucide-static@1.28.0 package
        # (trusted upstream) to copy inner elements into a <symbol>.
        root = ET.fromstring(raw)  # noqa: S314
    except ET.ParseError as exc:
        fail(f"{name}: SVG parse error: {exc}")
    if root.tag != f"{{{SVG_NS}}}svg":
        fail(f"{name}: root element is not <svg>")
    inner = "".join(ET.tostring(c, encoding="unicode") for c in root)
    # Drop redundant per-element xmlns; the <symbol> declares it once.
    inner = inner.replace(f'xmlns="{SVG_NS}"', "")
    return (
        f'<symbol id="icon-{name}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</symbol>'
    )


def main() -> None:
    if not ICONS_YAML.exists():
        fail(f"missing {ICONS_YAML}")

    version, names = load_icons()
    if version != REQUIRED_VERSION:
        fail(f"lucide_version '{version}' != required '{REQUIRED_VERSION}'")
    if not names:
        fail("no icons listed in config/icons.yaml")

    symbols: list[str] = []
    lock: dict[str, str] = {}
    for name in names:
        raw = fetch_svg(name, version)
        lock[name] = hashlib.sha256(raw).hexdigest()
        symbols.append(to_symbol(name, raw))

    sprite = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'style="position:absolute;width:0;height:0;overflow:hidden" '
        'aria-hidden="true" focusable="false">\n' + "\n".join(symbols) + "\n</svg>\n"
    )

    try:
        SPRITE_OUT.parent.mkdir(parents=True, exist_ok=True)
        SPRITE_OUT.write_text(sprite, encoding="utf-8")
        SPRITE_FRAGMENT.parent.mkdir(parents=True, exist_ok=True)
        SPRITE_FRAGMENT.write_text(sprite, encoding="utf-8")
        lines = [
            f"# APEXFIN icon lock -- lucide-static@{version} (generated, do not edit)",
            f'version: "{version}"',
        ]
        for n in names:
            lines.append(f"{n}: {lock[n]}")
        LOCK_OUT.parent.mkdir(parents=True, exist_ok=True)
        LOCK_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        fail(f"cannot write output: {exc}")

    print(
        f"[build_sprite] OK: {len(names)} icons -> {SPRITE_OUT.name} + "
        f"{SPRITE_FRAGMENT.name} + {LOCK_OUT.name}"
    )


if __name__ == "__main__":
    main()
