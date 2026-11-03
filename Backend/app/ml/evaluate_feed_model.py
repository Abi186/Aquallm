
"""
AquaLLM - Random Forest vs XGBoost Evaluation

Compares both models using:
1. Time-based holdout testing
2. Seven-day recursive forecast backtesting

The best model is selected using:
1. Lowest holdout MAPE
2. Lowest holdout MAE as tie-breaker

Run from Backend:
python -m app.ml.evaluate_feed_model
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error

from app.ml.feed_model import (
    FEATURES,
    TARGET,
    make_pipeline,
)


# ============================================================
# PATHS AND SETTINGS
# ============================================================

ML_DIR = Path(__file__).resolve().parent

DATA_PATH = ML_DIR / "feed_training_data.csv"
REPORT_PATH = ML_DIR / "feed_model_report.json"
PREDICTIONS_PATH = ML_DIR / "feed_model_test_predictions.csv"
PLOT_PATH = ML_DIR / "feed_model_report.png"

TEST_FRACTION = 0.20
HORIZON_DAYS = 7
GOOD_MAPE = 10.0

MODEL_NAMES = [
    "random_forest",
    "xgboost",
]


# ============================================================
# METRICS
# ============================================================

def regression_metrics(y_true, y_pred):

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    error = y_pred - y_true

    nonzero = y_true > 0

    if not np.any(nonzero):
        mape = 0.0
    else:
        percentage_error = (
            np.abs(error[nonzero])
            / y_true[nonzero]
        ) * 100

        mape = float(percentage_error.mean())

    return {
        "rows": int(len(y_true)),

        "mae_kg": round(
            float(mean_absolute_error(y_true, y_pred)), 3
        ),

        "mape_pct": round(mape, 2),

        "bias_kg": round(float(error.mean()), 3),
    }


# ============================================================
# LOAD DATA
# ============================================================

def load_data(path=DATA_PATH):

    if not path.exists():
        raise FileNotFoundError(
            "Training data is missing. Run: "
            "python -m app.ml.build_training_data"
        )

    data = pd.read_csv(path)

    required_columns = (
        FEATURES
        + [TARGET, "feed_date", "pond_id"]
    )

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns in training data: {missing}"
        )

    data["feed_date"] = pd.to_datetime(
        data["feed_date"]
    )

    data = data.dropna(subset=[TARGET])

    if data.empty:
        raise ValueError(
            "Training data contains no valid feed records."
        )

    return data.sort_values(
        ["feed_date", "pond_id"]
    ).reset_index(drop=True)


# ============================================================
# DATA SUMMARY
# ============================================================

def data_summary(data):

    missing = {
        column: int(data[column].isna().sum())
        for column in FEATURES
    }

    return {
        "rows": int(len(data)),

        "ponds": int(data["pond_id"].nunique()),

        "date_from": data["feed_date"].min().date().isoformat(),

        "date_to": data["feed_date"].max().date().isoformat(),

        "doc_min": int(data["doc"].min()),

        "doc_max": int(data["doc"].max()),

        "feed_kg_min": round(float(data[TARGET].min()), 2),

        "feed_kg_mean": round(float(data[TARGET].mean()), 2),

        "feed_kg_max": round(float(data[TARGET].max()), 2),

        "missing_values": missing,
    }


# ============================================================
# TIME-BASED TRAIN / TEST SPLIT
# ============================================================

def time_split(data):

    cutoff = data["feed_date"].quantile(
        1 - TEST_FRACTION
    )

    train = data[
        data["feed_date"] <= cutoff
    ].copy()

    test = data[
        data["feed_date"] > cutoff
    ].copy()

    if len(train) < 50 or len(test) < 20:
        raise ValueError(
            "Not enough data for a meaningful time-based test."
        )

    return train, test, cutoff


# ============================================================
# TRAIN A MODEL
# ============================================================

def fit_model(train, model_name):

    model = make_pipeline(model_name)

    model.fit(
        train[FEATURES],
        train[TARGET].clip(lower=0)
    )

    return model


# ============================================================
# SEVEN-DAY FORECAST BACKTEST
# ============================================================

def horizon_backtest(model, data, cutoff):

    origins = []
    outcomes = []

    for _, pond in data.groupby("pond_id"):

        pond = pond.sort_values(
            "feed_date"
        ).reset_index(drop=True)

        dates = pond["feed_date"].to_numpy()

        for i in range(
            len(pond) - HORIZON_DAYS
        ):

            row = pond.iloc[i]

            # Test only future records after the cutoff.
            if row["feed_date"] <= cutoff:
                continue

            span = (
                dates[i + HORIZON_DAYS] - dates[i]
            ) / np.timedelta64(1, "D")

            if span != HORIZON_DAYS:
                continue

            if (
                pd.isna(row["avg_weight_g"])
                or pd.isna(row["biomass_kg"])
            ):
                continue

            origins.append(row)

            outcomes.append(
                pond[TARGET].iloc[
                    i + 1:i + 1 + HORIZON_DAYS
                ].to_numpy()
            )

    if not origins:
        return []

    start = pd.DataFrame(
        origins
    ).reset_index(drop=True)

    actual = np.vstack(outcomes)

    previous = start[TARGET].to_numpy(
        dtype=float
    )

    results = []

    for day in range(1, HORIZON_DAYS + 1):

        inputs = pd.DataFrame({
            "doc": start["doc"] + day,
            "avg_weight_g": start["avg_weight_g"],
            "biomass_kg": start["biomass_kg"],
            "temperature_c": start["temperature_c"],
            "dissolved_oxygen": start["dissolved_oxygen"],
            "previous_feed_kg": previous,
        })[FEATURES]

        predictions = np.clip(
            model.predict(inputs),
            0,
            None
        )

        # Predicted feed becomes the next day's input.
        previous = predictions

        truth = actual[:, day - 1]

        metrics = regression_metrics(
            truth,
            predictions
        )

        results.append({
            "day": day,
            "start_days_tested": int(len(start)),
            "mae_kg": metrics["mae_kg"],
            "mape_pct": metrics["mape_pct"],
            "bias_kg": metrics["bias_kg"],
        })

    return results


# ============================================================
# RELIABLE FORECAST DAYS
# ============================================================

def reliable_days(horizon):

    days = 0

    for row in horizon:

        if row["mape_pct"] <= GOOD_MAPE:
            days = row["day"]
        else:
            break

    return days


# ============================================================
# SELECT BEST MODEL
# ============================================================

def select_best_model(model_results):

    available = {
        name: result
        for name, result in model_results.items()
        if result.get("holdout_metrics")
    }

    if not available:
        raise ValueError(
            "No model has valid holdout evaluation results."
        )

    best_name = min(
        available,
        key=lambda name: (
            available[name]["holdout_metrics"]["mape_pct"],
            available[name]["holdout_metrics"]["mae_kg"],
        )
    )

    return best_name


# ============================================================
# MAIN EVALUATION
# ============================================================

def evaluate(data=None, quiet=False):

    if data is None:
        data = load_data()

    log = (
        (lambda *args, **kwargs: None)
        if quiet else print
    )

    summary = data_summary(data)

    train, test, cutoff = time_split(data)

    model_results = {}

    trained_models = {}

    # --------------------------------------------------------
    # Evaluate both models on the same time-based split.
    # --------------------------------------------------------

    for model_name in MODEL_NAMES:

        log(f"\nEvaluating: {model_name}")

        model = fit_model(
            train,
            model_name
        )

        trained_models[model_name] = model

        predictions = np.clip(
            model.predict(test[FEATURES]),
            0,
            None
        )

        holdout = regression_metrics(
            test[TARGET],
            predictions
        )

        horizon = horizon_backtest(
            model,
            data,
            cutoff
        )

        model_results[model_name] = {
            "holdout_metrics": holdout,

            "horizon_backtest": horizon,

            "reliable_days_within_10pct": reliable_days(
                horizon
            ),
        }

        log(
            f"  Holdout MAPE: {holdout['mape_pct']}%"
        )

        log(
            f"  Holdout MAE: {holdout['mae_kg']} kg"
        )

    # --------------------------------------------------------
    # Select the best model.
    # --------------------------------------------------------

    best_model = select_best_model(
        model_results
    )

    best_metrics = model_results[
        best_model
    ]["holdout_metrics"]

    # --------------------------------------------------------
    # Selected model test predictions.
    # --------------------------------------------------------

    selected_model = trained_models[
        best_model
    ]

    selected_predictions = np.clip(
        selected_model.predict(test[FEATURES]),
        0,
        None
    )

    plain_summary = (
        f"{best_model} was selected based on the lowest "
        f"time-based holdout MAPE of "
        f"{best_metrics['mape_pct']}% "
        f"and MAE of {best_metrics['mae_kg']} kg."
    )

    report = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),

        "best_model": best_model,

        "selection_method": (
            "Lowest time-based holdout MAPE; "
            "lowest MAE used as tie-breaker."
        ),

        "features": FEATURES,

        "target": TARGET,

        "data": summary,

        "split": {
            "method": (
                "Time-based: train on earlier dates, "
                "test on the latest dates."
            ),

            "cutoff_date": cutoff.date().isoformat(),

            "train_rows": int(len(train)),

            "test_rows": int(len(test)),

            "test_doc_range": [
                int(test["doc"].min()),
                int(test["doc"].max()),
            ],
        },

        "models": model_results,

        "plain_summary": plain_summary,
    }

    # --------------------------------------------------------
    # PRINT COMPARISON
    # --------------------------------------------------------

    log("\n" + "=" * 65)
    log("AQUALLM - MODEL COMPARISON REPORT")
    log("=" * 65)

    log("\nTRAINING DATA")

    log(f"Rows: {summary['rows']}")

    log(f"Ponds: {summary['ponds']}")

    log(
        f"Dates: {summary['date_from']} to "
        f"{summary['date_to']}"
    )

    log("\nTIME-BASED TEST")

    log(f"Training rows: {len(train)}")

    log(f"Testing rows : {len(test)}")

    log(f"Cutoff date  : {cutoff.date()}")

    log("\nMODEL COMPARISON")

    for name, result in model_results.items():

        metrics = result["holdout_metrics"]

        log(f"\n{name.upper()}")

        log(f"MAE  : {metrics['mae_kg']} kg")

        log(f"MAPE : {metrics['mape_pct']}%")

        log(f"Bias : {metrics['bias_kg']} kg")

        log(
            "Reliable forecast days: "
            f"{result['reliable_days_within_10pct']}"
        )

    log("\n" + "=" * 65)

    log(f"SELECTED MODEL: {best_model.upper()}")

    log("=" * 65)

    log(plain_summary)

    # --------------------------------------------------------
    # SAVE SELECTED MODEL PREDICTIONS
    # --------------------------------------------------------

    output = test[
        ["pond_id", "feed_date", "doc", TARGET]
    ].copy()

    output["predicted_feed_kg"] = np.round(
        selected_predictions,
        2
    )

    output["error_kg"] = np.round(
        output["predicted_feed_kg"] - output[TARGET],
        2
    )

    output["abs_pct_error"] = np.round(
        (
            output["error_kg"].abs()
            / output[TARGET].where(
                output[TARGET] > 0
            )
        ) * 100,
        1
    )

    output = output.rename(
        columns={
            TARGET: "actual_feed_kg"
        }
    )

    output.to_csv(
        PREDICTIONS_PATH,
        index=False
    )

    # --------------------------------------------------------
    # SAVE EVALUATION REPORT
    # --------------------------------------------------------

    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    log(
        f"\nSaved: {REPORT_PATH.name}"
    )

    log(
        f"Saved: {PREDICTIONS_PATH.name}"
    )

    _plot(
        output,
        model_results[best_model]["horizon_backtest"],
        log
    )

    return report


# ============================================================
# OPTIONAL CHART
# ============================================================

def _plot(output, horizon, log):

    try:
        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt

    except ImportError:

        log(
            " Install matplotlib if required."
        )

        return

    if output.empty:
        return

    figure, axes = plt.subplots(
        1,
        2 if horizon else 1,
        figsize=(12, 4.5) if horizon else (6, 4.5)
    )

    if not isinstance(axes, np.ndarray):
        axes = [axes]

    axes[0].scatter(
        output["actual_feed_kg"],
        output["predicted_feed_kg"],
        s=8,
        alpha=0.5
    )

    top = float(
        max(
            output["actual_feed_kg"].max(),
            output["predicted_feed_kg"].max()
        )
    )

    axes[0].plot(
        [0, top],
        [0, top],
        color="red",
        linewidth=1
    )

    axes[0].set_title(
        "Selected model: Predicted vs actual feed"
    )

    axes[0].set_xlabel("Actual feed (kg)")

    axes[0].set_ylabel("Predicted feed (kg)")

    if horizon:

        days = [
            row["day"]
            for row in horizon
        ]

        mape = [
            row["mape_pct"]
            for row in horizon
        ]

        axes[1].plot(
            days,
            mape,
            marker="o"
        )

        axes[1].set_title(
            "Seven-day forecast MAPE"
        )

        axes[1].set_xlabel("Days ahead")

        axes[1].set_ylabel("MAPE (%)")

    figure.tight_layout()

    figure.savefig(
        PLOT_PATH,
        dpi=120
    )

    plt.close(figure)

    log(f"Saved: {PLOT_PATH.name}")


if __name__ == "__main__":
    evaluate()
