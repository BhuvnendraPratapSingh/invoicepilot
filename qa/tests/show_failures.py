import json
with open("qa/results.json") as f:
    data = json.load(f)
for r in data["results"]:
    if r["status"] == "FAIL":
        print("TEST:", r["test_id"], "-", r["name"])
        print("  Expected:", r["expected"])
        print("  Actual:  ", r["actual"])
        print("  Detail:  ", r["detail"])
        print()
