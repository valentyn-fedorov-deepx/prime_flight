# Backend onboarding

> Welcome to Backend. We make the results and alerts reach the people who act on them, without noise: MongoDB, the
> RampVision website, the alerts.

## 1. What you will work on

Alerts (one alert per violation, quiet windows, new alert types without code changes), the results store and the website,
the LLM analysis of the station managers' feedback. Owner: the *Backend team* page.

## 2. How it works, for Backend

- Every module job returns a verdict per check (Pass, Fail, Not observed), a report line and a timeline.
- The receiver writes the video and event documents and the tasks in MongoDB; the module timelines go to the
  `modules-inferences` bucket and are streamed to the website (`tasks-inferences-handler`).
- The website (frontend and backend on App Engine) shows the turnarounds, the verdicts and the video timeline.
- Real time, being built: the modules only produce verdict records; the **alert service** receives them, keeps one alert
  per violation and its lifecycle, and writes the event and alert documents that the website shows.

What each check means for the client: *2 System / Requirements / Client rules*.

## 3. Read, in this order

1. *2 System / System overview* (20 min).
2. *2 System / Requirements / Client rules* — the verdicts you store and show.
3. *2 System / Architecture / Post-processing* — where the results come from.
4. *2 System / Architecture / Real-time* — where the alerts will come from.
5. *2 System / Modules / Modules index* — which checks exist and how accurate they are.

## 4. Where things are

| What | Where |
|---|---|
| Website | GitLab `dxgat/web/mvp-web-portal` (frontend), `dxgat/web/gat-api` (backend), App Engine |
| Results streaming | `dxgat/ml_backend/tasks-inferences-handler` |
| Receiver | `dxgat/ml_backend/ml-backend-api` |
| Data | MongoDB (prod and dev); the `modules-inferences` bucket |

## 5. Rules for Backend

The rules everyone follows are in *Start here*. In Backend in particular:

- A verdict means what the client's rule says; the website never re-interprets it.
- The format of the verdict and alert records is agreed with CV and changes only through the decisions log.
- Production database changes follow a runbook and are announced first.

## 6. Your first two weeks

Week 1:

- [ ] Accounts: GitLab (`dxgat/web`), GCP `rampvision-2`, read access to the dev MongoDB, Jira, Slack.
- [ ] Read the list above.
- [ ] Run the website against dev; follow one turnaround from its MongoDB documents to the page that shows it.

Week 2:

- [ ] The first task from Jira with Aryan.
- [ ] Read the alert design and the open questions with CV.

## 7. Whom to ask

| About | Ask |
|---|---|
| Alerts, MongoDB, the website | Aryan Singh |
| Receiver, Kafka, jobs | Maksym Chernyshev (MLOps) |
| What the modules output | Yurii Luchko (CV) |
| Priorities, delivery channels | Valentyn Fedorov |
