from xml.etree import ElementTree


def test_sitemap_lists_public_pages_and_encoded_entity_urls(
    client_factory, sample_tracks
):
    client = client_factory()

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ElementTree.fromstring(response.text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [loc.text for loc in root.findall(".//sm:loc", namespace)]

    assert "https://vocaloid-rate.vercel.app/producers" in locs
    assert "https://vocaloid-rate.vercel.app/voicebanks" in locs
    assert "https://vocaloid-rate.vercel.app/producer/Producer%20A" in locs
    assert "https://vocaloid-rate.vercel.app/voicebank/Miku" in locs


def test_robots_points_to_configured_sitemap(client_factory, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/")
    client = client_factory()

    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert "Allow: /" in response.text
    assert "Sitemap: https://example.test/sitemap.xml" in response.text


def test_pages_render_canonical_url(client_factory):
    client = client_factory()

    response = client.get("/options")

    assert response.status_code == 200
    assert '<link rel="canonical" href="https://vocaloid-rate.vercel.app/options"' in (
        response.text
    )
