"""Terminal interface. Run from the repository: python -m buddy --help."""

import argparse
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from .agent import new_request, open_buddy, session_config
from .practice import PracticeModel, SAMPLE_NOTICE
from .provider import ROOT, doctor, live_model
from .storage import StorageUnavailable, Store


def show_result(state):
    result = state.get("result", {})
    if result:
        print(result.get("message", ""))
        if "verified_record" in result:
            print("Verified using a new database connection:")
            print(json.dumps(result["verified_record"], indent=2, ensure_ascii=False))
    else:
        for message in reversed(state.get("messages", [])):
            if message.content and (message.type == "ai" or (state.get("finished") and message.type == "tool")):
                print(message.content)
                break
        if state.get("outcome") == "working" and state.get("retrieval_status") == "empty":
            print("The lookup returned no matching saved records.")
    if state.get("errors"):
        print("Tool errors:", "; ".join(state["errors"]))
    if state.get("evidence_records"):
        print("Retrieved source evidence:")
        for record in state["evidence_records"]:
            print(f"[note:{record['note_id']}]")
            print(json.dumps(record, indent=2, ensure_ascii=False))


def interact(graph, config):
    while True:
        snapshot = graph.get_state(config)
        pending = [item for task in snapshot.tasks for item in task.interrupts]
        if not pending:
            if snapshot.next:
                graph.invoke(None, config)
                continue
            show_result(snapshot.values)
            return 1 if snapshot.values.get("outcome") == "error" else 0
        payload = pending[0].value
        if payload["kind"] == "clarification":
            print(payload["question"])
            answer = input("Reply (or quit/reject): ").strip()
            decision = {"action": "reply", "text": answer}
            if answer.casefold() == "reject":
                decision = {"action": "reject"}
            elif not answer:
                continue
        else:
            print("Proposed content (nothing here is confirmed yet):")
            for task in payload["proposal"]["tasks"]:
                print(f"- {task['title']}: due {task['due_date']}")
            print("Full proposal, including original source text and human replies:")
            print(json.dumps(payload["proposal"], indent=2, ensure_ascii=False))
            print("Proposal fingerprint:", payload["digest"])
            answer = input("Review [approve/edit/reject/quit]: ").strip().casefold()
            if answer not in {"approve", "edit", "reject", "quit"}:
                print("Enter approve, edit, reject, or quit.")
                continue
            decision = {"action": answer, "digest": payload["digest"]}
            if answer == "edit":
                prompt = ("Practice correction (consent due date, YYYY-MM-DD): "
                          if snapshot.values.get("mode") == "practice" else "Correction (use full dates): ")
                decision["text"] = input(prompt).strip()
                if not decision["text"]:
                    continue
                print("Correction received:", decision["text"])
                print("Preparing a new proposal for review; nothing has been approved or saved.")
        if answer.casefold() == "quit":
            print("Paused. Use the displayed session ID with --resume to continue later.")
            return 0
        graph.invoke(Command(resume=decision), config)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Working Mom's Buddy — text notice milestone")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Capture a notice or ask about saved information")
    run.add_argument("--text", help="Notice or question; otherwise enter it at the prompt")
    run.add_argument("--practice", action="store_true", help="Offline, fixed fictional notice; no LLM call")
    run.add_argument("--resume", metavar="SESSION_ID")
    run.add_argument("--data-dir", type=Path)
    check = commands.add_parser("doctor", help="Check configuration without printing secrets")
    check.add_argument("--list-models", action="store_true")
    check.add_argument("--probe", action="store_true", help="Make a small live inference/tool-call request")
    show = commands.add_parser("show", help="Read a confirmed note directly, without a model")
    show.add_argument("note_id")
    show.add_argument("--data-dir", type=Path, default=ROOT / "data" / "live")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor(list_models=args.list_models, probe=args.probe)
        if args.command == "show":
            record = Store(args.data_dir / "family.sqlite3").get_note(args.note_id)
            print(json.dumps(record, indent=2, ensure_ascii=False) if record else "No saved note found for that ID.")
            return 0 if record else 1
        if (args.resume and args.text) or (args.practice and args.text):
            parser.error("Use --text, --practice, or --resume; to resume practice use --practice --resume ID.")
        mode = "practice" if args.practice else "live"
        data_dir = args.data_dir or ROOT / "data" / mode
        model = PracticeModel() if args.practice else live_model()
        thread_id = args.resume or str(uuid4())
        config = session_config(thread_id)
        print("Session ID:", thread_id)
        print("Data folder:", data_dir.resolve())
        if args.practice:
            print("OFFLINE PRACTICE: a scripted stand-in, using real tools, checkpoints and storage.")
        with open_buddy(model, data_dir) as (graph, _):
            if args.resume:
                state = graph.get_state(config).values
                if not state:
                    raise ValueError("No session found. Check the session ID, mode and data folder.")
                if state.get("mode") != mode:
                    raise ValueError("Resume this session using the same practice/live mode.")
            else:
                text = SAMPLE_NOTICE if args.practice else args.text or input("Notice or question: ")
                if args.practice:
                    print(text)
                graph.invoke(new_request(text, mode), config)
            return interact(graph, config)
    except (EOFError, KeyboardInterrupt):
        print("\nPaused. Resume using the session ID printed above.")
        return 0
    except GraphRecursionError:
        print("Stopped at the step limit. Start a new request with clearer details; automatic retries are bounded.")
        return 1
    except (ValueError, StorageUnavailable, sqlite3.Error) as error:
        # SQLite errors may include local paths, but contain no API request/credential data.
        print("Could not complete the request:", str(error))
        return 1
    except Exception as error:
        print(f"Request stopped ({type(error).__name__}). Check provider access with 'python -m buddy doctor --probe'.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
