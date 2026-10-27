# What does each check read from the General Model and the tracker?

*September 2026 · Valentyn, with Vladyslav · Status: done; waiting for review by Vladyslav and Yurii Luchko*

## In short

We read the code of all 27 modules to list exactly what each takes from the shared parts. Together they decide on 26
kinds of objects the General Model finds; trailers, service vehicles and pushback tugs are read most often (22 to 23
modules), mostly to tell whether the view is blocked. They read four kinds of tracked objects: the aircraft (25
modules), people (14), belt loaders (11) and service vehicles (3). 15 modules read the video pictures, 13 run models of
their own, 4 read the recording twice, 9 work out the arrival themselves. The data format must stay exactly as it is.
Labelled cones (22 checks) and people (17) would unblock the most checks.

## The question

The General Model, the shared detector, draws a box (a **detection**) around every object it finds on each **frame**
(one picture of the video; the cameras take 8 per second). The tracker follows each object from frame to frame (a
**track**) and says whether it moves or stands still. **Service vehicles** are the ground support equipment (tugs, belt
loaders, fuel trucks, tractors); the General Model has one general class for them and separate classes for belt
loaders, pushback tugs, fuel trucks and trailers. To rebuild these parts without breaking a check, we need to know
exactly what each check reads, and, if a check got a small model of its own, what would need labels.

## What we did

1. Read the main program of every module and the code that hands the data over (14 September); checked the format
   against the production files of one 82-minute video.
2. Sorted each module's objects into those its rule is about, aircraft parts, and other vehicles (24 September).
3. Gave each module only the objects it declares and compared its verdicts (Pass, Fail or Not observed) with the full
   input over the monthly test (the client's validated turnarounds we measure on).

## What we found

### How the data reaches a check

- For every frame the General Model writes boxes of **exactly six numbers**: four corners, a score and the class number.
  For the aircraft the score's place holds the most common height of its box in pixels; no module reads it.
- It also adds **view-blocker rows**, made from large vehicles in front of the aircraft or at its sides. Eight modules
  read them like detections to decide "the view was blocked".
- The tracker writes each object's kind, number, box and internal state: status (moving, stopped, stopping, proceeding,
  not seen), the aircraft's arrival and departure frames, and a front-door or rear-door label for belt loaders.
- The two files are matched **line by line, by position**: every frame needs one line in each, or everything after a gap
  shifts.

### What each check reads

"Pushback" is the tug that pushes the aircraft back. Most checks read other vehicles to tell whether the view is
blocked; the pushback path check reads them as possible obstacles on the path.

| Check | Objects the rule is about | Aircraft parts | Other vehicles and equipment | Tracked objects | Reads the video |
|---|---|---|---|---|---|
| Chocks and cones ready before the aircraft arrives | cones, chocks | — | belt loaders, service vehicles, pushback, view-blockers | aircraft | no |
| Crew present 10 minutes before the aircraft arrives | people | — | service vehicles, pushback, trailers | aircraft | no |
| Foreign object debris walk completed | — | nose wheel, nose, tail | service vehicles, belt loaders, pushback | aircraft, people | yes |
| Safety huddle at the huddle cone | cones | — | belt loaders, service vehicles, pushback, trailers, fuel trucks | aircraft, people | yes |
| Safety vests worn and fastened | safety vests | — | — | people | yes |
| Safety zone clear before the aircraft arrives | cones, people | nose wheel | pushback, belt loaders, service vehicles, fuel trucks, trailers, other vehicles, view-blockers | aircraft | yes, twice |
| Hair policy | to confirm (protected code) | to confirm | to confirm | people | yes |
| Aircraft wheel chocks (three verdicts) | chocks, cones, pushback | nose wheel, main wheels, nose, tow bar | trailers, fuel trucks, ladders, other vehicles, view-blockers | aircraft, people, service vehicles, belt loaders | yes, twice |
| Cones placed in the right positions on time | wing, engine and tail cones, people | tail | service vehicles, pushback, trailers, belt loaders, fuel trucks, ladders | aircraft | no |
| Steering bypass pin installed | people, chocks | nose wheel | — | aircraft, people | yes |
| Lead marshaller and wing walkers in position | — | tail, wing | belt loaders, service vehicles, pushback, trailers, view-blockers | aircraft, people | no* |
| Belt loader rear cone placed after the belt loader is in place | belt loader, engine, wing and other cones, belt loaders, rear cargo door, people | main wheels, engine | pushback, trailers, service vehicles, fuel trucks, ladders | aircraft, belt loaders | no |
| Service vehicles guided to the aircraft with approved hand signals | front and rear cargo doors, people | main wheels, engine, wing | pushback, trailers, service vehicles, fuel trucks, ladders | aircraft, belt loaders, people | yes, twice |
| Walk-around inspection after arrival | front and rear cargo doors | main wheels, tail, wing, engine | belt loaders, fuel trucks, service vehicles, ladders, trailers | aircraft, people, belt loaders | yes |
| Three-stop brake check | — | — | service vehicles, pushback, trailers | aircraft, belt loaders | no |
| All cargo bin doors opened and verified | front and rear cargo doors | — | service vehicles, pushback, trailers, fuel trucks, other vehicles, view-blockers | aircraft | no |
| Motorized service vehicles parked and chocked | chocks, cones | — | pushback, trailers, fuel trucks, ladders | service vehicles, people, belt loaders | yes |
| Handrails on service vehicles being used | people, rear cargo door | engine, main wheels | trailers, service vehicles | aircraft, people, belt loaders | yes |
| Safety handrails fully extended and used | people | main wheels | trailers, service vehicles | aircraft, belt loaders | yes |
| Belt loader forward chock stays in place until the belt loader backs away | chocks, cones, belt loaders, rear cargo door, people | main wheels, engine, wing | pushback, trailers, service vehicles, fuel trucks, ladders | aircraft, belt loaders | no |
| Conditioned air hose removed 10 minutes before departure and stowed | the hose (its own detector) | nose wheel, nose | trailers, service vehicles, belt loaders, pushback | aircraft | yes |
| Cones removed only after all service vehicles are clear of the aircraft and chocked | engine, wing and tail cones, front cargo door, service vehicles, belt loaders | main wheels | pushback, trailers, fuel trucks, other vehicles | aircraft, belt loaders | no |
| Pushback driver checks the steering bypass pin | pushback | nose, nose wheel | belt loaders, service vehicles, trailers, other vehicles, view-blockers | aircraft, people | yes, twice |
| Walk-around inspection before departure | cones | engine, tail, nose | belt loaders, service vehicles, pushback, trailers | aircraft, people, belt loaders | yes |
| Pushback waits until the wing walkers are in place and ready | pushback | tail, wing, nose wheel | belt loaders, service vehicles, trailers, view-blockers | aircraft, people | no |
| Pushback path clear of obstacles | pushback, cones, chocks | tail, nose | belt loaders, service vehicles, fuel trucks, trailers, ladders | aircraft | no |
| Wing walkers in position with approved wands during pushback | — | engine, wing, nose, tail | pushback, belt loaders, service vehicles, trailers, view-blockers | aircraft, people | no* |

\* The analysis read each repository's default branch. For these two checks the branch that runs in production and in
the monthly test adds a pose model (it finds a person's joints) and reads the video. Where the check pages of this
handbook, written from the production branches, differ from this table, the check page is the reference. A 28th module,
seat belts on service vehicles, is out of scope.

### Copies of the same moment in many modules

- **Arrival:** 9 modules carry an identical copy of code that works it out from the tracker's internal data (the points
  it follows on the aircraft), although the tracker already publishes the answer.
- **Pushback attached:** 2 modules work it out by reading ahead.
- **Arrival and departure from the status:** 7 modules, each with its own waiting time: "departure" means anything from
  "moving now" to "moving for 30 seconds".
- **Exact frame match:** 4 modules compare frame numbers with the tracker's arrival or departure frame, which breaks if
  the numbering shifts by one frame.
- **Belt loader at the door or gone:** 9 modules. **Jet or aircraft:** 2.

### What must not change

- Six numbers per box (an extra number would silently become part of the box), the class numbers (7 modules crash on an
  unknown one) and the view-blocker rows.
- The set of entries in each tracked object's state, in both directions: an unknown entry makes the module fail, as
  happened once when two belt loader entries leaked into the aircraft's state.
- One line per frame: on an empty frame, 15 modules do not update the aircraft at all.

The modules also pin 10 different versions of the shared code library; five have "8 frames per second" in their code.

### Datasets

If each check got a detector of its own, these objects would need labels (as the check's own object, not scenery):

| Object | Checks | Object | Checks |
|---|---|---|---|
| cones | 22 | chocks | 5 |
| people | 17 | pushback | 4 |
| belt loaders | 9 | engine cones, wing-tip cones | 3 each |
| rear cargo door | 8 | service vehicles, tail cones | 2 each |
| front cargo door | 7 | safety vests, air conditioning unit, wands, belt loader cones | 1 each |

| Model the modules already carry | Trained on our pictures? | Used by |
|---|---|---|
| Handrail classifier (rail extended or not) | yes | handrails on service vehicles, safety handrails |
| Hand classifier (hand on the rail) | yes | handrails on service vehicles |
| Vest classifiers (which way the person faces; zipped or not) and colour rules | yes | safety vests |
| Conditioned air hose detector | yes | conditioned air |
| Chock classifiers (did a chock appear at the wheel) | yes | wheel chocks, service vehicles chocked |
| Movement classifier (pin installed, from 25 seconds of a worker's pose) | yes | steering bypass pin |
| Wand detector | unclear; loaded, never run | wing walkers with wands |
| Four pose models; a whole-body pose model; an outline model | no, ready-made | hand signals, steering, pin check, debris walk, service vehicles chocked; handrails; safety zone |
| Handrail segmentation model | to confirm | handrails on service vehicles |

Only safety vests needs nothing from the aircraft or the traffic. Seven more need four kinds of objects or fewer,
aircraft parts included: steering bypass pin, three-stop brake check, safety huddle, crew present, the pushback driver's
pin check, safety zone, chocks and cones ready. But 24 of the 27 modules work out the stage (the part of the turnaround)
from the aircraft's track, and most read the view-blocker rows. So a check taken off the General Model needs its own
detector, the stage detector's moments, and a replacement for the view-blocker rows.

### Checked by running

Giving each module only the classes found in the default branches changed 75 of 680 verdicts, because the branches that
actually run read more. With every class name in the running code (a deliberate over-count), **740 of 740 verdicts**
were identical.

## What it means

- While the modules run unchanged, the General Model cannot drop any of the 26 classes or its three detector parts.
- A rebuilt General Model or tracker must write the old format exactly; anything new goes into new, versioned fields.
- The stage detector should own arrival, departure, belt loader at the door and pushback attached, instead of the copies.
- A lost piece of video filled with empty frames makes 15 modules lose the aircraft; the filler should repeat the last
  aircraft track, or the loss must be accepted.

## What is next

1. Review by Vladyslav and Yurii; a pass over the newer branches of eight repositories.
2. Decide which General Model file production modules read (the code says the second, corrected one; to confirm) and
   what fills a lost piece of video.
3. Confirm a short class list per check by running it with only those classes.

## For developers

- Task PF-Q1-14; `docs/analysis/module_consumption.md` + `.json`, `module_dataset_needs.md`, `pf/rt/declarations.json`
  (`scripts/rt_declarations.py`); 740 / 740: `--subscription`, `docs/analysis/rt_module_cost.md` section 6; ADR-001.
- The table uses the decision classes of `module_consumption.json` (default-branch HEADs, 2026-09-14), grouped as in
  `module_dataset_needs.py`. That script subtracts `class_names_cosmetic`, which drops classes both drawn and decided
  (steering loses `person`, `front_wheel`); the dataset counts are the script's own.
- GM record `[x1, y1, x2, y2, conf, cls_id]` (class 2 conf = height mode; synthesized 29 / 30); track `{tr_id, xyxy,
  cls_str, conf, state_dict, data.bl_type}`; positional join in `db_worker/ML_worker.py`; checked on `AIjEAz70OfWCYG`.
  Arrival block `_p0`, `_st`, `_of_dots_lifetime`, `_init_dots_lifetime`; unknown keys raise in `from_state_dict`.
