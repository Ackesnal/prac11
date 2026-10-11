"""Run five live teaching cases. Metrics are diagnostics, not factual correctness scores."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import time

from client import request


def diagnose(case, response):
    required = set(case["required_ids"])
    retrieved = {p["id"] for p in response.get("retrieved", [])}
    cited = {p["id"] for p in response.get("sources", [])}
    return {
        "case": case["id"], "status": response.get("status", "transport_failure"),
        "status_expected": response.get("status") in case["expected_statuses"],
        "retrieval_recall": len(required & retrieved) / len(required) if required else "N/A",
        "all_required_retrieved": required <= retrieved if required else "N/A",
        "required_sources_cited": required <= cited if required else "N/A",
        "keyword_check": all(k.casefold() in response.get("answer", "").casefold()
                             for k in case["keywords"]) if case["keywords"] else "N/A",
        "generation_calls": response.get("model_calls", 0),
        "embedding_calls": response.get("embedding_calls", 0),
        "app_seconds": response.get("elapsed_s", "N/A"),
        "manual_claim_support": "TO REVIEW", "manual_notes": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["agent", "rag", "plain", "retrieve"], default="agent")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=.25)
    parser.add_argument("--cases", default="evaluation_cases.json")
    parser.add_argument("--out", default="results/agent-k3")
    args = parser.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    target = Path(args.out)
    target.mkdir(parents=True, exist_ok=False)  # Preserve previous experiments.
    rows, records, elapsed = [], [], []
    for case in cases:
        started = time.perf_counter()
        try:
            response = request({"question": case["question"], "mode": args.mode,
                                "top_k": args.top_k, "min_score": args.min_score})
        except Exception as exc:
            response = {"status":"transport_failure", "error_type":type(exc).__name__}
        client_seconds = round(time.perf_counter() - started, 3)
        row = diagnose(case, response)
        row["client_seconds"] = client_seconds
        rows.append(row)
        elapsed.append(client_seconds)
        records.append({"case":case, "response":response, "client_seconds":client_seconds})
        print(f"{case['id']}: {row['status']}; retrieval recall={row['retrieval_recall']}")
    (target / "responses.json").write_text(json.dumps({"configuration":vars(args), "records":records},
        indent=2, ensure_ascii=False), encoding="utf-8")
    with (target / "observations.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    eligible = [r["retrieval_recall"] for r in rows if isinstance(r["retrieval_recall"], (int,float))]
    summary = {"cases":len(rows), "mean_retrieval_recall":statistics.mean(eligible) if eligible else None,
        "median_client_seconds":statistics.median(elapsed),
        "generation_call_attempts":sum(r["generation_calls"] for r in rows),
        "query_embedding_attempts":sum(r["embedding_calls"] for r in rows),
        "note":"Five teaching cases, not a benchmark. Status/keyword/ID checks do not prove factual support. Review every claim."}
    (target / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if any(r["status"] in {"upstream_failure","transport_failure","not_ready","bad_request"} for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
