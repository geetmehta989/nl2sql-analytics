from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .models import AskRequest, AskResponse, UploadResponse
from .db import (
    get_engine,
    get_dataset_engine,
    initialize_dirty_schema,
    fetch_schema_snapshot,
    run_select_sql,
    ingest_excel_to_dataset,
)
from .ai import (
    generate_sql_from_question,
    repair_sql_on_error,
    explain_results,
    suggest_chart_type,
    clean_tabular_data,
)


ROOT_PATH = os.getenv("FASTAPI_ROOT_PATH", "")
app = FastAPI(title="NL2SQL Analytics API", version="1.0.0", root_path=ROOT_PATH)

# CORS for local dev and generic frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ENGINE = get_engine()


@app.on_event("startup")
def on_startup() -> None:
    initialize_dirty_schema(ENGINE)


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        dataset_engine = get_dataset_engine(request.dataset_id)
        schema_snapshot = fetch_schema_snapshot(dataset_engine)
        sql = generate_sql_from_question(request.question, schema_snapshot)
        try:
            columns, data = run_select_sql(dataset_engine, sql)
        except Exception as e:  # noqa: BLE001
            # Attempt a single repair using the error text
            repaired_sql = repair_sql_on_error(request.question, schema_snapshot, sql, str(e))
            columns, data = run_select_sql(dataset_engine, repaired_sql)
            sql = repaired_sql

        cleaned_cols, cleaned_data = clean_tabular_data(columns, data)
        explanation = explain_results(request.question, sql, cleaned_cols, cleaned_data)
        chart = suggest_chart_type(cleaned_cols, cleaned_data)

        return AskResponse(
            sql=sql,
            columns=cleaned_cols,
            data=cleaned_data,
            explanation=explanation,
            chart=chart,
        )
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


def get_app() -> FastAPI:
    return app


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    try:
        suffix = ".xlsx"
        from pathlib import Path
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        dataset_id, tables = ingest_excel_to_dataset(tmp_path)
        return UploadResponse(dataset_id=dataset_id, tables=tables, note=f"Parsed {len(tables)} sheet(s)")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to ingest file: {e}")
