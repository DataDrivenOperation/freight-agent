"""Pydantic models for the Load Matching Agent."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EquipmentType = Literal["dry_van", "reefer", "flatbed"]


class Load(BaseModel):
    """A freight load available to be booked onto a truck."""

    load_id: str
    origin: str
    destination: str
    equipment_type: EquipmentType
    rate_usd: float = Field(gt=0)
    weight_lbs: float = Field(gt=0)
    pickup_date: date
    hazmat_required: bool = False


class Truck(BaseModel):
    """A truck and its driver, available to be matched to a load."""

    truck_id: str
    current_location: str
    equipment_type: EquipmentType
    available_date: date
    driver_id: str
    driver_name: str
    hazmat_endorsement: bool = False


class DriverHOS(BaseModel):
    """Hours-of-service data for a driver at the time of matching."""

    driver_id: str
    hours_driven_today: float = Field(ge=0)
    hours_available_today: float = Field(ge=0)
    last_rest_start: datetime
    cycle_hours_used_8day: float = Field(ge=0)


class MatchScore(BaseModel):
    """Sub-scores that together make up a match's total score (0-100)."""

    lane_fit: int = Field(ge=0, le=40)
    rate_quality: int = Field(ge=0, le=30)
    hos_compliance: int = Field(ge=0, le=20)
    equipment_match: int = Field(ge=0, le=10)

    @property
    def total(self) -> int:
        """Sum of all sub-scores, out of a possible 100."""
        return (
            self.lane_fit
            + self.rate_quality
            + self.hos_compliance
            + self.equipment_match
        )


class MatchResult(BaseModel):
    """The scored result of matching one load to one truck."""

    load_id: str
    truck_id: str
    total_score: int = Field(ge=0, le=100)
    reasoning: str
    sub_scores: MatchScore
