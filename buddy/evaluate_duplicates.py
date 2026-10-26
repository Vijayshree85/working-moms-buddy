"""Opt-in live evaluation with fictional data and simulated review decisions.

Run explicitly: python -m buddy.evaluate_duplicates
This is never run by the offline test suite or the ordinary notice interface.
"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from langgraph.types import Command

from .agent import new_request, open_buddy, session_config
from .models import fingerprint, search_words
from .provider import ROOT, live_model, settings


NOTICE = ("Maya's class field trip is November 6, 2026. Bring packed lunch. "
          "Return the consent form by November 3, 2026.")


class CheckFailed(Exception):
    """An evaluator assertion with a safe, human-readable message."""


def require(condition, message):
    if not condition:
        raise CheckFailed(message)


def family_snapshot(path: Path) -> dict:
    """Read actual persisted rows independently of the graph's returned result."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        notes = connection.execute("SELECT id, content_json, approved_digest, saved_at FROM notes ORDER BY id").fetchall()
        tasks = connection.execute("SELECT id, note_id, title, due_date, evidence FROM tasks ORDER BY id").fetchall()
    return {"notes": notes, "tasks": tasks}


def verified_review(graph, config, store, expected_counts, *, notice=NOTICE, expected_clarifications=None):
    snapshot = graph.get_state(config)
    pending = [item.value for task in snapshot.tasks for item in task.interrupts]
    require(len(pending) == 1 and pending[0].get("kind") == "review", "Expected a complete proposal at human review.")
    payload = pending[0]
    proposal = payload["proposal"]
    require(store.counts() == expected_counts, "Confirmed record counts changed before test approval.")
    require(snapshot.values.get("approved_digest") is None, "A fresh request already carries approval.")
    require(fingerprint(proposal) == payload["digest"], "Review fingerprint does not match the displayed proposal.")
    require(proposal["source_text"] == notice and proposal["event_date"] == "2026-11-06",
            "The proposal changed the source notice or event date.")
    if expected_clarifications is not None:
        require(proposal["clarifications"] == expected_clarifications, "Expected human clarification history is missing or changed.")
    require(len(proposal["tasks"]) == 2, "Expected exactly the lunch and consent tasks.")
    expected = {"lunch": "2026-11-06", "consent": "2026-11-03"}
    for word, due_date in expected.items():
        tasks = [task for task in proposal["tasks"] if word in search_words(task["title"] + " " + task["evidence"])]
        require(len(tasks) == 1 and tasks[0]["due_date"] == due_date, f"The {word} task has an unexpected date.")
        require(any(tasks[0]["evidence"] in text for text in [notice, *proposal["clarifications"]]),
                f"The {word} task has an unsupported evidence quote.")
    return payload


def evaluate(data_dir: Path) -> dict:
    report = {"provider": "Nebius Token Factory", "model": settings()["model"],
              "data_kind": "fictional", "reviewer": "simulated, after checking the complete proposal",
              "data_folder": str(data_dir.resolve()), "scenarios": {}, "status": "running"}
    with open_buddy(live_model(), data_dir) as (graph, store):
        require(store.counts() == (0, 0), "Use a new empty evaluation folder; existing records are never deleted.")
        for attempt in (1, 2):
            config = session_config(f"duplicate-check-{attempt}-{uuid4()}")
            before = family_snapshot(store.path)
            # Extra surrounding whitespace in the second request should not create a different notice.
            text = NOTICE if attempt == 1 else "  " + NOTICE + "\n"
            graph.invoke(new_request(text), config)
            payload = verified_review(graph, config, store, (0, 0) if attempt == 1 else (1, 2))
            state = graph.invoke(Command(resume={"action": "approve", "digest": payload["digest"]}), config)
            expected_outcome = "saved" if attempt == 1 else "duplicate"
            require(state["outcome"] == expected_outcome,
                    f"Attempt {attempt} returned {state['outcome']!r}; expected {expected_outcome!r}.")
            require(store.counts() == (1, 2), "Expected one saved note and two tasks after approval.")
            after = family_snapshot(store.path)
            if attempt == 1:
                note_id, content, approved_digest, _ = after["notes"][0]
                require(fingerprint(json.loads(content)) == approved_digest == payload["digest"],
                        "Persisted content does not match the first approved proposal.")
                require(sorted((task[2], task[3], task[4]) for task in after["tasks"]) ==
                        sorted((task["title"], task["due_date"], task["evidence"]) for task in payload["proposal"]["tasks"]),
                        "Actual task rows do not match the approved proposal.")
            else:
                require(after == before, "The duplicate attempt changed stored note/task rows or IDs.")
                require(state["result"]["note_id"] == report["scenarios"]["1"]["note_id"],
                        "The duplicate attempt returned a different note ID.")
            scenario = "1" if attempt == 1 else "6"
            report["scenarios"][scenario] = {"result": "PASS", "session_id": config["configurable"]["thread_id"],
                "outcome": state["outcome"], "note_id": state["result"]["note_id"],
                "review_digest": payload["digest"], "counts_before_approval": [len(before["notes"]), len(before["tasks"])],
                "counts_after_approval": [len(after["notes"]), len(after["tasks"])],
                "no_preapproval_record_changes": True}
            if attempt == 2:
                report["scenarios"][scenario]["original_rows_and_ids_unchanged"] = True
            print(f"Scenario {scenario}: PASS ({state['outcome']}); confirmed counts: 1 note, 2 tasks.", flush=True)
    report["status"] = "PASS"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Live full-date and duplicate-save evaluation; fictional data only")
    parser.add_argument("--data-dir", type=Path, help="An empty evaluation folder; default creates a fresh folder under data/")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or ROOT / "data" / f"live-duplicate-{uuid4().hex[:12]}"
    print("LIVE EVALUATION: real model/tools, fictional notice, simulated reviewer decisions.", flush=True)
    print("Evaluation folder:", data_dir.resolve(), flush=True)
    try:
        report = evaluate(data_dir)
    except CheckFailed as error:
        print("Evaluation failed:", str(error))
        return 1
    except Exception as error:
        # Provider exceptions can contain request details; never print their bodies or credentials.
        print(f"Evaluation stopped ({type(error).__name__}). Check provider access or the saved session.")
        return 1
    destination = data_dir / "duplicate-evaluation.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Results:", destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
