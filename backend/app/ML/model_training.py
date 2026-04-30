"""Model training pipeline for PV production and household consumption forecasting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from .config import MODELS_DIR
# Import de ton moteur de features !
from .feature_engineering import build_features

try:
    from skforecast.ForecasterAutoreg import ForecasterAutoreg
except ImportError:  # pragma: no cover
    from skforecast.recursive import ForecasterRecursive as ForecasterAutoreg

# Sensible defaults — skip Optuna entirely in quick mode
DEFAULT_LGBM_PARAMS: dict[str, Any] = {
    "num_leaves": 63,
    "learning_rate": 0.08,
    "n_estimators": 400,
    "min_child_samples": 20,
    "verbosity": -1,
    "random_state": 42,
    "n_jobs": -1,
}


def _prepare_training_data(df: pd.DataFrame, target_col: str) -> tuple[pd.Series, pd.DataFrame | None]:
    """Prepare target and exogenous matrices from a numeric feature table."""
    if target_col not in df.columns:
        raise ValueError(f"Target column not found: {target_col}")

    numeric_df = df.select_dtypes(include=[np.number]).copy()
    exog_cols = [col for col in numeric_df.columns if col != target_col]
    cols_to_check = [target_col] + exog_cols
    prepared = numeric_df[cols_to_check].sort_index()
    prepared = prepared[~prepared.index.duplicated(keep="last")]

    # skforecast expects a DatetimeIndex with an explicit frequency.
    prepared = prepared.asfreq("15min")
    prepared = prepared.dropna()

    if len(prepared) < 300:
        raise ValueError("Not enough rows after dropping NaNs to train robustly.")

    y = prepared[target_col]
    exog = prepared[exog_cols] if exog_cols else None
    return y, exog


def create_forecasters() -> dict[str, Any]:
    """Create independent autoregressive forecasters for both targets."""
    # Les lags sont réduits ici car on utilise les lags de build_features en exogène
    base_lags = [1, 4]

    forecasters = {
        "production": ForecasterAutoreg(
            regressor=LGBMRegressor(**DEFAULT_LGBM_PARAMS), lags=base_lags,
        ),
        "consumption": ForecasterAutoreg(
            regressor=LGBMRegressor(**DEFAULT_LGBM_PARAMS), lags=base_lags,
        ),
    }
    return forecasters


def optimize_hyperparameters(
    forecaster: Any,
    df: pd.DataFrame,
    target_col: str,
    n_trials: int = 20,
) -> dict[str, Any]:
    """Optimize LGBMRegressor hyperparameters with Optuna and time CV."""
    y, exog = _prepare_training_data(df, target_col)
    splitter = TimeSeriesSplit(n_splits=3)
    forecaster_lags = forecaster.lags

    def objective(trial: optuna.trial.Trial) -> float:
        params = {
            "num_leaves": trial.suggest_int("num_leaves", 31, 127),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.2),
            "n_estimators": trial.suggest_int("n_estimators", 200, 600),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
            "verbosity": -1,
            "random_state": 42,
            "n_jobs": -1,
        }

        rmse_values: list[float] = []
        for train_idx, val_idx in splitter.split(y):
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            exog_train = exog.iloc[train_idx] if exog is not None else None
            exog_val = exog.iloc[val_idx] if exog is not None else None

            fold_forecaster = ForecasterAutoreg(
                regressor=LGBMRegressor(**params),
                lags=forecaster_lags,
            )
            fold_forecaster.fit(y=y_train, exog=exog_train)
            preds = fold_forecaster.predict(steps=len(y_val), exog=exog_val)

            rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
            rmse_values.append(rmse)

        return float(np.mean(rmse_values))

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)
    return dict(study.best_params)


def train_forecaster(forecaster: Any, df: pd.DataFrame, target_col: str) -> Any:
    """Train a forecaster on the full available dataset."""
    y, exog = _prepare_training_data(df, target_col)
    forecaster.fit(y=y, exog=exog)
    return forecaster


def save_forecaster(forecaster: Any, filepath: str) -> None:
    """Serialize a trained forecaster to disk with joblib."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(forecaster, path)


def load_forecaster(filepath: str) -> Any:
    """Load a serialized forecaster from a joblib file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Forecaster file not found: {filepath}")
    return joblib.load(path)


def run_training_pipeline(
    df: pd.DataFrame,
    output_dir: str = MODELS_DIR,
    optimize: bool = True,
    optuna_trials: int = 20,
) -> dict[str, Any]:
    """Run full training workflow for production and consumption models."""
    # On n'ajoute plus is_holiday ici, on suppose que df est déjà passé par build_features()
    forecasters = create_forecasters()

    target_map = {
        "production": "production_kw",
        "consumption": "consumption_kw",
    }

    best_params: dict[str, dict[str, Any]] = {}
    trained_forecasters: dict[str, Any] = {}

    for model_name, target_col in target_map.items():
        if optimize:
            best = optimize_hyperparameters(
                forecaster=forecasters[model_name],
                df=df,
                target_col=target_col,
                n_trials=optuna_trials,
            )
            best_params[model_name] = best
            forecasters[model_name].regressor.set_params(**best)
        else:
            best_params[model_name] = DEFAULT_LGBM_PARAMS

        trained = train_forecaster(
            forecaster=forecasters[model_name],
            df=df,
            target_col=target_col,
        )
        trained_forecasters[model_name] = trained

        model_path = Path(output_dir) / f"{model_name}_forecaster.joblib"
        save_forecaster(trained, str(model_path))

    return {
        "forecasters": trained_forecasters,
        "best_params": best_params,
    }


if __name__ == "__main__":

