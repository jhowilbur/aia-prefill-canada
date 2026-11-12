"""Evaluation metrics for the AIA pre-fill experiment (see docs/eval-plan.md).

Pure functions, NumPy only. Run the tests with:
    python3 -I -m unittest discover -s eval/tests -v

Record format (one per (AIA, question) item):
    {"aia_id": str, "department": str, "question_id": str,
     "y_true": str | tuple,           # department's answer (tuple for checkbox)
     "y_pred": str | tuple | None,    # None = "unable to determine" (abstain)
     "confidence": float in [0, 1]}   # model's P(y_pred is correct); ignored if abstain
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Callable, Iterable, Sequence

import numpy as np

ABSTAIN = None
Z95 = 1.959963984540054


# --------------------------------------------------------------------------- CIs
def wilson_ci(k: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (Wilson 1927)."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cluster_bootstrap(records: Sequence[dict], stat: Callable[[list], float],
                      cluster_key: str = "aia_id", B: int = 2000, seed: int = 0,
                      alpha: float = 0.05) -> tuple[float, float, float]:
    """Percentile bootstrap that resamples whole clusters (AIAs), so that the
    correlation of items inside one AIA is respected. Returns (est, lo, hi)."""
    groups = defaultdict(list)
    for r in records:
        groups[r[cluster_key]].append(r)
    keys = list(groups)
    rng = np.random.default_rng(seed)
    est = stat(list(records))
    vals = []
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        sample = [r for i in pick for r in groups[keys[i]]]
        v = stat(sample)
        if v is not None and not math.isnan(v):
            vals.append(v)
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(est), float(lo), float(hi)


def paired_cluster_bootstrap_diff(rec_a: Sequence[dict], rec_b: Sequence[dict],
                                  stat: Callable[[list], float],
                                  cluster_key: str = "aia_id", B: int = 2000,
                                  seed: int = 0, alpha: float = 0.05):
    """CI for stat(A) - stat(B) where A and B are two systems scored on the SAME
    items; the same clusters are drawn for both in every replicate."""
    ga, gb = defaultdict(list), defaultdict(list)
    for r in rec_a:
        ga[r[cluster_key]].append(r)
    for r in rec_b:
        gb[r[cluster_key]].append(r)
    keys = sorted(set(ga) & set(gb))
    rng = np.random.default_rng(seed)
    est = stat(list(rec_a)) - stat(list(rec_b))
    vals = []
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        a = [r for i in pick for r in ga[keys[i]]]
        b = [r for i in pick for r in gb[keys[i]]]
        vals.append(stat(a) - stat(b))
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(est), float(lo), float(hi)


# --------------------------------------------------------------- classification
def _norm(y):
    return tuple(sorted(y)) if isinstance(y, (list, tuple, set)) else y


def is_correct(r: dict) -> bool:
    return r["y_pred"] is not ABSTAIN and _norm(r["y_pred"]) == _norm(r["y_true"])


def accuracy(records: Sequence[dict], answered_only: bool = False) -> float:
    """Full-coverage accuracy (abstain = wrong) or selective accuracy
    (answered_only=True: accuracy over the items the model answered)."""
    rs = [r for r in records if r["y_pred"] is not ABSTAIN] if answered_only else list(records)
    if not rs:
        return float("nan")
    return sum(is_correct(r) for r in rs) / len(rs)


def coverage(records: Sequence[dict]) -> float:
    return sum(r["y_pred"] is not ABSTAIN for r in records) / len(records) if records else float("nan")


def macro_f1(y_true: Sequence, y_pred: Sequence, labels: Iterable | None = None) -> float:
    """Unweighted mean of per-class F1 over `labels` (default: classes seen in
    y_true). Abstentions (None) count as a prediction of no class, so they cost
    recall but not precision. A class with no true and no predicted items is
    skipped; one with 0 TP and some FP/FN scores 0."""
    yt = [_norm(y) for y in y_true]
    yp = [_norm(y) for y in y_pred]
    labs = list(dict.fromkeys(labels)) if labels is not None else list(dict.fromkeys(yt))
    f1s = []
    for c in labs:
        tp = sum(1 for a, b in zip(yt, yp) if a == c and b == c)
        fp = sum(1 for a, b in zip(yt, yp) if a != c and b == c)
        fn = sum(1 for a, b in zip(yt, yp) if a == c and b != c)
        if tp + fp + fn == 0:
            continue
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f1s)) if f1s else float("nan")


def per_question(records: Sequence[dict], choices: dict | None = None) -> dict:
    """{question_id: {n, coverage, accuracy, selective_accuracy, macro_f1,
    acc_ci (Wilson, items treated as independent: one item per AIA)}}."""
    by_q = defaultdict(list)
    for r in records:
        by_q[r["question_id"]].append(r)
    out = {}
    for q, rs in sorted(by_q.items()):
        k = sum(is_correct(r) for r in rs)
        labels = choices.get(q) if choices else None
        out[q] = {
            "n": len(rs),
            "coverage": coverage(rs),
            "accuracy": k / len(rs),
            "acc_ci": wilson_ci(k, len(rs)),
            "selective_accuracy": accuracy(rs, answered_only=True),
            "macro_f1": macro_f1([r["y_true"] for r in rs], [r["y_pred"] for r in rs], labels),
        }
    return out


def majority_baseline(train: Sequence[dict], test: Sequence[dict]) -> list[dict]:
    """Majority answer per question learned on TRAIN folds only; confidence =
    training frequency of that answer. Questions unseen in train -> abstain."""
    counts = defaultdict(lambda: defaultdict(int))
    for r in train:
        counts[r["question_id"]][_norm(r["y_true"])] += 1
    out = []
    for r in test:
        c = counts.get(r["question_id"])
        if not c:
            out.append({**r, "y_pred": ABSTAIN, "confidence": 0.0})
            continue
        ans, k = max(c.items(), key=lambda kv: (kv[1], str(kv[0])))
        out.append({**r, "y_pred": ans, "confidence": k / sum(c.values())})
    return out


# ------------------------------------------------------- selective prediction
def risk_coverage_curve(records: Sequence[dict]):
    """Sort answered items by confidence (desc). Abstentions are never covered.
    Returns (coverage[i], selective_accuracy[i]) for the top-i items, i=1..m,
    where coverage is relative to ALL items (answered + abstained)."""
    n = len(records)
    ans = [r for r in records if r["y_pred"] is not ABSTAIN]
    ans.sort(key=lambda r: -r["confidence"])
    corr = np.array([is_correct(r) for r in ans], dtype=float)
    if len(corr) == 0:
        return np.array([0.0]), np.array([float("nan")])
    k = np.arange(1, len(corr) + 1)
    return k / n, np.cumsum(corr) / k


def aurc(records: Sequence[dict]) -> float:
    """Area under the risk-coverage curve (risk = 1 - selective accuracy),
    averaged over the answered prefix; lower is better (Geifman & El-Yaniv 2017).
    Abstained items are added as risk 1 at the tail so systems that abstain
    more are not rewarded for it."""
    n = len(records)
    cov, sacc = risk_coverage_curve(records)
    if np.isnan(sacc).all():
        return 1.0
    risk = 1 - sacc
    m = len(risk)
    return float((risk.sum() + (n - m) * 1.0) / n)


def selective_accuracy_at(records: Sequence[dict], target_coverage: float) -> float:
    """Selective accuracy on the ceil(c*n) most confident answered items.
    NaN if the model answered fewer items than that (coverage not reachable)."""
    n = len(records)
    need = math.ceil(target_coverage * n - 1e-12)
    cov, sacc = risk_coverage_curve(records)
    m = int(round(cov[-1] * n)) if not np.isnan(sacc).all() else 0
    if need == 0:
        return float("nan")
    if need > m:
        return float("nan")
    return float(sacc[need - 1])


# ------------------------------------------------------------------ calibration
def default_n_bins(n: int, min_per_bin: int = 30, max_bins: int = 10) -> int:
    """Equal-mass bins with >= ~30 items each, at least 2, at most 10."""
    return int(max(2, min(max_bins, n // min_per_bin)))


def reliability_table(conf: Sequence[float], correct: Sequence[float], n_bins: int | None = None):
    """Equal-mass (adaptive) binning. Returns list of dicts per bin:
    {n, mean_conf, accuracy, acc_ci (Wilson)} — the data for a reliability diagram."""
    c = np.asarray(conf, float)
    y = np.asarray(correct, float)
    nb = n_bins or default_n_bins(len(c))
    order = np.argsort(c, kind="mergesort")
    rows = []
    for idx in np.array_split(order, nb):
        if len(idx) == 0:
            continue
        k = y[idx].sum()
        rows.append({"n": int(len(idx)), "mean_conf": float(c[idx].mean()),
                     "accuracy": float(k / len(idx)), "acc_ci": wilson_ci(k, len(idx))})
    return rows


def adaptive_ece(conf: Sequence[float], correct: Sequence[float], n_bins: int | None = None) -> float:
    """Expected calibration error with equal-mass bins (Nixon et al. 2019)."""
    rows = reliability_table(conf, correct, n_bins)
    n = sum(r["n"] for r in rows)
    return float(sum(r["n"] / n * abs(r["accuracy"] - r["mean_conf"]) for r in rows))


def null_ece_quantile(conf: Sequence[float], n_bins: int | None = None, q: float = 0.95,
                      n_sim: int = 2000, seed: int = 0) -> float:
    """ECE is biased upward at small n. Simulate a PERFECTLY calibrated model with
    the same confidences (y ~ Bernoulli(conf)) and return the q-quantile of its
    ECE. An observed ECE below this cannot be told apart from perfect calibration."""
    c = np.asarray(conf, float)
    rng = np.random.default_rng(seed)
    sims = [adaptive_ece(c, rng.random(len(c)) < c, n_bins) for _ in range(n_sim)]
    return float(np.quantile(sims, q))


def brier(conf: Sequence[float], correct: Sequence[float]) -> float:
    c = np.asarray(conf, float)
    y = np.asarray(correct, float)
    return float(np.mean((c - y) ** 2))


def calibration_slope_intercept(conf: Sequence[float], correct: Sequence[float],
                                eps: float = 1e-6, iters: int = 100):
    """Cox (1958) logistic recalibration: logit P(correct) = a + b*logit(conf).
    Perfect calibration: a = 0, b = 1. b < 1 = over-confident. Fitted by IRLS.
    Uses all data (no binning), which makes it better suited to small n than ECE."""
    c = np.clip(np.asarray(conf, float), eps, 1 - eps)
    y = np.asarray(correct, float)
    x = np.log(c / (1 - c))
    X = np.column_stack([np.ones_like(x), x])
    beta = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ beta)))
        w = np.clip(p * (1 - p), 1e-9, None)
        H = X.T @ (X * w[:, None]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, X.T @ (y - p))
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(beta[0]), float(beta[1])


def calibration_summary(records: Sequence[dict], n_bins: int | None = None, seed: int = 0) -> dict:
    ans = [r for r in records if r["y_pred"] is not ABSTAIN]
    conf = [r["confidence"] for r in ans]
    corr = [float(is_correct(r)) for r in ans]
    a, b = calibration_slope_intercept(conf, corr)
    nb = n_bins or default_n_bins(len(conf))
    return {"n": len(ans), "n_bins": nb, "ece_adaptive": adaptive_ece(conf, corr, nb),
            "ece_null95": null_ece_quantile(conf, nb, seed=seed), "brier": brier(conf, corr),
            "cal_intercept": a, "cal_slope": b, "reliability": reliability_table(conf, corr, nb)}


# ------------------------------------------------------------- impact level
def js_round(x: float) -> int:
    """JavaScript Math.round (half rounds toward +inf), NOT Python's banker's round."""
    return int(math.floor(x + 0.5))


def impact_level(answers: dict, questions: dict, mitigation_pct: float = 0.8,
                 deduction: float = 0.15, thresholds=(0.25, 0.5, 0.75)) -> dict:
    """Re-implementation of calculateFinalScore() in
    vendor/aia-eia-js/src/store.ts (read 2026-11-05).

    questions: {name: {"score_type": "RS"|"MS"|"NS", "qtype": "radiogroup"|"dropdown"|"checkbox",
                       "values": {choice: points}}}
    answers:   {name: choice | [choices]}; unanswered names score 0 but still add
               their max to the denominator, as in the vendor code for every name in
               questionNames (pass only the names the survey would include).
    """
    raw = max_raw = mit = max_mit = 0
    for name, q in questions.items():
        st = q["score_type"]
        if st not in ("RS", "MS"):
            continue
        vals = q["values"]
        qmax = sum(vals.values()) if q["qtype"] == "checkbox" else max(vals.values(), default=0)
        a = answers.get(name)
        if a is None:
            got = 0
        elif isinstance(a, (list, tuple, set)):
            got = sum(vals.get(x, 0) for x in a)
        else:
            got = vals.get(a, 0)
        if st == "RS":
            raw += got
            max_raw += qmax
        else:
            mit += got
            max_mit += qmax
    # vendor: maxMitigationScore / 2 because of the Design/Implementation fork
    total = js_round((1 - deduction) * raw) if mit >= mitigation_pct * (max_mit / 2) else raw
    t1, t2, t3 = (t * max_raw for t in thresholds)
    level = 1 if total <= t1 else 2 if total <= t2 else 3 if total <= t3 else 4
    return {"raw": raw, "max_raw": max_raw, "mitigation": mit, "max_mitigation": max_mit,
            "total": total, "level": level}


def fill_abstentions(pred: dict, questions: dict, policy: str, oracle: dict | None = None) -> dict:
    """Fill items the model abstained on before scoring the level.
    policy 'conservative': highest raw-risk choice, lowest mitigation choice (no oracle).
    policy 'oracle': the department's answer (= a human completes the gaps)."""
    out = dict(pred)
    for name, q in questions.items():
        if out.get(name) is not ABSTAIN:
            continue
        if policy == "oracle":
            out[name] = (oracle or {}).get(name)
        elif policy == "conservative":
            vals = q["values"]
            if not vals:
                continue
            if q["score_type"] == "RS":
                out[name] = list(vals) if q["qtype"] == "checkbox" else max(vals, key=vals.get)
            elif q["score_type"] == "MS":
                out[name] = [] if q["qtype"] == "checkbox" else min(vals, key=vals.get)
        else:
            raise ValueError(policy)
    return out


def level_agreement(true_levels: Sequence[int], pred_levels: Sequence[int]) -> dict:
    t = np.asarray(true_levels, int)
    p = np.asarray(pred_levels, int)
    n = len(t)
    k = int((t == p).sum())
    under = int((p < t).sum())
    return {"n": n, "exact": k / n, "exact_ci": wilson_ci(k, n),
            "under_rate": under / n, "under_ci": wilson_ci(under, n),
            "under_by_2plus": int(((t - p) >= 2).sum()),
            "within_1": float((np.abs(t - p) <= 1).mean()),
            "qwk": weighted_kappa(t, p, [1, 2, 3, 4], "quadratic")}


# ------------------------------------------------------------------ agreement
def weighted_kappa(a: Sequence, b: Sequence, labels: Sequence, weights: str | None = None) -> float:
    """Cohen's kappa; weights None (nominal), 'linear' or 'quadratic' (ordinal)."""
    L = list(labels)
    idx = {v: i for i, v in enumerate(L)}
    K = len(L)
    O = np.zeros((K, K))
    for x, y in zip(a, b):
        O[idx[x], idx[y]] += 1
    n = O.sum()
    E = np.outer(O.sum(1), O.sum(0)) / n
    i, j = np.indices((K, K))
    if weights is None:
        W = (i != j).astype(float)
    elif weights == "linear":
        W = np.abs(i - j) / (K - 1)
    else:
        W = ((i - j) / (K - 1)) ** 2
    den = (W * E).sum()
    return float(1 - (W * O).sum() / den) if den > 0 else 1.0


# -------------------------------------------------------------- evidence
EVIDENCE_LABELS = ("supports", "partial", "no")


def evidence_verbatim(sentence: str, source_text: str) -> bool:
    """Automatic hallucination check: the quoted evidence must occur in the input
    (whitespace-normalised, case-insensitive)."""
    norm = lambda s: " ".join(s.split()).lower()
    return bool(sentence) and norm(sentence) in norm(source_text)


def evidence_correctness(human_labels: Sequence[str]) -> dict:
    """Human judgement per answered item: 'supports' | 'partial' | 'no'.
    strict = supports; lenient = supports or partial. Wilson CIs."""
    n = len(human_labels)
    s = sum(h == "supports" for h in human_labels)
    p = sum(h == "partial" for h in human_labels)
    return {"n": n, "strict": s / n if n else float("nan"), "strict_ci": wilson_ci(s, n),
            "lenient": (s + p) / n if n else float("nan"), "lenient_ci": wilson_ci(s + p, n)}


# ------------------------------------------------------------------ report
def full_report(records: Sequence[dict], coverages=(0.4, 0.5, 0.6, 0.8), B: int = 2000, seed: int = 0) -> dict:
    """Primary item-level numbers with cluster-bootstrap CIs (resampling AIAs)."""
    rep = {"n_items": len(records), "n_aia": len({r["aia_id"] for r in records}),
           "n_departments": len({r["department"] for r in records}),
           "coverage": coverage(records),
           "accuracy_full": cluster_bootstrap(records, accuracy, B=B, seed=seed),
           "aurc": cluster_bootstrap(records, aurc, B=B, seed=seed)}
    for c in coverages:
        rep[f"sel_acc@{c}"] = cluster_bootstrap(records, lambda rs, c=c: selective_accuracy_at(rs, c), B=B, seed=seed)
    rep["macro_f1_mean_over_questions"] = cluster_bootstrap(
        records, lambda rs: float(np.nanmean([v["macro_f1"] for v in per_question(rs).values()])), B=B, seed=seed)
    rep["calibration"] = calibration_summary(records, seed=seed)
    return rep
