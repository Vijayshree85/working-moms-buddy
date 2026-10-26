"""Offline safeguards for the opt-in live evaluator; no provider requests."""

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

from buddy.evaluate_duplicates import CheckFailed, evaluate, family_snapshot
from buddy.evaluate_failures import evaluate as evaluate_failures
from buddy.evaluate_restart import DEADLINE_REPLY, evaluate as evaluate_restart
from buddy.__main__ import main as cli_main
from buddy.practice import tool_call
from buddy.storage import Store
from test_workflow import DRAFT, ScriptedModel, proposal_calls


class CitingScriptedModel(ScriptedModel):
    """Use the real retrieved record ID when scripting the final grounded answer."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        message = result.generations[0].message
        if message.content == "CITE_RETRIEVED_SOURCE":
            tool_reply = next(item for item in reversed(messages) if item.type == "tool")
            note_id = json.loads(tool_reply.content)["records"][0]["note_id"]
            message.content = f"Consent is due November 3, 2026. [note:{note_id}]"
        return result


class EvaluationGuards(unittest.TestCase):
    @staticmethod
    def restart_runner():
        identifiers = count(100)
        def run(arguments, user_input):
            output = StringIO()
            with patch("builtins.input", side_effect=user_input.splitlines()), redirect_stdout(output):
                exit_code = cli_main(arguments)
            return {"returncode": exit_code, "stdout": output.getvalue(), "pid": next(identifiers)}
        return run

    def test_restart_evaluator_checks_both_pauses_and_exact_approved_save(self):
        draft = deepcopy(DRAFT)
        draft["tasks"][1]["evidence"] = DEADLINE_REPLY
        responses = [tool_call("ask_clarification", {"question": "When is the consent form due?"}), *proposal_calls(draft)]
        model = ScriptedModel(responses=responses)
        with TemporaryDirectory() as directory:
            with patch("buddy.__main__.live_model", return_value=model), \
                 patch("buddy.evaluate_restart.live_model", return_value=model), \
                 patch("buddy.evaluate_restart.settings", return_value={"model": "offline-test-model"}), \
                 redirect_stdout(StringIO()):
                report = evaluate_restart(Path(directory), runner=self.restart_runner())
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["scenarios"]["3"]["confirmed_counts"], [1, 2])
            self.assertTrue(report["scenarios"]["10"]["approved_content_matches"])
            self.assertEqual(len(report["processes"]), 4)

    def test_restart_evaluator_refuses_a_guessed_deadline_without_clarification(self):
        draft = deepcopy(DRAFT)
        draft["tasks"][1]["evidence"] = "Return the consent form; its due date is not provided."
        model = ScriptedModel(responses=proposal_calls(draft))
        with TemporaryDirectory() as directory:
            with patch("buddy.__main__.live_model", return_value=model), \
                 patch("buddy.evaluate_restart.live_model", return_value=model), \
                 self.assertRaisesRegex(CheckFailed, "missing-deadline clarification"), redirect_stdout(StringIO()):
                evaluate_restart(Path(directory), runner=self.restart_runner())
            self.assertEqual(Store(Path(directory) / "family.sqlite3").counts(), (0, 0))

    def test_restart_evaluator_does_not_approve_wrong_date_after_reply(self):
        draft = deepcopy(DRAFT)
        draft["tasks"][1].update(due_date="2026-11-04", evidence=DEADLINE_REPLY)
        responses = [tool_call("ask_clarification", {"question": "When is the consent form due?"}), *proposal_calls(draft)]
        model = ScriptedModel(responses=responses)
        with TemporaryDirectory() as directory:
            with patch("buddy.__main__.live_model", return_value=model), \
                 patch("buddy.evaluate_restart.live_model", return_value=model), \
                 self.assertRaisesRegex(CheckFailed, "consent task has an unexpected date"), redirect_stdout(StringIO()):
                evaluate_restart(Path(directory), runner=self.restart_runner())
            self.assertEqual(Store(Path(directory) / "family.sqlite3").counts(), (0, 0))

    def test_failure_evaluator_verifies_actual_retry_and_failed_write_rows(self):
        responses = [*proposal_calls(), tool_call("lookup_existing_tasks", {"query": "Maya consent form"}),
                     AIMessage(content="CITE_RETRIEVED_SOURCE"), *proposal_calls()]
        with TemporaryDirectory() as directory:
            with patch("buddy.evaluate_failures.live_model", return_value=CitingScriptedModel(responses=responses)), \
                 patch("buddy.evaluate_failures.settings", return_value={"model": "offline-test-model"}), \
                 redirect_stdout(StringIO()):
                report = evaluate_failures(Path(directory))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["scenarios"]["8"]["connection_attempts"], ["injected failure", "connected"])
            self.assertTrue(report["scenarios"]["8"]["original_rows_unchanged"])
            self.assertEqual(report["scenarios"]["9"]["database_attempts"], 2)
            self.assertEqual(report["scenarios"]["9"]["confirmed_counts"], [0, 0])
            self.assertFalse(report["scenarios"]["9"]["verified_saved_record_returned"])

    def test_failure_evaluator_rejects_answer_without_exercising_database_fault(self):
        responses = [*proposal_calls(), AIMessage(content="Consent is due November 3, 2026.")]
        with TemporaryDirectory() as directory:
            with patch("buddy.evaluate_failures.live_model", return_value=ScriptedModel(responses=responses)), \
                 patch("buddy.evaluate_failures.settings", return_value={"model": "offline-test-model"}), \
                 self.assertRaisesRegex(CheckFailed, "did not execute and recover"):
                evaluate_failures(Path(directory))

    def test_two_reviewed_attempts_return_same_note_without_row_changes(self):
        with TemporaryDirectory() as directory:
            model = ScriptedModel(responses=[*proposal_calls(), *proposal_calls()])
            with patch("buddy.evaluate_duplicates.live_model", return_value=model), \
                 patch("buddy.evaluate_duplicates.settings", return_value={"model": "offline-test-model"}), \
                 redirect_stdout(StringIO()):
                report = evaluate(Path(directory))
            self.assertEqual(report["status"], "PASS")
            first, second = report["scenarios"]["1"], report["scenarios"]["6"]
            self.assertEqual(first["outcome"], "saved")
            self.assertEqual(second["outcome"], "duplicate")
            self.assertEqual(first["note_id"], second["note_id"])
            self.assertTrue(second["original_rows_and_ids_unchanged"])

    def test_incorrect_model_date_never_receives_simulated_approval(self):
        with TemporaryDirectory() as directory:
            incorrect = deepcopy(DRAFT)
            incorrect["tasks"][0]["due_date"] = "2026-11-07"
            model = ScriptedModel(responses=proposal_calls(incorrect))
            with patch("buddy.evaluate_duplicates.live_model", return_value=model), \
                 patch("buddy.evaluate_duplicates.settings", return_value={"model": "offline-test-model"}), \
                 self.assertRaisesRegex(CheckFailed, "lunch task has an unexpected date"):
                evaluate(Path(directory))
            self.assertEqual(Store(Path(directory) / "family.sqlite3").counts(), (0, 0))

    def test_existing_evaluation_data_is_preserved_and_not_reused(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            model = ScriptedModel(responses=[*proposal_calls(), *proposal_calls()])
            with patch("buddy.evaluate_duplicates.live_model", return_value=model), \
                 patch("buddy.evaluate_duplicates.settings", return_value={"model": "offline-test-model"}), \
                 redirect_stdout(StringIO()):
                evaluate(folder)
            before = family_snapshot(folder / "family.sqlite3")
            with patch("buddy.evaluate_duplicates.live_model", return_value=ScriptedModel()), \
                 patch("buddy.evaluate_duplicates.settings", return_value={"model": "offline-test-model"}), \
                 self.assertRaisesRegex(CheckFailed, "new empty evaluation folder"):
                evaluate(folder)
            self.assertEqual(family_snapshot(folder / "family.sqlite3"), before)


if __name__ == "__main__":
    unittest.main()
