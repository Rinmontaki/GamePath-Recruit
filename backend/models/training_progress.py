
"""Represent individual training progress in GamePath Recruit."""

from dataclasses import dataclass, field


SUPPORTED_SKILLS = frozenset({"aim", "tactics"})


@dataclass(frozen=True, slots=True)
class TrainingProgress:
    """Store the completed skills of an admitted player."""

    applicant_id: str
    completed_skills: frozenset[str] = field(
        default_factory=frozenset
    )

    def __post_init__(self) -> None:
        """Validate the applicant and completed skills."""
        if (
            not isinstance(self.applicant_id, str)
            or not self.applicant_id.strip()
        ):
            raise ValueError("Applicant ID cannot be empty.")

        if not isinstance(self.completed_skills, frozenset):
            raise TypeError("Completed skills must be a frozenset.")

        if any(
            not isinstance(skill, str) or not skill.strip()
            for skill in self.completed_skills
        ):
            raise ValueError("Invalid completed skill.")

        unknown_skills = self.completed_skills - SUPPORTED_SKILLS

        if unknown_skills:
            raise ValueError(
                f"Unsupported skills: {sorted(unknown_skills)}"
            )

    @property
    def current_node_id(self) -> str:
        """Map completed skills to the graph training state."""
        aim = int("aim" in self.completed_skills)
        tactics = int("tactics" in self.completed_skills)

        return f"training_{aim}{tactics}"

    @property
    def is_training_complete(self) -> bool:
        """Check whether both required skills are completed."""
        return SUPPORTED_SKILLS.issubset(self.completed_skills)

    @property
    def pending_skills(self) -> frozenset[str]:
        """Return skills that still need training."""
        return SUPPORTED_SKILLS - self.completed_skills
