# CV team

> The computer-vision team makes every check give the verdict the client's rule describes. We look after the shared
> detector (the General Model), the tracker, the stage detector, the code of every check, how fast and how cheap all of
> it runs, and moving the urgent checks to real time.

## Status

| | |
|---|---|
| Team lead | Valentyn Fedorov |
| People | Valentyn Fedorov, Yurii Luchko, Vladyslav Ivashchuk |
| Checks we look after | 30 checks of the client, in 27 modules (a module is the code of one or more checks) |
| Main work in October 2026 | the faster General Model went to production; a faster tracker with the same tracks (13 % less time in its first cluster run; the exact comparison is next); one shared pose model for the checks that read body poses; the first checks for the real-time branch; this documentation |

## What the team is responsible for

1. **Every check gives the right verdict.** For every check the client has a written rule: when the result is Pass,
   when it is Fail, when it is Not observed. The code of the check must follow that rule. When the code and the rule
   differ, we find it, measure it and either fix the code or bring the question to the client.
2. **The shared parts that all checks read.** The General Model finds the objects on every picture of the video. The
   tracker follows them from picture to picture. The stage detector (being built) tells where in the turnaround we are.
   If one of them changes, every check can change, so they get the strictest tests.
3. **Speed and cost.** All of this runs on rented graphics cards. Faster code means results sooner and a smaller bill.
4. **Real time.** The urgent checks have to decide while the turnaround happens, not a day later. We move them to the
   real-time branch one by one.
5. **The documentation of all of the above** — the pages of the checks, the shared parts and our research.

## People and directions

| Direction | Who | What it covers | Where it is written down |
|---|---|---|---|
| General Model | Yurii Luchko | the shared detector: its versions, its accuracy, new object types | *System / Shared parts / General Model* |
| Tracker | Yurii Luchko | following aircraft, belt loaders, service vehicles and people; when the aircraft arrived and left | *System / Shared parts / Tracker* |
| Stage detector | Yurii Luchko (to confirm) | the moments of the turnaround: the aircraft stopped, a belt loader reached a door or left, the pushback was attached, the aircraft started to leave | *System / Shared parts / Stage detector* |
| Checks in the real-time branch | Yurii Luchko | moving checks to real time and testing them there | *How-to / How a check is moved to real time* |
| Checks after the turnaround | one owner per check, to assign | the logic, accuracy and problems of each check | *System / Modules*, the *Modules index* |
| Pose models | Valentyn Fedorov | the models that find a person's joints, shared by several checks | *System / Shared parts / Pose models* |
| Speed and cost | Valentyn Fedorov with Yurii Luchko | faster General Model, tracker and checks with the same results | *Research / CV* |
| Hair policy, how the checks are organised | Vladyslav Ivashchuk | the hair policy check; the structure of the checks | *System / Modules / Hair policy* |
| Team lead | Valentyn Fedorov | priorities, reviews, this documentation | this page |

## How we work

- **Tasks** live in Jira. The plan of the month is in the Sprint Planning sheet.
- **A change goes to production like this:** a branch in the module's repository → a merge request → a review → the
  MLOps team builds the image → a run on a few videos next to production → production.
- **Every change is proven before it goes to production:**
  - a change that should not change any result (a speed-up, a clean-up) must give exactly the same output files —
    *How-to / How to prove that a change keeps the same results*;
  - a change of logic or of a model is measured on the monthly test, with the turnarounds the client labelled Fail —
    *How-to / How to measure a change on the monthly test*;
  - a change of what a verdict means (for example, deciding earlier so that an alert can be sent) is not a code change:
    it is a decision of the client's safety team, prepared by the lead.
- **Who decides:** technical questions — Ihor (the technical reviewer of the project); anything the client sees — the lead
  with Oksana (accuracy and the client's labels) and the client.
- **Monthly review:** in the first week of every month each owner opens the pages of their checks and parts, updates the
  *Status* block (accuracy from the new monthly test report, the version in production, the biggest open problem) and
  sets the review date — *How-to / How to keep the CV pages current*.

## Who we work with

| Team | About what |
|---|---|
| MLOps (Maksym Chernyshev) | images, tests on the cluster, the real-time worker |
| Data (Denys Filimonov, Oksana) | datasets and labels; the monthly test and the client's labels |
| Backend (Aryan Singh) | the verdicts that become alerts and appear on the website |
| Edge (Vladyslav Ivashchuk) | what can run on the camera box at the gate |

## Where to find what

| What | Where |
|---|---|
| How every check works, its accuracy and problems | *System / Modules* (one page per check) and the *Modules index* |
| The General Model, the tracker, the stage detector, the pose models | *System / Shared parts* |
| What we studied and measured | *Research / CV* |
| How to do the everyday work | *Teams / CV / How-to* |
| What to read in the first weeks | *CV onboarding*, next to this page |
