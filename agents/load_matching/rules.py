"""Deterministic scoring logic for the Load Matching Agent.

Every function here is pure (no I/O, no LLM calls) and fully unit-testable.
compute_match_score() combines the four sub-scores into a single MatchScore.
"""

import math

from agents.load_matching.schemas import DriverHOS, Load, MatchScore, Truck

# Approximate city-center coordinates for every city used in the load_matching
# fixtures. Distances derived from this table are used only to score matches,
# never to route real vehicles.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Atlanta, GA": (33.7490, -84.3880),
    "Dallas, TX": (32.7767, -96.7970),
    "Chicago, IL": (41.8781, -87.6298),
    "Los Angeles, CA": (34.0522, -118.2437),
    "Memphis, TN": (35.1495, -90.0490),
    "Charlotte, NC": (35.2271, -80.8431),
    "Columbus, OH": (39.9612, -82.9988),
    "Denver, CO": (39.7392, -104.9903),
    "Phoenix, AZ": (33.4484, -112.0740),
    "Nashville, TN": (36.1627, -86.7816),
    "Indianapolis, IN": (39.7684, -86.1581),
    "Kansas City, MO": (39.0997, -94.5786),
    "Louisville, KY": (38.2527, -85.7585),
    "Jacksonville, FL": (30.3322, -81.6557),
    "Houston, TX": (29.7604, -95.3698),
}

_EARTH_RADIUS_MILES = 3958.8
_AVG_TRUCK_SPEED_MPH = 50.0
_FMCSA_CYCLE_LIMIT_HOURS = 70.0

LANE_FIT_MAX = 40
RATE_QUALITY_MAX = 30
HOS_COMPLIANCE_MAX = 20
EQUIPMENT_MATCH_MAX = 10


def city_distance_miles(city_a: str, city_b: str) -> float:
    """Return the great-circle distance in miles between two known cities.

    Args:
        city_a: A city string present in CITY_COORDS, e.g. "Atlanta, GA".
        city_b: A city string present in CITY_COORDS.

    Returns:
        Distance in miles. Returns 0.0 if city_a == city_b.

    Raises:
        KeyError: If either city is not in CITY_COORDS.
    """
    if city_a == city_b:
        return 0.0

    lat1, lon1 = CITY_COORDS[city_a]
    lat2, lon2 = CITY_COORDS[city_b]

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_MILES * c


def score_lane_fit(load: Load, truck: Truck) -> int:
    """Score how well a truck's current position fits a load's origin (0-40).

    A truck already sitting at the load's origin scores the maximum; the
    score decays linearly with deadhead distance to the origin.

    Args:
        load: The load being scored.
        truck: The candidate truck.

    Returns:
        An integer score from 0 to 40.
    """
    deadhead_miles = city_distance_miles(truck.current_location, load.origin)
    score = LANE_FIT_MAX * max(0.0, 1 - deadhead_miles / 1000.0)
    return max(0, min(LANE_FIT_MAX, round(score)))


def score_rate_quality(load: Load, lane_avg: float) -> int:
    """Score a load's rate relative to its lane's historical average (0-30).

    A rate at the lane average scores at the midpoint; rates above average
    score higher, rates below average score lower.

    Args:
        load: The load being scored.
        lane_avg: The average rate (USD) for this load's lane.

    Returns:
        An integer score from 0 to 30.
    """
    if lane_avg <= 0:
        return 0
    ratio = load.rate_usd / lane_avg
    score = (RATE_QUALITY_MAX / 2) + (ratio - 1) * 100
    return max(0, min(RATE_QUALITY_MAX, round(score)))


def score_hos_compliance(load: Load, hos: DriverHOS) -> int:
    """Score whether a driver has legal hours to run a load's haul (0-20).

    Estimates required drive time from the load's origin-to-destination
    distance at an average highway speed. Returns 0 if the driver lacks
    enough hours today, or if driving the load would exceed the FMCSA
    70-hour/8-day cycle limit. Otherwise scales up with available headroom.

    Args:
        load: The load being scored.
        hos: The candidate driver's hours-of-service record.

    Returns:
        An integer score from 0 to 20.
    """
    required_hours = city_distance_miles(load.origin, load.destination) / _AVG_TRUCK_SPEED_MPH

    if required_hours > hos.hours_available_today:
        return 0
    if hos.cycle_hours_used_8day + required_hours > _FMCSA_CYCLE_LIMIT_HOURS:
        return 0

    surplus = hos.hours_available_today - required_hours
    surplus_ratio = min(1.0, surplus / max(required_hours, 1.0))
    score = (HOS_COMPLIANCE_MAX / 2) + (HOS_COMPLIANCE_MAX / 2) * surplus_ratio
    return max(0, min(HOS_COMPLIANCE_MAX, round(score)))


def score_equipment_match(load: Load, truck: Truck) -> int:
    """Score equipment compatibility between a load and a truck (0 or 10).

    Requires matching equipment type. If the load requires hazmat handling,
    the truck must also carry a hazmat endorsement.

    Args:
        load: The load being scored.
        truck: The candidate truck.

    Returns:
        10 if fully compatible, 0 otherwise.
    """
    if load.equipment_type != truck.equipment_type:
        return 0
    if load.hazmat_required and not truck.hazmat_endorsement:
        return 0
    return EQUIPMENT_MATCH_MAX


def compute_match_score(
    load: Load, truck: Truck, hos: DriverHOS, lane_avg: float
) -> MatchScore:
    """Compute the full MatchScore for one (load, truck) pair.

    Args:
        load: The load being scored.
        truck: The candidate truck.
        hos: The candidate driver's hours-of-service record.
        lane_avg: The average historical rate (USD) for this load's lane.

    Returns:
        A MatchScore with all four sub-scores populated.
    """
    return MatchScore(
        lane_fit=score_lane_fit(load, truck),
        rate_quality=score_rate_quality(load, lane_avg),
        hos_compliance=score_hos_compliance(load, hos),
        equipment_match=score_equipment_match(load, truck),
    )
