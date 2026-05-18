from datetime import datetime
from time import monotonic
from urllib.parse import quote
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.config import get_public_base_url
from app.dependencies import get_db

router = APIRouter()
SITEMAP_CACHE_TTL_SECONDS = 900
_sitemap_cache: tuple[float, str] | None = None


def _url(base_url: str, *parts: str) -> str:
    path = "/".join(quote(str(part), safe="") for part in parts)
    return f"{base_url}/{path}" if path else f"{base_url}/"


def _lastmod(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.date().isoformat()


def _url_entry(loc: str, lastmod: datetime | None = None) -> str:
    parts = [f"    <loc>{escape(loc)}</loc>"]
    formatted_lastmod = _lastmod(lastmod)
    if formatted_lastmod:
        parts.append(f"    <lastmod>{formatted_lastmod}</lastmod>")
    return "  <url>\n" + "\n".join(parts) + "\n  </url>"


@router.get("/sitemap.xml", response_class=Response)
def generate_sitemap(db: Session = Depends(get_db)):
    global _sitemap_cache

    now = monotonic()
    if _sitemap_cache and now - _sitemap_cache[0] < SITEMAP_CACHE_TTL_SECONDS:
        return Response(
            content=_sitemap_cache[1],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=900"},
        )

    base_url = get_public_base_url()

    entries: list[tuple[str, datetime | None]] = [
        (_url(base_url), None),
        (_url(base_url, "recently_added"), None),
        (_url(base_url, "playlists"), None),
        (_url(base_url, "options"), None),
        (_url(base_url, "about"), None),
        (_url(base_url, "producers"), None),
        (_url(base_url, "voicebanks"), None),
    ]

    # Add public playlists
    public_playlists = db.query(models.Playlist).filter(models.Playlist.is_public).all()
    for p in public_playlists:
        entries.append((_url(base_url, "playlist", str(p.id)), p.created_at))

    producer_rows = (
        db.query(models.Producer.name, func.max(models.Track.published_date))
        .outerjoin(models.Producer.tracks)
        .group_by(models.Producer.id, models.Producer.name)
        .all()
    )
    for name, latest_track in producer_rows:
        entries.append((_url(base_url, "producer", name), latest_track))

    voicebank_rows = (
        db.query(models.Voicebank.name, func.max(models.Track.published_date))
        .outerjoin(models.Voicebank.tracks)
        .group_by(models.Voicebank.id, models.Voicebank.name)
        .all()
    )
    for name, latest_track in voicebank_rows:
        entries.append((_url(base_url, "voicebank", name), latest_track))

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'

    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(_url_entry(loc, lastmod) for loc, lastmod in entries)
    sitemap += "\n"
    sitemap += "</urlset>"
    _sitemap_cache = (now, sitemap)

    return Response(
        content=sitemap,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=900"},
    )
