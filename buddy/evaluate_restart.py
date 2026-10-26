"""Opt-in live missing-deadline and actual process-restart evaluation.

Run explicitly: python -m buddy.evaluate_restart
All four CLI processes use fixed fictional data. Reviewer input is simulated.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from .agent import open_buddy, session_config
from .evaluate_duplicates import CheckFailed, family_snapshot, require, verified_review
from .models import fingerprint, search_words
from .provider import ROOT, live_model, settings


NOTICE = ("Maya's class field trip is November 6, 2026. Bring packed lunch. "
          "Return the consent form; its due date is not provided.")
DEADLINE_REPLY = "The consent form is due 2026-11-03."


def run_cli(arguments, user_input):
    command = [sys.executable, "-X", "utf8", "-m", "buddy", *arguments]
    with subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
        try:
            output, _ = process.communicate(input=user_input, timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise CheckFailed("A restart-evaluation process exceeded its two-minute limit.") from None
        # SDK stderr is deliberately omitted; it can contain request details.
        return {"returncode": process.returncode, "stdout": output, "pid": process.pid}


def evaluate(data_dir: Path, *, runner=None) -> dict:
    data_dir = Path(data_dir).resolve()
    require(not data_dir.exists() or not any(data_dir.iterdir()), "Use a fresh empty evaluation folder.")
    run = runner or run_cli
    processes = []

    def phase(name, arguments, user_input):
        result = run(arguments, user_input)
        require(result["returncode"] == 0, f"The {name} process stopped with an error; inspect its saved session.")
        processes.append({"phase": name, "pid": result["pid"], "exit_code": result["returncode"]})
        print(f"Process {len(processes)} exited: {name}.", flush=True)
        return result["stdout"]

    folder_args = ["--data-dir", str(data_dir)]
    first_output = phase("capture and pause at clarification", ["run", "--text", NOTICE, *folder_args], "quit\n")
    match = re.search(r"Session ID: ([a-f0-9-]+)", first_output)
    require(match is not None, "The capture process did not display a session ID.")
    thread_id = match.group(1)
    config = session_config(thread_id)
    with open_buddy(live_model(), data_dir) as (graph, store):
        snapshot = graph.get_state(config)
        questions = [item.value for task in snapshot.tasks for item in task.interrupts]
        require(len(questions) == 1 and questions[0].get("kind") == "clarification",
                "Expected missing-deadline clarification instead of a guessed date.")
        question = questions[0]["question"]
        require(search_words(question) & {"consent", "form", "deadline"}, "The clarification did not concern the missing task deadline.")
        require(store.counts() == (0, 0) and snapshot.values.get("approved_digest") is None,
                "The clarification pause already contains confirmed records or approval.")

    resume_args = ["run", "--resume", thread_id, *folder_args]
    phase("resume clarification and pause at review", resume_args, DEADLINE_REPLY + "\nquit\n")
    with open_buddy(live_model(), data_dir) as (graph, store):
        review = verified_review(graph, config, store, (0, 0), notice=NOTICE,
                                 expected_clarifications=[DEADLINE_REPLY])
        reviewed_proposal = review["proposal"]
        reviewed_digest = review["digest"]

    phase("resume review and approve checked proposal", resume_args, "approve\n")
    saved = family_snapshot(data_dir / "family.sqlite3")
    require(len(saved["notes"]) == 1 and len(saved["tasks"]) == 2, "Expected one approved notice and two tasks after restart.")
    note_id, content, approved_digest, _ = saved["notes"][0]
    require(json.loads(content) == reviewed_proposal and fingerprint(reviewed_proposal) == approved_digest == reviewed_digest,
            "The saved content differs from the proposal checked before process restart.")
    require(sorted((row[2], row[3], row[4]) for row in saved["tasks"]) ==
            sorted((task["title"], task["due_date"], task["evidence"]) for task in reviewed_proposal["tasks"]),
            "The persisted task rows differ from the reviewed proposal.")

    read_output = phase("read approved record independently", ["show", note_id, *folder_args], "")
    record = json.loads(read_output)
    require(record["note_id"] == note_id and record["approved_digest"] == reviewed_digest and
            record["tasks"] == reviewed_proposal["tasks"], "Independent-process read-back did not match the approved record.")
    require(family_snapshot(data_dir / "family.sqlite3") == saved, "The independent read changed persisted rows.")
    require(len({process["pid"] for process in processes}) == 4, "Expected four distinct CLI processes.")
    report = {"provider": "Nebius Token Factory", "model": settings()["model"], "data_kind": "fictional",
        "reviewer": "simulated; proposal, clarification, dates and fingerprint checked before test approval",
        "data_folder": str(data_dir), "status": "PASS", "session_id": thread_id, "processes": processes,
        "scenarios": {
            "3": {"result": "PASS", "clarification_question": question, "reply": DEADLINE_REPLY,
                  "counts_at_clarification": [0, 0], "counts_at_review": [0, 0],
                  "consent_due_date": "2026-11-03", "lunch_due_date": "2026-11-06",
                  "confirmed_counts": [1, 2], "note_id": note_id},
            "10": {"result": "PASS", "paused_at_clarification": True, "paused_at_review": True,
                   "distinct_cli_processes": 4, "same_session_resumed": True, "note_id": note_id,
                   "approved_digest": approved_digest, "approved_content_matches": True,
                   "independent_process_read_verified": True, "confirmed_counts": [1, 2]}}}
    print("Scenarios 3 and 10: PASS — clarified missing deadline, resumed both pauses, verified approved save across processes.", flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Live missing-deadline and process-restart evaluation with fictional data")
    parser.add_argument("--data-dir", type=Path, help="A fresh empty evaluation folder")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or ROOT / "data" / f"live-restart-{uuid4().hex[:12]}"
    print("LIVE EVALUATION: four CLI processes, fixed fictional notice, simulated clarification and review.", flush=True)
    print("Evaluation folder:", data_dir.resolve(), flush=True)
    try:
        report = evaluate(data_dir)
    except CheckFailed as error:
        print("Evaluation failed:", str(error))
        return 1
    except Exception as error:
        print(f"Evaluation stopped ({type(error).__name__}). Inspect the saved session or provider access.")
        return 1
    destination = data_dir / "restart-evaluation.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Results:", destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
