import os
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

# llmstxt plugin preprocess: put each page's own URL under its title, as a "Source:" line, so
# something reading the combined llms-full.txt can link to the page it found. The plugin only
# passes the page's output .md path, so the URL is worked out from where that sits in the site directory.

# Keep in step with the llmstxt plugin's base_url in properdocs.yml
BASE_URL = "https://autoarm.rhizomatics.org.uk/"
# Where on_config leaves the site directory, since the plugin loads this module separately from the hook
SITE_DIR_ENV = "AUTOARM_DOCS_SITE_DIR"


def on_config(config: Any) -> None:
    """Properdocs hook, recording the site directory, which `serve` points at a temporary directory"""
    os.environ[SITE_DIR_ENV] = str(config.site_dir)


def preprocess(soup: BeautifulSoup, output: str) -> None:
    site_dir = Path(os.environ[SITE_DIR_ENV])
    page = Path(output).resolve().relative_to(site_dir.resolve()).as_posix()
    url = BASE_URL + page.removesuffix("index.md")
    source = soup.new_tag("p")
    source.string = f"Source: {url}"
    if title := soup.find("h1"):
        title.insert_after(source)
    else:
        soup.insert(0, source)
