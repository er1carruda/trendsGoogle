from flask import Flask, jsonify, request
from pytrends.request import TrendReq
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)


@app.route('/trends')
def get_trends():
    keyword = request.args.get('keyword', 'nuuvem')
    geo = request.args.get('geo', 'BR')
    timeframe = request.args.get('timeframe', 'today 12-m')

    try:
        pytrends = TrendReq(hl='pt-BR', tz=-180)
        pytrends.build_payload([keyword], geo=geo, timeframe=timeframe)
        df = pytrends.interest_over_time()

        if df.empty:
            return jsonify([])

        df = df.reset_index()
        rows = df[['date', keyword]].rename(columns={keyword: 'value'})
        rows['date'] = rows['date'].dt.strftime('%Y-%m-%d')
        rows['keyword'] = keyword

        return jsonify(rows.to_dict(orient='records'))

    except Exception as e:
        logging.error(f"Error fetching trends: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
