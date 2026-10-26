# Project notes — Working Mom's Buddy

## Goal and scope

Help a busy working parent capture a text school notice, resolve missing details,
review proposed tasks, approve a persistent save, and retrieve the source later.
Target: finish at least 8 of 10 end-to-end scenarios, with zero unapproved
confirmed-record writes. This is a target for the live assistant, not a result
established by scripted-model tests.

First milestone: one dated school notice, one agent, five tools, terminal UI,
SQLite. The model chooses read tools, clarification, and proposal staging.
Application code validates drafts and controls approval and writes.

## What existed before this build — inspected October 25, 2026

- The workspace path ended in `working-moms-buddy`, but the Git clone was in a
  child folder also named `working-moms-buddy`.
- The inner repository tracked only README.md. Its user-written edits were
  already present; the implementation preserved them and expanded setup.
- The parent `.gitignore` had `.venv/`, `.env`, and `__pycache__/`. Because the
  Git root was the child folder, an effective `.gitignore` was added there too.
- The parent `.venv` ran CPython 3.14.5 and contained only pip 26.1.1 initially.
  The shell's `python` and `py` aliases were inaccessible to the sandbox; the
  `.venv\Scripts\python.exe` executable worked.
- Parent `docs` contained the Week 3 handout and the broader MomLife product PDF.
  No application source or installed application dependencies existed.
- No repository `.env` or process-level Nebius key/model was found. Checks
  printed only whether those settings existed.
- Git required a command-scoped `safe.directory` setting for inspection because
  the sandbox user differed from the repository owner. No global Git setting,
  commit, push, relocation, or GitHub write was made.

## Course handout reviewed

Local source: `../../docs/Week 3 Project Handout (Oct 2026).pdf` from this file's
folder. All 11 pages were extracted and read with pypdf; no linked solution
projects were opened. The PDF remains in its original parent docs folder.

- Page 1: agent decisions, tools, state, recovery and human handoff matter;
  a single model call or retrieval lookup is insufficient.
- Pages 7–8: use-case one-liner and framework; measure completed workflows,
  define memory and approval boundaries.
- Page 9: code track uses LangChain/LangGraph; checkpointers and interrupts
  support state and human review. Nebius is an available provider.
- Page 10: Google Doc with overview, datasets, AI coding prompts, iterations and
  learnings; live demo of at most five minutes including AI coding tool usage;
  GitHub code link. Failure handling is part of completion.
- Page 1 dates: Builder of the Week consideration October 25, 2026; final
  certification deadline November 11, 2026. These are transcribed from the local
  handout, not independently verified course announcements.

## Decisions and rationale

| Decision | Reason |
| --- | --- |
| Keep current folder layout | Avoid relocating the user's clone or virtual environment; document the real Git root |
| Terminal interface | A small surface for learning and demonstrating the complete text workflow |
| LangChain `create_agent` on LangGraph | One agent with a real tool loop and durable human-review interrupts |
| SQLite for this milestone | Built into Python, local persistence and transactions without a server |
| Separate checkpoint and family DBs | Unconfirmed drafts can resume without appearing as confirmed tasks |
| Full proposal SHA-256 fingerprint | Approval is tied to source, clarification history, title, event date and every task field |
| Immutable original text plus reply history | Preserve evidence, including corrections, instead of rewriting the notice |
| Transaction and unique notice key | A retry cannot leave half a notice or insert the same source/event twice |
| Strict message deserialization | Checkpoints reconstruct only the message classes used by this app |
| Offline practice mode | Test control flow without credentials; keep model-quality claims separate |
| Nebius adapter, no default model | Verify the account catalog and a real tool call before selecting a model |

The database and provider choices are provisional for the first milestone.
No multi-agent architecture, MCP, Mem0, vector store, or knowledge graph was added.

## Learning map for a C# engineer

- A Python module is a `.py` file; `python -m buddy` runs `buddy/__main__.py`.
- Pydantic models are validated data contracts, comparable to DTOs plus runtime
  validation. `date | None` means a date may be unknown.
- A LangChain `@tool` turns a function signature and docstring into a model-visible
  tool schema. `ToolRuntime` injects trusted application state; the model cannot
  provide it as a tool argument.
- `BuddyState` is the request state bag. A tool returns `Command(update=...)` to
  persist changes. Messages accumulate as the model and tools exchange results.
- `interrupt(...)` pauses the graph and persists a question/review payload.
  Resuming uses `Command(resume=...)` with the same thread/session ID.
- An interrupted tool restarts when resumed. Keep side effects after the
  approval interrupt and make the save idempotent in case execution is replayed.
- A SHA-256 fingerprint is a content consistency check, not user authentication.
  The trusted human-input boundary here is the local terminal. A hosted service
  would need real authentication and ownership controls.
- A SQLite transaction commits all note/task inserts together or rolls them back.
  A separate connection reads the saved record to verify persistence.

## Current validation and remaining work

Python 3.14 compatibility was checked with current package metadata, a successful
pip resolution/install, `pip check`, imports, provider/tool binding, and real
workflow execution. This supports the exact locked environment; it is not a
claim about every Python 3.14 package combination.

The ten scripted-model workflow scenarios passed, with additional focused
approval, evidence, input, transaction and retry guards. A terminal practice run
saved a fictional notice and two tasks; another process read the same note ID.
See test-scenarios.md for measured results and live evaluation status.

Subsequently on October 25, 2026, the user added a Nebius key locally. An
authenticated model-list request returned 30 models. Selected
`Qwen/Qwen3-30B-A3B-Instruct-2507` provisionally and passed a real inference/tool-call
probe. The first live notice asked for its missing year, received fictional year
2026, and proposed lunch for November 6 and consent return for November 3.
The run paused at review; a separate checkpoint read confirmed the pending
review and zero confirmed notes/tasks. No approval was supplied.

The user subsequently approved that proposal in their terminal. A separate
process verified note `1a03e73d-4499-4598-9048-53ec1c5ffdad`, counts of 1 note/2
tasks, and a stored fingerprint matching the complete saved content. The first
live capture → clarification → review → approval → persistent-save workflow is
complete, validating the missing-year scenario.

The fresh-conversation retrieval check initially failed: the model searched for
`Maya consent form`, but lookup required an exact substring. After word matching
was introduced, the next model query also included `due`, which was absent from
the original notice. Added deterministic query preparation to remove common
question words, possessive-name handling, and whole-word matching across saved
fields. Search excludes internal JSON keys and hashes. Task lookup prefers
matches in the task's own text over matches only in notice context. Added
regressions for the real queries, wrong names, possessives and internal metadata.

The final live retrieval passed: November 3, 2026, the original consent quote,
the saved note citation and the year clarification were shown. Confirmed counts
stayed 1 note/2 tasks, and the stored approval still matched the original content.
A separate empty-store question about fictional Noah's swimming lesson reported
no matching information and created zero confirmed records. Automated tests now
pass 20/20. See live-retrieval-check.json for the recorded session evidence.

The live correction exercise exposed another failure: the model changed the
date to November 4 but rewrote the old evidence quote with the new date. Exact
quote validation rejected it, and the model unnecessarily asked for text it
already had. Human replies are now appended as actual HumanMessage entries,
with tool replies still completing the protocol. Invalid proposals return the
available original text and human replies so the model can repair its quote.
The prompt explicitly gives latest corrections priority while preserving source
text. Terminal review now summarizes task dates and acknowledges submitted edits.

All 21 automated tests pass, including a new invented-quote recovery regression.
Recovered the live draft to consent due 2026-11-04 with the exact correction as
evidence, lunch still due 2026-11-06, and a new fingerprint. The user approved it
in session `9c99556c-04d9-422e-8dff-c2437c69b67b`. Independently verified corrected
note `5b07c0bf-b3ef-4fba-b9b6-8844393b03c6`, one note/two tasks, a matching approved
fingerprint and the actual task-table rows. Scenario 4 now passes after the fix.
The earlier saved November 3 notice is unchanged in its separate test folder.

The live rejection scenario also passed in a separate empty database. Even with
misleading notice text claiming immediate approval, the model paused for review.
The test rejected the proposal; persisted state had no approval and confirmed
counts stayed zero.

Added an opt-in, single-purpose live evaluation command for full-date capture
and duplicate prevention. It uses fixed fictional input, a fresh isolated folder,
the real model and tools, and simulated review decisions supplied only after
checking source, dates, evidence, fingerprint and preapproval counts. A live run
saved one note/two tasks; the second request in a new session returned the same
note ID with outcome duplicate. Exact row comparisons verified no changes to
notes, tasks, IDs, timestamp or the original approved content. Results are in
live-duplicate-check.json. No storage-schema or ordinary workflow change was
needed. Three offline safeguards cover the evaluator, bringing tests to 24/24.

Added an opt-in live tool-failure evaluator using deterministic SQLite
connection errors and the real store retry logic. A temporary read failure
recovered on the second connection; the live model returned the correct date
and saved-source citation, with all existing rows unchanged. A persistent
approved-write failure in a separate empty database stopped after two attempts,
reported an unverified save, and left zero notes/tasks. Faults and reviewer
decisions are simulated; model calls, tool execution, graph state and database
transactions are real. Results are in live-failure-check.json.

Two new offline evaluator safeguards check the complete injected-fault flow and
refuse a passing answer that never exercised the database fault. All 26 tests
pass. No production workflow, retry-policy or dependency change was needed.

The final evaluator combined missing-deadline clarification and real process
restarts. Four separate CLI processes captured and paused, resumed with the
deadline and paused at review, resumed for checked simulated approval, then
read the record independently. It preserved the same session, source, human
reply, proposal fingerprint and actual task values. Counts were zero at both
pauses, then one note/two tasks after approval. Scenarios 3 and 10 pass; see
live-restart-check.json. Three evaluator safeguards bring the offline suite to
29/29, including refusal of guessed deadlines and wrong post-clarification dates.

All ten named live scenarios now have passing final outcomes across documented
iterations. Reviewer input is simulated in automated evaluators; the earlier
capture/correction used actual user terminal approval. Database faults are
deliberately injected. Earlier failed retrieval/correction attempts remain in
the log. The result is 10/10 defined-case outcomes after fixes, rather than a
first-attempt or repeated production reliability rate. Zero unapproved confirmed
writes were observed in the checked paths. Credits/billing balance is unmeasured.

The user's `data/demo` independently shows one saved note/two tasks and a found
source during recall. Supplemental live recall of the corrected record answered
November 4, quoted the actual correction and cited its saved note, despite the
original source still mentioning November 3.

The next stage is submission packaging. submission-draft.md is copy-ready source
for the required Google Doc; demo-guide.md provides a rehearsal/recording plan
under five minutes and the remaining GitHub/submission steps. A narrated video
has since been generated locally; video-artifact.md records its provenance.
The external Doc and video review/upload remain pending. Code and documentation
are maintained at the GitHub repository linked below.

## Deliverables to complete later

- Copy submission-draft.md into the Google Doc and add its share link.
- Review the generated 4:28 MP4 using video-artifact.md, upload it, and add the
  share link. demo-guide.md also supports a personal screen recording.
- Verify access to the code at
  https://github.com/Vijayshree85/working-moms-buddy.
- Submit the three links using the course form. The coding agent created a local
  narrated video; no external Doc, media upload or course submission has been
  performed. GitHub publication is authorized separately by the user's request.

## Technical references checked October 25, 2026

- [LangChain create_agent](https://docs.langchain.com/oss/python/langchain/agents)
- [LangGraph interrupts and resuming](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [SQLite checkpoint package and serialization guidance](https://pypi.org/project/langgraph-checkpoint-sqlite/)
- [LangChain provider adapter Python compatibility](https://pypi.org/project/langchain-openai/)
- [Nebius tool calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling)
- [Nebius API setup](https://docs.tokenfactory.nebius.com/quickstart)
- [Nebius account model list](https://docs.tokenfactory.nebius.com/api-reference/examples/list-of-models)
