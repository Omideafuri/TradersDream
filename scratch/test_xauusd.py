import urllib.request
import json
import datetime

url = 'https://query1.finance.yahoo.com/v8/finance/chart/XAU-USD?interval=1h&range=5d'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        meta = data['chart']['result'][0]['meta']
        print('Meta Symbol:', meta.get('symbol'))
        print('Short Name:', meta.get('shortName'))
        print('Instrument Type:', meta.get('instrumentType'))
        print('Regular Market Price:', meta.get('regularMarketPrice'))
        quotes = data['chart']['result'][0]['indicators']['quote'][0]
        ts = data['chart']['result'][0]['timestamp']
        print('Total hourly bars received:', len(ts))
        latest_dt = datetime.datetime.fromtimestamp(ts[-1], tz=datetime.timezone.utc)
        print('Latest timestamp UTC:', latest_dt)
        print('Latest Open:', quotes['open'][-1])
        print('Latest High:', quotes['high'][-1])
        print('Latest Low:', quotes['low'][-1])
        print('Latest Close:', quotes['close'][-1])
        print('Latest Volume:', quotes['volume'][-1])
except Exception as e:
    print('Failed:', e)
