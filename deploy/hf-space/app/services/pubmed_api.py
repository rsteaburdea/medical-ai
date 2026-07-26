from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


async def search_pubmed(query: str, retmax: int = 5) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
        "email": settings.pubmed_email,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        search_resp = await client.get(ESEARCH, params=params)
        search_resp.raise_for_status()
        data = search_resp.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            "email": settings.pubmed_email,
        }
        fetch_resp = await client.get(EFETCH, params=fetch_params)
        fetch_resp.raise_for_status()
        return _parse_pubmed_xml(fetch_resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    articles: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID") or ""
        title = " ".join((article.findtext(".//ArticleTitle") or "").split())
        abstract_parts = [
            " ".join("".join(node.itertext()).split())
            for node in article.findall(".//Abstract/AbstractText")
        ]
        abstract = " ".join(abstract_parts)
        journal = article.findtext(".//Journal/Title") or ""
        year = article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate") or ""
        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": year,
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return articles


def format_articles_context(articles: list[dict[str, Any]]) -> str:
    if not articles:
        return "No PubMed articles retrieved."
    blocks = []
    for i, a in enumerate(articles, 1):
        blocks.append(
            f"[{i}] PMID {a['pmid']} — {a['title']} ({a.get('journal', '')}, {a.get('year', '')})\n"
            f"Abstract: {a.get('abstract') or 'N/A'}\n"
            f"URL: {a.get('pubmed_url')}"
        )
    return "\n\n".join(blocks)
