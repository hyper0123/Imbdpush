import os
import re
import sys
from tmdbv3api import TMDb, Movie

# Inicializar TMDb
tmdb = TMDb()
tmdb.api_key = os.getenv('TMDB_API_KEY')

# Patrón para líneas EXTINF y tvg-logo
EXTINF_LINE = re.compile(r'^#EXTINF:.*?,(?P<title>.+)$')
LOGO_ATTR = re.compile(r'tvg-logo="(.*?)"')


def fetch_logo_url(title):
    """Busca en TMDb el primer resultado y devuelve la URL del póster"""
    if not tmdb.api_key:
        raise RuntimeError("TMDb API key no configurada")
    search = Movie()
    results = search.search(title)
    if results and results[0].poster_path:
        return f"https://image.tmdb.org/t/p/w500{results[0].poster_path}"
    return None


def process_m3u(path):
    updated = False
    lines_out = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            m = EXTINF_LINE.match(line)
            if m:
                logo_m = LOGO_ATTR.search(line)
                if logo_m and logo_m.group(1) == '':
                    title = m.group('title').strip()
                    new_logo = fetch_logo_url(title)
                    if new_logo:
                        line = LOGO_ATTR.sub(f'tvg-logo="{new_logo}"', line)
                        updated = True
            lines_out.append(line)

    if updated:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines_out)
        print(f"✅ Insertados nuevos logos en {path}")
    else:
        print(f"⚠️ No se encontraron entradas sin logo en {path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python fetch_logos.py <ruta/a/tu_playlist.m3u>")
        sys.exit(1)
    process_m3u(sys.argv[1])
