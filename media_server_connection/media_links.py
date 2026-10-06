import re

MBID_PATTERN = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

# public pages that can be linked in the rich presence: (button label, url template, id pattern)
# ids come from user editable server metadata, so only ids matching the pattern are used
LINK_SITES = {
    "imdb": ("IMDb", "https://www.imdb.com/title/{}/", r"tt\d{1,10}"),
    "tmdb_movie": ("TMDB", "https://www.themoviedb.org/movie/{}", r"\d{1,10}"),
    "musicbrainz_release": ("MusicBrainz", "https://musicbrainz.org/release/{}", MBID_PATTERN),
    "musicbrainz_recording": ("MusicBrainz", "https://musicbrainz.org/recording/{}", MBID_PATTERN),
    "audible": ("Audible", "https://www.audible.com/pd/{}", r"[A-Z0-9]{10}"),
    "openlibrary": ("Open Library", "https://openlibrary.org/isbn/{}", r"\d{9}[\dX]|\d{13}"),
    "apple_podcasts": ("Apple Podcasts", "https://podcasts.apple.com/podcast/id{}", r"\d{1,12}"),
}


def media_link(site, media_id):
    """Build a {"label", "url"} link to a public page for the given id, or None if the id is missing or invalid."""
    label, url_template, id_pattern = LINK_SITES[site]
    media_id = str(media_id or "").strip()
    if not re.fullmatch(id_pattern, media_id):
        return None
    return {"label": label, "url": url_template.format(media_id)}


def media_links(*links):
    """Drop the missing links."""
    return [link for link in links if link]
