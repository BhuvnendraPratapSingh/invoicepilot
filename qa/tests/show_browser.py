import json
with open("qa/browser_results.json") as f:
    d = json.load(f)
print("Summary:", d["summary"])
for r in d["results"]:
    icon = "P" if r["status"]=="PASS" else "F" if r["status"]=="FAIL" else "B"
    det = ""
    if r.get("detail") and r["status"] != "PASS":
        det = " - " + r["detail"][:80]
    print("  " + icon + " " + r["test_id"] + ": " + r["name"] + det)
