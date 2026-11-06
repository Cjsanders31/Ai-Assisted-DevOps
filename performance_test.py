import json
import statistics
import time
from pathlib import Path

from test_adapter import ask_chatbot

CASES = json.loads(Path("test_cases.json").read_text(encoding="utf-8"))
questions = [c["question"] for c in CASES[:10]]

latencies = []
failures = 0
for i, question in enumerate(questions, start=1):
    start = time.perf_counter()
    try:
        answer = ask_chatbot(question)
        ok = bool(str(answer).strip())
        if not ok:
            failures += 1
    except Exception as exc:
        failures += 1
        print(f"Q{i} ERROR: {exc}")
    elapsed = time.perf_counter() - start
    latencies.append(elapsed)
    print(f"Q{i}: {elapsed:.6f} seconds")

if latencies:
    print("\n--- Performance Summary ---")
    print(f"Requests: {len(latencies)}")
    print(f"Failures: {failures}")
    print(f"Minimum: {min(latencies):.6f}s")
    print(f"Average: {statistics.mean(latencies):.6f}s")
    print(f"Median:  {statistics.median(latencies):.6f}s")
    print(f"Maximum: {max(latencies):.6f}s")

    if len(latencies) > 1:
        warm_latencies = latencies[1:]
        print("\n--- Warm Query Summary (excluding first request/index build) ---")
        print(f"Requests: {len(warm_latencies)}")
        print(f"Minimum: {min(warm_latencies):.6f}s")
        print(f"Average: {statistics.mean(warm_latencies):.6f}s")
        print(f"Median:  {statistics.median(warm_latencies):.6f}s")
        print(f"Maximum: {max(warm_latencies):.6f}s")
