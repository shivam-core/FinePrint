# app/schemas.py
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class ExtractResponse(BaseModel):
    source_name: str
    source_type: str
    text: str
    pages: Optional[int] = None
    warnings: List[str] = []
    characters: int
    editable: bool = True

class AnalyzeRequest(BaseModel):
    text: str
    source_name: str = "Pasted text"
    source_type: str = "text/plain"
    user_edited: bool = False

class Explanation(BaseModel):
    intercept: float
    context: str
    features: List[Dict[str, Any]] # {feature: str, weight: float, spans: list}

class CategoryResult(BaseModel):
    id: int
    name: str
    model_score: float
    threshold: float

class Segment(BaseModel):
    id: str
    text: str
    start: int
    end: int
    page: Optional[int] = None
    status: str
    reason: Optional[str] = None
    categories: List[CategoryResult] = []
    scores: Dict[str, float] = {}
    explanations: Dict[str, Explanation] = {}

class AnalysisSummary(BaseModel):
    total: int
    potentially_unfair: int
    no_issue_detected: int
    needs_review: int

class AnalyzeResponse(BaseModel):
    analysis_id: str
    model_version: str
    source_name: str
    text: str
    summary: AnalysisSummary
    category_counts: Dict[str, int]
    warnings: List[str] = []
    segments: List[Segment]

class CompareRequest(BaseModel):
    original: str
    revised: str

class ReportRequest(BaseModel):
    analysis: AnalyzeResponse
