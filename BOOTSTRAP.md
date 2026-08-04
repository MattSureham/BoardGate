Bootstrap Multi-Agent Collaboration Protocol
This repository will be collaboratively developed by multiple independent participants, including AI models (e.g. Codex, Claude Code, Kimi, GPT), subprocesses, and human developers.
From this point forward, this repository should follow a persistent multi-agent collaboration protocol.
Your task is to initialize that protocol.

Objective
Create (or migrate) a repository-level collaboration system centered around a single file:
HANDOFF.md

This file becomes the canonical collaboration state shared by every participant.
The goal is to make it possible for any future participant to take over the project with minimal ambiguity, without relying on previous chat history.

Core Protocol
At the top of HANDOFF.md, write a protocol section that every participant must follow.
The protocol should explicitly state the following principles:

Every participant must read HANDOFF.md before starting work.
Every participant updates only its own structured state.
Preserve prior evidence and previous participants' records.
Never silently rewrite or delete another participant's findings.
Record disagreements as new evidence instead of overwriting history.
Clearly distinguish:

Confirmed
Inferred
Unknown


Repository evidence always takes precedence over assumptions or summaries.
Leave exactly one unambiguous Next Action before finishing.
The collaboration history should remain understandable even if participants change completely between turns.


HANDOFF.md Structure
Design HANDOFF.md using the following top-level structure.
HANDOFF.md

├── Current State
├── Active Issues
├── Next Action
├── Recent Activity
└── Archived Summary

The exact schema inside each section is up to you.
However, the schema must satisfy the following goals:
Current State
Represents the authoritative snapshot of the project.
It should answer questions such as:

What is currently implemented?
What is currently accepted as true?
What is unfinished?
What constraints currently exist?
What verification has actually been performed?

This section should describe the present state only.
Avoid historical narratives here.

Active Issues
Contains every unresolved issue discovered during collaboration.
Each issue should have:

stable identifier
status
severity
owner (if applicable)
evidence
current resolution state

Resolved issues may remain until archived.

Next Action
Contains exactly one clearly bounded next action.
It should be immediately actionable by the next participant.
Avoid vague goals.
Examples of good next actions:

Implement retry logic for MemoryStore.
Review commits abc123..def456.
Add regression tests for Issue R-014.

Examples of bad next actions:

Continue improving.
Clean things up.
Make the architecture better.


Recent Activity
Acts as the collaboration event log.
Every participant appends one structured entry describing:

role
task
context inspected
actions performed
files modified
findings
verification performed
issues created or updated
remaining uncertainty
recommended next action

Recent entries should remain detailed.
The newest entry should appear first.
Participants must never edit another participant's activity entry except to fix objectively incorrect references.

Archived Summary
Older Recent Activity entries may eventually become too large.
Design a mechanism that compresses older activity into concise summaries while preserving:

important architectural decisions
unresolved issues
rejected approaches
major reasoning
context necessary for future participants

No important evidence should disappear during archival.

Current State vs Recent Activity
Make this distinction explicit inside the document.
Current State:
Represents the current accepted project state.
Recent Activity:
Explains how the repository reached that state.
The Current State should be understandable without reading Recent Activity.
Recent Activity should provide the reasoning history behind Current State.

Evidence-first Collaboration
Design the document so that unsupported claims are discouraged.
Participants should always indicate whether statements are:

Confirmed
Inferred
Unknown

Verification should only be recorded if actually performed.
Do not allow participants to claim tests passed unless they actually executed them.

Repository Integration
If a suitable location exists, add a short section to the README pointing contributors to HANDOFF.md as the repository's collaboration protocol.
Do not otherwise modify project documentation unless necessary.

Migration
If an existing HANDOFF.md already exists:

preserve existing useful information
reorganize it into the new structure
do not discard historical information unnecessarily
preserve authorship where possible


Final Deliverable
When finished:

Show the proposed structure of HANDOFF.md.
Explain the reasoning behind the schema.
Describe how future participants should interact with it.
Summarize any assumptions made during migration.

Do not implement unrelated code changes.
Limit this task strictly to initializing the multi-agent collaboration protocol.


# Background Task State

Any long-running background task that cannot be continuously observed in the
foreground — for example CI watches, remote jobs, or asynchronous processes
that may outlive the current turn — must not represent its running state
solely through in-session memory. A background task must never be "started
then forgotten": it must carry a queryable lifecycle state on disk.

## Lifecycle marker

The participant must persist one machine-readable JSON marker per task at
`.boardgate/tasks/<task_id>.json` (gitignored, so it survives the session
without polluting the tree). The marker lifecycle is fixed:

- At start, record: `task_id`, `command`, `start_time`, and either `pid`
  for a local process or `remote_ref` for a remote task (for example
  `github-actions:<owner>/<repo>:<run_id>`), with `status: "running"`.
- While running, the state must be queryable: local tasks via their `pid`,
  remote tasks via their `remote_ref` (for example `gh run view`).
- At end, whether the task succeeded, failed, or was cancelled, record the
  terminal `status` (`"succeeded"`, `"failed"`, or `"cancelled"`),
  `exit_code` (or the remote equivalent conclusion), `end_time`, and
  `log_path` pointing at the captured output.

A marker whose task is still legitimately running when the participant
finishes its turn keeps `status: "running"` with the fields above, never an
informal note.

## Reconciliation on takeover

Before starting new work, a participant must reconcile every marker it finds:

1. Read each `.boardgate/tasks/*.json` marker with `status: "running"`.
2. Check liveness: the `pid` still exists for a local task, or the
   `remote_ref` still reports a non-terminal state for a remote task.
3. If the task is alive, leave the marker untouched.
4. If the task is dead but the marker still says `running`, the participant
   must not keep pretending it is alive: update the marker to
   `status: "orphaned"` (or the observed terminal state) with `end_time`,
   and record the reconciliation in HANDOFF.md when the outcome matters to
   the recorded project state (Current State, Active Issues, or Recent
   Activity).

Terminal markers may be deleted once their outcome has been reflected into
HANDOFF.md or is no longer relevant.

# Protocol Evolution

The collaboration protocol is allowed to evolve.

However, participants must not silently modify the protocol.

If a participant believes the protocol should change, it must:

1. Propose the change.
2. Explain the motivation.
3. Describe compatibility with existing history.
4. Record the proposal in HANDOFF.md.
5. Wait for explicit approval before adopting the new protocol.