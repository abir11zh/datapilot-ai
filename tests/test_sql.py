import pandas as pd
import pytest
from services.sql_validator import validate_sql
from services.duckdb_service import DuckDBService
from services.sql_generator import SQLGenerator

@pytest.mark.parametrize('sql', [
    'SELECT * FROM sales;', 'WITH x AS (SELECT * FROM sales) SELECT COUNT(*) FROM x',
    "SELECT 'DROP TABLE sales;' AS text FROM sales", 'SELECT COUNT(*) AS n FROM sales',
    'SELECT Country, SUM(Quantity) AS q FROM sales GROUP BY Country',
])
def test_allowed(sql, retail):
    db=DuckDBService(); db.register_dataframe(retail)
    try:
        assert isinstance(db.execute_query(sql), pd.DataFrame)
    finally:
        db.close()

@pytest.mark.parametrize('sql', [
    'DROP TABLE sales', 'DELETE FROM sales', 'UPDATE sales SET Quantity=0', 'INSERT INTO sales VALUES(1)',
    'CREATE TABLE x(a INT)', 'ALTER TABLE sales ADD x INT', 'TRUNCATE sales', 'MERGE INTO sales USING sales s ON true WHEN MATCHED THEN DELETE',
    "COPY sales TO 'x.csv'", "ATTACH 'x.db' AS x", 'DETACH x', 'INSTALL httpfs', 'LOAD httpfs',
    'SELECT * FROM sales; DROP TABLE sales;', 'SELECT * FROM sales; SELECT 2',
    "SELECT * FROM read_csv_auto('secret.csv')", "SELECT * FROM 'secret.csv'", 'SELECT * FROM sqlite_scan(1,2)',
    'SELECT * FROM duckdb_tables()', "SELECT * FROM query('SELECT 1')", 'PRAGMA version',
    'WITH x AS (DELETE FROM sales RETURNING *) SELECT * FROM x',
    'SELECT * FROM information_schema.tables', 'SELECT * FROM range(1000000000)',
    'WITH RECURSIVE x AS (SELECT 1) SELECT * FROM x', 'SELECT * FROM other_table',
])
def test_reject(sql, retail):
    db=DuckDBService(); db.register_dataframe(retail)
    try:
        with pytest.raises(Exception):
            db.execute_query(sql)
        assert db.execute_query('SELECT COUNT(*) AS n FROM sales').iloc[0,0]==len(retail)
    finally:
        db.close()

def test_cap(retail):
    db=DuckDBService();db.register_dataframe(retail)
    try:
        r=db.execute_query('SELECT * FROM sales',max_rows=3)
        assert len(r)==3 and r.attrs['truncated']
    finally: db.close()

def test_generator():
    assert SQLGenerator().generate_select_query('sales',['Quantity'])=='SELECT Quantity FROM sales'


def test_quoted_generic_columns():
    df=pd.DataFrame({'Sales ($)':[1.,2.], 'DROP':['a','b']})
    db=DuckDBService();db.register_dataframe(df)
    try:
        assert db.query('SELECT SUM("Sales ($)") AS total FROM sales').iloc[0,0]==3
        assert len(db.query('SELECT "DROP" FROM sales'))==2
    finally:db.close()
