
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.ml.evaluate_feed_model import load_data, evaluate
from app.ml.feed_model import (
    FEATURES,
    TARGET,
    META_PATH,
    train_models,
    save_models,
)


def main():
    print("\n========== AquaLLM Feed Model Training ==========\n")

    # 1. Load the training dataset
    print("Step 1: Loading training data...")
    data = load_data()

    if data is None or data.empty:
        raise ValueError("Training dataset is empty. Check feed_training_data.csv.")

    print(f"Total records: {len(data)}")

    # 2. Evaluate both algorithms
    print("\nStep 2: Comparing Random Forest and XGBoost...")
    report = evaluate(data, quiet=False)

    selected_model = report["best_model"]

    model_names = {
        "random_forest": "Random Forest",
        "xgboost": "XGBoost",
    }

    if selected_model not in model_names:
        raise ValueError(f"Unexpected selected model: {selected_model}")

    print(f"\nSelected algorithm: {model_names[selected_model]}")

    # 3. Train both models using the complete dataset
    print("\nStep 3: Training both models on the complete dataset...")
    models = train_models(data)

    # 4. Save both models and the selected model
    print("\nStep 4: Saving models...")
    save_models(models, selected_model)

    # 5. Get selected model evaluation results
    selected_results = report["models"][selected_model]

    holdout_metrics = selected_results.get("holdout_metrics", {})
    unseen_metrics = selected_results.get("unseen_pond_metrics", {})

    # 6. Prepare model metadata
    date_column = "feed_date"

    date_from = None
    date_to = None

    if date_column in data.columns:
        dates = pd.to_datetime(data[date_column], errors="coerce").dropna()

        if not dates.empty:
            date_from = str(dates.min().date())
            date_to = str(dates.max().date())

    pond_count = (
        int(data["pond_id"].nunique())
        if "pond_id" in data.columns
        else None
    )

    metadata = {
        "selected_model": selected_model,
        "selected_model_display": model_names[selected_model],
        "selection_method": report.get("selection_method"),
        "selected_holdout_metrics": holdout_metrics,
        "selected_unseen_pond_metrics": unseen_metrics,
        "reliable_days_within_10pct": selected_results.get(
            "reliable_days_within_10pct"
        ),
        "training_rows": int(len(data)),
        "pond_count": pond_count,
        "date_from": date_from,
        "date_to": date_to,
        "features": FEATURES,
        "target": TARGET,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "model_files": {
            "random_forest": "random_forest_model.joblib",
            "xgboost": "xgboost_model.joblib",
            "selected_model": "feed_model.joblib",
        },
    }

    # 7. Save metadata
    META_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(META_PATH, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4, default=str)

    print("\n========== Training Completed ==========")
    print(f"Selected model: {model_names[selected_model]}")
    print(f"Training records: {len(data)}")
    print(f"Metadata saved: {META_PATH}")
    print("The selected model is ready for feed prediction.")


if __name__ == "__main__":
    main()
