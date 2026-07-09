# verify.py
import json
from pathlib import Path

# Check weights exist
weights = Path.home() / ".tars" / "needle.pkl"
assert weights.exists() and weights.stat().st_size > 40_000_000, "Weights missing or too small"
print(f"Weights OK: {weights.stat().st_size / 1e6:.1f}MB")

# Check tool schema is valid JSON string
from classifier import TOOLS
parsed = json.loads(TOOLS)
assert isinstance(parsed, list), "TOOLS must be a JSON array"
assert len(parsed) == 2, "Must have exactly 2 tools"
assert parsed[0]["name"] == "fire_trigger"
assert parsed[1]["name"] == "no_match"
for tool in parsed:
    props = tool["parameters"]["properties"]
    for prop_name, prop in props.items():
        assert isinstance(prop["type"], str), f"type must be string, got {type(prop['type'])}"
print("Schema OK")
print("All checks passed - ready to run main.py")
