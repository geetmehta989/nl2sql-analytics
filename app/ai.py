from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage


def _get_llm(model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")) -> ChatOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    base_url = os.environ.get("OPENAI_BASE_URL")
    # ChatOpenAI supports custom base_url for OpenAI-compatible proxies
    if base_url:
        return ChatOpenAI(model=model, temperature=0.1, api_key=api_key, base_url=base_url)
    return ChatOpenAI(model=model, temperature=0.1, api_key=api_key)


def extract_sql_from_text(text: str) -> str:
    fenced = re.search(r"```sql\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip().rstrip(";")
    # fallback: find first SELECT ...; occurrence
    select_match = re.search(r"(SELECT[\s\S]+)$", text, flags=re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip().rstrip(";")
    return text.strip().rstrip(";")


def ensure_safe_sql(sql: str) -> str:
    candidate = sql.strip().rstrip(";")
    lowered = candidate.lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT statements are allowed.")
    if any(keyword in lowered for keyword in [" update ", " delete ", " insert ", " drop ", " alter ", " create ", " attach ", " pragma "]):
        raise ValueError("Mutation or unsafe commands are not allowed.")
    # Add LIMIT if absent and not already limited
    if " limit " not in lowered:
        candidate = f"{candidate} LIMIT 200"
    return candidate


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(2))
def generate_sql_from_question(question: str, schema_snapshot: str) -> str:
    llm = _get_llm()
    system = SystemMessage(
        content=(
            "You are a careful SQLite SQL generator.\n"
            "- Use ONLY the provided schema.\n"
            "- Quote identifiers that contain spaces, symbols, or mixed casing using double quotes.\n"
            "- Return a single valid SQLite SELECT statement.\n"
            "- Prefer simple joins and aggregations.\n"
            "- If a name looks approximate, pick the closest from the schema.\n"
            "- Do not include explanations, only the SQL.\n"
        )
    )
    human = HumanMessage(
        content=(
            f"SCHEMA\n{schema_snapshot}\n\n"
            f"QUESTION\n{question}\n\n"
            "Return only SQL in a fenced block like:\n````sql\nSELECT ...\n````\n"
        )
    )
    response = llm.invoke([system, human])
    sql = extract_sql_from_text(response.content)
    return ensure_safe_sql(sql)


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(2))
def repair_sql_on_error(question: str, schema_snapshot: str, attempted_sql: str, error_text: str) -> str:
    llm = _get_llm()
    system = SystemMessage(
        content=(
            "You fix invalid SQLite SELECT statements.\n"
            "Only return a corrected SQL SELECT that would run successfully.\n"
            "Remember to double-quote dirty identifiers.\n"
        )
    )
    human = HumanMessage(
        content=(
            f"SCHEMA\n{schema_snapshot}\n\n"
            f"QUESTION\n{question}\n\n"
            f"ATTEMPTED SQL\n{attempted_sql}\n\n"
            f"ERROR\n{error_text}\n\n"
            "Return only the corrected SQL in a fenced block."
        )
    )
    response = llm.invoke([system, human])
    sql = extract_sql_from_text(response.content)
    return ensure_safe_sql(sql)


def explain_results(question: str, sql: str, columns: List[str], data: List[Dict[str, Any]]) -> str:
    llm = _get_llm()
    preview_rows = data[:10]
    system = SystemMessage(
        content=(
            "Explain query results concisely for a business user.\n"
            "Write 1-3 sentences max."
        )
    )
    human = HumanMessage(
        content=(
            f"QUESTION: {question}\nSQL: {sql}\nCOLUMNS: {columns}\nROWS (sample): {preview_rows}"
        )
    )
    response = llm.invoke([system, human])
    return response.content.strip()


def suggest_chart_type(columns: List[str], data: List[Dict[str, Any]]) -> str:
    if not data or not columns:
        return "table"

    def is_number(value: Any) -> bool:
        return isinstance(value, (int, float))

    first_row = data[0]
    numeric_columns = [c for c in columns if is_number(first_row.get(c))]
    non_numeric_columns = [c for c in columns if c not in numeric_columns]

    # Time series detection
    time_like = [c for c in columns if "date" in c.lower() or "dt" in c.lower()]
    if time_like and len(numeric_columns) >= 1:
        return "line"

    # Distribution by category
    if len(non_numeric_columns) >= 1 and len(numeric_columns) >= 1:
        # If small number of categories, pie; else bar
        category_col = non_numeric_columns[0]
        unique_values = {row.get(category_col) for row in data}
        if 2 <= len(unique_values) <= 6 and len(numeric_columns) == 1 and len(columns) == 2:
            return "pie"
        return "bar"

    # Two numeric columns -> scatter
    if len(numeric_columns) >= 2:
        return "scatter"

    return "table"


def clean_column_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", name).strip("_")
    cleaned = re.sub(r"__+", "_", cleaned)
    return cleaned.lower() or "col"


def clean_tabular_data(columns: List[str], data: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    rename_map = {c: clean_column_name(c) for c in columns}
    new_columns = [rename_map[c] for c in columns]
    new_data: List[Dict[str, Any]] = []
    for row in data:
        new_row = {rename_map[c]: row.get(c) for c in columns}
        new_data.append(new_row)
    return new_columns, new_data
