from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app import models
from app.dependencies import get_db

router = APIRouter()


@router.get("/sitemap.xml", response_class=Response)
def generate_sitemap(db: Session = Depends(get_db)):
    # Base URL for your deployment (update this!)
    base_url = "https://vocaloid-rate.vercel.app"

    urls = [
        f"{base_url}/",
        f"{base_url}/recently_added",
        f"{base_url}/playlists",
        f"{base_url}/options",
    ]

    # Add public playlists
    public_playlists = db.query(models.Playlist).filter(models.Playlist.is_public).all()
    for p in public_playlists:
        urls.append(f"{base_url}/playlist/{p.id}")

    # Add producer hubs
    producers = db.query(models.Producer).all()
    for p in producers:
        urls.append(f"{base_url}/producer/{p.name}")

    # Add voicebank hubs
    voicebanks = db.query(models.Voicebank).all()
    for v in voicebanks:
        urls.append(f"{base_url}/voicebank/{v.name}")

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'

    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        sitemap += f"  <url><loc>{url}</loc></url>\n"
    sitemap += "</urlset>"

    return Response(content=sitemap, media_type="application/xml")
