"""DataPilot web API, shared by local HTTP and production WSGI transports."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import math
import logging
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse
import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs
from services.workspace_service import Workspace
from services.chart_service import ChartService
from services.llm_service import LLMService
from services.duckdb_service import DuckDBService
from services.config import Settings, load_env_file
from services.profile_service import column_profile
from ml.anomaly_detection import AnomalyDetector
from pages.dashboard import show_dashboard
from pages.dataset_explorer import show_dataset_explorer
from pages.data_quality import show_data_quality
from pages.insights import show_insights
from pages.segmentation import show_segmentation
from pages.ai_chat import show_ai_chat

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'data/raw/online_retail_II.xlsx'
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
REFERENCE_CACHE = {}
REFERENCE_LOCK = threading.Lock()
MAX_UPLOAD = 100 * 1024 * 1024
PLOTLY_JS = None
log = logging.getLogger('datapilot')


def serial(value):
    if isinstance(value, pd.DataFrame):
        return {'columns': list(value.columns), 'rows': json.loads(value.head(1000).to_json(orient='records', date_format='iso')),
                'total_rows': len(value), 'truncated': len(value) > 1000 or bool(value.attrs.get('truncated'))}
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def attach_charts(payload):
    if not isinstance(payload, dict):
        return payload
    for item in payload.get('analyses', []):
        if 'figure' not in item:
            fig = ChartService().create_chart(item['table'], item['kind'], item['x'], item['y'], item['title'])
            if fig:
                fig.update_layout(title=None)
            item['figure'] = json.loads(fig.to_json()) if fig else None
    if payload.get('visualization') and 'table' in payload:
        fig = ChartService().create_chart(payload['table'], payload['visualization'], payload.get('x'), payload.get('y'))
        payload['figure'] = json.loads(fig.to_json()) if fig else None
    return payload


class Application:
    server_version = 'DataPilot/1.0'

    def log_message(self, fmt, *args):
        # Do not log query strings, file names, cookies, SQL or uploaded values.
        log.info('HTTP response sent')

    def session(self):
        cookies = dict(part.strip().split('=', 1) for part in self.headers.get('Cookie', '').split(';') if '=' in part)
        sid = cookies.get('datapilot')
        with SESSIONS_LOCK:
            now = time.time()
            settings = Settings.from_env()
            for key in list(SESSIONS):
                if now - SESSIONS[key][1] > settings.session_ttl and SESSIONS[key][0].lock.acquire(blocking=False):
                    SESSIONS[key][0].lock.release()
                    del SESSIONS[key]
            if sid not in SESSIONS:
                if len(SESSIONS) >= settings.max_sessions:
                    raise ValueError('Workspace capacity reached. Please try again after an idle session expires.')
                sid = secrets.token_urlsafe(32)
                SESSIONS[sid] = (Workspace(), now)
            workspace = SESSIONS[sid][0]
            SESSIONS[sid] = (workspace, now)
        self.sid = sid
        return workspace

    def reply(self, value, code=200, content_type='application/json; charset=utf-8'):
        data = json.dumps(serial(value), ensure_ascii=False, allow_nan=False).encode() if content_type.startswith('application/json') else value
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        if getattr(self, 'sid', None):
            secure = '; Secure' if Settings.from_env().public_url.startswith('https://') else ''
            self.send_header('Set-Cookie', f'datapilot={self.sid}; HttpOnly; SameSite=Strict; Path=/{secure}')
        self.end_headers()
        self.wfile.write(data)

    def guard(self, mutation=False):
        settings = Settings.from_env()
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        origins = {'http://' + h for h in allowed}
        if settings.mode == 'cloud' and settings.public_url:
            allowed.add(urlparse(settings.public_url).netloc)
            origins.add(settings.public_url)
        if host not in allowed:
            raise ValueError('This host is not allowed. Check PUBLIC_URL on the server.')
        origin = self.headers.get('Origin')
        if origin and origin not in origins:
            raise ValueError('Cross-origin requests are not permitted.')
        if mutation and self.headers.get('X-DataPilot') != '1':
            raise ValueError('Missing same-origin request header.')

    def fail(self, exc):
        incident = secrets.token_hex(4)
        log.warning('Request failed; incident=%s operation=%s error_type=%s', incident,
                    urlparse(self.path).path[:80], type(exc).__name__)
        message = str(exc) if type(exc) is ValueError else 'This analysis could not be completed. Check the file format or selected columns and try again.'
        self.reply({'error': message, 'detail': f'Reference {incident} · {type(exc).__name__}. No dataset or credentials were written to the log.'}, 400)

    def do_GET(self):
        try:
            self.guard()
            path = urlparse(self.path).path
            if path == '/favicon.ico':
                return self.reply(b'', content_type='image/x-icon')
            if path == '/api/health':
                return self.reply({'status': 'ok'})
            if path == '/api/config':
                return self.reply({**Settings.from_env().public_settings(), 'reference_available': REFERENCE.exists()})
            if path in {'/api/ollama', '/api/provider'}:
                return self.reply(LLMService().health_check())
            if path == '/vendor/plotly.js':
                global PLOTLY_JS
                if PLOTLY_JS is None:
                    PLOTLY_JS = get_plotlyjs().encode()
                return self.reply(PLOTLY_JS, content_type='text/javascript')
            if not path.startswith('/api/'):
                file = {'/': 'index.html', '/app.js': 'app.js', '/ui.js': 'ui.js', '/styles.css': 'styles.css'}.get(path)
                if not file:
                    return self.reply({'error': 'Not found'}, 404)
                mime = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[file.rsplit('.', 1)[-1]]
                return self.reply((ROOT/'frontend'/file).read_bytes(), content_type=mime + '; charset=utf-8')
            ws = self.session()
            query = parse_qs(urlparse(self.path).query)
            with ws.lock:
                if path == '/api/status':
                    result = ws.status()
                elif path == '/api/explorer':
                    result = show_dataset_explorer(ws)
                elif path == '/api/profile':
                    column = query.get('column', [''])[0]
                    result = ws.get('column:' + column, lambda: column_profile(ws.active(), column))
                elif path == '/api/customer':
                    customer = query.get('id', [''])[0]
                    segments = ws.segments()
                    row = segments['customers'].loc[segments['customers'].CustomerID.astype(str) == customer]
                    if row.empty:
                        raise ValueError('Select an available customer.')
                    result = {'customer': row, 'profile': segments['statistics'].loc[segments['statistics'].Cluster == row.iloc[0].Cluster]}
                elif path == '/api/anomaly-detail':
                    result = AnomalyDetector.explain(ws.anomalies(float(query.get('contamination', [.02])[0])), query.get('row', [0])[0])
                elif path == '/api/dashboard':
                    result = show_dashboard(ws)
                elif path == '/api/quality':
                    ws.active()
                    result = show_data_quality(ws)
                elif path == '/api/history':
                    result = {'history': [{**entry, 'result': attach_charts(entry['result'])} for entry in ws.chat_results]}
                elif path == '/api/unique':
                    df = ws.active(); col = query.get('column', [''])[0]
                    if col not in df:
                        raise ValueError('Select an available column.')
                    result = {'values': df[col].value_counts(dropna=False).rename('Count').reset_index().head(200)}
                elif path == '/api/download':
                    data = ws.active().to_csv(index=False).encode('utf-8-sig')
                    return self.reply(data, content_type='text/csv; charset=utf-8')
                elif path == '/api/download-segments':
                    return self.reply(ws.segments()['customers'].to_csv(index=False).encode(), content_type='text/csv; charset=utf-8')
                else:
                    return self.reply({'error': 'Not found'}, 404)
                return self.reply(attach_charts(result))
        except Exception as exc:
            self.fail(exc)

    def do_POST(self):
        try:
            self.guard(mutation=True)
            size = int(self.headers.get('Content-Length', '0'))
            limit = Settings.from_env().max_upload_mb
            if not 0 <= size <= limit * 1024 * 1024:
                raise ValueError(f'The upload limit is {limit} MB.')
            body = self.rfile.read(size)
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            ws = self.session()
            with ws.lock:
                if path == '/api/upload':
                    filename = Path(query.get('name', ['data.csv'])[0]).name
                    sheet = query.get('sheet', [0])[0]
                    ws.load(body, filename, sheet)
                    ws.upload_bytes = body
                    ws.sheets = pd.ExcelFile(BytesIO(body)).sheet_names if filename.lower().endswith(('.xlsx', '.xls')) else []
                    return self.reply(ws.status())
                args = json.loads(body or b'{}')
                if not isinstance(args, dict):
                    raise ValueError('Request parameters must be an object.')
                if path == '/api/reference':
                    if not REFERENCE.exists():
                        raise ValueError('Reference workbook is not installed on this host. Import a CSV or Excel file to continue.')
                    sheet = args.get('sheet', 'Year 2010-2011')
                    with REFERENCE_LOCK:
                        if sheet not in REFERENCE_CACHE:
                            from services.data_loader import DataLoader
                            cache_key = hashlib.sha256(('v2:' + str(REFERENCE.stat().st_mtime_ns) + str(sheet)).encode()).hexdigest()[:16]
                            cache = ROOT / 'data/processed' / ('reference_cache_' + cache_key + '.parquet')
                            cache.parent.mkdir(parents=True, exist_ok=True)
                            if cache.exists() and cache.with_suffix('.json').exists():
                                cached = pd.read_parquet(cache)
                                encoded = json.loads(cache.with_suffix('.json').read_text())
                                for col in encoded:
                                    cached[col] = cached[col].map(lambda v: json.loads(v) if pd.notna(v) else float('nan'))
                                REFERENCE_CACHE[sheet] = cached
                            else:
                                REFERENCE_CACHE[sheet] = DataLoader().load_file(REFERENCE, sheet_name=sheet)
                                cached = REFERENCE_CACHE[sheet].copy()
                                encoded = list(cached.select_dtypes(include='object').columns)
                                for col in encoded:
                                    cached[col] = cached[col].map(lambda v: json.dumps(v) if pd.notna(v) else None)
                                cached.to_parquet(cache, index=False)
                                cache.with_suffix('.json').write_text(json.dumps(encoded))
                        raw = REFERENCE_CACHE[sheet]
                    from services.data_cleaner import prepare_data
                    ws.raw = raw.copy(); ws.prepared = prepare_data(raw); ws.cleaned = None
                    ws.filename = REFERENCE.name; ws.sheet = sheet
                    ws.source = 'reference'; ws.segment_k = 4
                    ws.sheets = ['Year 2009-2010', 'Year 2010-2011']
                    ws.upload_bytes = None; ws.mode = 'prepared'; ws.filters = {}; ws.cleaning_report = None
                    ws.invalidate(); result = ws.status()
                elif path == '/api/sheet':
                    if ws.upload_bytes is None:
                        raise ValueError('Use the reference dataset sheet selector to change the bundled workbook.')
                    ws.load(ws.upload_bytes, ws.filename, args['sheet']); result = ws.status()
                elif path == '/api/mode':
                    if args.get('mode') not in {'raw', 'prepared', 'cleaned'}:
                        raise ValueError('Unknown data view.')
                    if args['mode'] == 'cleaned' and ws.cleaned is None:
                        raise ValueError('Create a cleaned copy first.')
                    if ws.mode != args['mode']:
                        ws.mode = args['mode']; ws.invalidate()
                    result = ws.status()
                elif path == '/api/filters':
                    for key in ('start', 'end'):
                        if args.get(key):
                            pd.Timestamp(args[key])
                    if args.get('start') and args.get('end') and args['start'] > args['end']:
                        raise ValueError('Start date must precede end date.')
                    selected = {k: v for k, v in args.items() if k in {'country', 'start', 'end'} and v}
                    if selected != ws.filters:
                        ws.filters = selected; ws.invalidate()
                    result = ws.status()
                elif path == '/api/clean':
                    ws.active(); result = ws.clean(args)
                elif path == '/api/clean-preview':
                    ws.active(); result = ws.preview_cleaning(args)
                elif path == '/api/clean-apply':
                    result = ws.apply_cleaning(args.get('token'))
                elif path == '/api/insights':
                    result = show_insights(ws, args.get('summarize', False))
                elif path == '/api/segments':
                    result = show_segmentation(ws, min(8, max(2, int(args.get('clusters', 4)))))
                elif path == '/api/anomalies':
                    data = ws.anomalies(float(args.get('contamination', .02)))
                    result = {k: v for k, v in data.items() if k != 'data'}
                elif path == '/api/chat':
                    result = show_ai_chat(ws, args.get('question', ''))
                elif path == '/api/clear':
                    ws.memory.clear(); ws.chat_results.clear(); result = {'ok': True}
                elif path == '/api/sql':
                    db = DuckDBService()
                    try:
                        db.register_dataframe(ws.active())
                        result = {'table': db.execute_query(args.get('sql', ''))}
                    finally:
                        db.close()
                elif path == '/api/chart':
                    df = ws.active()
                    fig = ChartService().create_chart(df, args.get('kind'), args.get('x'), args.get('y'))
                    result = {'figure': json.loads(fig.to_json()) if fig else None,
                              'note': 'Charts use up to the first 1,000 active rows. Use SQL or AI aggregates for full-dataset analysis.'}
                else:
                    return self.reply({'error': 'Not found'}, 404)
                return self.reply(attach_charts(result))
        except Exception as exc:
            self.fail(exc)


class Handler(Application, BaseHTTPRequestHandler):
    """Loopback development transport; analytics dispatch is shared with WSGI."""
    pass


def main():
    parser = argparse.ArgumentParser(description='DataPilot AI analytics workspace')
    parser.add_argument('--env-file', help='Optional environment file; existing variables take precedence')
    parser.add_argument('--port', type=int)
    parser.add_argument('--host')
    parser.add_argument('--server', choices=['builtin', 'waitress'])
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    settings = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    host, port = args.host or settings.host, args.port or settings.port
    server_type = args.server or ('waitress' if settings.mode == 'cloud' else 'builtin')
    if settings.mode == 'cloud' and (not settings.public_url or server_type != 'waitress'):
        parser.error('Cloud mode requires PUBLIC_URL and the waitress server.')
    log.info('Starting DataPilot; mode=%s transport=%s port=%s', settings.mode, server_type, port)
    if server_type == 'waitress':
        from waitress import serve
        from services.wsgi_service import create_application
        serve(create_application(port), host=host, port=port, threads=8,
              max_request_body_size=settings.max_upload_mb * 1024 * 1024,
              channel_timeout=300, connection_limit=100, ident='DataPilot')
        return
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
