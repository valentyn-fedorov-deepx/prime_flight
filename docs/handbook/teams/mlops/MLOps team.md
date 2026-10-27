# MLOps team

> The video gets from the camera to the result reliably, quickly and at a sensible cost.

## People and directions

| Direction | Who | What it covers |
|---|---|---|
| Architecture of the real-time branch | Maksym Chernyshev | the real-time worker end to end, the data format between its parts |
| Infrastructure | Maksym Chernyshev | GKE clusters and node pools, Kafka, images, CI/CD, the move to Azure |
| The running pipeline | Maksym Chernyshev | receiver, orchestrator, subscribers, merge; manual merges |
| Test server during the Azure move | Andrii P. (to confirm) |  |

## What the team keeps in the shared folder

- 2 System / Architecture

## Repositories

`dxgat/ml_backend/*` (receiver, orchestrator, subscribers, Kafka), `dxgat/utils/camera_software` (merge), `dxgat/detectors/realtime-pipeline`, `dxgat/detectors/ci_configuration`

## Works with

- CV — running and testing their models
- Edge — upload from the gate
- Backend — where results and events are stored

## How we work

- Tasks in Jira; the month's plan in the Sprint Planning sheet.
- The rules in *Start here*: the client's rules are the contract; measure every change; production only through
  a reviewed merge request.
- **Monthly review** (first week of the month, 30 minutes): each owner updates the *Status* block of the pages they own
  and sets the review date.


New in the team: *MLOps onboarding*, next to this page.
