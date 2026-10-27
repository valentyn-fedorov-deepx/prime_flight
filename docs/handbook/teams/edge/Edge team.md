# Edge team

> Every gate records and uploads its video, and we know what can run on the device itself.

## People and directions

| Direction | Who | What it covers |
|---|---|---|
| Edge device | Vladyslav Ivashchuk, with Valentyn Fedorov | what the CameraBox can run: battery, compute, Hair Policy on the device |
| CameraBox software | Vladyslav Ivashchuk | recording, chunks, upload |
| Devices and network | hardware engineer (to name) | device health, CamBox Pro rollout with the PrimeFlight IT team |

## What the team keeps in the shared folder

- 2 System / Architecture / Edge (with MLOps)

## Repositories

`dxgat/utils/camera_software`, `dxgat/cambox-api/*` (logs handler, ping service, bucket checker)

## Works with

- MLOps — upload into the buckets and the real-time worker
- Data — data collected at the gate
- PrimeFlight IT — devices and network

## How we work

- Tasks in Jira; the month's plan in the Sprint Planning sheet.
- The rules in *Start here*: the client's rules are the contract; measure every change; production only through
  a reviewed merge request.
- **Monthly review** (first week of the month, 30 minutes): each owner updates the *Status* block of the pages they own
  and sets the review date.


New in the team: *Edge onboarding*, next to this page.
