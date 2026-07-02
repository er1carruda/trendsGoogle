from flask import Flask, jsonify, request
from pytrends.request import TrendReq
import requests as http_requests
import xml.etree.ElementTree as ET
import logging
import os
import time
import threading

try:
    from pytrends.exceptions import TooManyRequestsError
except Exception:  # pytrends version without the dedicated class
    TooManyRequestsError = None

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Cache TTL in seconds (default 12h). Trends interest is a daily-granularity
# signal, so within a day repeat/retry calls can be served from cache instead
# of hitting Google again.
CACHE_TTL = int(os.environ.get('TRENDS_CACHE_TTL', 12 * 60 * 60))

# pytrends retry/backoff/timeout tuning (all overridable via env).
RETRIES = int(os.environ.get('TRENDS_RETRIES', 3))
BACKOFF_FACTOR = float(os.environ.get('TRENDS_BACKOFF_FACTOR', 0.6))
CONNECT_TIMEOUT = int(os.environ.get('TRENDS_CONNECT_TIMEOUT', 10))
READ_TIMEOUT = int(os.environ.get('TRENDS_READ_TIMEOUT', 25))

_cache = {}
_cache_lock = threading.Lock()


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
    if not entry:
        return None, False
    payload, ts = entry
    fresh = (time.time() - ts) < CACHE_TTL
    return payload, fresh


def _cache_set(key, payload):
    with _cache_lock:
        _cache[key] = (payload, time.time())


def _is_rate_limited(exc):
    if TooManyRequestsError is not None and isinstance(exc, TooManyRequestsError):
        return True
    text = str(exc).lower()
    return '429' in text or 'too many requests' in text


def _make_trendreq():
    return TrendReq(
        hl='pt-BR',
        tz=-180,
        retries=RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )


@app.route('/trends')
def get_trends():
    keyword = request.args.get('keyword', 'nuuvem')
    geo = request.args.get('geo', 'BR')
    timeframe = request.args.get('timeframe', 'today 12-m')
    key = (keyword, geo, timeframe)

    cached, fresh = _cache_get(key)
    if cached is not None and fresh:
        return jsonify(cached)

    try:
        pytrends = _make_trendreq()
        pytrends.build_payload([keyword], geo=geo, timeframe=timeframe)
        df = pytrends.interest_over_time()

        if df.empty:
            _cache_set(key, [])
            return jsonify([])

        df = df.reset_index()
        rows = df[['date', keyword]].rename(columns={keyword: 'value'})
        rows['date'] = rows['date'].dt.strftime('%Y-%m-%d')
        rows['keyword'] = keyword
        result = rows.to_dict(orient='records')

        _cache_set(key, result)
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error fetching trends for {key}: {e}")
        # Stale-on-error: if we have any previous value (even expired), serve it
        # rather than failing — a slightly old interest number beats nothing.
        if cached is not None:
            logging.warning(f"Serving stale cache for {key}")
            return jsonify(cached)
        if _is_rate_limited(e):
            return jsonify({'error': 'rate limited by Google', 'detail': str(e)}), 429
        return jsonify({'error': str(e)}), 500


@app.route('/trending')
def get_trending():
    geo = request.args.get('geo', 'BR')
    top = int(request.args.get('top', 10))

    try:
        r = http_requests.get(
            'https://trends.google.com/trending/rss',
            params={'geo': geo},
            timeout=10
        )
        r.raise_for_status()

        ns = {'ht': 'https://trends.google.com/trending/rss'}
        root = ET.fromstring(r.text)
        items = root.findall('./channel/item')[:top]

        def parse_traffic(item):
            raw = item.findtext('ht:approx_traffic', namespaces=ns) or '0+'
            return int(raw.replace('+', '').replace(',', ''))

        items.sort(key=parse_traffic, reverse=True)

        result = [
            {
                'rank': i + 1,
                'title': item.findtext('title'),
                'traffic': item.findtext('ht:approx_traffic', namespaces=ns),
                'date': item.findtext('pubDate'),
            }
            for i, item in enumerate(items)
        ]
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error fetching trending searches: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
