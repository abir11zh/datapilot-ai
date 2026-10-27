"""Conservative SELECT-only policy, plus DuckDB disabled external access."""
import re
import sqlparse
from sqlparse import tokens as T

FORBIDDEN = set('DROP DELETE UPDATE INSERT ALTER CREATE TRUNCATE MERGE COPY ATTACH DETACH INSTALL LOAD EXPORT IMPORT PRAGMA CALL SET RESET VACUUM ANALYZE GRANT REVOKE PIVOT UNPIVOT INTO EXECUTE PREPARE DEALLOCATE SUMMARIZE DESCRIBE SHOW USE'.split())
FUNCTIONS = set('SUM AVG MIN MAX COUNT MEDIAN QUANTILE_CONT QUANTILE_DISC STDDEV STDDEV_SAMP VARIANCE ROUND ABS CEIL FLOOR COALESCE NULLIF IFNULL IF CAST TRY_CAST EXTRACT DATE_TRUNC DATE_PART STRFTIME STRPTIME TRY_STRPTIME YEAR MONTH DAY HOUR DAYNAME MONTHNAME DATEDIFF DATE_DIFF LOWER UPPER TRIM LTRIM RTRIM LENGTH SUBSTR SUBSTRING REPLACE CONCAT CONCAT_WS CONTAINS STARTS_WITH ENDS_WITH REGEXP_MATCHES ROW_NUMBER RANK DENSE_RANK LAG LEAD FIRST_VALUE LAST_VALUE NTILE OVER FILTER IN AS VALUES GREATEST LEAST PERCENT_RANK CUME_DIST STRING_AGG BOOL_AND BOOL_OR POWER SQRT LOG LN EXP'.split())


def validate_sql(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 20000:
        raise ValueError('SQL must be nonempty and at most 20,000 characters.')
    statements = sqlparse.parse(query)
    if len(statements) != 1 or statements[0].get_type() != 'SELECT':
        raise ValueError('Only one SELECT or WITH ... SELECT statement is permitted.')
    visible = []
    flat = list(statements[0].flatten())
    for index, token in enumerate(flat):
        if token.ttype in T.Comment:
            continue
        if token.ttype in T.Literal.String.Symbol:
            following = next((t.value for t in flat[index+1:] if not t.is_whitespace and t.ttype not in T.Comment), '')
            visible.append(token.value if following == '(' else 'quoted_identifier')
            continue
        if token.ttype in T.Literal.String.Single:
            visible.append("'literal'")
            continue
        if token.value.upper() in FORBIDDEN or token.value.upper() == 'RECURSIVE':
            raise ValueError(f'Forbidden SQL operation: {token.value}.')
        visible.append(token.value)
    sql = ''.join(visible)
    if re.search(r'\b(?:read_\w+|\w*_scan|duckdb_\w+|sqlite_\w+|pg_\w+|query|query_table|getenv)\b', sql, re.I):
        raise ValueError('External readers and system functions are not permitted.')
    if re.search(r'\b(?:information_schema|pg_catalog)\b|\$', sql, re.I):
        raise ValueError('System catalogs and variable indirection are not permitted.')
    for match in re.finditer(r'([\w"]+)\s*\(', sql):
        name = match.group(1).strip('"').upper()
        if name not in FUNCTIONS | {'DECIMAL', 'NUMERIC', 'VARCHAR', 'INTEGER', 'BIGINT', 'DOUBLE', 'FLOAT', 'TIMESTAMP', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'EXISTS', 'ON', 'WHEN', 'THEN', 'ELSE', 'SELECT', 'HAVING', 'BY', 'DISTINCT', 'JOIN'}:
            raise ValueError(f'Function or expression {name} is outside the allowed analytical subset.')
    return query.strip().rstrip(';').strip()


class SQLValidator:
    def validate(self, sql_query):
        try:
            validate_sql(sql_query)
            return True, 'Read-only analytical SQL.'
        except ValueError as exc:
            return False, str(exc)
