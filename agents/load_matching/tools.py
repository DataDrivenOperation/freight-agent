"""Data access functions for the Load Matching Agent.

All data comes from fixtures under /fixtures/load_matching/ via
shared/fixtures.py. No real API calls are made in v1.
"""

from agents.load_matching.schemas import DriverHOS, Load, Truck
from shared.errors import DataError
from shared.fixtures import load_fixtures

_AGENT_NAME = "load_matching"


def get_available_loads() -> list[Load]:
    """Return all loads from the load_matching fixtures.

    Returns:
        A list of Load objects.
    """
    raw_loads = load_fixtures(_AGENT_NAME, "loads.json")
    return [Load.model_validate(item) for item in raw_loads]


def get_available_trucks() -> list[Truck]:
    """Return all trucks from the load_matching fixtures.

    Returns:
        A list of Truck objects.
    """
    raw_trucks = load_fixtures(_AGENT_NAME, "trucks.json")
    return [Truck.model_validate(item) for item in raw_trucks]


def get_driver_hos(driver_id: str) -> DriverHOS:
    """Return hours-of-service data for a specific driver.

    Args:
        driver_id: The driver's id, e.g. "DRV001".

    Returns:
        The driver's DriverHOS record.

    Raises:
        DataError: If no HOS record exists for driver_id.
    """
    raw_records = load_fixtures(_AGENT_NAME, "driver_hos.json")
    for record in raw_records:
        if record["driver_id"] == driver_id:
            return DriverHOS.model_validate(record)
    raise DataError(f"No HOS record found for driver_id: {driver_id}")


def get_lane_history_rate(origin: str, destination: str) -> float:
    """Return the average rate for loads on a given lane, from fixture data.

    The lane is treated as undirected: loads running destination->origin
    count toward the same lane average as origin->destination. If no other
    loads share the lane, the single matching load's own rate is returned.

    Args:
        origin: Origin city string, e.g. "Atlanta, GA".
        destination: Destination city string, e.g. "Charlotte, NC".

    Returns:
        The average rate in USD for loads on this lane.

    Raises:
        DataError: If no loads exist for this lane at all.
    """
    loads = get_available_loads()
    lane = {origin, destination}
    matching_rates = [
        load.rate_usd for load in loads if {load.origin, load.destination} == lane
    ]
    if not matching_rates:
        raise DataError(f"No lane history found for {origin} <-> {destination}")
    return sum(matching_rates) / len(matching_rates)
