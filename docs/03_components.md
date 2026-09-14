# Shared components (E01–E33)

Джерело: `docs/arch_review/essential_inventory.json` (baseline 2026-09-07, 32 компоненти після виключення E23/M25). Повний текст — `docs/arch_review/ESSENTIALS.md`, інтерактив — `docs/arch_review/components.html` та `hierarchy.html`.

Правила меж (з ревʼю): списки задач містять лише evidence, потрібний політиці; пороги, дедлайни, eligibility і фінальний Pass/Fail лишаються локальними в модулі; один ID = один контракт.

| ID | Група | Компонент | Impl | Контракт | Хто споживає |
|---|---|---|---|---|---|
| E01 | Context | **Aircraft arrival context** | CODE | Arrival time, whether arrival was seen, and how much pre-arrival footage is available. | M06, M10, M11, M18, M24, M02A, M09, M26, M15, M17, M03, U02, U03, U04 |
| E02 | Context | **Aircraft departure context** | CODE | Departure time, whether departure was seen, and the available departure footage. | M07, M08, M16, M19, M20, M21, M27, U02, U04 |
| E03 | Context | **Aircraft layout** | CODE | Aircraft and part locations, aircraft type and camera view, including missing or off-screen parts. | M02A, M09, M26, M15, M01, M03, M02B, M07, M08, M16, M20, M27, M02C, U01, U02 |
| E04 | Detections | **Chocks and cones detections** | CODE | Chock and cone locations, types and counts over time. Placement requirements remain in the policy. | M06, M24, M09, M05, M08, M21, U02 |
| E05 | Detections | **Transport detections** | CODE | Vehicle and ground-equipment locations and classes, including beltloaders, GSE, pushback and ladders. | M06, M21, U01, U02 |
| E06 | Detections | **People detections** | CODE | Person locations and counts per frame. Counts alone do not establish worker identity. | M10, M18, U02 |
| E07 | Context | **Camera obstacle status** | CODE | Which camera regions are blocked or not visible, and when. Keep region-specific visibility rather than one global flag. | M06, M10, M11, M18, M24, M02A, M09, M26, M15, M13, M17, M01, M03, M12, M14, M02B, M07, M08, M16, M19, M20, M21, M02C, U02 |
| E08 | Movement | **Vehicle movement and stops** | CODE | Vehicle identity, position, direction and moving or stopped periods, with continuity across track changes. | M24, M01, M12, U03, U04 |
| E09 | Movement | **Beltloader service status** | CODE | Which loader serves each door, its approach and parked periods, and when it leaves or returns. | M05, M13, M17, M01, M14, M22, M02B, M08, M04, M19, U02, U03 |
| E10 | Movement | **Pushback attachment status** | CODE | When pushback appears attached to the aircraft. Current implementations use sustained proximity, not mechanical coupling detection. | M02B, M16, M02C |
| E11 | Workers | **Worker tracks and paths** | CODE | Worker identities and time-stamped positions, directions and paths relative to the aircraft or work area. | M11, M23, M15, M20, M27, U03 |
| E12 | Workers | **Worker pose** | CODE | Body landmarks and confidence; hand landmarks where needed. Body-only and whole-body models remain separate profiles. |  |
| E13 | Workers | **Workers near equipment** | CODE | Which workers are drivers, helpers, climbers or interacting near a wheel, and during which equipment visit. | M13, M12, M16, M20 |
| E14 | Equipment | **Chock analysis** | CODE | Chock evidence at the relevant wheel over time, with separate nose-wheel, main-gear, beltloader and GSE profiles. Keep direct sightings, worker-action clues and image-change clues distinct; final policy rules stay local. | M02A, M12, M02B, M04, M02C |
| E15 | Workers | **Worker actions** | CODE | Time-stamped bending, sitting or raised-hand evidence. These are task-specific action profiles, not an approved signal vocabulary. | M13, M16 |
| E16 | Equipment | **Handrail state** | CODE | Whether rails appear extended and where the rails are. Location masks are only needed by contact checks. | M14, M22 |
| E17 | Workers | **Handrail contact** | CODE | Whether and when a climber appears to hold the rail, with contact visibility and observation coverage. | M14 |
| E18 | Workers | **Walk-around evidence** | CODE | Inspection paths, aircraft-relative coverage, model scores and usable observation coverage. Arrival and departure scorers remain distinct profiles. | M17, M19 |
| E19 | Context | **Ground work areas** | CODE | The relevant ground region: FOD corridor, safety zone or pushback path. These are different region profiles, not the same polygon. | M11, M24, M21 |
| E20 | Equipment | **Hose state** | CODE | Hose location and deployed or stowed appearance over time. Visual changes do not prove physical disconnection. | M07 |
| E21 | Detections | **Huddle cone detection** | CODE | The location and identity of the green meeting cone, including its color check. | M18 |
| E22 | Equipment | **Vest closure** | CODE | Each worker's zipped, unzipped or unknown vest appearance, with viewing direction and image quality. | M23 |
| E24 | Workers | **Pin installation actions** | CODE | Worker action classes and times near the nose wheel from the learned installation model. This does not directly see the pin. | M26 |
| E25 | Detections | **Wand evidence** | MISSING | Visible wands associated with workers. Required by the checklist, but active visual verification is missing in the reviewed module. | M27 |
| E26 | Perception | **Scene type and image quality** | CODE | Inside or outside scene, image noise and usable image quality, with suitable preprocessing. | U01, U02, U04 |
| E27 | Movement | **Aircraft movement** | CODE | The main aircraft's identity and moving or stopped history. Capture boundaries and analytical stage rules remain separate profiles. | U01, U02, U03, U04 |
| E28 | Infrastructure | **Video frames and timing** | CODE | Read video frames with their source identity and timing, including frame access and replay. | U01, U04, U05 |
| E29 | Infrastructure | **Turn video assembly** | CODE | Find, order and merge camera chunks into a turn video, retain context and resume incomplete processing. | U01 |
| E30 | Infrastructure | **Metadata exchange** | CODE | Read, align, store and deliver frame metadata through NDJSON or messaging. Current positional joins still need correction. | U02, U03, U04, U05 |
| E31 | Infrastructure | **Job setup and execution** | CODE | Load configuration and weights, run pipeline stages and modules, and manage artifacts and retries. | U05 |
| E32 | Infrastructure | **Results and evidence** | CODE | Map task outputs, retain evidence and deliver reports, keeping processing errors separate from compliance failures. | U01, U04, U05 |
| E33 | Infrastructure | **CV runtime helpers** | CODE | Shared model wrappers and image, box, mask and coordinate operations. These are library internals, not policy inputs. | U04 |

## Групи

- **Context**: E01, E02, E03, E07, E19
- **Detections**: E04, E05, E06, E21, E25
- **Equipment**: E14, E16, E20, E22
- **Infrastructure**: E28, E29, E30, E31, E32, E33
- **Movement**: E08, E09, E10, E27
- **Perception**: E26
- **Workers**: E11, E12, E13, E15, E17, E18, E24
