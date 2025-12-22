import yaml
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_LABEL_PATH = Path(__file__).resolve().parents[1] / "config" / "cvat_labels.yaml"


def load_cvat_labels(config_path: Path = DEFAULT_LABEL_PATH) -> List[Dict[str, Any]]:
    if not config_path.exists():
        raise FileNotFoundError(f"CVAT label config not found: {config_path}")

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    if "labels" not in data:
        raise ValueError("Invalid label config: 'labels' key missing")

    return data["labels"]
