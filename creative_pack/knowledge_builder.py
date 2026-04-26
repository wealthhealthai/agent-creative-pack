"""
knowledge_builder.py — URL text scraper and product knowledge pack writer.

Stage: Pre-pipeline (before Stage 0 scraper.py, which handles visual assets).

PURPOSE
-------
Build a flat-markdown knowledge pack for a client's product.
The knowledge pack is the agent's long-term memory about a product —
what it is, who it's for, what to say, what not to say.
It feeds brief expansion (Stage 1) and informs every creative generation run.

DESIGN PHILOSOPHY
-----------------
This module handles scraping and file I/O only.
The CALLING AGENT is responsible for synthesis — reading raw material,
combining it with what it already knows, and writing the final knowledge pack.

CALLING AGENT RESPONSIBILITIES (not automated here)
----------------------------------------------------
1. Before calling anything in this module, search MEMORY.md,
   memory/*.md, and workspace reference files for existing product
   knowledge. Enterprise agents may be preloaded with accurate product
   info at deploy time — always check first and do not ask the user
   for information you already have.
2. Pass any found context into gather_build_material() via prior_context=.
3. Read the returned BuildMaterial, synthesize all sources into a clean
   knowledge pack (format in AGENT_GUIDE.md), then call write_knowledge_pack()
   with the final content.
4. Confirm sources used to the operator:
   "Saved knowledge pack for [Product]. Sources: [memory / scrape / user-provided]"

PUBLIC API
----------
    scrape_text(url)                          → ScrapeResult | raises ScraperBlockedError
    load_knowledge_pack(client_id, slug)      → str | None
    write_knowledge_pack(client_id, slug, ...) → Path
    gather_build_material(client_id, slug, ...) → BuildMaterial
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Paths ─────────────────────────────────────────────────────────────────────

PACKAGE_ROOT = Path(__file__).parent.parent
KNOWLEDGE_DIR = PACKAGE_ROOT / "knowledge"
KNOWLEDGE_DIR.mkdir(exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────

# Mirrors the Prometheus two-pass approach: full Chrome fingerprint on Pass 1.
CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# Maximum scraped text length. Marketing pages rarely need more.
# Keeps context manageable for brief expansion without truncating important copy.
MAX_CONTENT_CHARS = 12_000

# Short text below this length is treated as a bot block or empty page.
MIN_USEFUL_CHARS = 300

# Signals that indicate a bot-blocker challenge page rather than real content.
BOT_BLOCK_SIGNALS = [
    "access denied",
    "checking your browser",
    "cloudflare",
    "ddos protection",
    "enable javascript and cookies",
    "human verification",
    "just a moment",
    "please verify",
    "security check",
]


# ── Exceptions ────────────────────────────────────────────────────────────────

class ScraperBlockedError(Exception):
    """
    Raised when both scrape passes fail.

    The caller (agent) must surface this to the user with a clear message
    and ask them to paste or upload product content manually.
    Never hallucinate content when this error occurs.
    """
    pass


class KnowledgePackExistsError(FileExistsError):
    """
    Raised when a knowledge pack already exists and overwrite=False.
    Caller should ask the user whether to update the existing pack.
    """
    pass


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ScrapeResult:
    """Result of a successful URL text scrape."""
    text: str
    source: str   # "requests" | "playwright"
    url: str
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


@dataclass
class BuildMaterial:
    """
    All raw material gathered for a knowledge pack build.

    The calling agent reads this, synthesizes all sources into a clean
    knowledge pack (following AGENT_GUIDE.md format), then calls
    write_knowledge_pack() with the final content.
    """
    client_id: str
    product_slug: str
    pack_path: Path
    already_existed: bool
    existing_content: Optional[str]     # content of existing pack, if any
    prior_context: Optional[str]        # from agent memory / reference files
    scraped: Optional[ScrapeResult]     # from URL scrape
    user_text: Optional[str]            # from user-provided paste
    sources_used: list[str] = field(default_factory=list)

    def has_new_material(self) -> bool:
        """True if there is anything to synthesize into a new pack."""
        return bool(self.prior_context or self.scraped or self.user_text)

    def combined_raw(self) -> str:
        """
        Return all raw material concatenated with section headers.
        Useful for the agent to pass into its synthesis prompt.
        """
        parts: list[str] = []
        if self.prior_context and self.prior_context.strip():
            parts.append(
                "=== FROM AGENT MEMORY / REFERENCE FILES ===\n\n"
                + self.prior_context.strip()
            )
        if self.scraped and self.scraped.text.strip():
            parts.append(
                f"=== FROM WEB SCRAPE ({self.scraped.url}) ===\n\n"
                + self.scraped.text.strip()
            )
        if self.user_text and self.user_text.strip():
            parts.append(
                "=== USER-PROVIDED CONTENT ===\n\n"
                + self.user_text.strip()
            )
        return "\n\n---\n\n".join(parts)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_text_from_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to produce readable plain text."""
    # Remove script and style blocks entirely — their text is not useful
    html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str) -> str:
    """Hard cap at MAX_CONTENT_CHARS with a clear marker."""
    if len(text) <= MAX_CONTENT_CHARS:
        return text
    return text[:MAX_CONTENT_CHARS] + f"\n\n[... content truncated at {MAX_CONTENT_CHARS} chars]"


def _looks_blocked(text: str, status_code: int = 200) -> bool:
    """
    Heuristic to detect bot-blocker challenge pages.
    Short content + block signals = blocked.
    """
    if status_code in (403, 429, 503):
        return True
    if len(text) >= MIN_USEFUL_CHARS:
        return False   # long enough to be real content
    lower = text.lower()
    return any(signal in lower for signal in BOT_BLOCK_SIGNALS)


# ── Pass 1: requests + Chrome headers ─────────────────────────────────────────

def _scrape_pass1(url: str) -> Optional[ScrapeResult]:
    """
    Pass 1 — Standard HTTP fetch with a full Chrome header fingerprint.

    Works for ~70% of public marketing pages. Fast, no browser launch overhead.
    Returns None if the response is blocked, thin, or an error.
    """
    try:
        import requests  # type: ignore
    except ImportError:
        print("[knowledge_builder] Pass 1: requests not installed, skipping")
        return None

    try:
        resp = requests.get(
            url,
            headers=CHROME_HEADERS,
            timeout=10,
            allow_redirects=True,
        )
    except Exception as exc:
        print(f"[knowledge_builder] Pass 1: request error — {exc}")
        return None

    text = _extract_text_from_html(resp.text)

    if _looks_blocked(text, resp.status_code):
        print(
            f"[knowledge_builder] Pass 1: blocked or thin "
            f"(status={resp.status_code}, chars={len(text)}) — escalating"
        )
        return None

    text = _truncate(text)
    print(f"[knowledge_builder] Pass 1: OK ({len(text)} chars)")
    return ScrapeResult(text=text, source="requests", url=url)


# ── Pass 2: Playwright headless ───────────────────────────────────────────────

def _scrape_pass2(url: str) -> Optional[ScrapeResult]:
    """
    Pass 2 — Headless Playwright browser.

    Handles JS-rendered SPAs and most basic bot detection (Cloudflare Free,
    simple CAPTCHA-free challenges). Launches a real headless Chromium instance.
    Returns None if still blocked, content is thin, or Playwright is unavailable.

    Note: Does NOT use OpenClaw's browser relay (profile="chrome"). This must
    run headless and unattended — relay requires an attached user tab.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        print("[knowledge_builder] Pass 2: Playwright not installed, skipping")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=CHROME_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                extra_http_headers={
                    k: v for k, v in CHROME_HEADERS.items() if k != "User-Agent"
                },
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            # Allow JS-heavy pages to settle before reading text
            page.wait_for_timeout(2_000)

            # Extract inner text, stripping nav/footer/header noise
            body_text: str = page.evaluate("""() => {
                const strip = ['script', 'style', 'nav', 'footer', 'header', 'aside'];
                strip.forEach(tag => {
                    document.querySelectorAll(tag).forEach(el => el.remove());
                });
                return document.body ? document.body.innerText : '';
            }""")
            browser.close()

        body_text = body_text.strip() if body_text else ""

        if _looks_blocked(body_text):
            print(
                f"[knowledge_builder] Pass 2: still blocked "
                f"(chars={len(body_text)}) — giving up"
            )
            return None

        if len(body_text) < MIN_USEFUL_CHARS:
            print(f"[knowledge_builder] Pass 2: content too thin ({len(body_text)} chars)")
            return None

        body_text = _truncate(body_text)
        print(f"[knowledge_builder] Pass 2: OK ({len(body_text)} chars)")
        return ScrapeResult(text=body_text, source="playwright", url=url)

    except Exception as exc:
        print(f"[knowledge_builder] Pass 2: error — {exc}")
        return None


# ── Public: scrape text ───────────────────────────────────────────────────────

def scrape_text(url: str) -> ScrapeResult:
    """
    Scrape readable text from a URL. Two-pass with explicit hard fail.

    Pass 1: requests + Chrome headers  (fast, no browser)
    Pass 2: Playwright headless        (JS-rendered, bot-resilient)
    Fail:   raises ScraperBlockedError — caller must ask user for manual input.
                                         Never hallucinate content.

    Args:
        url: The URL to scrape.

    Returns:
        ScrapeResult with text content and source label.

    Raises:
        ScraperBlockedError: if both passes fail.
    """
    result = _scrape_pass1(url)
    if result:
        return result

    result = _scrape_pass2(url)
    if result:
        return result

    raise ScraperBlockedError(
        f"Could not retrieve content from {url}. "
        "The site may use Cloudflare Enterprise, a login wall, or advanced "
        "bot detection that cannot be bypassed headlessly. "
        "Please paste the product description or key page content directly "
        "and I will build the knowledge pack from what you provide."
    )


# ── Public: knowledge pack file I/O ──────────────────────────────────────────

def _pack_path(client_id: str, product_slug: str) -> Path:
    return KNOWLEDGE_DIR / f"{client_id}_{product_slug}_knowledge.md"


def load_knowledge_pack(client_id: str, product_slug: str) -> Optional[str]:
    """
    Load an existing knowledge pack if one exists.

    Returns the file content as a string, or None if not found.
    Call this before scraping anything — if a pack already exists,
    the agent may only need to update gaps rather than rebuild from scratch.
    """
    path = _pack_path(client_id, product_slug)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def write_knowledge_pack(
    client_id: str,
    product_slug: str,
    content: str,
    sources_used: list[str],
    author: str = "agent",
    overwrite: bool = False,
) -> Path:
    """
    Write a synthesized knowledge pack to disk.

    The content must already be synthesized by the calling agent into
    the flat-markdown format described in AGENT_GUIDE.md.
    This function adds a metadata comment header and writes to disk.

    Args:
        client_id:    Client identifier (e.g. "helio")
        product_slug: Product slug (e.g. "livertrace")
        content:      Synthesized markdown content (agent-written)
        sources_used: List of source labels used (for operator transparency)
        author:       Agent name, for metadata
        overwrite:    If False and file exists, raises KnowledgePackExistsError

    Returns:
        Path to the written file.

    Raises:
        KnowledgePackExistsError: if file exists and overwrite=False.
    """
    path = _pack_path(client_id, product_slug)

    if path.exists() and not overwrite:
        raise KnowledgePackExistsError(
            f"Knowledge pack already exists at {path}. "
            "Pass overwrite=True to update it, or call load_knowledge_pack() "
            "first to review the existing content."
        )

    sources_str = ", ".join(sources_used) if sources_used else "unknown"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    metadata_header = (
        f"<!-- "
        f"sources: {sources_str} | "
        f"author: {author} | "
        f"built: {timestamp}"
        f" -->\n"
    )

    path.write_text(metadata_header + content, encoding="utf-8")
    print(f"[knowledge_builder] Knowledge pack written: {path}")
    return path


# ── Public: orchestrated gather ───────────────────────────────────────────────

def gather_build_material(
    client_id: str,
    product_slug: str,
    url: Optional[str] = None,
    prior_context: Optional[str] = None,
    user_provided_text: Optional[str] = None,
    overwrite: bool = False,
) -> BuildMaterial:
    """
    Gather all raw material needed to build a knowledge pack.

    This is the main entry point for the calling agent. It collects everything
    available — existing pack, prior context, scraped content — and returns it
    as a BuildMaterial for the agent to synthesize.

    The agent then:
      1. Reads BuildMaterial.combined_raw()
      2. Synthesizes a clean knowledge pack (AGENT_GUIDE.md format)
      3. Calls write_knowledge_pack() with the final synthesized content

    Args:
        client_id:           Client ID (must match brand kit)
        product_slug:        Product slug (e.g. "livertrace")
        url:                 URL to scrape for product information (optional)
        prior_context:       Text extracted by agent from MEMORY.md and workspace
                             reference files. Pass everything relevant — this
                             module does not search files itself.
        user_provided_text:  Text pasted by the user (used if scraping fails or
                             as a supplement). Pass this in when the user provides
                             content directly rather than a URL.
        overwrite:           If False and a pack already exists, returns early
                             with already_existed=True. The agent should ask the
                             user before overwriting.

    Returns:
        BuildMaterial with all gathered content and source metadata.

    Raises:
        ScraperBlockedError: if a URL was provided, user_provided_text was NOT
                             provided as a fallback, and both scrape passes fail.
                             The caller must surface this to the user explicitly.
        ValueError:          if no source material is available at all.
    """
    path = _pack_path(client_id, product_slug)
    sources_used: list[str] = []

    # ── Step 1: Check for existing pack ──────────────────────────────────────
    existing_content: Optional[str] = None
    if path.exists():
        existing_content = path.read_text(encoding="utf-8")
        if not overwrite:
            print(f"[knowledge_builder] Existing pack found: {path}")
            return BuildMaterial(
                client_id=client_id,
                product_slug=product_slug,
                pack_path=path,
                already_existed=True,
                existing_content=existing_content,
                prior_context=prior_context,
                scraped=None,
                user_text=user_provided_text,
                sources_used=["existing"],
            )

    # ── Step 2: Register prior context as a source ────────────────────────────
    if prior_context and prior_context.strip():
        sources_used.append("agent_memory")

    # ── Step 3: Scrape URL or accept user-provided text ───────────────────────
    scraped: Optional[ScrapeResult] = None

    if url:
        if user_provided_text:
            # User already pasted content — skip scraping, use what we have.
            # This may happen when the agent pre-emptively asks for text
            # because it knows the site is likely blocked.
            sources_used.append("user_provided")
        else:
            # Attempt two-pass scrape. ScraperBlockedError propagates to caller.
            scraped = scrape_text(url)
            sources_used.append(f"scrape:{scraped.source}")
    elif user_provided_text and user_provided_text.strip():
        sources_used.append("user_provided")

    # ── Step 4: Validate we have something to work with ───────────────────────
    if not sources_used:
        raise ValueError(
            "No material available to build a knowledge pack. "
            "Provide at least one of: url=, prior_context=, or user_provided_text=."
        )

    return BuildMaterial(
        client_id=client_id,
        product_slug=product_slug,
        pack_path=path,
        already_existed=False,
        existing_content=existing_content,  # None unless overwrite=True
        prior_context=prior_context,
        scraped=scraped,
        user_text=user_provided_text,
        sources_used=sources_used,
    )
