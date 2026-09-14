"""Load Matching Agent — main entry point and CLI.

Scores every available truck against a target load using deterministic
rules (agents/load_matching/rules.py) and prints the top 10 matches.

Usage:
    python -m agents.load_matching.agent --load-id LOAD001 [--dry-run]
"""

import argparse
import sys

from rich.console import Console
from rich.table import Table

from agents.load_matching.rules import compute_match_score
from agents.load_matching.schemas import Load, MatchResult, MatchScore, Truck
from agents.load_matching.tools import (
    get_available_loads,
    get_available_trucks,
    get_driver_hos,
    get_lane_history_rate,
)
from shared.errors import DataError
from shared.logging import get_logger

logger = get_logger("load_matching")

TOP_N_MATCHES = 10


def find_load(load_id: str) -> Load:
    """Find a load by id among all available loads.

    Args:
        load_id: The load id to look up, e.g. "LOAD001".

    Returns:
        The matching Load.

    Raises:
        DataError: If no load with that id exists.
    """
    for load in get_available_loads():
        if load.load_id == load_id:
            return load
    raise DataError(f"No load found with load_id: {load_id}")


def build_reasoning(load: Load, truck: Truck, sub_scores: MatchScore) -> str:
    """Build a one-line, plain-English explanation for a match's score.

    Args:
        load: The load being matched.
        truck: The candidate truck.
        sub_scores: The computed sub-scores for this pair.

    Returns:
        A short human-readable reasoning string.
    """
    parts = []

    if sub_scores.lane_fit >= 35:
        parts.append(f"{truck.truck_id} is already at the origin ({load.origin})")
    elif sub_scores.lane_fit > 0:
        parts.append(f"{truck.truck_id} has a moderate deadhead to {load.origin}")
    else:
        parts.append(f"{truck.truck_id} has a long deadhead to {load.origin}")

    if sub_scores.equipment_match == 0:
        if load.equipment_type != truck.equipment_type:
            parts.append(f"equipment mismatch ({truck.equipment_type} vs required {load.equipment_type})")
        else:
            parts.append("missing required hazmat endorsement")
    else:
        parts.append("equipment matches")

    if sub_scores.hos_compliance == 0:
        parts.append("driver lacks legal hours for this haul")
    elif sub_scores.hos_compliance >= 15:
        parts.append("driver has ample HOS headroom")
    else:
        parts.append("driver has adequate but limited HOS headroom")

    if sub_scores.rate_quality >= 20:
        parts.append("rate beats the lane average")
    elif sub_scores.rate_quality >= 10:
        parts.append("rate is near the lane average")
    else:
        parts.append("rate is below the lane average")

    return "; ".join(parts) + "."


def match_load(load_id: str) -> list[MatchResult]:
    """Score every available truck against a load and return ranked matches.

    Args:
        load_id: The load id to match trucks against.

    Returns:
        The top TOP_N_MATCHES MatchResult objects, sorted by total_score
        descending.

    Raises:
        DataError: If the load id does not exist.
    """
    load = find_load(load_id)
    trucks = get_available_trucks()
    lane_avg = get_lane_history_rate(load.origin, load.destination)

    logger.info(
        f"Scoring load {load.load_id} ({load.origin} -> {load.destination}) "
        f"against {len(trucks)} trucks; lane_avg=${lane_avg:.2f}"
    )

    results: list[MatchResult] = []
    for truck in trucks:
        hos = get_driver_hos(truck.driver_id)
        sub_scores = compute_match_score(load, truck, hos, lane_avg)
        if sub_scores.equipment_match == 0:
            # Equipment-incompatible trucks (wrong trailer type, or missing a
            # required hazmat endorsement) cannot legally or physically haul
            # this load, so they are excluded from the ranked results rather
            # than merely down-scored.
            continue
        results.append(
            MatchResult(
                load_id=load.load_id,
                truck_id=truck.truck_id,
                total_score=sub_scores.total,
                reasoning=build_reasoning(load, truck, sub_scores),
                sub_scores=sub_scores,
            )
        )

    results.sort(key=lambda r: r.total_score, reverse=True)
    return results[:TOP_N_MATCHES]


def print_matches(load: Load, results: list[MatchResult]) -> None:
    """Print ranked match results as a rich table.

    Args:
        load: The load that was matched.
        results: Ranked MatchResult objects to display.
    """
    console = Console()
    trucks_by_id = {truck.truck_id: truck for truck in get_available_trucks()}

    console.print(
        f"\n[bold]Top matches for {load.load_id}[/bold] "
        f"({load.origin} -> {load.destination}, {load.equipment_type}, "
        f"${load.rate_usd:,.0f})\n"
    )

    table = Table(show_lines=False)
    table.add_column("Rank", justify="right")
    table.add_column("Truck ID")
    table.add_column("Driver")
    table.add_column("Total", justify="right")
    table.add_column("Lane", justify="right")
    table.add_column("Rate", justify="right")
    table.add_column("HOS", justify="right")
    table.add_column("Equip", justify="right")
    table.add_column("Reasoning")

    for rank, result in enumerate(results, start=1):
        truck = trucks_by_id[result.truck_id]
        table.add_row(
            str(rank),
            result.truck_id,
            truck.driver_name,
            str(result.total_score),
            str(result.sub_scores.lane_fit),
            str(result.sub_scores.rate_quality),
            str(result.sub_scores.hos_compliance),
            str(result.sub_scores.equipment_match),
            result.reasoning,
        )

    console.print(table)


def main() -> None:
    """CLI entry point: python -m agents.load_matching.agent --load-id LOAD001."""
    parser = argparse.ArgumentParser(description="Load Matching Agent")
    parser.add_argument("--load-id", required=True, help="Load id to match, e.g. LOAD001")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip any LLM calls and only print deterministic rule-based results.",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("Running in --dry-run mode: no LLM calls will be made.")

    try:
        load = find_load(args.load_id)
        results = match_load(args.load_id)
    except DataError as exc:
        logger.error(f"Load matching failed: {exc}")
        Console().print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)

    print_matches(load, results)


if __name__ == "__main__":
    main()
