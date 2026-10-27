"""Conservative edits to already executed queries for unambiguous follow-ups."""
import sqlparse
from sqlparse.sql import Identifier, Where
from services.sql_validator import validate_sql


def exclude_country(sql: str, country: str):
    """Preserve SELECT, existing filters, aggregates, ordering and limit.

    Only a simple SELECT from sales is eligible. Complex joins/CTEs remain the
    planner's responsibility. The resulting query still passes the SQL validator.
    """
    statement = sqlparse.parse(validate_sql(sql))[0]
    tokens = statement.tokens
    significant = [t for t in tokens if not t.is_whitespace]
    if not significant or significant[0].normalized != 'SELECT':
        return None
    if any(t.is_keyword and any(word in t.normalized.split() for word in ('JOIN', 'UNION', 'EXCEPT', 'INTERSECT')) for t in tokens):
        return None
    from_index = next((i for i, t in enumerate(significant) if t.normalized == 'FROM'), None)
    if from_index is None or from_index + 1 >= len(significant):
        return None
    relation = significant[from_index + 1]
    if not isinstance(relation, Identifier) or relation.get_real_name().lower() != 'sales':
        return None
    alias = relation.get_alias()
    column = ('"' + alias.replace('"', '""') + '".') if alias else ''
    predicate = column + '"Country" <> ' + "'" + country.replace("'", "''") + "'"
    where = next((t for t in tokens if isinstance(t, Where)), None)
    if where is not None:
        rewritten = ''.join('WHERE (' + t.value[5:].strip() + ') AND ' + predicate + ' ' if t is where else t.value for t in tokens)
    else:
        boundary = next((i for i,t in enumerate(tokens) if t.is_keyword and t.normalized in {'GROUP BY','ORDER BY','HAVING','LIMIT','OFFSET','FETCH'}), len(tokens))
        rewritten = ''.join(t.value for t in tokens[:boundary]).rstrip() + ' WHERE ' + predicate + ' ' + ''.join(t.value for t in tokens[boundary:])
    return validate_sql(rewritten)
