# Data onboarding

> Welcome to Data. We make sure every model and every measurement has the right data, and that everyone can find it:
> datasets, labels, test sets, and the accuracy check against the client's validation.

## 1. What you will work on

Data collection, datasets in DVC, training and test sets, labels, and the monthly accuracy check. Owners: the *Data team*
page.

## 2. How it works, for Data

- **Videos:** one per camera per turnaround, merged from the CameraBox chunks, in the buckets.
- **Labels:** the client validates the verdicts — Pass, Fail or Not observed per check and turnaround. From them comes the
  **monthly test set** (69 turnarounds, 90 videos): the accuracy of every check is the share of turnarounds where our
  verdict matches the label.
- **Training data:** for the General Model heads, the chocks detector, the camera classifier and the module models,
  versioned with DVC.
- Few Fail labels make a check's accuracy look better than it is: some checks have one to three labelled Fails. Finding
  Fail turnarounds is part of the work.

## 3. Read, in this order

1. *2 System / System overview* (20 min).
2. *2 System / Requirements / Client rules* — the labels follow these rules.
3. *2 System / Modules / Modules index* — accuracy and labelled Fails per check.
4. The module pages of the checks you collect data for (*Uses*, *Own models*).

## 4. Where things are

| What | Where |
|---|---|
| Datasets | DVC buckets `dvc_training_datasets`, `dvc_test_datasets` |
| Videos | `Videos-to-process` (merged), `CamboxChunks` (raw) — read-only |
| Labels | Google Sheets |
| Model weights | DVC, `gs://cv_weights/DVC` |

## 5. Rules for Data

The rules everyone follows are in *Start here*. In Data in particular:

- Every dataset is versioned in DVC, never in git; a test set is not used for training.
- A balanced sample includes turnarounds labelled Fail.
- Videos show people at work: they stay inside the project's buckets and drives.

## 6. Your first two weeks

Week 1:

- [ ] Accounts: GCP `rampvision-2` (buckets), DVC, the label sheets, Jira, Slack.
- [ ] Read the list above.
- [ ] `dvc pull` one test set; open one turnaround's video next to its labels.

Week 2:

- [ ] The first task from Jira with Denys.
- [ ] Pick one check with few labelled Fails and list where more could come from.

## 7. Whom to ask

| About | Ask |
|---|---|
| Datasets, DVC | Denys Filimonov |
| Labels, accuracy, the client's validation | Oksana |
| What a model needs | Yurii Luchko (CV) |
| Data from the gate | Vladyslav Ivashchuk (Edge) |
