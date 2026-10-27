from io import BytesIO
import threading
import secrets
import pandas as pd
from services.data_loader import DataLoader, inspect_dataset
from services.data_cleaner import prepare_data, analyze_data_quality, DataCleaner, CleaningOptions
from services.insight_service import InsightService
from services.memory_service import MemoryService
from ml.rfm import RFMAnalyzer
from ml.segmentation import SegmentationModel
from ml.anomaly_detection import AnomalyDetector


class Workspace:
    def __init__(self):
        self.raw = None
        self.prepared = None
        self.cleaned = None
        self.mode = 'prepared'
        self.source = 'upload'
        self.segment_k = 4
        self.filename = ''
        self.sheets = []
        self.sheet = None
        self.upload_bytes = None
        self.cache = {}
        self.memory = MemoryService()
        self.chat_results = []
        self.cleaning_report = None
        self.filters = {}
        self.pending_cleaning = None
        self.lock = threading.RLock()

    def load(self, source, filename, sheet=0):
        df = DataLoader().load_file(source, filename, sheet)
        self.source = 'upload'
        self.segment_k = 4
        self.raw = df
        self.prepared = prepare_data(df)
        self.cleaned = None
        self.mode = 'prepared'
        self.filename = filename
        self.sheet = sheet
        self.cleaning_report = None
        self.filters = {}
        self.invalidate()

    def invalidate(self):
        self.cache.clear()
        self.memory.clear()
        self.chat_results.clear()
        self.pending_cleaning = None

    def active(self):
        if self.raw is None:
            raise ValueError('Upload a dataset or load the reference workbook first.')
        df = {'raw': self.raw, 'prepared': self.prepared, 'cleaned': self.cleaned}[self.mode]
        if df is None:
            raise ValueError('Clean the dataset before selecting the cleaned view.')
        if self.filters:
            df = df.copy()
            if self.filters.get('country') and 'Country' in df:
                df = df.loc[df.Country == self.filters['country']]
            if 'InvoiceDate' in df:
                dates = pd.to_datetime(df.InvoiceDate, errors='coerce')
                if self.filters.get('start'):
                    df = df.loc[dates >= pd.Timestamp(self.filters['start'])]
                if self.filters.get('end'):
                    df = df.loc[pd.to_datetime(df.InvoiceDate, errors='coerce') < pd.Timestamp(self.filters['end']) + pd.Timedelta(days=1)]
        return df

    def get(self, key, factory):
        if key not in self.cache:
            self.cache[key] = factory()
        return self.cache[key]

    def profile(self):
        return self.get('profile', lambda: inspect_dataset(self.active()))

    def quality(self):
        return self.get('quality', lambda: analyze_data_quality(self.raw))

    def insights(self):
        return self.get('insights', lambda: InsightService().generate(self.active()))

    def segments(self, k=None):
        k = self.segment_k if k is None else int(k)
        if k != self.segment_k:
            self.memory.clear()
            self.chat_results.clear()
        self.segment_k = k
        def calculate():
            rfm = RFMAnalyzer().analyze(self.active())
            customers, stats = SegmentationModel().segment(rfm, k)
            return {'customers': customers, 'statistics': stats, 'reference_date': rfm.attrs['reference_date'],
                    'eligible_rows': rfm.attrs['eligible_rows'], 'excluded_rows': rfm.attrs['excluded_rows']}
        return self.get(f'segments:{k}', calculate)

    def anomalies(self, contamination=.02):
        return self.get(f'anomalies:{contamination}', lambda: AnomalyDetector().detect(self.active(), contamination))

    def clean(self, settings):
        settings = dict(settings)
        numeric = settings.pop('numeric_columns', [])
        dates = settings.pop('date_columns', [])
        self.cleaned, self.cleaning_report = DataCleaner().clean_with_report(
            self.raw, CleaningOptions(**settings), numeric_columns=numeric, date_columns=dates)
        self.mode = 'cleaned'
        self.invalidate()
        return self.cleaning_report

    def preview_cleaning(self, settings):
        settings = dict(settings)
        numeric = settings.pop('numeric_columns', [])
        dates = settings.pop('date_columns', [])
        candidate, report = DataCleaner().clean_with_report(
            self.raw, CleaningOptions(**settings), numeric_columns=numeric, date_columns=dates)
        token = secrets.token_urlsafe(24)
        self.pending_cleaning = (token, candidate, report)
        return {'token': token, 'report': report, 'preview': candidate.head(50),
                'conversions': analyze_data_quality(self.raw, numeric, dates)['conversions']}

    def apply_cleaning(self, token):
        if not self.pending_cleaning or token != self.pending_cleaning[0]:
            raise ValueError('This preview has expired. Preview the changes again before applying.')
        _, self.cleaned, self.cleaning_report = self.pending_cleaning
        self.mode = 'cleaned'
        self.invalidate()
        return self.cleaning_report

    def status(self):
        if self.raw is None:
            return {'loaded': False}
        df = self.active()
        return {'loaded': True, 'filename': self.filename, 'sheet': self.sheet, 'sheets': self.sheets,
                'source': self.source, 'cluster_count': self.segment_k,
                'rows': len(df), 'columns': len(df.columns), 'mode': self.mode,
                'has_cleaned': self.cleaned is not None, 'filters': self.filters,
                'column_names': list(df.columns),
                'countries': sorted(self.prepared.Country.dropna().astype(str).unique().tolist()) if 'Country' in self.prepared else [],
                'has_dates': 'InvoiceDate' in self.prepared,
                'cleaning_report': self.cleaning_report}
