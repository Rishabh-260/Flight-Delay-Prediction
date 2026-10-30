from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score, precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from flight_delay.features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, assert_no_target_leakage

RANDOM_STATE = 42


def chronological_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Use Jan-Sep for training, Oct validation, and Nov-Dec final test for a 2025 cohort."""
    dates = pd.to_datetime(frame["flight_date"])
    train = frame.loc[dates.dt.month <= 9]
    valid = frame.loc[dates.dt.month == 10]
    test = frame.loc[dates.dt.month >= 11]
    if min(map(len, (train, valid, test))) == 0:
        raise ValueError("Chronological split requires at least one row in Jan-Sep, Oct, and Nov-Dec.")
    return train, valid, test


def _pipeline(estimator: object) -> Pipeline:
    prep = ColumnTransformer([
        ("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20)),
        ]), CATEGORICAL_FEATURES),
        ("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler(with_mean=False)),
        ]), NUMERIC_FEATURES),
    ])
    return Pipeline([("preprocess", prep), ("model", estimator)])


def _models(positive_weight: float) -> dict[str, Pipeline]:
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("XGBoost is required for model training; install project requirements with `pip install -r requirements.txt`.") from exc
    return {
        "logistic_regression": _pipeline(LogisticRegression(class_weight="balanced", max_iter=500, solver="saga", random_state=RANDOM_STATE, n_jobs=-1)),
        "random_forest": _pipeline(RandomForestClassifier(n_estimators=250, min_samples_leaf=3, max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1, random_state=RANDOM_STATE)),
        "xgboost": _pipeline(XGBClassifier(n_estimators=350, max_depth=7, learning_rate=0.08, subsample=0.85, colsample_bytree=0.85, reg_lambda=2.0, scale_pos_weight=positive_weight, eval_metric="logloss", tree_method="hist", n_jobs=-1, random_state=RANDOM_STATE)),
    }


def _threshold_for_f1(y_true: pd.Series, probabilities: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    if not len(thresholds):
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.nanargmax(f1))])


def _sample_training(frame: pd.DataFrame, cap: int = 300_000) -> pd.DataFrame:
    if len(frame) <= cap:
        return frame
    sampled = frame.groupby("is_delayed", group_keys=False).apply(
        lambda group: group.sample(n=max(1, round(cap * len(group) / len(frame))), random_state=RANDOM_STATE),
        include_groups=True,
    )
    return sampled.sample(n=min(cap, len(sampled)), random_state=RANDOM_STATE)


def train_and_evaluate(frame: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    assert_no_target_leakage(FEATURES)
    train, valid, test = chronological_split(frame)
    train = _sample_training(train)
    X_train, y_train = train[FEATURES], train["is_delayed"].astype(int)
    X_valid, y_valid = valid[FEATURES], valid["is_delayed"].astype(int)
    X_test, y_test = test[FEATURES], test["is_delayed"].astype(int)
    positive_weight = max(1.0, float((y_train == 0).sum() / max((y_train == 1).sum(), 1)))
    metrics, fitted = [], {}
    for name, model in _models(positive_weight).items():
        model.fit(X_train, y_train)
        valid_probability = model.predict_proba(X_valid)[:, 1]
        threshold = _threshold_for_f1(y_valid, valid_probability)
        test_probability = model.predict_proba(X_test)[:, 1]
        prediction = test_probability >= threshold
        metrics.append({
            "model": name, "threshold": threshold,
            "precision": precision_score(y_test, prediction, zero_division=0),
            "recall": recall_score(y_test, prediction, zero_division=0),
            "f1": f1_score(y_test, prediction, zero_division=0),
            "roc_auc": roc_auc_score(y_test, test_probability),
            "test_rows": len(test), "train_rows": len(train),
        })
        fitted[name] = model
    metric_frame = pd.DataFrame(metrics).sort_values("roc_auc", ascending=False)
    winner = str(metric_frame.iloc[0]["model"])
    output_dir.mkdir(parents=True, exist_ok=True)
    metric_frame.to_csv(output_dir / "model_metrics.csv", index=False)
    (output_dir / "model_metrics.json").write_text(metric_frame.to_json(orient="records", indent=2), encoding="utf-8")
    joblib.dump({"model": fitted[winner], "features": FEATURES, "threshold": float(metric_frame.iloc[0]["threshold"]), "model_name": winner}, output_dir / "best_model.joblib")
    # Model-agnostic importance on a reproducible 5k-row test sample.
    importance_data = test.sample(n=min(5000, len(test)), random_state=RANDOM_STATE)
    importance = permutation_importance(fitted[winner], importance_data[FEATURES], importance_data["is_delayed"].astype(int), scoring="roc_auc", n_repeats=3, random_state=RANDOM_STATE, n_jobs=-1)
    importance_frame = pd.DataFrame({"feature": FEATURES, "importance_mean": importance.importances_mean, "importance_std": importance.importances_std}).sort_values("importance_mean", ascending=False)
    importance_frame.to_csv(output_dir / "feature_importance.csv", index=False)
    return metric_frame, importance_frame
