"""Pins the end-to-end run and the §4 export contract.

The two scenarios that matter most here are S1 and S5: the same shared-rail
fault, misattributed when it manifests on only part of its footprint, correct
when fully manifested. That pair is the honest picture of what footprint
attribution does and does not deliver, and it is recorded in validation.md
§12-§15. If S1 ever starts passing, the fix must be argued for — not absorbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foae import config, pipeline
from foae.attribution.footprint import (
    GATE_STATES,
    REASON_FOOTPRINT_COLLISION,
    REASON_TIER1_CONFOUND,
)


@pytest.fixture(scope="module")
def results() -> list:
    return pipeline.run_all()


@pytest.fixture(scope="module")
def export(results: list) -> dict:
    return pipeline.build_export(results)


# ---------------------------------------------------------------------------
# The five scenarios
# ---------------------------------------------------------------------------


def test_five_scenarios_ship(export: dict) -> None:
    ids = [s["id"] for s in export["scenarios"]]
    assert set(ids) == {
        "S1_shared_rail",
        "S2_single_connector",
        "S3_tier1_confound",
        "S4_footprint_collision",
        "S5_rail_full_manifest",
    }


def _scenario(export: dict, sid: str) -> dict:
    return next(s for s in export["scenarios"] if s["id"] == sid)


def test_s1_partial_manifestation_is_WRONG(export: dict) -> None:
    """THE OPEN FAILURE (validation.md §12). Pinned deliberately.

    REF_5V_A degrades but only engine_rpm clears detection, so the observed set
    is a strict subset of the rail footprint and an exact match for the CKP
    connector. The attributor names the connector, at full confidence, and is
    wrong. Four mechanisms have been tried against this and rejected.

    This test asserts the failure is still there. If it starts failing, the
    behaviour changed — go read §12-§15 before calling that a fix.
    """
    s = _scenario(export, "S1_shared_rail")
    assert s["ground_truth"]["segment_id"] == "SEG_RAIL_REF_5V_A"
    assert s["observed_anomalous"] == ["engine_rpm"]
    assert s["verdict"]["segment_id"] == "SEG_CONN_CKP"
    assert s["verdict"]["correct"] is False
    assert s["verdict"]["abstained"] is False
    assert s["verdict"]["confidence"] == pytest.approx(1.0)


def test_s5_full_manifestation_is_CORRECT(export: dict) -> None:
    """The control that isolates the §12 cause: same rail, same fault kernel,
    severity raised until both member sensors clear detection.
    """
    s = _scenario(export, "S5_rail_full_manifest")
    assert s["ground_truth"]["segment_id"] == "SEG_RAIL_REF_5V_A"
    assert sorted(s["observed_anomalous"]) == ["engine_rpm", "intake_map"]
    assert s["verdict"]["segment_id"] == "SEG_RAIL_REF_5V_A"
    assert s["verdict"]["correct"] is True


def test_s1_and_s5_are_the_same_fault_at_different_severity(export: dict) -> None:
    s1, s5 = _scenario(export, "S1_shared_rail"), _scenario(export, "S5_rail_full_manifest")
    assert s1["ground_truth"]["fault_type"] == s5["ground_truth"]["fault_type"]
    assert s1["ground_truth"]["segment_id"] == s5["ground_truth"]["segment_id"]
    assert s1["ground_truth"]["severity"] < s5["ground_truth"]["severity"]


def test_s2_names_the_connector(export: dict) -> None:
    s = _scenario(export, "S2_single_connector")
    assert s["verdict"]["segment_id"] == "SEG_CONN_ECT"
    assert s["verdict"]["correct"] is True


def test_s3_abstains_on_the_tier1_gate(export: dict) -> None:
    s = _scenario(export, "S3_tier1_confound")
    assert s["tier1"]["gate"] == "TRIPPED"
    assert s["tier1"]["cmv_anomalous"] is True
    assert s["verdict"]["abstained"] is True
    assert s["verdict"]["reason"] == REASON_TIER1_CONFOUND
    assert s["verdict"]["confidence"] is None
    assert s["verdict"]["correct"] is None


def test_s4_abstains_on_the_collision(export: dict) -> None:
    s = _scenario(export, "S4_footprint_collision")
    assert s["verdict"]["abstained"] is True
    assert s["verdict"]["reason"] == REASON_FOOTPRINT_COLLISION
    # Retained here, unlike the Tier-1 case.
    assert s["verdict"]["confidence"] is not None


# ---------------------------------------------------------------------------
# validation.experiments — measured, never transcribed
# ---------------------------------------------------------------------------


def test_validation_experiments_present_and_numeric(export: dict) -> None:
    rows = export["validation"]["experiments"]
    assert isinstance(rows, list) and rows

    for row in rows:
        assert set(row) >= {"name", "measured", "baseline", "n", "note"}
        assert isinstance(row["name"], str) and row["name"]
        assert isinstance(row["measured"], (int, float)), row["name"]
        assert isinstance(row["n"], int) and row["n"] >= 1
        if row["baseline"] is not None:
            assert isinstance(row["baseline"], (int, float))


def test_experiments_are_computed_from_this_run(results: list) -> None:
    """Not read from a document. The spec carried hardcoded rows once and they
    disagreed with the suite by a wide margin.
    """
    rows = pipeline.measure_experiments(results)
    names = {r["name"] for r in rows}
    assert any("accuracy vs chance" in n for n in names)
    assert any("Abstention rate" in n for n in names)

    abst = next(r for r in rows if r["name"] == "Abstention rate")
    n_abstained = sum(1 for r in results if r.attribution.abstained)
    assert abst["measured"] == pytest.approx(n_abstained / len(results))


def test_chance_baseline_is_the_topology_hypothesis_space(results: list) -> None:
    rows = pipeline.measure_experiments(results)
    acc = next(r for r in rows if "accuracy vs chance" in r["name"])
    assert acc["baseline"] == pytest.approx(1 / 9, abs=1e-4)


# ---------------------------------------------------------------------------
# Export contract (spec §4)
# ---------------------------------------------------------------------------


def test_meta_declares_simulation_and_no_hardware(export: dict) -> None:
    m = export["meta"]
    assert m["evidence_basis"] == "simulation"
    assert m["hardware_validated"] is False
    assert m["config_hash"].startswith("sha256:")
    assert m["harness_id"] == "FOAE_TIER2"


def test_scenario_field_names_are_the_contract(export: dict) -> None:
    for s in export["scenarios"]:
        assert set(s) == {
            "id", "label", "ground_truth", "traces", "tier1",
            "observed_anomalous", "candidates", "verdict",
        }
        assert set(s["verdict"]) == {
            "origin_layer", "segment_id", "confidence",
            "abstained", "reason", "correct",
        }
        assert set(s["tier1"]) == {
            "confound_score", "threshold", "gate", "cmv_anomalous",
        }


def test_enumerated_values_stay_closed(export: dict) -> None:
    for s in export["scenarios"]:
        assert s["tier1"]["gate"] in GATE_STATES
        v = s["verdict"]
        if v["abstained"]:
            assert v["reason"] is not None
        else:
            assert v["reason"] is None


def test_ground_truth_layer_is_physical(export: dict) -> None:
    for s in export["scenarios"]:
        assert s["ground_truth"]["origin_layer"] == "physical"


def test_topology_block_matches_the_graph(export: dict) -> None:
    kinds = {n["kind"] for n in export["topology"]["nodes"]}
    assert kinds == {"sensor", "connector", "rail", "ecu"}
    ids = {n["id"] for n in export["topology"]["nodes"]}
    assert config.PID_CONTROL_MODULE_VOLTAGE not in ids
    for e in export["topology"]["edges"]:
        assert set(e) == {"from", "to", "rail"}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_export_run_writes_the_payload_it_is_given(
    results: list, export: dict, tmp_path: Path
) -> None:
    """The filename and the contents must come from ONE payload. export_run
    used to rebuild, stamping a second generated_utc.
    """
    out = tmp_path / "run.json"
    pipeline.export_run(results, out, payload=export)
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["meta"] == export["meta"]


def test_export_is_utf8_and_json_round_trips(
    results: list, export: dict, tmp_path: Path
) -> None:
    out = tmp_path / "run.json"
    pipeline.export_run(results, out, payload=export)
    assert out.stat().st_size > 0
    assert json.loads(out.read_text(encoding="utf-8"))["meta"]["seed"] == export["meta"]["seed"]


def test_run_is_deterministic_at_a_fixed_seed() -> None:
    a = pipeline.run_all(seed=7)
    b = pipeline.run_all(seed=7)
    assert [r.attribution.segment_id for r in a] == [r.attribution.segment_id for r in b]
    assert [sorted(r.observed_anomalous) for r in a] == [
        sorted(r.observed_anomalous) for r in b
    ]
