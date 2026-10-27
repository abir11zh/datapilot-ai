import threading
import duckdb
from services.sql_validator import validate_sql


class DuckDBService:
    def __init__(self):
        self.conn = duckdb.connect(':memory:', config={'enable_external_access': 'false',
                                                     'threads': '2', 'memory_limit': '512MB'})
        self.tables = {}

    def register_dataframe(self, df, name='sales'):
        if name not in {'sales', 'segments'}:
            raise ValueError('Only sales and segments can be registered.')
        self.conn.register(name, df)
        self.tables[name] = df

    def execute_query(self, sql, max_rows=1000, timeout=15):
        safe = validate_sql(sql)
        relations = self.conn.get_table_names(safe)
        if not relations <= self.tables.keys():
            raise ValueError('Queries can reference only registered sales and segments tables.')
        timer = threading.Timer(timeout, self.conn.interrupt)
        timer.daemon = True
        timer.start()
        try:
            result = self.conn.execute(f'SELECT * FROM ({safe}) AS result LIMIT {int(max_rows)+1}').fetchdf()
            result.attrs['truncated'] = len(result) > max_rows
            return result.head(max_rows)
        finally:
            timer.cancel()

    query = execute_query

    def get_schema(self):
        schema = {}
        for name, df in self.tables.items():
            columns = []
            for c in df:
                item = {'name': str(c), 'type': str(df[c].dtype)}
                if c == 'Segment':
                    item['allowed_values'] = df[c].dropna().unique().tolist()
                columns.append(item)
            schema[name] = columns
        return schema

    def get_columns(self, name='sales'):
        return list(self.tables[name].columns)

    def close(self):
        self.conn.close()
