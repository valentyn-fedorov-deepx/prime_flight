# How to keep the CV pages current

**For:** every CV engineer who owns a check or a shared part.

The pages of the CV team must always say how the system works **today**. They are kept current in two ways: when
something changes, and once a month.

## When something changes

When your task changes something a page describes — a new version in production, a new threshold, a new problem found,
a problem fixed — update the page in the same task. The task is not done before the page is.

## Once a month (first week, about 30 minutes per person)

1. **Refresh the numbers.** When the new monthly test report has arrived, the accuracy and Fails-caught numbers of every
   check are recomputed from it and written into the *Status* blocks and the *Modules index* automatically (see *For
   developers*).
2. **Open the pages you own** and read the *Status* block:
   - *In production* — did a new version go to production this month?
   - *Biggest open problem* — is it still the biggest, or fixed?
   - *Who looks after it* — still you?
3. **Read the accuracy numbers.** If a check got worse, find the turnarounds that changed and write a line about it in
   *How accurate it is*.
4. **Research.** If you measured something this month, add a report to *Research / CV*.
5. **Set the review date** at the top of the page.

## What not to do

- Do not rewrite a page that is still right.
- Do not copy a number from another page — link to the page that owns it.
- Do not leave a guess: write "to confirm" and who can confirm it.

## For developers

```bash
# after a new monthly report is parsed into out/testset/monthly_report_parsed.json
python scripts/handbook_module_data.py     # facts per check: accuracy, Fails caught, production version, findings
python scripts/build_handbook.py           # the Word documents of the shared folder
```

The page texts live in `docs/handbook/` in the Prime Flight repository; `docs/handbook/STYLE.md` says how they are
written. Parsing the monthly report into JSON is still a manual step: to automate.
