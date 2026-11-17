
"""Represent an applicant in GamePath Recruit."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Applicant:
    """Store a VALORANT applicant's competitive profile."""

    applicant_id: str
    game_name: str
    daily_play_hours: float
    peak_rank: str
    accepts_training: bool

    current_rank: str | None = None
    preferred_role: str | None = None
    vod_reference: str | None = None

    def __post_init__(self) -> None:
        """Validate the applicant's initial information."""
        required_fields = (
            "applicant_id",
            "game_name",
            "peak_rank",
        )

        for field_name in required_fields:
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Invalid required field: {field_name}"
                )

        hours = self.daily_play_hours

        if (
            type(hours) not in (int, float)
            or not math.isfinite(hours)
            or not 0 <= hours <= 24
        ):
            raise ValueError(
                "Daily play hours must be between 0 and 24."
            )

        if type(self.accepts_training) is not bool:
            raise ValueError(
                "Training acceptance must be boolean."
            )

        optional_fields = (
            "current_rank",
            "preferred_role",
            "vod_reference",
        )

        for field_name in optional_fields:
            value = getattr(self, field_name)

            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
            ):
                raise ValueError(
                    f"Invalid optional field: {field_name}"
                )

    def to_profile(self) -> dict[str, object]:
        """Return the fields required by the binary tree."""
        return {
            "daily_play_hours": self.daily_play_hours,
            "peak_rank": self.peak_rank,
            "accepts_training": self.accepts_training,
        }
