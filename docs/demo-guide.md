# Demo and submission guide

## Generated video available

A narrated video has now been created locally:
`artifacts/working-moms-buddy-demo.mp4` — **4 minutes 28 seconds**, 1080p, with
captions. It presents actual live app output, scripted fictional demo inputs
and synthetic narration. See [video-artifact.md](video-artifact.md) for provenance
and companion files. Review it before uploading; the manual recording plan below
is also available for a personal screen recording.

## Manual recording plan

Aim for about 4 minutes 30 seconds, leaving a 30-second buffer under the course's
five-minute limit. Rehearse once; live model wording and latency can vary.

## Prepare off camera

Use the working virtual environment. From the current workspace, these are
**Windows Command Prompt commands**:

```bat
cd /d C:\codebase\GenAcademy\Week3\working-moms-buddy\working-moms-buddy
..\.venv\Scripts\activate.bat
```

Keep `.env` out of the recording. Open README.md, buddy/agent.py and the AI
coding log as needed. Use a new `data/recording-take-1` folder for the take;
choose `recording-take-2` for another attempt instead of resetting old data.

## Recording plan

| Time | Show and explain |
| --- | --- |
| 0:00–0:25 | State the working-parent use case and text-first scope |
| 0:25–0:55 | Show AI coding prompts/log and one concrete failure/fix |
| 0:55–1:15 | Explain one agent, tools, state and human review using agent.py/README |
| 1:15–3:00 | Run live capture, clarify the year, edit consent date, review and approve |
| 3:00–3:40 | Ask a fresh question and show the corrected date with source evidence |
| 3:40–4:10 | Show recorded duplicate/failure/restart results and measured scope |
| 4:10–4:30 | State learnings, limits and repository/document links |

Suggested opening: “Working Mom's Buddy turns school notices into reviewed
tasks. One agent decides when to retrieve or clarify, while application code
controls approval and persistent writes.”

For AI coding usage, show the actual instruction to explain components before
implementation and the iteration log. Explain the live search or correction
evidence failure and its regression test. Demonstrate the application live;
test-report screenshots alone do not replace the live workflow.

## Live capture

**Terminal command:**

```bat
python -m buddy run --data-dir data/recording-take-1
```

**Text to enter at the app's “Notice or question” prompt:**

```text
Maya's class field trip is November 6. Bring packed lunch. Return the consent form by November 3.
```

**App responses to enter:**

1. At the missing-year question: `2026`.
2. At review: `edit`.
3. At the correction prompt: `The consent form is due 2026-11-04.`
4. Read the new proposal: lunch November 6, consent November 4, exact correction
   evidence and original notice preserved. Explain that editing invalidates the
   old proposal fingerprint.
5. At fresh review, enter `approve` only after checking it.

Show the successful one-note/two-task save and separate-connection read-back.

## Recall in a new conversation

**Terminal command:**

```bat
python -m buddy run --text "When is Maya's consent form due?" --data-dir data/recording-take-1
```

Expected: November 4, 2026, with the correction quote and note citation. Explain
that the new conversation retrieves persisted information rather than relying
on the earlier terminal process's memory. The original source may still say
November 3; the saved correction establishes the current deadline.

## Results and conclusion

Show docs/test-scenarios.md and a compact portion of live-failure-check.json or
live-restart-check.json. Explain:

- 29 offline tests pass and all ten defined live cases have passing final outcomes
  after documented iterations.
- Live evaluators use the real model with simulated review and injected database
  faults where labeled. Actual user capture/correction approvals also passed.
- Repeated saves preserve original rows/IDs; failure retries are bounded; failed
  writes do not leave partial records.
- Zero unapproved confirmed writes were observed in checked paths. Draft state
  is intentionally checkpointed before approval.

Suggested learning: “The difficult parts were state, failure recovery and the
approval boundary. Real-model testing exposed search phrasing and evidence-quote
bugs that the first scripted tests missed.”

Keep the scope description accurate: this is a terminal school-notice assistant;
voice, browser/mobile screens and external calendars are later extensions.

## Publish and submit

The repository origin is https://github.com/Vijayshree85/working-moms-buddy and
the current branch is `main`. Application code and documentation are maintained
there. For subsequent changes, review them before publication.

**Terminal commands — review, stage, inspect, commit and push when ready:**

```bat
git status --short
git add .gitignore .env.example README.md requirements.txt requirements.lock.txt buddy tests docs
git diff --cached --stat
git diff --cached
git commit -m "Build text notice agent with approval and persistence"
git push origin main
```

These commands also serve as a reference for future updates. `.env`, virtual
environments, local databases and generated video artifacts are ignored.

1. Create the Google Doc from submission-draft.md and add its final share link.
2. Review/upload the generated video, or record a personal take, and check the
   final video is no longer than five minutes.
3. Open the GitHub link and confirm the new source and README are available.
4. Submit the document, video and code links using the form in the handout:
   https://forms.gle/waBYFkkf5xxmcouV9.

The supplied handout lists October 25, 2026 for Builder of the Week consideration
and November 11, 2026 as the final certification deadline. No form submission has
been made by the coding agent.
