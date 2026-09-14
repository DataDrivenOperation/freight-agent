"""FastAPI web UI for the Load Matching Agent.

A thin browser front end over the existing CLI logic in
agents/load_matching/ — it imports find_load(), match_load(), and
get_available_loads()/get_available_trucks() but does not modify that
package. No async is used, per CLAUDE.md ("No async in v1"); FastAPI runs
these plain `def` routes in a threadpool automatically.

Run with:
    uvicorn app:app --reload
Then open http://localhost:8000
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.load_matching.agent import find_load, match_load
from agents.load_matching.tools import get_available_loads, get_available_trucks
from shared.errors import DataError
from shared.logging import get_logger

logger = get_logger("load_matching_web")

app = FastAPI(title="Freight Load Matcher")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class MatchRow(BaseModel):
    """One ranked truck match, shaped for the web UI's results table."""

    rank: int
    truck_id: str
    driver: str
    total_score: int
    lane_fit: int
    rate_quality: int
    hos_compliance: int
    equipment_match: int
    reasoning: str


class MatchResponse(BaseModel):
    """Full JSON response for a GET /match/{load_id} request."""

    load_id: str
    origin: str
    destination: str
    equipment_type: str
    rate_usd: float
    matches: list[MatchRow]


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the single-page dispatch UI with a dropdown of all loads.

    Args:
        request: The incoming request, required by Jinja2Templates.

    Returns:
        The rendered index.html page.
    """
    loads = get_available_loads()
    return templates.TemplateResponse("index.html", {"request": request, "loads": loads})


@app.get("/match/{load_id}", response_model=MatchResponse)
def match(load_id: str) -> MatchResponse:
    """Score every available truck against a load and return ranked matches.

    Reuses the existing deterministic scoring pipeline (compute_match_score
    via agents.load_matching.agent.match_load) unchanged — this endpoint
    only reshapes the result for JSON/UI consumption.

    Args:
        load_id: The load id to match trucks against, e.g. "LOAD001".

    Returns:
        A MatchResponse with the load's summary and ranked truck matches.

    Raises:
        HTTPException: 404 if load_id does not exist in the fixture data.
    """
    try:
        load = find_load(load_id)
        results = match_load(load_id)
    except DataError as exc:
        logger.error(f"Web match request failed for load_id={load_id}: {exc}")
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    trucks_by_id = {truck.truck_id: truck for truck in get_available_trucks()}
    rows = [
        MatchRow(
            rank=rank,
            truck_id=result.truck_id,
            driver=trucks_by_id[result.truck_id].driver_name,
            total_score=result.total_score,
            lane_fit=result.sub_scores.lane_fit,
            rate_quality=result.sub_scores.rate_quality,
            hos_compliance=result.sub_scores.hos_compliance,
            equipment_match=result.sub_scores.equipment_match,
            reasoning=result.reasoning,
        )
        for rank, result in enumerate(results, start=1)
    ]

    return MatchResponse(
        load_id=load.load_id,
        origin=load.origin,
        destination=load.destination,
        equipment_type=load.equipment_type,
        rate_usd=load.rate_usd,
        matches=rows,
    )
