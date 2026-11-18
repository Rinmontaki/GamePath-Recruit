"""Thin integration layer between Streamlit screens and the existing backend.

The backend is authoritative for decisions, validations, paths and persistence.
The UI does not pretend to implement authentication; reviewer identities in this
prototype must be backed by a real authentication system before deployment.
"""

from __future__ import annotations

import csv
import io
import os
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from backend.algorithms.bfs import bfs
from backend.structures.binary_tree import BinaryDecisionTree
from backend.algorithms.dfs import dfs
from backend.loaders.graph_loader import load_graph
from backend.loaders.tree_loader import load_tree
from backend.models.applicant import Applicant
from backend.models.vod_review import ReviewDecision, SkillScores, VodReview
from backend.repositories.applicant_repository import ApplicantRepository
from backend.repositories.training_progress_repository import TrainingProgressRepository
from backend.repositories.vod_review_repository import VodReviewRepository
from backend.services.opportunities_workflow_service import OpportunitiesWorkflowService
from backend.services.recruitment_service import RecruitmentService
from backend.services.reevaluation_workflow_service import ReevaluationWorkflowService
from backend.services.review_workflow_service import ReviewWorkflowService
from backend.services.training_completion_workflow_service import TrainingCompletionWorkflowService
from backend.services.training_service import TrainingService
from backend.services.training_workflow_service import TrainingWorkflowService
from backend.services.vod_review_service import VodReviewService
from backend.storage.database import Database

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("GAMEPATH_DB_PATH", str(ROOT / "data" / "gamepath.sqlite3"))).resolve()
UPLOADS = ROOT / "uploads"
MAX_VOD_BYTES = 150 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi"}
RANKS = ("hierro", "bronce", "plata", "oro", "platino", "diamante", "ascendente", "inmortal", "radiante")
ROLES = ("Duelista", "Iniciador", "Controlador", "Centinela", "Flexible")


@dataclass(frozen=True)
class ApplicantSummary:
    applicant: Applicant
    classification: str
    eligible: bool
    stage: str
    reviewed: bool
    decision: str | None
    completed_skills: frozenset[str]
    reevaluation_approved: bool


class GamePathFacade:
    """Operate the project using the original services, not mock business rules."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self.database = Database(db_path)
        self.database.initialize()
        self.graph = load_graph(ROOT / "backend" / "data" / "training_graph.json")
        self.tree = load_tree(ROOT / "backend" / "data" / "profile_tree.json")
        self.recruitment = RecruitmentService(BinaryDecisionTree(self.tree))
        self.applicants = ApplicantRepository(self.database)
        self.reviews = VodReviewRepository(self.database)
        self.progress = TrainingProgressRepository(self.database)

    @property
    def db_path(self) -> Path:
        return self.database._path

    def list_reviewers(self) -> tuple[dict, ...]:
        with self.database.connection() as conn:
            rows = conn.execute(
                "SELECT reviewer_id, display_name, is_active FROM reviewers ORDER BY display_name"
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def reviewer_ids(self) -> set[str]:
        return {r["reviewer_id"] for r in self.list_reviewers() if r["is_active"] == 1}

    def activate_local_reviewer(self) -> None:
        """Demo-only reviewer for local workshops; not a login or role system."""
        with self.database.connection() as conn:
            conn.execute(
                "INSERT INTO reviewers (reviewer_id, display_name, is_active) VALUES (?, ?, 1) "
                "ON CONFLICT(reviewer_id) DO UPDATE SET display_name = excluded.display_name, is_active = 1",
                ("reclutador_demo", "Reclutador local (DEMO)"),
            )

    def register(self, *, game_name: str, daily_play_hours: float, peak_rank: str,
                 accepts_training: bool, current_rank: str | None = None,
                 preferred_role: str | None = None, vod_reference: str | None = None,
                 applicant_id: str | None = None) -> Applicant:
        applicant = Applicant(
            applicant_id=applicant_id or f"GP-{uuid.uuid4().hex[:8].upper()}",
            game_name=game_name.strip(), daily_play_hours=float(daily_play_hours),
            peak_rank=peak_rank.strip().lower(), accepts_training=accepts_training,
            current_rank=current_rank or None, preferred_role=preferred_role or None,
            vod_reference=vod_reference or None,
        )
        if applicant.peak_rank not in RANKS:
            raise ValueError("El rango maximo no existe en el arbol de VALORANT.")
        self.applicants.add(applicant)
        return applicant

    def set_vod_reference(self, applicant_id: str, reference: str) -> None:
        """Allow uploading a missing/new VOD while preserving review history."""
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Indica una referencia de VOD valida.")
        if self.applicants.get_by_id(applicant_id) is None:
            raise ValueError("Aspirante no encontrado.")
        with self.database.connection() as conn:
            conn.execute(
                "UPDATE applicants SET vod_reference = ? WHERE applicant_id = ?",
                (reference.strip(), applicant_id),
            )

    @staticmethod
    def store_vod(uploaded_file) -> str:
        """Store limited-size video with generated name (never trust filenames)."""
        original = str(getattr(uploaded_file, "name", ""))
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Solo se permiten grabaciones MP4, MOV, AVI o WEBM.")
        declared_size = getattr(uploaded_file, "size", None)
        if declared_size is not None and declared_size > MAX_VOD_BYTES:
            raise ValueError("El video supera los 150 MB permitidos.")
        UPLOADS.mkdir(parents=True, exist_ok=True)
        file_name = f"vod_{uuid.uuid4().hex}{suffix}"
        dest = UPLOADS / file_name
        count = 0
        try:
            with dest.open("wb") as output:
                while True:
                    block = uploaded_file.read(1024 * 1024)
                    if not block:
                        break
                    count += len(block)
                    if count > MAX_VOD_BYTES:
                        raise ValueError("El video supera los 150 MB permitidos.")
                    output.write(block)
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        return f"uploads/{file_name}"

    @staticmethod
    def local_vod_path(reference: str | None) -> Path | None:
        """Resolve only known app upload paths; never traverse the filesystem."""
        if not reference or not reference.startswith("uploads/"):
            return None
        name = Path(reference).name
        if not re.fullmatch(r"vod_[0-9a-f]{32}\.(mp4|mov|webm|avi)", name):
            return None
        file = (UPLOADS / name).resolve()
        return file if file.is_file() and file.parent == UPLOADS.resolve() else None

    def get_applicant(self, applicant_id: str) -> Applicant | None:
        return self.applicants.get_by_id(applicant_id)

    def preselect(self, applicant_id: str) -> dict:
        applicant = self.get_applicant(applicant_id)
        if applicant is None:
            raise ValueError("Aspirante no encontrado.")
        return self.recruitment.preselect(applicant)

    def list_summaries(self) -> tuple[ApplicantSummary, ...]:
        result: list[ApplicantSummary] = []
        for applicant in self.applicants.get_all():
            pre = self.recruitment.preselect(applicant)
            review = self.reviews.get_latest_for_applicant(applicant.applicant_id)
            active_review = bool(review and review.vod_reference == applicant.vod_reference)
            current_review = review if active_review else None
            progress = self.progress.get_for_applicant(applicant.applicant_id)
            skills = progress.completed_skills if progress and current_review else frozenset()
            with self.database.connection() as conn:
                current_reviewer = conn.execute(
                    "SELECT is_active FROM reviewers WHERE reviewer_id = ?",
                    (current_review.reviewer_id,) if current_review else ("",),
                ).fetchone()
                reviewer_active = bool(current_reviewer and current_reviewer["is_active"] == 1)
                reevaluation = conn.execute(
                    "SELECT approved, vod_review_id, reviewer_id FROM reevaluations WHERE applicant_id = ? "
                    "ORDER BY reevaluation_id DESC LIMIT 1", (applicant.applicant_id,)
                ).fetchone()
                last_review_id = conn.execute(
                    "SELECT review_id FROM vod_reviews WHERE applicant_id = ? "
                    "ORDER BY review_id DESC LIMIT 1", (applicant.applicant_id,)
                ).fetchone()
            reevaluation_approved = bool(
                reevaluation and reevaluation["approved"] == 1 and active_review
                and current_review and current_review.is_approved
                and last_review_id and reevaluation["vod_review_id"] == last_review_id["review_id"]
                and reviewer_active and reevaluation["reviewer_id"] in self.reviewer_ids()
            )
            if not pre["eligible_for_vod_review"]:
                stage = "Orientacion"
            elif not applicant.vod_reference:
                stage = "VOD pendiente"
            elif not current_review:
                stage = "Revision VOD"
            elif not reviewer_active:
                stage = "Revision suspendida"
            elif current_review.decision is ReviewDecision.REJECTED:
                stage = "No admitido"
            elif current_review.decision is ReviewDecision.MORE_EVIDENCE:
                stage = "Mas evidencia"
            elif len(skills) < 2:
                stage = "Entrenamiento"
            elif reevaluation_approved:
                stage = "Oportunidades"
            elif reevaluation and reevaluation["approved"] == 0:
                stage = "Reevaluacion no aprobada"
            else:
                stage = "Reevaluacion"
            result.append(ApplicantSummary(
                applicant=applicant, classification=str(pre["classification"]),
                eligible=bool(pre["eligible_for_vod_review"]), stage=stage,
                reviewed=bool(current_review),
                decision=current_review.decision.value if current_review else None,
                completed_skills=skills,
                reevaluation_approved=reevaluation_approved,
            ))
        return tuple(result)

    def get_summary(self, applicant_id: str) -> ApplicantSummary:
        return next(s for s in self.list_summaries() if s.applicant.applicant_id == applicant_id)

    def latest_review(self, applicant_id: str):
        return self.reviews.get_latest_for_applicant(applicant_id)

    def review_history(self, applicant_id: str):
        return self.reviews.get_for_applicant(applicant_id)

    def _services(self):
        reviewers = self.reviewer_ids()
        if not reviewers:
            raise PermissionError("No hay reclutadores activos. Activa el reclutador local de demostracion.")
        vod_service = VodReviewService(self.recruitment, reviewers)
        review_flow = ReviewWorkflowService(self.database, vod_service)
        training_flow = TrainingWorkflowService(
            self.database, TrainingService(self.graph, vod_service)
        )
        completion_flow = TrainingCompletionWorkflowService(self.database, training_flow, reviewers)
        reevaluation_flow = ReevaluationWorkflowService(self.database, training_flow, reviewers)
        opportunities_flow = OpportunitiesWorkflowService(self.database, training_flow, self.graph, reviewers)
        return review_flow, training_flow, completion_flow, reevaluation_flow, opportunities_flow

    def record_review(self, applicant_id: str, reviewer_id: str, decision: str,
                      scores: dict[str, int], feedback: str) -> int:
        applicant = self.get_applicant(applicant_id)
        if applicant is None or not applicant.vod_reference:
            raise ValueError("El aspirante necesita un VOD registrado.")
        review = VodReview(
            applicant_id=applicant_id, reviewer_id=reviewer_id,
            vod_reference=applicant.vod_reference, scores=SkillScores(**scores),
            decision=ReviewDecision(decision), feedback=feedback.strip(),
        )
        review_flow, *_ = self._services()
        return review_flow.record_review(review, authenticated_reviewer_id=reviewer_id)

    def training_plan(self, applicant_id: str):
        return self._services()[1].plan_for_applicant(applicant_id)

    def record_completion(self, applicant_id: str, skill: str, reviewer_id: str):
        return self._services()[2].record_completion(
            applicant_id, skill, authenticated_reviewer_id=reviewer_id,
        )

    def record_reevaluation(self, applicant_id: str, reviewer_id: str,
                            approved: bool, feedback: str) -> int:
        return self._services()[3].record_reevaluation(
            applicant_id, approved=approved, feedback=feedback,
            authenticated_reviewer_id=reviewer_id,
        )

    def latest_reevaluation(self, applicant_id: str) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT r.*, v.display_name FROM reevaluations r "
                "LEFT JOIN reviewers v ON v.reviewer_id = r.reviewer_id "
                "WHERE r.applicant_id = ? ORDER BY r.reevaluation_id DESC LIMIT 1",
                (applicant_id,),
            ).fetchone()
        return dict(row) if row else None

    def opportunities(self, applicant_id: str):
        return self._services()[4].get_available_opportunities(applicant_id)

    def graph_traversals(self, include_opportunities: bool = False) -> dict[str, tuple[str, ...]]:
        granted = ["recruiter_admission_approved"]
        if include_opportunities:
            granted.append("human_reevaluation_approved")
        return {"BFS": bfs(self.graph, granted), "DFS": dfs(self.graph, granted)}

    def counts(self) -> dict[str, int]:
        summaries = self.list_summaries()
        return {
            "total": len(summaries),
            "preselected": sum(s.eligible for s in summaries),
            "review": sum(s.stage in ("Revision VOD", "Mas evidencia") for s in summaries),
            "training": sum(s.stage == "Entrenamiento" for s in summaries),
            "opportunities": sum(s.stage == "Oportunidades" for s in summaries),
        }

    def export_csv(self) -> bytes:
        """Export summaries with spreadsheet formula neutralization."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "jugador", "peak_rank", "rango_actual", "rol", "horas_dia", "clasificacion", "estado"])
        def safe(value):
            value = str(value or "")
            return "'" + value if value and value[0] in "=+-@" else value
        for s in self.list_summaries():
            a = s.applicant
            writer.writerow([safe(a.applicant_id), safe(a.game_name), safe(a.peak_rank),
                             safe(a.current_rank), safe(a.preferred_role), a.daily_play_hours,
                             safe(s.classification), safe(s.stage)])
        return output.getvalue().encode("utf-8-sig")

    def seed_demo(self) -> int:
        """Idempotent sample scenario, only called after an explicit UI click."""
        self.activate_local_reviewer()
        examples = [
            ("DEMO-001", "NOVA#404", 7.0, "inmortal", "ascendente", "Duelista", "https://example.com/demo-vod-1"),
            ("DEMO-002", "ECHO#808", 5.5, "diamante", "diamante", "Iniciador", "https://example.com/demo-vod-2"),
            ("DEMO-003", "KIRA#777", 6.0, "platino", "oro", "Centinela", "https://example.com/demo-vod-3"),
            ("DEMO-004", "ONYX#002", 3.0, "plata", "plata", "Controlador", None),
            ("DEMO-005", "PHASE#5", 8.0, "radiante", "inmortal", "Flexible", "https://example.com/demo-vod-5"),
            ("DEMO-006", "SYN#730", 5.0, "oro", "oro", "Iniciador", None),
        ]
        added = 0
        for user_id, game, hours, peak, rank, role, vod in examples:
            if self.get_applicant(user_id) is not None:
                continue
            self.register(applicant_id=user_id, game_name=game, daily_play_hours=hours,
                          peak_rank=peak, accepts_training=True, current_rank=rank,
                          preferred_role=role, vod_reference=vod)
            added += 1
        scores = {"aim": 4, "game_sense": 4, "rotations": 3, "macro": 4, "micro": 4, "communication": 5}
        for user_id, decision, message in [
            ("DEMO-001", "approved", "Excelente disciplina competitiva."),
            ("DEMO-002", "approved", "Buena lectura de rondas; desarrollar comunicacion."),
            ("DEMO-003", "more_evidence", "Se requiere un VOD completo de partida."),
            ("DEMO-005", "approved", "Nivel avanzado, apto para entrenamiento."),
        ]:
            if not self.latest_review(user_id):
                self.record_review(user_id, "reclutador_demo", decision, scores, message)
        for user_id, skills in [("DEMO-001", ["aim", "tactics"]), ("DEMO-002", ["aim"]), ("DEMO-005", ["aim", "tactics"])]:
            done = self.progress.get_for_applicant(user_id)
            for skill in skills:
                if done and skill in done.completed_skills:
                    continue
                self.record_completion(user_id, skill, "reclutador_demo")
        if self.latest_reevaluation("DEMO-001") is None:
            self.record_reevaluation("DEMO-001", "reclutador_demo", True, "Aprobado para rutas competitivas.")
        return added
