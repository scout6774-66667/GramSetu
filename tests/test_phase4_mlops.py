"""GramSetu AI Phase 4: Data Engineering, MLOps, Time-Series & DemandSync Acceptance Tests.

Validates:
1. Data acquisition, pagination, immutable raw bytes, SHA-256 provenance and row-level quarantine.
2. Canonical normalized price contracts, duplicate rejection, and strict provenance tiering.
3. Time-series feature contracts (exact calendar lags, no target interpolation, temporal splits).
4. Training gates: min history (730 days), coverage (>=80%), baseline comparisons (lag-1, lag-7),
   holdout evaluation, inert JSON model serialization, and zero synthetic data in training.
5. DemandSync integration via /api/v1/market/forecasts (feature gating, production refusal,
   unavailable disclosures, planning notices).
6. Phase 3 regressions: exact half-up rounding (accepted*price+500)//1000, negative adjustment handling,
   and partial delivery inspection reconciliation (pending_grams=0 required for final settlement).
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gramsetu.core import Settings, Environment, DevActor, Role, DEV_ACTOR_HEADER
from gramsetu.main import create_app
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.units import (
    DatasetContractError,
    gross_paise_half_up,
    calculate_gross_paise,
    calculate_adjustment_paise_half_up,
    reconcile_delivery_inspection,
)
from gramsetu.pipeline import (
    FIELDS,
    SOURCE_TIERS,
    DataGateError,
    sha256_file,
    require_price,
    read_normalized,
    parse_source_date,
    convert_government_export,
    approval_check,
    compute_feature,
    train_series,
    predict_one,
    audit_v2_2_zip,
    maepairs,
    smape,
)
from gramsetu.acquisition import (
    ingest_raw_agmarknet_batch,
    RawBatchMetadata,
    compute_bytes_sha256,
    CANONICAL_MARKET_CROSSWALK,
    CANONICAL_COMMODITY_CROSSWALK,
    NAMESPACE_GOVERNMENT_ORIGIN,
    NAMESPACE_SECONDARY_REPUBLISHED,
    NAMESPACE_SYNTHETIC_SANDBOX,
)
from gramsetu.services.market import get_market_price_forecast

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_ZIP = REPO_ROOT / "GramSetu_All_Corrected_CSV_v2_2.zip"


# ==============================================================================
# 1. Baseline Audit & 43-Row v2.2 Dataset Verification
# ==============================================================================
def test_p4_01_v2_2_baseline_audit_gate_blocks_training():
    """Verify that the existing v2.2 dataset has only 43 prices on 2 dates and blocks model training."""
    audit = audit_v2_2_zip(BASELINE_ZIP)
    assert audit["market_prices"] == 43
    assert audit["market_price_distinct_dates"] == 2
    assert audit["market_arrivals"] == 0
    assert audit["price_forecasts"] == 0
    assert audit["synthetic_prices"] == 0
    assert audit["training_gate"] == "BLOCKED_INSUFFICIENT_AUTHENTIC_HISTORICAL_DATA"


# ==============================================================================
# 2. Data Acquisition, Lineage, Immutable Raw Bytes & Row-Level Quarantine
# ==============================================================================
def test_p4_02_raw_ingest_with_quarantine_and_sha_tracking(tmp_path):
    """Raw batch is stored immutably with SHA-256; corrupted rows are quarantined without mutating raw source."""
    raw_csv = (
        "market,commodity,variety,grade,arrival_date,min_price,modal_price,max_price\n"
        "Burdwan,Potato,Jyoti,A,15/11/2026,1200,1250,1300\n"  # Valid row 1
        "Burdwan,Potato,Jyoti,A,15/11/2026,1400,1250,1300\n"  # Corrupt: min > modal
        "UnknownMandi,Wheat,Lokwan,A,15/11/2026,2000,2100,2200\n"  # Corrupt: unmapped market
        "Kalna,Tomato,Desi,A,25/12/2099,800,900,1000\n"  # Corrupt: future date
    ).encode("utf-8")

    meta = ingest_raw_agmarknet_batch(
        raw_content=raw_csv,
        batch_id="BATCH_TEST_001",
        source_url="https://data.gov.in/test-resource",
        source_tier="OFFICIAL_EXPORT_UNVERIFIED",
        namespace=NAMESPACE_GOVERNMENT_ORIGIN,
        storage_root=tmp_path,
    )

    # Immutable raw file exists
    raw_file = tmp_path / "raw" / NAMESPACE_GOVERNMENT_ORIGIN / "BATCH_TEST_001.raw"
    assert raw_file.exists()
    assert raw_file.read_bytes() == raw_csv
    assert meta.sha256 == compute_bytes_sha256(raw_csv)

    # 1 valid row normalized, 3 quarantined
    assert meta.normalized_records == 1
    assert meta.quarantined_records == 3
    assert meta.extraction_outcome == "PARTIAL_WITH_QUARANTINE"

    # Verify quarantine rejection JSON
    quarantine_file = tmp_path / "quarantine" / NAMESPACE_GOVERNMENT_ORIGIN / "BATCH_TEST_001.rejected.json"
    assert quarantine_file.exists()
    rejections = json.loads(quarantine_file.read_text(encoding="utf-8"))
    assert len(rejections) == 3
    reasons = [r["reason"] for r in rejections]
    assert any("Price ordering invariant violated" in r for r in reasons)
    assert any("Unmapped source market" in r for r in reasons)
    assert any("Future observation date rejected" in r for r in reasons)


# ==============================================================================
# 3. Canonical Normalized Contract & Approval Verification
# ==============================================================================
def test_p4_03_normalized_contract_schema_and_tamper_rejection(tmp_path):
    """read_normalized strictly validates all 17 fields, price orders, future dates, and SHA hashes."""
    norm_csv = tmp_path / "test_norm.csv"
    today_str = date.today().isoformat()
    now_utc = datetime.now(timezone.utc).isoformat()
    valid_sha = "0" * 64

    header = ",".join(FIELDS) + "\n"
    valid_row = f"OBS_1,MKT_000001,COM_POTATO,Jyoti,A,{today_str},1200.00,1250.00,1300.00,KEY_1,https://data.gov.in/test,{valid_sha},{now_utc},OFFICIAL_EXPORT_UNVERIFIED,False,NOT_REVIEWED,NOT_REVIEWED\n"
    norm_csv.write_text(header + valid_row, encoding="utf-8")

    rows = read_normalized(norm_csv)
    assert len(rows) == 1

    # A. Tamper price ordering: min > modal
    bad_price_row = f"OBS_2,MKT_000001,COM_POTATO,Jyoti,A,{today_str},1500.00,1250.00,1300.00,KEY_2,https://data.gov.in/test,{valid_sha},{now_utc},OFFICIAL_EXPORT_UNVERIFIED,False,NOT_REVIEWED,NOT_REVIEWED\n"
    norm_csv.write_text(header + bad_price_row, encoding="utf-8")
    with pytest.raises(DataGateError, match="Price ordering min<=modal<=max violated"):
        read_normalized(norm_csv)

    # B. Tamper SHA hash length
    bad_sha_row = f"OBS_3,MKT_000001,COM_POTATO,Jyoti,A,{today_str},1200.00,1250.00,1300.00,KEY_3,https://data.gov.in/test,short_hash,{now_utc},OFFICIAL_EXPORT_UNVERIFIED,False,NOT_REVIEWED,NOT_REVIEWED\n"
    norm_csv.write_text(header + bad_sha_row, encoding="utf-8")
    with pytest.raises(DataGateError, match="Invalid SHA-256"):
        read_normalized(norm_csv)

    # C. Duplicate PK
    dup_rows = header + valid_row + valid_row
    norm_csv.write_text(dup_rows, encoding="utf-8")
    with pytest.raises(DataGateError, match="Duplicate observation ID or business key"):
        read_normalized(norm_csv)


def test_p4_04_approval_check_rejects_synthetic_data_and_mismatched_sha(tmp_path):
    """approval_check refuses synthetic data and enforces hash-bound approvals."""
    norm_csv = tmp_path / "norm.csv"
    today_str = date.today().isoformat()
    now_utc = datetime.now(timezone.utc).isoformat()
    valid_sha = "0" * 64

    # Synthetic row
    synth_row = (
        ",".join(FIELDS) + "\n"
        f"OBS_1,MKT_000001,COM_POTATO,Jyoti,A,{today_str},1200,1250,1300,KEY_1,https://test,{valid_sha},{now_utc},SYNTHETIC,True,NOT_REVIEWED,NOT_REVIEWED\n"
    )
    norm_csv.write_text(synth_row, encoding="utf-8")
    rows = read_normalized(norm_csv)

    appr_file = tmp_path / "approval.json"
    csv_hash = sha256_file(norm_csv)
    appr_file.write_text(json.dumps({"approved_normalized_sha256": csv_hash, "approval_id": "APPR_001"}), encoding="utf-8")

    # Synthetic rejected
    with pytest.raises(DataGateError, match="Synthetic records prohibited from model training"):
        approval_check(rows, norm_csv, appr_file, allow_research=True)

    # Hash mismatch rejected
    appr_file.write_text(json.dumps({"approved_normalized_sha256": "wrong_hash", "approval_id": "APPR_001"}), encoding="utf-8")
    with pytest.raises(DataGateError, match="Approval manifest does not match exact normalized CSV hash"):
        approval_check(rows, norm_csv, appr_file, allow_research=True)


# ==============================================================================
# 4. Feature Contracts & Exact Calendar Lags (No Lookahead Leakage)
# ==============================================================================
def test_p4_05_feature_computation_exact_date_lags():
    """compute_feature calculates exact-date lags (1, 7, 14, 28) and rolling statistics without target leakage."""
    base_d = date(2026, 1, 1)
    # Populate daily prices for 35 consecutive days
    prices = {base_d + timedelta(days=i): float(1000 + i * 10) for i in range(35)}

    target_d = base_d + timedelta(days=30)
    features = compute_feature(prices, target_d)
    assert features is not None
    assert len(features) == 10  # 4 lags + 2 rolling + 4 trig DOW/DOY

    # Exact calendar day lookbacks:
    assert features[0] == prices[target_d - timedelta(days=1)]   # lag_1
    assert features[1] == prices[target_d - timedelta(days=7)]   # lag_7
    assert features[2] == prices[target_d - timedelta(days=14)]  # lag_14
    assert features[3] == prices[target_d - timedelta(days=28)]  # lag_28

    # If an exact lag is missing (e.g. holiday or non-reporting day), compute_feature returns None
    sparse_prices = dict(prices)
    del sparse_prices[target_d - timedelta(days=7)]  # missing lag_7
    assert compute_feature(sparse_prices, target_d) is None


# ==============================================================================
# 5. Training Gates: History, Coverage, Baseline Comparison & Model Artifact
# ==============================================================================
def test_p4_06_insufficient_history_rejects_and_writes_unavailable_artifact(tmp_path):
    """When a market series has <730 days history, training fails honestly and writes UNAVAILABLE.json."""
    norm_csv = tmp_path / "short_series.csv"
    rows_data = []
    base_d = date(2026, 1, 1)
    # Only 100 days of history (< 730 days gate)
    now_utc = datetime.now(timezone.utc).isoformat()
    dummy_sha = "a" * 64
    for i in range(100):
        d_str = (base_d + timedelta(days=i)).isoformat()
        rows_data.append({
            "observation_id": f"OBS_{i:04d}",
            "market_id": "MKT_000001",
            "commodity_id": "COM_POTATO",
            "variety": "Jyoti",
            "grade": "A",
            "observed_date": d_str,
            "min_price_inr_quintal": "1000",
            "modal_price_inr_quintal": "1050",
            "max_price_inr_quintal": "1100",
            "source_record_key": f"KEY_{i}",
            "source_url": "https://data.gov.in/test",
            "source_file_sha256": dummy_sha,
            "retrieved_at_utc": now_utc,
            "source_tier": "SECONDARY_REPUBLISHED",
            "simulation_flag": "False",
            "review_status": "NOT_REVIEWED",
            "review_id": "NOT_REVIEWED",
        })

    with open(norm_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows_data)

    appr_file = tmp_path / "appr.json"
    appr_file.write_text(json.dumps({
        "approved_normalized_sha256": sha256_file(norm_csv),
        "approval_id": "APPR_RESEARCH_01"
    }), encoding="utf-8")

    out_dir = tmp_path / "model_out"
    summary = train_series(
        rows=rows_data,
        csv_path=norm_csv,
        approval_file=appr_file,
        output_dir=out_dir,
        allow_research=True,
        min_span_days=730,
    )

    assert summary["trained_groups"] == 0
    assert summary["blocked_groups"] == 1
    assert "INSUFFICIENT_HISTORY" in summary["rejections"][0]["reason"]

    # UNAVAILABLE.json must be written
    unavail_file = out_dir / "UNAVAILABLE.json"
    assert unavail_file.exists()
    unavail_data = json.loads(unavail_file.read_text(encoding="utf-8"))
    assert unavail_data["status"] == "UNAVAILABLE"
    assert unavail_data["reason"] == "NO_GROUP_PASSED_ALL_TRAINING_GATES"


def test_p4_07_full_pipeline_synthetic_evaluation_and_json_serialization(tmp_path):
    """When a series passes 730 days and beats naive baselines, serializes an inert JSON candidate model."""
    norm_csv = tmp_path / "multiyear_series.csv"
    rows_data = []
    base_d = date(2024, 1, 1)
    now_utc = datetime.now(timezone.utc).isoformat()
    dummy_sha = "b" * 64

    # 750 days of continuous data with weekly periodicity + trend
    for i in range(750):
        d = base_d + timedelta(days=i)
        # Price with clear day-of-week and seasonal pattern
        price = 1000.0 + (i * 0.5) + (50.0 if d.weekday() == 0 else 0.0) + (100.0 if d.month == 11 else 0.0)
        rows_data.append({
            "observation_id": f"OBS_{i:04d}",
            "market_id": "MKT_000001",
            "commodity_id": "COM_POTATO",
            "variety": "Jyoti",
            "grade": "A",
            "observed_date": d.isoformat(),
            "min_price_inr_quintal": str(round(price - 50, 2)),
            "modal_price_inr_quintal": str(round(price, 2)),
            "max_price_inr_quintal": str(round(price + 50, 2)),
            "source_record_key": f"KEY_{i}",
            "source_url": "https://data.gov.in/test",
            "source_file_sha256": dummy_sha,
            "retrieved_at_utc": now_utc,
            "source_tier": "SECONDARY_REPUBLISHED",
            "simulation_flag": "False",
            "review_status": "NOT_REVIEWED",
            "review_id": "NOT_REVIEWED",
        })

    with open(norm_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows_data)

    appr_file = tmp_path / "appr.json"
    appr_file.write_text(json.dumps({
        "approved_normalized_sha256": sha256_file(norm_csv),
        "approval_id": "APPR_EVAL_01"
    }), encoding="utf-8")

    out_dir = tmp_path / "candidate_model_out"
    summary = train_series(
        rows=rows_data,
        csv_path=norm_csv,
        approval_file=appr_file,
        output_dir=out_dir,
        allow_research=True,
        min_span_days=730,
        min_coverage=0.80,
        val_days=60,
        test_days=90,
    )

    # In case regression beats baseline on this pattern:
    if summary["trained_groups"] > 0:
        candidate_file = out_dir / "candidate_model.json"
        assert candidate_file.exists()
        artifact = json.loads(candidate_file.read_text(encoding="utf-8"))
        assert artifact["algorithm"] == "SKLEARN_RIDGE_PER_MARKET_COMMODITY"
        # Zero pickle / joblib
        assert "models" in artifact

        # Test single-step prediction
        last_d = date.fromisoformat(rows_data[-1]["observed_date"])
        pred_target_d = last_d + timedelta(days=1)
        pred = predict_one(
            model_artifact=artifact,
            history_rows=rows_data,
            group=("MKT_000001", "COM_POTATO", "Jyoti", "A"),
            prediction_date=pred_target_d,
        )
        assert pred["status"] == "PREDICTED_RESEARCH_ONLY"
        assert pred["predicted_modal_price_inr_quintal"] > 0
    else:
        # If it didn't beat baseline by 2%, it must be safely blocked and recorded as failure
        assert summary["blocked_groups"] > 0
        assert (out_dir / "UNAVAILABLE.json").exists()


# ==============================================================================
# 6. DemandSync API Integration & Production Safety Refusals
# ==============================================================================
def test_p4_08_demandsync_api_endpoint_feature_gated_and_unavailable(tmp_path):
    """GET /api/v1/market/forecasts respects feature gating and returns clean UNAVAILABLE states."""
    # 1. Feature Gate DISABLED (Default)
    cfg_disabled = Settings(
        ENVIRONMENT=Environment.TESTING,
        PHASE4_FORECASTING_ENABLED=False
    )
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    app = create_app(settings=cfg_disabled, store=store, coordinator=coord)
    client = TestClient(app)

    res = client.get(
        "/api/v1/market/forecasts?market_id=MKT_000001&commodity_id=COM_POTATO",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "UNAVAILABLE_FEATURE_DISABLED"
    assert body["predicted_modal_price_inr_quintal"] is None
    assert "DISABLED by system configuration" in body["operational_notice"]

    # 2. Feature Gate ENABLED, but Model Artifact is Missing
    cfg_enabled = Settings(
        ENVIRONMENT=Environment.TESTING,
        PHASE4_FORECASTING_ENABLED=True,
        PHASE4_MODEL_ARTIFACT_PATH=str(tmp_path / "non_existent_model.json")
    )
    app2 = create_app(settings=cfg_enabled, store=store, coordinator=coord)
    client2 = TestClient(app2)

    res2 = client2.get(
        "/api/v1/market/forecasts?market_id=MKT_000001&commodity_id=COM_POTATO",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["status"] == "UNAVAILABLE_NO_TRAINED_MODEL"
    assert body2["predicted_modal_price_inr_quintal"] is None

    # 3. Production Environment Lock (Refuses unreviewed research models)
    import jwt
    cfg_prod = Settings(
        ENVIRONMENT=Environment.PRODUCTION,
        PHASE4_FORECASTING_ENABLED=True,
        ALLOW_RESEARCH_EVALUATION=False,
    )
    app3 = create_app(settings=cfg_prod, store=store, coordinator=coord)
    client3 = TestClient(app3)

    prod_jwt = jwt.encode(
        {
            "sub": "fpo-admin-alpha",
            "role": "FPO_ADMIN",
            "org_id": "fpo-alpha",
            "name": "Alpha Admin",
            "iss": cfg_prod.JWT_ISSUER,
            "aud": cfg_prod.JWT_AUDIENCE,
            "exp": 9999999999,
        },
        cfg_prod.JWT_SECRET_KEY,
        algorithm="HS256"
    )

    res3 = client3.get(
        "/api/v1/market/forecasts?market_id=MKT_000001&commodity_id=COM_POTATO",
        headers={"Authorization": f"Bearer {prod_jwt}"}
    )
    assert res3.status_code == 200
    body3 = res3.json()
    assert body3["status"] == "REFUSED_UNVERIFIED_PROVENANCE"
    assert body3["predicted_modal_price_inr_quintal"] is None
    assert "Production safety refusal" in body3["operational_notice"]


# ==============================================================================
# 7. Phase 3 Regressions: Exact Half-Up Rounding & Inspection Reconciliation
# ==============================================================================
def test_p4_09_exact_half_up_settlement_rounding_boundary_tests():
    """Verify gross_paise = (accepted_grams * price_paise_per_kg + 500) // 1000 half-up boundaries."""
    # 1. Half-paise threshold exact tests:
    # 1 gram at 1500 paise/kg -> 1500 / 1000 = 1.5 paise -> rounds to 2
    assert gross_paise_half_up(1, 1500) == 2
    assert calculate_gross_paise(1, 1500) == 2

    # 1 gram at 1499 paise/kg -> 1499 / 1000 = 1.499 paise -> rounds to 1
    assert gross_paise_half_up(1, 1499) == 1
    assert calculate_gross_paise(1, 1499) == 1

    # 1 gram at 1501 paise/kg -> 1501 / 1000 = 1.501 paise -> rounds to 2
    assert gross_paise_half_up(1, 1501) == 2
    assert calculate_gross_paise(1, 1501) == 2

    # Exactly 0.50 paise: 500 / 1000 -> rounds to 1
    assert gross_paise_half_up(1, 500) == 1

    # Exactly 0.499 paise: 499 / 1000 -> rounds to 0
    assert gross_paise_half_up(1, 499) == 0

    # 2. Integer extremes (no overflow or precision degradation):
    # 10,000,000,000 grams (10,000 tonnes) @ 2500 paise/kg
    # 10^10 * 2500 / 1000 = 25,000,000,000 paise (250 million INR)
    assert gross_paise_half_up(10_000_000_000, 2500) == 25_000_000_000

    # 3. Negative adjustment handling (symmetric rounding):
    assert calculate_adjustment_paise_half_up(1, 1500) == 2
    assert calculate_adjustment_paise_half_up(-1, 1500) == -2
    assert calculate_adjustment_paise_half_up(-1, 1499) == -1
    assert calculate_adjustment_paise_half_up(-1, 500) == -1
    assert calculate_adjustment_paise_half_up(-1, 499) == 0

    # 4. Negative quantities rejected for gross settlement
    with pytest.raises(DatasetContractError, match="cannot be negative"):
        gross_paise_half_up(-100, 2500)


def test_p4_10_delivery_inspection_reconciliation_contracts():
    """Verify delivered_grams == accepted + rejected + pending, and final settlement requires pending==0."""
    # 1. Valid intermediate delivery with pending inspections:
    assert reconcile_delivery_inspection(
        delivered_grams=1000,
        accepted_grams=700,
        rejected_grams=100,
        pending_grams=200,
        final=False
    ) is True

    # 2. Conservation of mass failure: sum != delivered
    with pytest.raises(DatasetContractError, match="Delivery mass conservation failure"):
        reconcile_delivery_inspection(
            delivered_grams=1000,
            accepted_grams=700,
            rejected_grams=100,
            pending_grams=150,  # sum is 950 != 1000
            final=False
        )

    # 3. Final settlement with pending_grams > 0 is strictly rejected
    with pytest.raises(DatasetContractError, match="Final settlement requires FULLY_INSPECTED delivery with pending_grams == 0"):
        reconcile_delivery_inspection(
            delivered_grams=1000,
            accepted_grams=700,
            rejected_grams=100,
            pending_grams=200,
            final=True  # Final settlement blocked!
        )

    # 4. Valid final settlement: pending_grams == 0
    assert reconcile_delivery_inspection(
        delivered_grams=1000,
        accepted_grams=850,
        rejected_grams=150,
        pending_grams=0,
        final=True
    ) is True
