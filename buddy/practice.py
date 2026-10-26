"""A narrow offline stand-in for the model, used only for the fictional practice notice.

This exercises the real tools, LangGraph interrupts, checkpoints and SQLite store.
It does not measure an LLM's extraction or reasoning ability.
"""

import json
import re
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


SAMPLE_NOTICE = ("Maya's class field trip is November 6. Bring packed lunch. "
                 "Return the consent form by November 3.")


def tool_call(name: str, arguments: dict | None = None) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": arguments or {},
                                              "id": str(uuid4()), "type": "tool_call"}])


class PracticeModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "offline-fictional-practice"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        last = next((message for message in reversed(messages) if isinstance(message, ToolMessage)), None)
        if last is None:
            response = tool_call("ask_clarification", {"question": "What year is this field trip?"})
        elif last.content == "Proposal staged. Call review_and_save to show it to the user.":
            response = tool_call("review_and_save")
        else:
            replies = []
            for message in messages:
                if isinstance(message, ToolMessage):
                    try:
                        data = json.loads(message.content)
                        replies.extend(data[key] for key in ("reply", "correction") if key in data)
                    except (ValueError, TypeError):
                        pass
            years = re.findall(r"\b(20\d{2})\b", " ".join(replies))
            if not years:
                response = tool_call("ask_clarification", {"question": "For this practice, enter a four-digit year, such as 2026."})
            else:
                year = years[-1]
                consent = f"{year}-11-03"
                # The practice model understands only a year and an optional ISO consent-date correction.
                for reply in replies:
                    dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", reply)
                    if dates:
                        consent = dates[-1]
                response = tool_call("propose_notice", {"draft": {
                    "title": "Maya's class field trip", "event_date": f"{year}-11-06", "tasks": [
                        {"title": "Bring packed lunch", "due_date": f"{year}-11-06", "evidence": "Bring packed lunch."},
                        {"title": "Return the consent form", "due_date": consent,
                         "evidence": "Return the consent form by November 3."}]}})
        return ChatResult(generations=[ChatGeneration(message=response)])
