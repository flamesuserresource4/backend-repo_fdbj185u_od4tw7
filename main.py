import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str
    lang: Optional[str] = "en"  # "en" or "te"


class AnalyzeResponse(BaseModel):
    summary: str
    actions: List[str] = []


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


def _heuristic_summary(text: str, lang: str) -> str:
    # Simple line-based summary: first sentence or trimmed first 150 chars
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return "No content provided."
    # If Telugu selected, prepend a tag to indicate handling
    prefix = "[Telugu] " if (lang or "en").lower().startswith("te") else ""
    # Try to extract up to first period or 150 chars
    m = re.search(r"([^.?!]{10,200}[.?!])", cleaned)
    base = m.group(1).strip() if m else cleaned[:150].strip()
    return f"{prefix}{base}"


action_keywords = [
    "schedule", "reschedule", "meeting", "review", "submit", "report", "call",
    "notify", "send", "prepare", "follow up", "follow-up", "remind", "escalate",
    "approve", "circulate", "assign", "deadline", "arrange", "brief"
]


def _extract_actions(text: str) -> List[str]:
    actions: List[str] = []
    lines = [l.strip(" -•\t") for l in text.splitlines() if l.strip()]
    for line in lines:
        low = line.lower()
        if any(k in low for k in action_keywords):
            actions.append(line)
            continue
        # imperative verb heuristic: starts with a verb-like word
        if re.match(r"^(please\s+)?([a-zA-Z]+)(\s+)[A-Za-z]", line):
            token = re.match(r"^(please\s+)?([a-zA-Z]+)", line).group(2).lower()
            if token.endswith("e") or token.endswith("d") or token.endswith("n") or token.endswith("y"):
                actions.append(line)
    # Deduplicate while keeping order
    seen = set()
    deduped = []
    for a in actions:
        key = a.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    # If nothing found but we have content, propose a generic action
    if not deduped and text.strip():
        deduped = ["Review the message and assign to the concerned department."]
    return deduped[:10]


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    summary = _heuristic_summary(req.text, req.lang or "en")
    actions = _extract_actions(req.text)
    return AnalyzeResponse(summary=summary, actions=actions)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
