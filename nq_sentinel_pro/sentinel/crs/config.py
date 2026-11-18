"""Load the versioned CRS rule set from crs_v1.json."""
import json
import hashlib
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("crs_v1.json")
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
CONFIG_SHA256 = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
MODULE_WEIGHTS = CONFIG["module_weights_pct"]
MIN_TOTAL_COVERAGE = float(CONFIG["min_total_coverage_pct"])
MIN_PERCENTILE_HISTORY = int(CONFIG["percentile_min_observations"])
PERCENTILE_WINDOW = int(CONFIG["percentile_window_observations"])
THRESHOLD_WEIGHT = float(CONFIG["threshold_percentile_weight"])
PERCENTILE_WEIGHT = float(CONFIG["history_percentile_weight"])
CRITICAL_MODULES = tuple(CONFIG["critical_modules"])
RULES = {
    key: (value["module"], value["group"], value["polarity"],
          [(float(level), float(score)) for level, score in value["levels"]])
    for key, value in CONFIG["thresholds"].items()
}
GROUPS = {m: sorted({r[1] for r in RULES.values() if r[0] == m}) for m in MODULE_WEIGHTS}
if round(sum(MODULE_WEIGHTS.values())) != 100:
    raise ValueError("CRS module weights must total 100")
if abs(THRESHOLD_WEIGHT + PERCENTILE_WEIGHT - 1.0) > 1e-12:
    raise ValueError("CRS score blend weights must total 1.0")
