import os
from pathlib import Path

import yaml


def load_config():
    path = Path(__file__).parent.parent / "config.yaml"
    with open(path, "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    if os.getenv("MONGO_URI"):
        cfg["mongodb"]["uri"] = os.getenv("MONGO_URI")
    if os.getenv("MLFLOW_TRACKING_URI"):
        cfg["mlflow"]["tracking_uri"] = os.getenv("MLFLOW_TRACKING_URI")
    if os.getenv("MLFLOW_TRACKING_USERNAME"):
        cfg["mlflow"]["tracking_username"] = os.getenv("MLFLOW_TRACKING_USERNAME")
    if os.getenv("MLFLOW_TRACKING_PASSWORD"):
        cfg["mlflow"]["tracking_password"] = os.getenv("MLFLOW_TRACKING_PASSWORD")
    return cfg


settings = load_config()
