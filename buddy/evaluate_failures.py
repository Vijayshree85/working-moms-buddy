"""Opt-in live-model evaluation with deterministic SQLite fault injection.

Run explicitly: python -m buddy.evaluate_failures
Reviewer replies are simulated on fixed fictional data in a fresh test folder.
"""

import argparse
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from uuid import uuid4

from langgraph.types import Command

from .agent import new_request, open_buddy, session_config
from .evaluate_duplicates import CheckFailed, NOTICE, family_snapshot, require, verified_review
from .provider import ROOT, live_model, settings


def evaluate(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    require(not data_dir.exists() or not any(data_dir.iterdir()),
            "Use a fresh empty evaluation folder; existing data is never removed.")
    report = {"provider": "Nebius Token Factory", "model": settings()["model"],
              "data_kind": "fictional", "data_folder": str(data_dir.resolve()),
              "faults": "injected sqlite3.OperationalError exceptions; real store retry handling",
              "reviewer": "simulated, after checking complete proposals", "scenarios": {}}

    # Scenario 8: seed one approved fictional notice, then fail the first read connection.
    with open_buddy(live_model(), data_dir / "temporary-read") as (graph, store):
        config = session_config(f"failure-seed-{uuid4()}")
        graph.invoke(new_request(NOTICE), config)
        review = verified_review(graph, config, store, (0, 0))
        saved = graph.invoke(Command(resume={"action": "approve", "digest": review["digest"]}), config)
        require(saved["outcome"] == "saved", "Could not seed the fictional notice.")
        note_id = saved["result"]["note_id"]
        before = family_snapshot(store.path)
        connect = store._connect
        attempts = []

        def temporary_failure():
            if not attempts:
                attempts.append("injected failure")
                raise sqlite3.OperationalError("simulated temporary database connection failure")
            attempts.append("connected")
            return connect()

        query_config = session_config(f"temporary-read-{uuid4()}")
        with patch.object(store, "_connect", side_effect=temporary_failure):
            state = graph.invoke(new_request("When is Maya's consent form due? Check the saved information."), query_config)
        require(attempts[:2] == ["injected failure", "connected"],
                "The agent did not execute and recover from the injected lookup failure.")
        require(state["retrieval_status"] == "found" and not state["errors"],
                "The database retry did not produce a successful lookup.")
        calls = [call for message in state["messages"] for call in getattr(message, "tool_calls", [])]
        require(calls and all(call["name"] in {"search_saved_notes", "lookup_existing_tasks"} for call in calls),
                "Expected only retrieval tools for the saved-information question.")
        answer = next((message.content for message in reversed(state["messages"])
                       if message.type == "ai" and message.content and not message.tool_calls), "")
        normalized = " ".join(answer.casefold().split())
        require(any(value in normalized for value in ("november 3, 2026", "november 3rd, 2026",
                                                       "3 november 2026", "2026-11-03")),
                "The recovered answer did not state the expected consent deadline.")
        require(f"[note:{note_id}]" in answer and any(record["note_id"] == note_id for record in state["evidence_records"]),
                "The recovered answer did not cite its retrieved source.")
        require(family_snapshot(store.path) == before, "The lookup changed confirmed family records.")
        report["scenarios"]["8"] = {"result": "PASS", "session_id": query_config["configurable"]["thread_id"],
            "note_id": note_id, "injected_failures": 1, "connection_attempts": attempts,
            "retrieval_status": state["retrieval_status"], "answer": answer,
            "source_citation_verified": True, "original_rows_unchanged": True, "confirmed_counts": [1, 2]}
        print("Scenario 8: PASS — first connection failed, retry succeeded, answer cited the saved notice.", flush=True)

    # Scenario 9: keep storage unavailable throughout an approved write in a different empty database.
    with open_buddy(live_model(), data_dir / "permanent-write") as (graph, store):
        config = session_config(f"permanent-write-{uuid4()}")
        graph.invoke(new_request(NOTICE), config)
        review = verified_review(graph, config, store, (0, 0))
        with patch.object(store, "_connect", side_effect=sqlite3.OperationalError("simulated persistent storage failure")) as connect:
            state = graph.invoke(Command(resume={"action": "approve", "digest": review["digest"]}), config)
        require(connect.call_count == 2, "The failed write did not stop after exactly two database attempts.")
        require(state["outcome"] == "error" and state["finished"] and state["errors"],
                "The failed write did not terminate with a reported error.")
        require(state["approved_digest"] == review["digest"], "The write was not tied to the simulated approval.")
        require("verified_record" not in state["result"], "The failed write incorrectly returned a verified saved record.")
        actual = family_snapshot(store.path)
        require(actual == {"notes": [], "tasks": []}, "The failed write left partial confirmed records.")
        report["scenarios"]["9"] = {"result": "PASS", "session_id": config["configurable"]["thread_id"],
            "injected_failures": connect.call_count, "database_attempts": connect.call_count,
            "outcome": state["outcome"], "errors": state["errors"], "message": state["result"]["message"],
            "approved_digest": state["approved_digest"], "verified_saved_record_returned": False,
            "confirmed_counts": [0, 0], "partial_records": False}
        print("Scenario 9: PASS — stopped after two attempts; save reported unverified; zero confirmed records.", flush=True)

    report["status"] = "PASS"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Live SQLite retry/failure evaluation with fictional data and simulated review")
    parser.add_argument("--data-dir", type=Path, help="A fresh empty evaluation folder")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or ROOT / "data" / f"live-failures-{uuid4().hex[:12]}"
    print("LIVE EVALUATION: real model/tools, injected database faults, simulated test reviewer.", flush=True)
    print("Evaluation folder:", data_dir.resolve(), flush=True)
    try:
        report = evaluate(data_dir)
    except CheckFailed as error:
        print("Evaluation failed:", str(error))
        return 1
    except Exception as error:
        print(f"Evaluation stopped ({type(error).__name__}). Check provider access or the saved session.")
        return 1
    destination = data_dir / "failure-evaluation.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Results:", destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
