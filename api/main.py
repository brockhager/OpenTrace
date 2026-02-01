from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Opentrace API", version="0.1.0")

# Models
class IntelItem(BaseModel):
    source_url: str
    text: Optional[str] = None

class BulkIntelRequest(BaseModel):
    items: List[IntelItem]

# Mock database (replace with real SQLAlchemy models)
person_profiles = []
intel_items = []

# Mock authentication (replace with real JWT/OAuth)
def get_current_user():
    # Placeholder - implement proper auth
    return {"role": "admin", "id": 1}

def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user

# Public endpoints
@app.get("/search")
async def search_profiles(q: str, location: Optional[str] = None):
    """Search person profiles (public or reviewed intel only)."""
    # Mock implementation - filter confirmed profiles
    results = [
        p for p in person_profiles
        if (p.get("is_confirmed") or p.get("reviewed")) and
        (q.lower() in p.get("full_name", "").lower() or q.lower() in p.get("given_name", "").lower())
    ]
    if location:
        results = [p for p in results if location.lower() in p.get("last_seen_location", "").lower()]
    return {"results": results}

@app.post("/intel/submit")
async def submit_intel(item: IntelItem):
    """Submit community intel (requires source_url)."""
    if not item.source_url:
        raise HTTPException(status_code=400, detail="source_url required")

    # Mock PII filtering
    if any(word in item.text.lower() for word in ["phone", "email", "address"]):
        raise HTTPException(status_code=400, detail="PII detected - remove sensitive info")

    intel_items.append({
        "id": len(intel_items) + 1,
        "source_url": item.source_url,
        "text": item.text,
        "reviewed": False,
        "submitted_at": "2024-01-01T00:00:00Z"
    })
    return {"message": "Intel submitted for review"}

@app.post("/intel/bulk-submit")
async def bulk_submit_intel(request: BulkIntelRequest, user: dict = Depends(require_admin)):
    """Bulk submit intel for trusted partners."""
    for item in request.items:
        if not item.source_url:
            raise HTTPException(status_code=400, detail="All items must have source_url")

        # Mock PII filtering
        if item.text and any(word in item.text.lower() for word in ["phone", "email", "address"]):
            raise HTTPException(status_code=400, detail="PII detected in bulk submission")

        intel_items.append({
            "id": len(intel_items) + 1,
            "source_url": item.source_url,
            "text": item.text,
            "reviewed": True,  # Trusted partners get auto-review
            "submitted_at": "2024-01-01T00:00:00Z"
        })

    return {"message": f"Bulk submitted {len(request.items)} items"}

@app.get("/profiles/{profile_id}/intel")
async def get_profile_intel(profile_id: int):
    """Get reviewed intel for a profile."""
    # Mock - return only reviewed intel
    profile_intel = [i for i in intel_items if i["reviewed"]]
    return {"intel": profile_intel}

@app.get("/sources")
async def get_sources():
    """List data sources with last update times."""
    return {
        "sources": [
            {"name": "NamUs", "last_update": "2024-01-01T00:00:00Z"},
            {"name": "Interpol Yellow Notices", "last_update": "2024-01-01T00:00:00Z"},
            {"name": "The Charley Project", "last_update": "2024-01-01T00:00:00Z"}
        ]
    }

# Admin endpoints
@app.get("/admin/review-queue", dependencies=[Depends(require_admin)])
async def get_review_queue():
    """List unreviewed intel items."""
    queue = [i for i in intel_items if not i["reviewed"]]
    return {"queue": queue}

@app.post("/admin/approve", dependencies=[Depends(require_admin)])
async def approve_intel(intel_id: int):
    """Approve intel and create profile link."""
    for item in intel_items:
        if item["id"] == intel_id:
            item["reviewed"] = True
            # Mock profile link creation
            return {"message": f"Intel {intel_id} approved and linked"}
    raise HTTPException(status_code=404, detail="Intel item not found")

@app.post("/admin/takedown", dependencies=[Depends(require_admin)])
async def takedown_profile(pfif_id: str):
    """Remove profile (GDPR compliance)."""
    # Mock CASCADE delete
    global person_profiles, intel_items
    person_profiles = [p for p in person_profiles if p.get("pfif_id") != pfif_id]
    intel_items = [i for i in intel_items if i.get("source_url") != f"https://namus.nij.ojp.gov/case/{pfif_id.split('.')[-1]}"]

    # Log to audit (mock)
    print(f"Audit: Takedown requested for {pfif_id}")
    return {"message": f"Profile {pfif_id} removed"}

@app.post("/scrape/namus", dependencies=[Depends(require_admin)])
async def trigger_namus_scrape(case_id: str):
    """Trigger manual NamUs scrape (for testing)."""
    # Mock - in real implementation, call scraper
    return {"message": f"Scrape triggered for NamUs case {case_id}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)