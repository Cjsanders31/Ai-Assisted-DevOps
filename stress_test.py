import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from test_adapter import ask_chatbot, get_rag

CASES = json.loads(Path("test_cases.json").read_text(encoding="utf-8"))
QUESTIONS = [c["question"] for c in CASES]


def one_request(question):
    start = time.perf_counter()
    try:
        answer = ask_chatbot(question)
        answer = str(answer)
        return bool(answer.strip()), time.perf_counter() - start, answer[:80]
    except Exception as exc:
        return False, time.perf_counter() - start, repr(exc)


def run_level(workers):
    questions = (QUESTIONS * ((workers // max(1, len(QUESTIONS))) + 1))[:workers]
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one_request, q) for q in questions]
        for f in as_completed(futures):
            results.append(f.result())
    total = time.perf_counter() - started
    latencies = [latency for _, latency, _ in results]
    failures = sum(1 for ok, _, _ in results if not ok)
    print(f"\nConcurrency={workers}; requests={len(results)}; "
          f"failed={failures}; wall_time={total:.6f}s")
    print(f"  min={min(latencies):.6f}s; "
          f"average={statistics.mean(latencies):.6f}s; "
          f"median={statistics.median(latencies):.6f}s; "
          f"max={max(latencies):.6f}s")
    for ok, lat, msg in results:
        if not ok:
            print(f"  FAILURE after {lat:.2f}s: {msg}")


# Keep one-time PDF ingestion/indexing out of the per-query latency measurements.
index_started = time.perf_counter()
get_rag()
print(f"Index build (measured separately): {time.perf_counter() - index_started:.6f}s")

for level in [1, 3, 5]:
    run_level(level)
