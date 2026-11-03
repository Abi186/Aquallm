
from pathlib import Path
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor

from xgboost import XGBRegressor


# ============================================================
# PATHS
# ============================================================

ML_DIR = Path(__file__).resolve().parent

MODEL_PATH = ML_DIR / "feed_model.joblib"

RANDOM_FOREST_PATH = ML_DIR / "random_forest_model.joblib"
XGBOOST_PATH = ML_DIR / "xgboost_model.joblib"

META_PATH = ML_DIR / "feed_model_meta.json"


# ============================================================
# FEATURES AND TARGET
# ============================================================

FEATURES = [
    "doc",
    "avg_weight_g",
    "biomass_kg",
    "temperature_c",
    "dissolved_oxygen",
    "previous_feed_kg",
]

TARGET = "feed_quantity_kg"


# ============================================================
# MODEL BUILDERS
# ============================================================

def make_random_forest_pipeline():

    return Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "model",
            RandomForestRegressor(
                n_estimators=300,
                max_depth=15,
                min_samples_split=4,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
        )
    ])


def make_xgboost_pipeline():

    return Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "model",
            XGBRegressor(
                n_estimators=400,
                max_depth=5,
                learning_rate=0.04,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_lambda=1.0,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=-1,
                verbosity=0
            )
        )
    ])


# ============================================================
# COMMON PIPELINE FUNCTION
# ============================================================

def make_pipeline(model_name="random_forest"):

    if model_name == "random_forest":
        return make_random_forest_pipeline()

    if model_name == "xgboost":
        return make_xgboost_pipeline()

    raise ValueError(
        f"Unknown model name: {model_name}"
    )


# ============================================================
# TRAIN BOTH MODELS
# ============================================================

def train_models(training_data):

    X = training_data[FEATURES]

    y = training_data[TARGET].clip(lower=0)

    models = {}

    # Train Random Forest
    rf_model = make_random_forest_pipeline()
    rf_model.fit(X, y)

    models["random_forest"] = rf_model

    # Train XGBoost
    xgb_model = make_xgboost_pipeline()
    xgb_model.fit(X, y)

    models["xgboost"] = xgb_model

    return models


# ============================================================
# SAVE BOTH MODELS
# ============================================================

def save_models(models, selected_model):

    if selected_model not in models:
        raise ValueError(
            f"Selected model '{selected_model}' does not exist."
        )

    joblib.dump(
        models["random_forest"],
        RANDOM_FOREST_PATH
    )

    joblib.dump(
        models["xgboost"],
        XGBOOST_PATH
    )

    # The API always loads this selected model.
    joblib.dump(
        models[selected_model],
        MODEL_PATH
    )

    # Clear cached model so the next prediction loads the new one.
    load_model.cache_clear()


# ============================================================
# LOAD SELECTED MODEL
# ============================================================

@lru_cache(maxsize=1)
def load_model():

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Feed prediction model not found. "
            "Run: python -m app.ml.train_feed_model"
        )

    return joblib.load(MODEL_PATH)


# ============================================================
# PREDICT FEED
# ============================================================

def predict_feed(values):

    model = load_model()

    if isinstance(values, dict):
        values = pd.DataFrame(
            [values],
            columns=FEATURES
        )

    elif not isinstance(values, pd.DataFrame):
        values = pd.DataFrame(
            values,
            columns=FEATURES
        )

    values = values[FEATURES]

    prediction = model.predict(values)

    prediction = np.clip(
        prediction,
        0,
        None
    )

    return float(prediction[0])
