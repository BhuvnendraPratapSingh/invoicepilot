import httpx
B = "http://127.0.0.1:8000"
httpx.post(B+"/api/demo/reset", timeout=20)
with open("data/fixtures/happy_path_apex_invoice.pdf","rb") as f:
    r = httpx.post(B+"/api/upload", files={"file":("hp.pdf",f,"application/pdf")}, timeout=30).json()
print("PDF upload:", r.get("decision"), "error:", r.get("error","none"))
