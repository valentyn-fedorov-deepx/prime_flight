# RampVision documentation — start here

This folder describes the RampVision system and the teams that build it.

**New in the team?** Open the onboarding of your team: *1 Teams / <your team> / <team> onboarding*. It tells you what to
read, where things are and what to do in the first two weeks.

## What is where

| Folder or document | What it answers | Kept by |
|---|---|---|
| **Start here** (this page) | where to find what; the rules everyone follows | Lead |
| **1 Teams** / one folder per team | the team page (who is in the team, who owns which direction), the team's onboarding, the team's step-by-step guides | each team lead |
| **2 System / System overview** | what the system does, how it works, the state of every part; the words you will hear | Lead |
| **2 System / Architecture** | how the system runs: after the turnaround (today), in real time (being built), at the gate | MLOps |
| **2 System / Requirements** | the client's rule for every check: when it is Pass, Fail or Not observed | Lead with QA |
| **2 System / Shared parts** | the General Model (the shared detector), the tracker, the stage detector, the pose models: what they do, their state | CV |
| **2 System / Modules** | one page per check, by stage of the turnaround: logic, models, settings, accuracy, problems; the index of all checks | CV |
| **3 Research** / one folder per team | what we studied and measured: the question, what we did, what we found, what it means | each team |

## Where to find the answer

| Question | Open |
|---|---|
| I am new. Where do I start? | 1 Teams / your team / onboarding |
| Who owns something? Whom do I ask? | 1 Teams / the team page |
| How does the whole system work, and what state is it in? | 2 System / System overview |
| What does a word mean (turnaround, stage, belt loader, Not observed)? | 2 System / System overview, last section |
| What must a check detect, and when is it Pass, Fail or Not observed? | 2 System / Requirements / Client rules |
| How does a check decide, how accurate is it, what is wrong with it? | 2 System / Modules / the stage / the page of the check |
| All checks at a glance: accuracy, version, owner | 2 System / Modules / Modules index |
| What does the General Model detect, which version runs? | 2 System / Shared parts / General Model |
| How are aircraft, belt loaders, service vehicles and people followed? | 2 System / Shared parts / Tracker |
| How does a video get from the gate to a result today? | 2 System / Architecture / Post-processing |
| How does the real-time branch work? | 2 System / Architecture / Real-time |
| What runs at the gate, and how does the video get uploaded? | 2 System / Architecture / Edge |
| What did we measure about speed, cost, accuracy, real time? | 3 Research / the team |
| How do I run a check, prove a change, measure it? | 1 Teams / CV / How-to |
| What are we doing this month? | Jira and the Sprint Planning sheet (not kept in these folders) |

## Rules everyone follows

1. **The client's rules are the contract.** What Pass, Fail and Not observed mean for a check changes only with the
   client's agreement, through the lead.
2. **Measure, do not assume.** A change of a check's logic or model is measured on the monthly test, including the
   turnarounds labelled Fail. A speed-up that should not change the result is proven to give the same outputs.
3. **Production only through the agreed path:** a reviewed merge request, an image built by MLOps, a run on a few
   videos next to production first. Production buckets are read-only.
4. No model weights, videos or result files in git; videos stay inside the project's buckets and drives.
5. Code, commits and documents in English.
6. Change something documented — update its page in the same task.

## How we keep it current

- Every document starts with its owner and the date it was last reviewed.
- One fact lives in one place; other pages link to it instead of copying it.
- **Monthly review, about 30 minutes per person, first week of the month.** Each owner reads the *Status* block at the
  top of their pages — accuracy, version in production, the biggest open problem — corrects it and sets the date. The
  accuracy numbers are filled from the monthly test report automatically.
- Research reports are dated and are not rewritten later: a new study gets a new report.

## Not here yet

Planning and the decisions log, the data catalogue and test sets, the infrastructure and backend pages, the research of
the other teams. The full October 2026 package is kept next to this one as an archive.
