"""Integration tests for the real backend and the Streamlit facade."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import frontend.core as core
from frontend.core import GamePathFacade


@pytest.fixture
def facade(tmp_path):
    return GamePathFacade(tmp_path / "gamepath.sqlite3")


def test_register_and_tree_preselection(facade):
    player = facade.register(game_name="TEST#123", daily_play_hours=7,
                             peak_rank="diamante", accepts_training=True,
                             vod_reference="https://example.org/recording")
    result = facade.preselect(player.applicant_id)
    assert result["eligible_for_vod_review"] is True
    assert [d["node_id"] for d in result["decision_path"]] == ["D01","D02","D03","D04"]
    assert facade.get_summary(player.applicant_id).stage == "Revision VOD"
    with pytest.raises(PermissionError):
        facade.training_plan(player.applicant_id)


def test_orientation_cannot_be_reviewed(facade):
    player = facade.register(game_name="LOW#123", daily_play_hours=2,
                             peak_rank="plata", accepts_training=True,
                             vod_reference="https://example.org/vod")
    assert facade.get_summary(player.applicant_id).stage == "Orientacion"
    facade.activate_local_reviewer()
    with pytest.raises(ValueError):
        facade.record_review(player.applicant_id, "reclutador_demo", "approved",
                             dict.fromkeys(("aim","game_sense","rotations","macro","micro","communication"),3),
                             "Needs more playtime")


def test_full_workflow_to_opportunities(facade):
    p = facade.register(game_name="MAIN#777", daily_play_hours=8,
                        peak_rank="radiante", accepts_training=True,
                        vod_reference="https://example.org/vod")
    facade.activate_local_reviewer()
    scores = {s:4 for s in ("aim","game_sense","rotations","macro","micro","communication")}
    facade.record_review(p.applicant_id, "reclutador_demo", "approved", scores, "Approved after human review")
    assert facade.get_summary(p.applicant_id).stage == "Entrenamiento"
    first = facade.training_plan(p.applicant_id)
    assert first.estimated_hours == 6.0
    facade.record_completion(p.applicant_id, "aim", "reclutador_demo")
    assert facade.training_plan(p.applicant_id).estimated_hours == 4.0
    facade.record_completion(p.applicant_id, "tactics", "reclutador_demo")
    assert facade.get_summary(p.applicant_id).stage == "Reevaluacion"
    with pytest.raises(PermissionError):
        facade.opportunities(p.applicant_id)
    facade.record_reevaluation(p.applicant_id,"reclutador_demo",True,"Passes final human gate")
    assert facade.get_summary(p.applicant_id).stage == "Oportunidades"
    routes = facade.opportunities(p.applicant_id)
    assert {r.opportunity_id for r in routes} == {"tournaments","tryouts","sponsorships"}
    assert sorted(r.estimated_hours for r in routes) == [1.0,2.0,2.0]


def test_new_vod_invalidates_prior_admission(facade):
    facade.seed_demo()
    assert facade.get_summary("DEMO-001").stage == "Oportunidades"
    facade.set_vod_reference("DEMO-001", "https://another.example.org/match")
    assert facade.get_summary("DEMO-001").stage == "Revision VOD"
    with pytest.raises(ValueError):
        facade.training_plan("DEMO-001")
    with pytest.raises((ValueError,PermissionError)):
        facade.opportunities("DEMO-001")


def test_seed_demo_is_idempotent(facade):
    assert facade.seed_demo() == 6
    assert facade.seed_demo() == 0
    assert facade.counts()["total"] == 6
    assert facade.counts()["opportunities"] == 1


def test_restricted_file_paths(tmp_path,monkeypatch):
    monkeypatch.setattr(core,"UPLOADS",tmp_path)
    facade = GamePathFacade(tmp_path / "database.sqlite3")
    assert facade.local_vod_path("uploads/../database.sqlite3") is None
    assert facade.local_vod_path("uploads/evil.mp4") is None
    payload = io.BytesIO(b"demo video contents")
    payload.name = "file.mp4"
    ref = facade.store_vod(payload)
    assert ref.startswith("uploads/vod_")
    assert facade.local_vod_path(ref).read_bytes() == b"demo video contents"


def test_csv_spreadsheet_injection_is_escaped(facade):
    facade.register(game_name="=SUM(A1:A2)",daily_play_hours=5,
                    peak_rank="oro",accepts_training=True)
    exported = facade.export_csv().decode("utf-8-sig")
    assert "'=SUM(A1:A2)" in exported


def test_graph_traversals_depend_on_requirements(facade):
    without = facade.graph_traversals()
    with_gate = facade.graph_traversals(include_opportunities=True)
    assert "opportunities" not in without["BFS"]
    assert "opportunities" in with_gate["BFS"]
    assert "tournaments" in with_gate["DFS"]


def test_deactivated_reviewer_suspends_opportunities(facade):
    facade.seed_demo()
    assert facade.get_summary("DEMO-001").stage == "Oportunidades"
    with facade.database.connection() as conn:
        conn.execute("UPDATE reviewers SET is_active = 0 WHERE reviewer_id = 'reclutador_demo'")
    assert facade.get_summary("DEMO-001").stage == "Revision suspendida"
    assert facade.counts()["opportunities"] == 0
    with pytest.raises(PermissionError):
        facade.opportunities("DEMO-001")


def test_reenabled_reviewer_restores_valid_decisions(facade):
    facade.seed_demo()
    with facade.database.connection() as conn:
        conn.execute("UPDATE reviewers SET is_active = 0 WHERE reviewer_id = 'reclutador_demo'")
    assert facade.counts()["opportunities"] == 0
    facade.activate_local_reviewer()
    assert facade.counts()["opportunities"] == 1
    assert facade.get_summary("DEMO-001").stage == "Oportunidades"
