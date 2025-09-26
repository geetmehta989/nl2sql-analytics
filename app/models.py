from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User natural language question")
    dataset_id: str = Field(..., min_length=1, description="Identifier of uploaded dataset")


class AskResponse(BaseModel):
    sql: str
    columns: List[str]
    data: List[Dict[str, Any]]
    explanation: str
    chart: Literal["bar", "line", "pie", "scatter", "table"]


class UploadResponse(BaseModel):
    dataset_id: str
    tables: List[str]
    note: Optional[str] = None
