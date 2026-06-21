import warnings; warnings.filterwarnings("ignore")
import requests, json, time, sys

# Fix encoding for Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"
passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    symbol = "PASS" if condition else "FAIL"
    print(f"  [{symbol}] {name} {detail}")
    if condition:
        passed += 1
    else:
        failed += 1

print("=" * 50)
print("PHASE 1 + PHASE 2 TEST SUITE")
print("=" * 50)

# Use existing case instead of re-uploading
print("\n--- Using existing case ---")
r = requests.get(f"{BASE}/upload/cases")
cases = r.json()["cases"]
ready_cases = [c for c in cases if c["status"] == "ready"]
if not ready_cases:
    print("No ready cases. Uploading new one...")
    with open("data/sample_ufdr/sample_case_001.json", "rb") as f:
        r = requests.post(f"{BASE}/upload/case", files={"file": f})
    case_id = r.json()["case_id"]
    print(f"  Uploaded: {case_id[:8]}...")
    for _ in range(20):
        r = requests.get(f"{BASE}/upload/case/{case_id}/status")
        if r.json()["status"] == "ready":
            break
        time.sleep(1)
else:
    case_id = ready_cases[0]["case_id"]
    print(f"  Using case: {case_id[:8]}... ({ready_cases[0]['case_name']})")

test("Case is ready", requests.get(f"{BASE}/upload/case/{case_id}/status").json()["status"] == "ready")

print("\n--- PHASE 1: SQL Keyword Search ---")
r = requests.get(f"{BASE}/query/{case_id}/summary")
s = r.json()["summary"]
test("Summary API (HTTP 200)", r.status_code == 200)
test("100 chats stored", s["chats"]["total"] == 100, f"got {s['chats']['total']}")
test("50 calls stored", s["calls"]["total"] == 50, f"got {s['calls']['total']}")
test("9 contacts stored", s["contacts"]["total"] == 9, f"got {s['contacts']['total']}")
test("30 media stored", s["media"]["total"] == 30, f"got {s['media']['total']}")
test("Flagged messages detected", s["chats"]["flagged"] > 0, f"got {s['chats']['flagged']}")
test("Foreign calls detected", s["calls"]["foreign"] > 0, f"got {s['calls']['foreign']}")

r = requests.get(f"{BASE}/query/{case_id}/chats/crypto")
test("Crypto chats found", r.json()["total_found"] > 0, f"got {r.json()['total_found']}")

r = requests.get(f"{BASE}/query/{case_id}/calls/foreign")
test("Foreign calls found", r.json()["total_found"] > 0, f"got {r.json()['total_found']}")

r = requests.get(f"{BASE}/query/{case_id}/chats/search?q=bitcoin")
test("Keyword search: bitcoin", r.json()["total_found"] > 0)

r = requests.get(f"{BASE}/query/{case_id}/chats/search?q=hawala")
test("Keyword search: hawala", r.json()["total_found"] > 0)

print("\n--- PHASE 2: Semantic Vector Search ---")

# Reindex to make sure ChromaDB is populated
print("  Running reindex...")
requests.post(f"{BASE}/search/{case_id}/reindex")
time.sleep(2)

r = requests.get(f"{BASE}/search/{case_id}/index-status")
idx = r.json()
test("Index status API works", r.status_code == 200)
test("ChromaDB has records", idx["chromadb_indexed"] > 0, f"got {idx['chromadb_indexed']}")
test("All 159 records indexed", idx["chromadb_indexed"] >= 159, f"got {idx['chromadb_indexed']}")
test("is_fully_indexed = true", idx["is_fully_indexed"] == True)

queries = [
    ("bitcoin wallet address BTC", "chat"),
    ("foreign international phone call", "call"),
    ("Dubai supplier foreign contact", "contact"),
    ("hawala money cash transfer", "chat"),
    ("delivery package secret meeting", "chat"),
]
for query_text, rtype in queries:
    body = {"query": query_text, "record_type": rtype, "n_results": 5}
    r = requests.post(f"{BASE}/search/{case_id}/semantic",
                      json=body, headers={"Content-Type": "application/json"})
    found = r.json()["total_found"]
    score = r.json()["results"][0]["similarity_score"] if found > 0 else 0
    test(f'Semantic [{rtype}]: "{query_text[:25]}..."',
         found > 0, f"found={found} top_score={score:.3f}")

print("\n" + "=" * 50)
print(f"  RESULTS: {passed} PASSED  |  {failed} FAILED")
if failed == 0:
    print("  ALL TESTS PASSED - PHASE 1 + PHASE 2 COMPLETE!")
else:
    print("  Some tests failed. Check output above.")
print("=" * 50)
