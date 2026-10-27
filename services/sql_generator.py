import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['sql_query', 'dataset_info', 'statistics', 'data_quality', 'chart', 'insights', 'segmentation', 'anomaly_detection', 'clarification']
    sql: str | None = Field(default=None, max_length=20000)
    visualization: Literal['bar', 'line', 'scatter', 'pie', 'histogram'] | None = None
    x: str | None = None
    y: str | None = None
    message: str | None = Field(default=None, max_length=1000)
    missing_columns: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def needs_sql(self):
        if self.action == 'sql_query' and not self.sql:
            raise ValueError('sql_query needs SQL.')
        return self


class SQLGenerator:
    def generate(self, question, schema, history, llm, error=None):
        root = Path(__file__).resolve().parents[1] / 'prompts'
        history = [{k: (v[:(1200 if k == 'generated_sql' else 300)] if isinstance(v, str) else v) for k, v in item.items()} for item in history[-4:]]
        messages = [{'role': 'system', 'content': (root/'system_prompt.txt').read_text() + '\n' + (root/'sql_prompt.txt').read_text()},
                    {'role': 'user', 'content': json.dumps({'schema': schema, 'history': history[-8:], 'question': question, 'previous_error': error}, default=str)}]
        return llm.parse_structured(llm.chat(messages, QueryPlan.model_json_schema()), QueryPlan)

    def generate_select_query(self, table_name, columns=None, where_clause=None, limit=None):
        query = f"SELECT {', '.join(columns or ['*'])} FROM {table_name}"
        if where_clause:
            query += f' WHERE {where_clause}'
        if limit is not None:
            query += f' LIMIT {int(limit)}'
        return query

    def generate_count_query(self, table_name, where_clause=None):
        return self.generate_select_query(table_name, ['COUNT(*) AS total_rows'], where_clause)
