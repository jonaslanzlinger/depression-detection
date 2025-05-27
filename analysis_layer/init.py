import json
from pathlib import Path

with open("analysis_layer/mapping/config.json", "r") as f:
    mapping_config = json.load(f)

for indicator, details in mapping_config.items():
    for feature, props in details["metrics"].items():
        weight = props["weight"]
        direction = props["direction"]
        print(f"{indicator} <- {feature} (weight: {weight}, direction: {direction})")
