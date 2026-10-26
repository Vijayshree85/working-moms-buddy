# Working Mom's Buddy — Week 3 project documentation

Prepared October 25, 2026. Copy this content into the required Google Doc, review
it, and add the final links. This file is the local source draft.

Repository: https://github.com/Vijayshree85/working-moms-buddy

Google Doc link: [add after creating the document]

Demo video link: [add after reviewing/uploading the generated video and checking access]

A 4-minute-28-second narrated video is available locally as
`artifacts/working-moms-buddy-demo.mp4`. It is an edited walkthrough of actual
live CLI output, with labeled scripted fictional inputs and synthetic narration.

Application code, setup instructions and evaluation evidence are in the linked
GitHub repository. Generated video and local data are shared separately.

## Overview and use case

Working Mom's Buddy helps a busy working parent turn a school notice into
reviewed tasks and retrieve the details later. It is the text-notice first
version of the broader MomLife idea. The interface is a local terminal app.

For example, a notice says the field trip is November 6, packed lunch is needed,
and the consent form must be returned by November 3. The assistant identifies
the tasks, asks for a missing year or deadline, shows a proposal, and saves only
after approval. The parent can correct or reject the proposal. Later questions
are answered using the saved notice and human clarification as evidence.

One-line goal: help a working parent capture, clarify, review, approve and recall
school-notice tasks through one assistant, with persistent records and a human
controlling every confirmed save.

## Chosen scope and architecture

I chose bring-your-own-use-case and the Python code track, using one LangChain
agent running on LangGraph. Multiple tools and graph nodes belong to that one
agent. The first version focuses on text notices and tasks.

| Component | Purpose |
| --- | --- |
| Python 3.14.5 | Application and evaluation runtime, verified with the installed dependencies |
| LangChain | Model messages, agent loop and model-visible tools |
| LangGraph | Request state, persistent checkpoints and human-review interrupts |
| Nebius Token Factory | Live model calls; selected Qwen/Qwen3-30B-A3B-Instruct-2507 provisionally |
| Pydantic | Validated notice/task data contracts |
| SQLite | Local transactional storage and persistent workflow checkpoints |
| Terminal interface | Text input, clarification, review decisions and source-backed answers |

Dependency versions are pinned in requirements.txt and requirements.lock.txt.
No separate database service is required.

The agent can choose these five tools:

1. `search_saved_notes`: read saved notes and source evidence.
2. `lookup_existing_tasks`: read existing tasks and due dates.
3. `ask_clarification`: pause for missing information from the user.
4. `propose_notice`: validate and stage a complete proposal.
5. `review_and_save`: pause for the user's decision and save exact approved content.

The LLM chooses retrieval and clarification actions. Application code controls
validation, the approval boundary, retries, transactions and duplicate saves.
The design demonstrates decisions and tool use across multiple steps.

## Input preparation, state and persistence

Text is checked for empty/oversized input, normalized line endings and unwanted
control characters before the model uses it. Search queries are prepared to
handle possessive names, word order and question words such as “when” and “due.”
Search matches descriptive words across saved human-readable fields.

The request state includes the original request, human replies, missing details,
proposed tasks, proposal fingerprint, approval fingerprint, retrieval evidence,
errors and outcome. The same session ID lets a paused request resume later.

Two SQLite files have different purposes:

- `sessions.sqlite3` stores conversation state, unconfirmed drafts and pending
  clarification/review pauses.
- `family.sqlite3` stores approved notes/tasks. Its note record includes the
  complete approved content and fingerprint, and task records link to the note.

Original notice text is preserved alongside clarification/correction history.
Answers expose the relevant note ID and source text. A correction can override
an old date while retaining the original notice for traceability.

## Human handoff and write protection

LangGraph pauses for missing information and again for review. The parent can
approve, edit or reject. Editing invalidates the previous proposal and approval.

A SHA-256 fingerprint covers the complete proposal, including source, replies,
dates and task evidence. Approval must match the displayed fingerprint. The
write uses that staged content directly, with no intervening model call.
The model cannot provide the trusted runtime state or human approval as tool
arguments. This prototype uses the local terminal as its trusted reviewer.

Confirmed note/task inserts occur in one SQLite transaction. A unique notice
key and task comparison let an identical repeat return the existing note without
extra rows. Read-back through another connection verifies persistence.

“Zero unapproved writes” in the evaluation means zero unapproved confirmed
family records; workflow drafts are intentionally checkpointed before approval.

## Datasets and examples

All initial examples and evaluation inputs are fictional. No external training
dataset, embeddings or fine-tuning were used.

Main example:

> Maya's class field trip is November 6. Bring packed lunch.
> Return the consent form by November 3.

Variants cover a missing year, missing consent deadline, a corrected deadline
of November 4, approval/rejection, duplicate capture, storage errors and restart
recovery. An empty-store query asks about fictional Noah's swimming lesson.

The course handout was read for requirements. It is not an app input dataset.
PDF/image uploads, voice, calendar integration, meals and broader family-planning
features are outside this first version. Credentials are local environment
settings, excluded from Git and never used as notice content.

## How AI coding tools were used

I worked with Codex as a coding partner and Python/agentic-AI trainer. It
inspected the repository, explained components before implementing them,
created the code/tests, checked dependency compatibility, ran the workflows,
and maintained project notes and an iteration log. I entered the credential
locally, tried the app, reviewed proposals and supplied actual approvals.

Representative prompts from the work:

- “Create a git ignore file” with `.venv/`, `.env` and `__pycache__/`.
- “Continue my existing project as my coding partner and beginner-friendly trainer.”
- “Explain what each component does and why we need it before implementing it.”
- “One school notice through clarification, review, approval, and a verified persistent save.”
- “Can I see how the mom life app works?”

My bug reports included a consent date still appearing as November 3 after a
correction. The coding partner inspected persisted tool calls and reproduced
the failure before changing the implementation. Full prompts, changes and
observations are retained in docs/ai-coding-log.md.

## Iterations and learning

1. **Repository/environment:** inspection found the Git root nested below the
   workspace. The first .gitignore was outside the clone, so an effective one
   was added inside it. Python 3.14 compatibility was checked through package
   resolution, installation, imports and actual execution, with a version lock.
2. **Completion control:** an initial attempt to terminate through a dynamic END
   command still allowed the built-in agent's normal model edge. A before-model
   completion guard now ends saved/rejected/error flows without another call.
3. **Live search failure:** the real model searched for words that were not an
   exact phrase in the saved notice. Whole-word matching and question-word
   preparation fixed retrieval, with regressions using the actual failed queries.
4. **Correction evidence failure:** the model changed a date but invented a new
   quote. Validation blocked it. Human replies now have their own message role,
   corrections take priority, and failed validation supplies exact available
   source text so the model can repair its quote without weakening validation.
5. **Reliable evaluation:** tests check complete workflows and database rows.
   Live evaluators validate proposals before simulated review, compare original
   rows/IDs for duplicates, inject SQLite faults and launch independent processes.

My main learning is that a useful agent needs explicit state, reliable tool
contracts, bounded error handling and a clear human write boundary. Prompting
alone did not solve the search or correction failures. Scripted-model tests and
real-model checks exposed different issues and both were needed.

## Evaluation and measured results

Initial target: at least 8/10 successful scenarios and zero unapproved confirmed
record writes. Final defined-case outcomes: **10/10 live cases pass after the
documented fixes**. The offline suite passes **29/29 tests**.

| Live scenario | Final outcome |
| --- | --- |
| Complete dates, review and approved persistent save | PASS |
| Missing year and subsequent approved save | PASS |
| Missing consent deadline and clarification | PASS |
| Corrected deadline with fresh review/approval | PASS after evidence-handling fix |
| Rejection, including misleading automatic-approval text | PASS; zero confirmed records |
| Repeated notice in another session | PASS; original IDs/rows unchanged |
| Empty retrieval | PASS; no invented date or source |
| Temporary database failure | PASS; one retry, grounded answer, existing rows unchanged |
| Persistent approved-write failure | PASS; two attempts, honest error, no partial records |
| Clarification/review pauses across process exits | PASS; four processes, exact approved content persisted |

Live calls used the configured Nebius model. Automated evaluator reviewer
decisions and database faults are simulated and explicitly labeled in results.
The original capture/correction and the user's demo also used actual terminal
interaction. Earlier failures remain recorded. The 10/10 figure is the final
pass status of these defined cases across iterations, not a claim that every
attempt succeeded or a repeated statistical production-reliability measurement.
Zero unapproved confirmed writes were observed in the checked paths.

Evidence: docs/test-scenarios.md and the live retrieval, duplicate, failure and
restart JSON reports. Corrected recall also returned November 4 with its exact
correction quote despite the original notice mentioning November 3.

## Current limits and future extensions

- The prototype runs locally in a terminal. Browser/mobile UI and hosted
  authentication are future work.
- Every captured task currently requires a full date. Unknown information pauses
  for clarification, with bounded rounds and graph steps.
- Keyword search does not guarantee synonyms or paraphrase matching.
- Duplicate detection covers the same normalized source/event and matching task
  titles/dates. Arbitrary semantic duplicates are outside the current guarantee.
- Corrections apply to unconfirmed proposals. Editing already-saved tasks is
  outside the first version.
- Voice, images/PDF inputs, calendars and broader MomLife planning come later.

## Final delivery checklist

- Create/share the Google Doc using this reviewed content.
- Review and upload the generated demo of five minutes or less, including its
  actual app workflow and AI coding tool usage; add the share link.
- Verify the GitHub code link and viewing access.
- Add the document, recording and repository links to the course submission form.
