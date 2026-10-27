# Data team

> Every model and every measurement has the right data, and everyone can find it.

## People and directions

| Direction | Who | What it covers |
|---|---|---|
| Datasets and labels | Denys Filimonov | collection, DVC, training and test sets, labels |
| Accuracy validation | Oksana | the monthly test against the client's validation; which checks go to the client |

## What the team keeps in the shared folder

- Data catalogue and test sets (next stage)

## Repositories

DVC buckets `dvc_training_datasets` and `dvc_test_datasets`; labels in Google Sheets

## Works with

- CV — what data each model and module needs
- Edge — data collected at the gate
- Backend — testing the LLM output

## How we work

- Tasks in Jira; the month's plan in the Sprint Planning sheet.
- The rules in *Start here*: the client's rules are the contract; measure every change; production only through
  a reviewed merge request.
- **Monthly review** (first week of the month, 30 minutes): each owner updates the *Status* block of the pages they own
  and sets the review date.


New in the team: *Data onboarding*, next to this page.
