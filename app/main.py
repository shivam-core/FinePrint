# app/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import hashlib
from app.schemas import ExtractResponse, AnalyzeRequest, AnalyzeResponse, AnalysisSummary, CompareRequest
from app.extraction import extract_pdf, extract_docx, extract_txt
from app.segmentation import sentencize
from app.inference import get_model

app = FastAPI(title="FinePrint")

# Global dict to store generated analysis for PDF to ensure it's not tampered.
# In a real app we might use redis, but memory is fine for MVP.
# We'll just recompute based on hash if needed, or cache it.
analysis_cache = {}

@app.on_event("startup")
def load_model_on_startup():
    if not os.path.exists("artifacts/model.joblib"):
        print("CRITICAL: artifacts/model.joblib not found.")
        raise RuntimeError("Model bundle missing. Run train.py first.")
    # Initialize singleton
    get_model()

@app.get("/healthz")
def healthz():
    try:
        m = get_model()
        return {"status": "ok", "model_version": "v1.0"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Model not loaded")

@app.post("/api/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)):
    if file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (limit 5MiB)")
        
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Empty file")
        
    filename = file.filename.lower()
    text = ""
    warnings = []
    pages = None
    
    if filename.endswith(".pdf"):
        text, pages, warnings = extract_pdf(contents)
        source_type = "application/pdf"
    elif filename.endswith(".docx"):
        text, warnings = extract_docx(contents)
        source_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.endswith(".txt"):
        text, warnings = extract_txt(contents)
        source_type = "text/plain"
    else:
        raise HTTPException(status_code=422, detail="Unsupported file type")
        
    if len(text) > 100000:
        raise HTTPException(status_code=413, detail="Extracted text too large (limit 100,000 characters)")
        
    return ExtractResponse(
        source_name=file.filename,
        source_type=source_type,
        text=text,
        pages=pages,
        warnings=warnings,
        characters=len(text),
        editable=True
    )

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    if len(req.text) > 100000:
        raise HTTPException(status_code=413, detail="Text too large (limit 100,000 characters)")
        
    m = get_model()
    spans = sentencize(req.text)
    
    if len(spans) > 500:
        raise HTTPException(status_code=413, detail="Too many segments (limit 500)")
        
    segments = []
    summary = {"total": len(spans), "potentially_unfair": 0, "no_issue_detected": 0, "needs_review": 0}
    category_counts = {}
    
    for i, (sentence, start, end) in enumerate(spans):
        sid = f"s{i:03d}"
        res = m.analyze_segment(sid, sentence, start, end)
        segments.append(res)
        
        status = res["status"]
        summary[status] += 1
        
        for c in res["categories"]:
            category_counts[c["name"]] = category_counts.get(c["name"], 0) + 1
            
    content_hash = hashlib.sha256(req.text.encode('utf-8')).hexdigest()
    
    resp = AnalyzeResponse(
        analysis_id=content_hash,
        model_version="v1.0",
        source_name=req.source_name,
        text=req.text,
        summary=AnalysisSummary(**summary),
        category_counts=category_counts,
        warnings=["User-edited extracted text. Source page mapping disabled."] if req.user_edited else [],
        segments=segments
    )
    
    analysis_cache[content_hash] = resp
    return resp

@app.post("/api/report")
def report(req: AnalyzeRequest):
    # Rerun analysis to be authoritative
    resp = analyze(req)
    
    from app.reporting import generate_report
    pdf_bytes = generate_report(resp)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="FinePrint_Analysis_Report.pdf"',
            "Cache-Control": "no-store"
        }
    )

@app.post("/api/compare")
def compare(req: CompareRequest):
    if len(req.original) > 2000 or len(req.revised) > 2000:
        raise HTTPException(status_code=413, detail="Comparison text too long (limit 2000 chars)")
        
    m = get_model()
    res1 = m.analyze_segment("orig", req.original, 0, len(req.original))
    res2 = m.analyze_segment("rev", req.revised, 0, len(req.revised))
    
    return {"original": res1, "revised": res2}

@app.get("/api/audit")
def audit():
    try:
        with open("artifacts/evaluation.json") as f:
            return json.load(f)
    except:
        raise HTTPException(status_code=404, detail="Audit not found")

@app.get("/api/model-card")
def model_card():
    if not os.path.exists("artifacts/model_card.pdf"):
        raise HTTPException(status_code=404, detail="Model card not found")
    return FileResponse("artifacts/model_card.pdf", media_type="application/pdf", filename="FinePrint_Model_Card.pdf")

# Mount static files
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
