# How the handbook is written

The handbook is the team documentation of RampVision for people, not for code reviewers: a new engineer, a project
manager, the client's safety team. Everything here is turned into Word documents in the shared folder.

## Plain and detailed

- **Plain language.** Short sentences, active voice, everyday words. Explain what happens at the gate, then what the
  software does about it. Someone who has never seen the code must understand every sentence.
- **Detailed.** Plain does not mean short. Give the real numbers ("the aircraft must have stood still for 5 seconds in
  total"), every step of the logic, every known problem and what it means for the verdict. Leave nothing out that the
  technical sources say; translate it.
- **No identifiers in the text.** No task numbers (PF-…), no module codes (M01, M27, HP), no commit hashes, no file names
  with line numbers, no configuration keys, no class ids, no internal labels (X1–X4, E0·I1, BL@door, T_arr). They go only
  into the last section, *For developers*.
- **No abbreviations.** Write the words: "General Model" (never GM), "belt loader" (never BL), "service vehicle" (for GSE:
  ground support equipment — tugs, belt loaders, fuel trucks, tractors; say so the first time), "aircraft" (never A/C),
  "foreign object debris" (FOD), "air conditioning unit", "frames per second". Model names (HRNet, RTMPose, YOLO,
  EfficientNet) appear only in *For developers*; in the text say what the model does: "a pose model — it finds a
  person's joints: shoulders, elbows, wrists, knees".
- **Words that need a short explanation the first time on a page:** frame (one picture of the video; the cameras take 8
  per second), track (the same object followed from frame to frame), detection (a box the detector draws around an
  object), stage (a part of the turnaround), verdict (Pass, Fail or Not observed).
- **Time in seconds and minutes, not frames.** Convert: 8 frames = 1 second, 40 frames = 5 seconds, 480 frames = 60
  seconds. Keep the frame number only in *For developers* if needed.
- **No invented facts.** Use only what the sources say. If something is not known, write "not known yet" or "to
  confirm" and say who could confirm it. Never guess a number.
- **English.** Words like Pass, Fail, Not observed are written with capital letters.
- **No links to repository files in the text** (the readers do not have the workspace). Say "see the page *General
  Model*" for other handbook pages.

## The words we use

| Say | Not |
|---|---|
| the General Model (the shared detector) | GM, the detector model |
| the tracker | trackers job, DeepSORT |
| the module (the code of one check); the check (what the client asked for) | task, M-number |
| turnaround | event, turn |
| the cone camera (looks towards the aircraft nose), the wing camera (looks along the wing) | cone / wing cam |
| service vehicle | GSE |
| belt loader | BL, beltloader |
| the stage detector (the part that knows where in the turnaround we are) | stage machine |
| the monthly test (the client's validated turnarounds we measure on) | CI report, test set |
| post-processing (after the turnaround), real time (while it happens) | batch, streaming |
| the view is blocked (by a vehicle or an object in front of the camera) | obstacle logic, obstruction |

## Page types

### A check (module) page

```
# <plain title from docs/handbook/_data/modules.json>

> Two or three sentences: what the check makes sure of at the gate, and how the software sees it.

## Status
| | |
|---|---|
| How accurate it is | <X of Y turnarounds correct (P %) on the monthly test> |
| Fail turnarounds it caught | <a of b> (say "no turnaround in the monthly test was labelled Fail" if b = 0) |
| In production | <plain: "the version of <month year>"> |
| Who looks after it | to assign |
| Biggest open problem | <one sentence> |

## What the client wants
The client's name of the check in italics, then the rule in plain words — when the verdict is Pass, Fail, Not observed,
and Not observed because the view is blocked — as a table with the column "Verdict" first. Keep every condition the client
wrote; explain unclear ones.

## When and where it looks
Which part of the turnaround (the stage bar picture is added automatically), from what moment to what moment, which
camera(s), for aircraft and for jets.

## What it looks at
- From the General Model: which objects (in words: people, cones, chocks, the aircraft nose, …).
- From the tracker: which tracked objects and what it uses from them (moving or stopped, arrival moment, …).
- From the video itself: whether it reads the pictures and why.
- Its own models: what each one recognises, in plain words.

## How it decides, step by step
A numbered list that follows the code in order, with every number converted to seconds or minutes. Each step: what it
looks for, the exact condition, what happens next.

## Settings that change the result
A table: setting (plain name) · value (with unit) · what it changes.

## What it reports
The verdict, the sentence the client sees (an example), the timeline entry, any files.

## How accurate it is
The monthly test numbers and what they mean: how many turnarounds were labelled, how many Fail ones there were, what the
module got wrong where we know it. If there are almost no Fail labels, say that the accuracy number cannot show whether
it catches violations.

## Known problems
Every problem from the code review and the technical page, each as: what the code does · what the client's rule says ·
what it means for the verdict. Mark the ones still to confirm.

## In real time
Can it run while the turnaround happens, what it needs for that (the video, the stage detector, a change of when it
decides), and how much computing it costs if known.

## For developers
Repository, production branch and commit, entry point, how to run it on one turnaround, the configuration keys of the
settings above, the code places of the steps above, the module code (M-number) used in our workspace.
```

### A shared part page (General Model, tracker, stage detector, pose models)

`# Title` · one-paragraph summary · **Status** table (in production, last change, next step, who looks after it) · What
it does (plain) · What it finds (classes or outputs, explained) · How it works step by step · How fast it is and what it
costs · How good it is · Which checks depend on it · Known problems · What changes next · For developers.

### A research report

`# <Plain question as a title>` · *Date, who, status (done / in progress)* · **In short** (3–5 sentences with the main
numbers) · The question · What we did · What we found (tables with the numbers) · What it means for the team or the
client · What is next · For developers (scripts, files, branches, task numbers).

### A how-to guide

`# How to <do something>` · who it is for · what you need before (access, tools) · numbered steps with the exact commands
in code blocks · how to see that it worked · common problems.

## Before you finish a page

- Read it as a new team member: is any word unexplained? Is any number without a unit?
- Search the text above *For developers* for: M0, M1, M2, PF-, GM, BL, GSE, A/C, FOD, ROI, CLAHE, ndjson, `.py`, `@`,
  commit hashes. Rewrite what you find.
