import os
import re
import sys
from tmdbv3api import TMDb, Movie

# Inicializar TMDb

tmdb = TMDb()
# La clave se toma del secreto de GitHub Actions

tmdb.api_key = os.getenv('TMDB_API_KEY')

# Expresión para extraer cada línea EXTINF de tu M3U
MOVIE_LINE_RE = re.compile(
    r'(#EXTINF:-1\s+tvg-name="(?P<name>.*?)"\s+tvg-id="(?P<id>.*?)"\s+tvg-logo="(?P<logo>.*?)"\s+group-title="(?P<group>.*?)",(?P<title>.*))'
)


def fetch_logo_url(title):
    """Busca en TMDb el primer resultado de la película y devuelve la URL del póster"""
    search = Movie()
    results = search.search(title)
    if results:
        poster = results[0].poster_path
        if poster:
            return f"https://image.tmdb.org/t/p/w500{poster}"
    return None


def process_m3u(path):
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            match = MOVIE_LINE_RE.match(line)
            if match:
                logo = match.group('logo')
                title = match.group('title')
                if not logo:
                    new_logo = fetch_logo_url(title)
                    if new_logo:
                        line = re.sub(r'tvg-logo=".*?"', f'tvg-logo="{new_logo}"', line)
            lines.append(line)

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u>")
        sys.exit(1)
    process_m3u(sys.argv[1])
