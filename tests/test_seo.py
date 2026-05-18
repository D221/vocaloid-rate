from xml.etree import ElementTree


def test_sitemap_lists_public_pages_and_encoded_entity_urls(
    client_factory, sample_tracks
):
    client = client_factory()

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.headers["cache-control"] == "public, max-age=900"

    root = ElementTree.fromstring(response.text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [loc.text for loc in root.findall(".//sm:loc", namespace)]

    assert "https://vocaloid-rate.vercel.app/about" in locs
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


def test_producers_page_has_specific_seo_copy(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/producers")

    assert response.status_code == 200
    assert "<title>Vocaloid Producers - Vocaloid Rate</title>" in response.text
    assert "Browse Vocaloid producers" in response.text
    assert "Explore Entities" not in response.text


def test_voicebank_page_has_specific_seo_copy(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/voicebank/Miku")

    assert response.status_code == 200
    assert "<title>Miku Vocaloid Songs - Vocaloid Rate</title>" in response.text
    assert "Newest Vocaloid tracks featuring Miku." in response.text
    assert "Tracks by this entity" not in response.text


def test_about_page_renders_public_explanation(client_factory):
    client = client_factory()

    response = client.get("/about")

    assert response.status_code == 200
    assert "<title>About Vocaloid Rate - Vocaloid Rate</title>" in response.text
    assert "discover songs, rate tracks, build playlists" in response.text


def test_about_link_is_available_sitewide(client_factory):
    client = client_factory()

    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/about"' in response.text
