"""Validated data contracts, similar to C# DTOs with validation attributes."""

from datetime import date
import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def prepare_text(text: str) -> str:
    """Prepare text before giving it to the model; preserve its wording as evidence."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip().lstrip("\ufeff").strip()
    if not text or len(text) > 8000:
        raise ValueError("Enter between 1 and 8,000 characters.")
    if any(not char.isprintable() and char not in "\n\t" for char in text):
        raise ValueError("Remove control characters from the text.")
    return text


class TaskDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = Field(description="Full YYYY-MM-DD date, or null if unknown.")
    evidence: str = Field(min_length=1, max_length=1000, description="Exact quote from user text.")


class NoticeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    event_date: date | None = Field(description="Full YYYY-MM-DD event date, or null if unknown.")
    tasks: list[TaskDraft] = Field(min_length=1, max_length=10)

    @field_validator("tasks")
    @classmethod
    def distinct_tasks(cls, tasks: list[TaskDraft]) -> list[TaskDraft]:
        keys = [(normalize(task.title), task.due_date) for task in tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("The proposal contains duplicate tasks.")
        return tasks


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def search_words(text: str) -> set[str]:
    """Match whole words regardless of order, punctuation or a name's possessive ending."""
    text = normalize(text).replace("’", "'")
    text = re.sub(r"(?<=\w)'s\b", "", text)
    return set(re.findall(r"[^\W_]+", text))


def search_terms(query: str) -> set[str]:
    # Keep names, actions and date values; omit the wording used to ask about them.
    question_words = {"a", "an", "the", "is", "are", "was", "were", "when", "what", "which",
                      "where", "how", "do", "does", "did", "can", "could", "please", "tell", "me",
                      "for", "on", "in", "at", "to", "of", "and", "about", "by", "due", "date", "deadline"}
    return search_words(query) - question_words


def canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(value: dict) -> str:
    """Bind approval to every field, including source text and clarification history."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_proposal(draft: NoticeDraft, source: str, clarifications: list[str]) -> tuple[dict, list[str]]:
    sources = [source, *clarifications]
    missing = []
    if draft.event_date is None:
        missing.append("What is the full event date, including the year?")
    for task in draft.tasks:
        if task.due_date is None:
            missing.append(f"What is the full due date for '{task.title}'?")
        if not any(task.evidence in text for text in sources):
            raise ValueError("Each task needs an exact evidence quote from the notice or your replies.")
    # Do not silently assume this year when a notice says only 'November 6'.
    years = set(re.findall(r"\b\d{4}\b", "\n".join(sources)))
    dates = [draft.event_date, *(task.due_date for task in draft.tasks)]
    if any(value is not None and str(value.year) not in years for value in dates):
        missing.append("Please confirm the year for the proposed dates.")
    proposal = {**draft.model_dump(mode="json"), "source_text": source, "clarifications": clarifications}
    return proposal, missing
