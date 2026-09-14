"""Pytest suite for the Load Matching Agent: scoring functions, tools, and
the end-to-end CLI matching flow. All data comes from fixtures — no real
API calls are made.
"""

import pytest

from agents.load_matching.agent import find_load, match_load
from agents.load_matching.rules import (
    city_distance_miles,
    compute_match_score,
    score_equipment_match,
    score_hos_compliance,
    score_lane_fit,
    score_rate_quality,
)
from agents.load_matching.schemas import DriverHOS, Load, Truck
from agents.load_matching.tools import (
    get_available_loads,
    get_available_trucks,
    get_driver_hos,
    get_lane_history_rate,
)
from shared.errors import DataError


@pytest.fixture
def loads() -> dict[str, Load]:
    """All fixture loads, keyed by load_id."""
    return {load.load_id: load for load in get_available_loads()}


@pytest.fixture
def trucks() -> dict[str, Truck]:
    """All fixture trucks, keyed by truck_id."""
    return {truck.truck_id: truck for truck in get_available_trucks()}


@pytest.fixture
def hos_by_driver() -> dict[str, DriverHOS]:
    """HOS records for every fixture driver, keyed by driver_id."""
    return {truck.driver_id: get_driver_hos(truck.driver_id) for truck in get_available_trucks()}


# ---------------------------------------------------------------------------
# tools.py
# ---------------------------------------------------------------------------


def test_get_available_loads_returns_fifteen():
    """Fixture data must contain exactly 15 loads, per spec."""
    assert len(get_available_loads()) == 15


def test_get_available_trucks_returns_ten():
    """Fixture data must contain exactly 10 trucks, per spec."""
    assert len(get_available_trucks()) == 10


def test_get_available_loads_are_typed():
    """Every loaded load must be a valid Load instance."""
    assert all(isinstance(load, Load) for load in get_available_loads())


def test_get_driver_hos_returns_record_for_known_driver():
    """A known driver_id returns its HOS record with a matching driver_id."""
    hos = get_driver_hos("DRV001")
    assert hos.driver_id == "DRV001"


def test_get_driver_hos_raises_for_unknown_driver():
    """An unknown driver_id raises DataError rather than failing silently."""
    with pytest.raises(DataError):
        get_driver_hos("DRV999")


def test_get_lane_history_rate_is_undirected():
    """Lane average must be identical regardless of query direction."""
    forward = get_lane_history_rate("Atlanta, GA", "Charlotte, NC")
    backward = get_lane_history_rate("Charlotte, NC", "Atlanta, GA")
    assert forward == backward
    assert forward == pytest.approx(1950.0)


def test_get_lane_history_rate_raises_for_unknown_lane():
    """A lane with no fixture loads at all raises DataError."""
    with pytest.raises(DataError):
        get_lane_history_rate("Nowhere, ZZ", "Nowhere Else, ZZ")


# ---------------------------------------------------------------------------
# score_lane_fit
# ---------------------------------------------------------------------------


def test_lane_fit_max_when_truck_already_at_origin(loads, trucks):
    """A truck sitting at the load's origin scores the maximum lane_fit."""
    load = loads["LOAD001"]  # origin: Atlanta, GA
    truck = trucks["TRUCK001"]  # current_location: Atlanta, GA
    assert score_lane_fit(load, truck) == 40


def test_lane_fit_decreases_with_deadhead(loads, trucks):
    """A truck far from the load's origin scores lower than one nearby."""
    load = loads["LOAD001"]  # origin: Atlanta, GA
    near = trucks["TRUCK006"]  # Charlotte, NC — a few hundred miles away
    far = trucks["TRUCK004"]  # Los Angeles, CA — cross-country
    assert score_lane_fit(load, near) > score_lane_fit(load, far)


def test_lane_fit_never_negative(loads, trucks):
    """Lane fit score is clamped at 0, never negative, for very long deadheads."""
    load = loads["LOAD004"]  # origin: Los Angeles, CA
    truck = trucks["TRUCK007"]  # Columbus, OH — very far from LA
    assert score_lane_fit(load, truck) >= 0


def test_city_distance_zero_for_same_city():
    """Distance between a city and itself is exactly zero."""
    assert city_distance_miles("Atlanta, GA", "Atlanta, GA") == 0.0


# ---------------------------------------------------------------------------
# score_rate_quality
# ---------------------------------------------------------------------------


def test_rate_quality_high_when_rate_beats_lane_average(loads):
    """A load priced above its lane average scores above the midpoint."""
    load = loads["LOAD013"]  # rate 2800, lane_avg 2125
    lane_avg = get_lane_history_rate(load.origin, load.destination)
    assert score_rate_quality(load, lane_avg) > 15


def test_rate_quality_low_for_below_market_load(loads):
    """The intentionally below-market load (LOAD006) scores rate_quality at 0."""
    load = loads["LOAD006"]  # rate 1450, lane_avg 2125 (~32% below average)
    lane_avg = get_lane_history_rate(load.origin, load.destination)
    assert score_rate_quality(load, lane_avg) == 0


def test_rate_quality_midpoint_when_rate_equals_average(loads):
    """A load priced exactly at the lane average scores the midpoint (15)."""
    load = loads["LOAD001"]
    assert score_rate_quality(load, load.rate_usd) == 15


def test_rate_quality_capped_at_max(loads):
    """rate_quality never exceeds its documented maximum of 30."""
    load = loads["LOAD013"]
    assert score_rate_quality(load, lane_avg=1.0) == 30


def test_rate_quality_zero_for_invalid_lane_avg(loads):
    """A non-positive lane average returns 0 rather than dividing by zero."""
    load = loads["LOAD001"]
    assert score_rate_quality(load, lane_avg=0) == 0


# ---------------------------------------------------------------------------
# score_hos_compliance
# ---------------------------------------------------------------------------


def test_hos_compliance_zero_for_exhausted_driver(loads, hos_by_driver):
    """DRV007 (nearly out of hours) scores 0 hos_compliance on any real haul."""
    load = loads["LOAD001"]
    hos = hos_by_driver["DRV007"]  # hours_available_today: 0.5
    assert score_hos_compliance(load, hos) == 0


def test_hos_compliance_positive_for_fresh_driver(loads, hos_by_driver):
    """A driver with ample hours and cycle headroom scores above 0."""
    load = loads["LOAD001"]
    hos = hos_by_driver["DRV002"]  # 11.0 hours available, low cycle usage
    assert score_hos_compliance(load, hos) > 0


def test_hos_compliance_zero_when_cycle_limit_would_be_exceeded():
    """A driver near the 70-hour/8-day cycle cap scores 0 even with hours today."""
    load = Load(
        load_id="LOADX",
        origin="Atlanta, GA",
        destination="Charlotte, NC",
        equipment_type="dry_van",
        rate_usd=2000,
        weight_lbs=20000,
        pickup_date="2026-09-15",
    )
    hos = DriverHOS(
        driver_id="DRVX",
        hours_driven_today=1.0,
        hours_available_today=10.0,
        last_rest_start="2026-09-14T20:00:00",
        cycle_hours_used_8day=69.5,
    )
    assert score_hos_compliance(load, hos) == 0


def test_hos_compliance_capped_at_max(loads):
    """hos_compliance never exceeds its documented maximum of 20."""
    load = loads["LOAD001"]
    hos = DriverHOS(
        driver_id="DRVX",
        hours_driven_today=0.0,
        hours_available_today=11.0,
        last_rest_start="2026-09-14T20:00:00",
        cycle_hours_used_8day=0.0,
    )
    assert score_hos_compliance(load, hos) <= 20


# ---------------------------------------------------------------------------
# score_equipment_match
# ---------------------------------------------------------------------------


def test_equipment_match_perfect(loads, trucks):
    """Matching equipment type with no hazmat requirement scores the max (10)."""
    load = loads["LOAD001"]  # dry_van, no hazmat
    truck = trucks["TRUCK001"]  # dry_van
    assert score_equipment_match(load, truck) == 10


def test_equipment_match_wrong_type_scores_zero(loads, trucks):
    """A reefer truck cannot serve a dry_van load."""
    load = loads["LOAD001"]  # dry_van
    truck = trucks["TRUCK008"]  # reefer
    assert score_equipment_match(load, truck) == 0


def test_reefer_load_rejects_dry_van_truck(loads, trucks):
    """The reefer load (LOAD006) rejects a dry_van truck outright."""
    load = loads["LOAD006"]  # reefer
    truck = trucks["TRUCK001"]  # dry_van
    assert score_equipment_match(load, truck) == 0


def test_hazmat_load_rejects_truck_without_endorsement(loads, trucks):
    """The hazmat-required load (LOAD004) rejects a same-equipment truck
    that lacks a hazmat endorsement, even though truck types match."""
    load = loads["LOAD004"]  # dry_van, hazmat_required
    truck = trucks["TRUCK001"]  # dry_van, no hazmat endorsement
    assert truck.equipment_type == load.equipment_type
    assert score_equipment_match(load, truck) == 0


def test_hazmat_load_accepts_truck_with_endorsement(loads, trucks):
    """The hazmat-required load (LOAD004) accepts a matching, endorsed truck."""
    load = loads["LOAD004"]  # dry_van, hazmat_required
    truck = trucks["TRUCK004"]  # dry_van, hazmat_endorsement=True
    assert score_equipment_match(load, truck) == 10


# ---------------------------------------------------------------------------
# compute_match_score
# ---------------------------------------------------------------------------


def test_compute_match_score_total_is_sum_of_sub_scores(loads, trucks, hos_by_driver):
    """MatchScore.total equals the sum of its four sub-scores."""
    load = loads["LOAD001"]
    truck = trucks["TRUCK001"]
    hos = hos_by_driver[truck.driver_id]
    lane_avg = get_lane_history_rate(load.origin, load.destination)
    score = compute_match_score(load, truck, hos, lane_avg)
    assert score.total == (
        score.lane_fit + score.rate_quality + score.hos_compliance + score.equipment_match
    )


def test_compute_match_score_within_bounds(loads, trucks, hos_by_driver):
    """The total score is always within the documented 0-100 range."""
    load = loads["LOAD001"]
    truck = trucks["TRUCK008"]
    hos = hos_by_driver[truck.driver_id]
    lane_avg = get_lane_history_rate(load.origin, load.destination)
    score = compute_match_score(load, truck, hos, lane_avg)
    assert 0 <= score.total <= 100


# ---------------------------------------------------------------------------
# agent.py — end-to-end matching
# ---------------------------------------------------------------------------


def test_find_load_raises_for_unknown_id():
    """Requesting a non-existent load_id fails gracefully with DataError."""
    with pytest.raises(DataError):
        find_load("LOAD999")


def test_match_load_returns_at_most_ten_results():
    """match_load never returns more than the top 10 matches."""
    results = match_load("LOAD001")
    assert len(results) <= 10


def test_match_load_results_sorted_descending():
    """Results are sorted by total_score, highest first."""
    results = match_load("LOAD001")
    scores = [r.total_score for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize(
    "load_id,expected_top_truck",
    [
        ("LOAD001", "TRUCK001"),  # Atlanta origin, dry_van, driver has hours
        ("LOAD002", "TRUCK002"),  # Dallas origin, dry_van, driver has hours
        ("LOAD004", "TRUCK004"),  # LA origin, hazmat-required, hazmat-endorsed truck
        ("LOAD006", "TRUCK008"),  # Denver origin, reefer-required, only reefer truck
        ("LOAD013", "TRUCK008"),  # Chicago origin, reefer-required, only reefer truck
    ],
)
def test_deterministic_top_match_for_fixture_loads(load_id, expected_top_truck):
    """Given fixed fixture data, the top match for each load is deterministic."""
    results = match_load(load_id)
    assert results[0].truck_id == expected_top_truck


def test_incompatible_equipment_excluded_from_results():
    """A reefer-only load's results never include a non-reefer truck."""
    results = match_load("LOAD006")
    assert all(r.truck_id == "TRUCK008" for r in results)


def test_hazmat_load_results_only_include_endorsed_trucks():
    """A hazmat-required load's results never include a non-endorsed truck."""
    results = match_load("LOAD004")
    assert all(r.truck_id == "TRUCK004" for r in results)
