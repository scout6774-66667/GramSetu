"""GramSetu Phase 4: provenance-preserving mandi data, temporal features and gated training.

This does not fetch data or endorse the authenticity of a source export. Verified status
must come from an independently reviewed, hash-bound provenance approval.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from sklearn.linear_model import Ridge

SCHEMA_VERSION = "phase4.1"
FIELDS = [
    "observation_id", "market_id", "commodity_id", "variety", "grade", "observed_date",
    "min_price_inr_quintal", "modal_price_inr_quintal", "max_price_inr_quintal",
    "source_record_key", "source_url", "source_file_sha256", "retrieved_at_utc",
    "source_tier", "simulation_flag", "review_status", "review_id"
]
SOURCE_TIERS = {"OFFICIAL_PRIMARY_REVIEWED", "OFFICIAL_EXPORT_UNVERIFIED", "SECONDARY_REPUBLISHED", "SYNTHETIC"}
KEYS = ("market_id", "commodity_id", "variety", "grade")
FEATURE_NAMES = ["lag_1", "lag_7", "lag_14", "lag_28", "rolling_mean_7", "rolling_std_7", "dow_sin", "dow_cos", "doy_sin", "doy_cos"]


class DataGateError(ValueError):
    pass


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def iso_datetime(text: str) -> datetime:
    out = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if out.tzinfo is None or out.utcoffset() is None:
        raise DataGateError("retrieved_at_utc must include UTC offset")
    return out.astimezone(timezone.utc)


def require_price(x: str, field: str) -> Decimal:
    try:
        d = Decimal(x)
    except (InvalidOperation, TypeError):
        raise DataGateError(f"Invalid {field}: {x!r}")
    if not d.is_finite() or d < 0:
        raise DataGateError(f"Invalid {field}: {x!r}")
    return d


def read_normalized(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or set(FIELDS) - set(r.fieldnames):
            raise DataGateError(f"Required columns missing: {sorted(set(FIELDS) - set(r.fieldnames or []))}")
        rows = list(r)
    seen_id, seen_business = set(), set()
    for n, x in enumerate(rows, start=2):
        try:
            if not all(str(x.get(k, "")).strip() for k in FIELDS):
                raise DataGateError("Blank required field")
            if x["source_tier"] not in SOURCE_TIERS:
                raise DataGateError("Invalid source tier")
            if x["simulation_flag"] not in ("True", "False"):
                raise DataGateError("simulation_flag must be True or False")
            d = date.fromisoformat(x["observed_date"])
            if d > date.today():
                raise DataGateError("Future market observation")
            retrieved = iso_datetime(x["retrieved_at_utc"])
            if retrieved.date() < d:
                raise DataGateError("Retrieval precedes observation")
            prices = [require_price(x[k], k) for k in ("min_price_inr_quintal", "modal_price_inr_quintal", "max_price_inr_quintal")]
            if not (prices[0] <= prices[1] <= prices[2]):
                raise DataGateError("Price ordering min<=modal<=max violated")
            if len(x["source_file_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in x["source_file_sha256"]):
                raise DataGateError("Invalid SHA-256")
            if x["source_tier"] == "SYNTHETIC" and x["simulation_flag"] != "True":
                raise DataGateError("Synthetic provenance inconsistency")
            if x["source_tier"] == "OFFICIAL_PRIMARY_REVIEWED" and (x["review_status"] != "REVIEWED" or x["review_id"] == "NOT_REVIEWED"):
                raise DataGateError("Unreviewed primary data falsely marked reviewed")
            pk = x["observation_id"]
            bk = (x["market_id"], x["commodity_id"], x["variety"], x["grade"], x["observed_date"])
            if pk in seen_id or bk in seen_business:
                raise DataGateError("Duplicate observation ID or business key")
            seen_id.add(pk)
            seen_business.add(bk)
        except (ValueError, DataGateError) as e:
            raise DataGateError(f"CSV line {n}: {e}") from e
    return rows


def parse_source_date(text: str) -> date:
    # AGMARKNET/OGD exports may use DD/MM/YYYY or ISO dates; never guess MM/DD/YYYY.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise DataGateError(f"Unsupported source date format: {text!r}; expected YYYY-MM-DD or DD/MM/YYYY")


def convert_government_export(raw_path: str | Path, output_path: str | Path, source_url: str, source_tier: str, reviewed_id: str = "NOT_REVIEWED") -> dict:
    """Normalize a downloaded data.gov.in/AGMARKNET *CSV export* with no fuzzy entity mapping.

    Note: source_tier OFFICIAL_PRIMARY_REVIEWED must be applied only after external
    verification; this converter never upgrades raw inputs to verified.
    """
    if source_tier not in {"OFFICIAL_EXPORT_UNVERIFIED", "SECONDARY_REPUBLISHED"}:
        raise DataGateError("Converter cannot assert independently verified provenance")
    if not source_url.startswith("https://"):
        raise DataGateError("Source URL must be HTTPS")
    raw_hash = sha256_file(raw_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    aliases = {"arrival_date": "observed_date", "date": "observed_date", "min_price": "min_price_inr_quintal", "modal_price": "modal_price_inr_quintal", "max_price": "max_price_inr_quintal"}
    needed = {"market", "commodity", "observed_date", "min_price_inr_quintal", "modal_price_inr_quintal", "max_price_inr_quintal"}
    output = []
    issues = []
    with open(raw_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for line, orig in enumerate(reader, start=2):
            x = {}
            for k, v in orig.items():
                key = (k or "").strip().lower().replace(" ", "_")
                key = aliases.get(key, key)
                x[key] = str(v or "").strip()
            if not needed <= set(x):
                raise DataGateError(f"CSV missing required vendor columns {sorted(needed - set(x))}")
            try:
                d = parse_source_date(x["observed_date"])
                if d > date.today():
                    raise DataGateError("future report date")
                prices = [require_price(x[k], k) for k in ("min_price_inr_quintal", "modal_price_inr_quintal", "max_price_inr_quintal")]
                if not prices[0] <= prices[1] <= prices[2]:
                    raise DataGateError("price order")
                market, commodity = x["market"].strip(), x["commodity"].strip()
                if not market or not commodity:
                    raise DataGateError("empty market or commodity")
                variety = x.get("variety", "") or "NOT_REPORTED"
                grade = x.get("grade", "") or "NOT_REPORTED"
                state, district = x.get("state", ""), x.get("district", "")
                # A stable source-derived identifier is NOT a verified GramSetu market_id.
                mk = "RAW_" + hashlib.sha256((state + "|" + district + "|" + market).encode()).hexdigest()[:16].upper()
                cm = "RAW_" + hashlib.sha256(commodity.encode()).hexdigest()[:12].upper()
                srckey = "|".join((state, district, market, commodity, variety, grade, d.isoformat()))
                obs = "OBS_" + hashlib.sha256((raw_hash + "|" + str(line)).encode()).hexdigest()[:20].upper()
                output.append(dict(observation_id=obs, market_id=mk, commodity_id=cm, variety=variety, grade=grade,
                    observed_date=d.isoformat(), min_price_inr_quintal=str(prices[0]), modal_price_inr_quintal=str(prices[1]),
                    max_price_inr_quintal=str(prices[2]), source_record_key=srckey, source_url=source_url,
                    source_file_sha256=raw_hash, retrieved_at_utc=timestamp, source_tier=source_tier,
                    simulation_flag="False", review_status="NOT_REVIEWED", review_id="NOT_REVIEWED"))
            except (ValueError, DataGateError) as e:
                issues.append({"line": line, "reason": str(e)})
    outp = Path(output_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    # separate rejected source lines, never silently disregard
    with outp.with_suffix(".rejected.json").open("w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2)
    return {"source_sha256": raw_hash, "rows_written": len(output), "rejected_rows": len(issues), "review_status": "NOT_REVIEWED", "destination": str(outp)}


def approval_check(rows: list[dict], csv_path: str | Path, approval_file: str | Path, allow_research: bool = False) -> dict:
    if not rows:
        raise DataGateError("No rows")
    approvals = json.loads(Path(approval_file).read_text(encoding="utf-8"))
    if approvals.get("approved_normalized_sha256") != sha256_file(csv_path):
        raise DataGateError("Approval manifest does not match exact normalized CSV hash")
    if not approvals.get("approval_id") or approvals["approval_id"] == "NOT_REVIEWED":
        raise DataGateError("Missing independent review approval ID")
    tiers = set(r["source_tier"] for r in rows)
    if any(r["simulation_flag"] == "True" for r in rows) or "SYNTHETIC" in tiers:
        raise DataGateError("Synthetic records prohibited from model training")
    if tiers == {"OFFICIAL_PRIMARY_REVIEWED"} and all(r["review_status"] == "REVIEWED" for r in rows):
        return {"deployment_scope": "RESEARCH_CANDIDATE_REQUIRES_FIELD_SIGNOFF", "review_id": approvals["approval_id"]}
    if allow_research and tiers <= {"SECONDARY_REPUBLISHED", "OFFICIAL_EXPORT_UNVERIFIED", "OFFICIAL_PRIMARY_REVIEWED"}:
        return {"deployment_scope": "SANDBOX_RESEARCH_ONLY", "review_id": approvals["approval_id"]}
    raise DataGateError("Primary verified data required; use --allow-research only for explicit sandbox evaluation")


def group_data(rows: list[dict]):
    groups = defaultdict(dict)
    for row in rows:
        group = tuple(row[k] for k in KEYS)
        d = date.fromisoformat(row["observed_date"])
        groups[group][d] = float(Decimal(row["modal_price_inr_quintal"]))
    return groups


def compute_feature(prices: dict[date, float], target_date: date):
    lags = {}
    for n in (1, 7, 14, 28):
        if target_date - timedelta(days=n) not in prices:
            return None
        lags[n] = prices[target_date - timedelta(days=n)]
    lastweek = [prices.get(target_date - timedelta(days=i)) for i in range(1, 8)]
    if any(v is None for v in lastweek):
        return None
    ave = mean(lastweek)
    std = math.sqrt(sum((x - ave) ** 2 for x in lastweek) / len(lastweek))
    dow = target_date.weekday()
    doy = target_date.timetuple().tm_yday
    values = [lags[1], lags[7], lags[14], lags[28], ave, std,
              math.sin(2 * math.pi * dow / 7), math.cos(2 * math.pi * dow / 7),
              math.sin(2 * math.pi * doy / 365.25), math.cos(2 * math.pi * doy / 365.25)]
    return values


def maepairs(predicted, actual):
    return sum(abs(float(a) - float(p)) for p, a in zip(predicted, actual)) / len(actual)


def smape(predicted, actual):
    return 100 * sum((2 * abs(float(a) - float(p))) / (abs(float(a)) + abs(float(p))) if a or p else 0 for p, a in zip(predicted, actual)) / len(actual)


def train_series(rows: list[dict], csv_path: str | Path, approval_file: str | Path, output_dir: str | Path,
                 allow_research=False, min_span_days=730, min_coverage=.80, val_days=90, test_days=180):
    approval = approval_check(rows, csv_path, approval_file, allow_research)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    models = {}
    fail = []
    for group, prices in group_data(rows).items():
        dates = sorted(prices)
        span = (dates[-1] - dates[0]).days + 1
        coverage = len(dates) / span
        if span < min_span_days or coverage < min_coverage:
            fail.append({"group": "|".join(group), "reason": f"INSUFFICIENT_HISTORY span={span} coverage={coverage:.3f}"})
            continue
        X = []
        Y = []
        D = []
        BASE1 = []
        BASE7 = []
        for d in dates:
            v = compute_feature(prices, d)
            if v is not None:
                D.append(d)
                X.append(v)
                Y.append(prices[d])
                BASE1.append(v[0])
                BASE7.append(v[1])
        test_start = dates[-1] - timedelta(days=test_days - 1)
        val_start = test_start - timedelta(days=val_days)
        ti = [i for i, d in enumerate(D) if d < val_start]
        vi = [i for i, d in enumerate(D) if val_start <= d < test_start]
        ei = [i for i, d in enumerate(D) if d >= test_start]
        if len(ti) < 300 or len(vi) < 45 or len(ei) < 90:
            fail.append({"group": "|".join(group), "reason": f"INSUFFICIENT_SPLIT train={len(ti)} val={len(vi)} test={len(ei)}"})
            continue

        def fit(idxs):
            reg = Ridge(alpha=10.0)
            reg.fit([X[i] for i in idxs], [Y[i] for i in idxs])
            return reg

        model = fit(ti)
        pred_val = model.predict([X[i] for i in vi])
        gt_val = [Y[i] for i in vi]
        val_model = maepairs(pred_val, gt_val)
        val_naive1 = maepairs([BASE1[i] for i in vi], gt_val)
        val_naive7 = maepairs([BASE7[i] for i in vi], gt_val)
        win_baseline = min(val_naive1, val_naive7)
        best_baseline = "LAG_1" if val_naive1 <= val_naive7 else "LAG_7"
        selected_model = val_model < win_baseline * .98
        if not selected_model:
            fail.append({"group": "|".join(group), "reason": f"MODEL_DID_NOT_BEAT_BASELINE val_model={val_model:.3f},val_baseline={win_baseline:.3f}"})
            continue
        model = fit(ti + vi)
        pred_test = model.predict([X[i] for i in ei])
        gt_test = [Y[i] for i in ei]
        test_mae = maepairs(pred_test, gt_test)
        base_test = maepairs([BASE1[i] if best_baseline == "LAG_1" else BASE7[i] for i in ei], gt_test)
        if not test_mae < base_test:
            fail.append({"group": "|".join(group), "reason": f"MODEL_WORSE_ON_HELDOUT test_model={test_mae:.3f},test_baseline={base_test:.3f}"})
            continue
        key = "|".join(group)
        models[key] = {"coefficients": [float(v) for v in model.coef_], "intercept": float(model.intercept_), "latest_observation_date": dates[-1].isoformat(), "training_records": len(ti) + len(vi)}
        results.append({"group": key, "train_rows": len(ti), "validation_rows": len(vi), "test_rows": len(ei),
            "validation_model_mae": round(val_model, 4), "validation_best_baseline_mae": round(win_baseline, 4),
            "test_model_mae": round(test_mae, 4), "test_baseline_mae": round(base_test, 4),
            "test_model_smape_pct": round(smape(pred_test, gt_test), 4), "test_start": test_start.isoformat(), "test_end": dates[-1].isoformat(), "deployment_scope": approval["deployment_scope"]})
    summary = {"schema_version": SCHEMA_VERSION, "dataset_sha256": sha256_file(csv_path), "approval_id": approval["review_id"],
             "deployment_scope": approval["deployment_scope"], "trained_groups": len(models), "blocked_groups": len(fail),
             "metrics": results, "rejections": fail, "generated_at_utc": datetime.now(timezone.utc).isoformat()}
    (output_dir / "training_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if models:
        # No pickle/joblib loading; JSON coefficients are inert and auditable.
        artifact = {"schema_version": SCHEMA_VERSION, "algorithm": "SKLEARN_RIDGE_PER_MARKET_COMMODITY",
                  "feature_names": FEATURE_NAMES, "models": models, "approval_id": approval["review_id"],
                  "dataset_sha256": summary["dataset_sha256"], "deployment_scope": approval["deployment_scope"],
                  "generated_at_utc": summary["generated_at_utc"]}
        (output_dir / "candidate_model.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    else:
        (output_dir / "UNAVAILABLE.json").write_text(json.dumps({"status": "UNAVAILABLE", "reason": "NO_GROUP_PASSED_ALL_TRAINING_GATES", "group_failures": fail}, indent=2), encoding="utf-8")
    return summary


def predict_one(model_artifact: dict, history_rows: list[dict], group: tuple[str, str, str, str], prediction_date: date):
    if model_artifact.get("deployment_scope") not in ("RESEARCH_CANDIDATE_REQUIRES_FIELD_SIGNOFF", "SANDBOX_RESEARCH_ONLY"):
        raise DataGateError("Invalid model deployment scope")
    key = "|".join(group)
    model = model_artifact["models"].get(key)
    if model is None:
        raise DataGateError("Model unavailable for requested market/commodity/variety/grade")
    data = group_data(history_rows).get(group, {})
    if not data:
        raise DataGateError("No matching historical data")
    if max(data) >= prediction_date:
        raise DataGateError("Inference history includes future/target data")
    if prediction_date != max(data) + timedelta(days=1):
        raise DataGateError("Only next-day forecasts supported; no recursive leap forecasting")
    if model["latest_observation_date"] != max(data).isoformat():
        raise DataGateError("Model and history not aligned")
    features = compute_feature(data, prediction_date)
    if features is None:
        raise DataGateError("Missing exact-date history for required lags")
    p = float(model["intercept"]) + sum(float(c) * x for c, x in zip(model["coefficients"], features))
    if not math.isfinite(p) or p <= 0:
        raise DataGateError("Invalid forecast output")
    return {"status": "PREDICTED_RESEARCH_ONLY", "forecast_date": prediction_date.isoformat(), "market_id": group[0],
            "commodity_id": group[1], "variety": group[2], "grade": group[3],
            "predicted_modal_price_inr_quintal": round(p, 2), "deployment_scope": model_artifact["deployment_scope"],
            "training_dataset_sha256": model_artifact["dataset_sha256"]}


def audit_v2_2_zip(zip_path: str | Path) -> dict:
    import io
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        counts = {}
        for n in ("market_prices", "market_arrivals", "price_forecasts"):
            rows = list(csv.DictReader(io.StringIO(z.read(f"csv/{n}.csv").decode("utf-8-sig"))))
            counts[n] = len(rows)
            if n == "market_prices":
                dates = sorted({r["observed_date"] for r in rows})
                counts["market_price_distinct_dates"] = len(dates)
                counts["market_price_date_range"] = [dates[0], dates[-1]] if dates else []
                counts["source_quality_flags"] = dict(Counter(r["quality_flag"] for r in rows))
                counts["synthetic_prices"] = sum(r["simulation_flag"].strip().lower() == "true" for r in rows)
        counts["training_gate"] = "BLOCKED_INSUFFICIENT_AUTHENTIC_HISTORICAL_DATA" if counts["market_price_distinct_dates"] < 730 else "REQUIRES_EXTERNAL_PROVENANCE_REVIEW"
        return counts


def gross_paise_half_up(accepted_grams: int, price_paise_per_kg: int) -> int:
    if not isinstance(accepted_grams, int) or not isinstance(price_paise_per_kg, int) or accepted_grams < 0 or price_paise_per_kg < 0:
        raise ValueError("Nonnegative integer quantities and prices required")
    return (accepted_grams * price_paise_per_kg + 500) // 1000


def reconcile_inspection(delivered_grams: int, accepted_grams: int, rejected_grams: int, pending_grams: int, final: bool) -> bool:
    vals = (delivered_grams, accepted_grams, rejected_grams, pending_grams)
    if any(not isinstance(v, int) or v < 0 for v in vals):
        return False
    return delivered_grams == accepted_grams + rejected_grams + pending_grams and (not final or pending_grams == 0)
