> A small renovation contractor had quotes, tenders, site notes and subcontractor paperwork in different places. I linked them into one system the owner can check before anything goes out.

## [THE PROBLEM] The same job, typed in five times

A Kent renovation contractor kept enquiries, quotes, tender packs, site notes and subcontractor statements in separate places. The same information was re-entered again and again, filing drifted, and there was no single view of every job at once.

## [MY PART] Discovery to handover

I ran the discovery, designed the workflows and the folder structure, and built and tested every skill in ChatGPT Work. The testing ran on **Thorne & Hale**, a fictional company with the same shape as the real business, so no real client file was touched until each skill worked. Then I delivered the build and a training session to the founder.

[[image:th-quotes]]

## [HOW IT WORKS] Six workflows, one folder

- **Quote qualification.** Checks a new brief against written go/no-go rules, then drafts a branded quote from the closest past examples and logs it with a unique reference.
- **Tender pack to estimate.** Reads specifications, drawings and supporting documents and builds a linked Excel estimate with measurement, trade and summary sheets.
- **Site transcripts.** Matches a voice transcript to the right job, keeps the original, and adds progress, decisions, snags and actions to that job's highlights.
- **Roadmap.** Reconciles the project register, quotes and site flags into one workbook covering every job.
- **Enquiry replies.** Drafts replies in the company voice for review. It never sends.
- **CIS statements.** Finds the accountant's monthly email, checks each statement against its PDF, and files it into that subcontractor's Drive folder without duplicates.

Three dashboards sit on top (quotes, roadmap and site highlights), and scheduled tasks run the transcript, roadmap and email steps.

[[image:th-roadmap]]

## [DESIGN DECISION] Safe by default

>> If the skill is not sure, it says so and leaves it for a person.

Drafts are review-only. Raw transcripts are kept as evidence. A transcript that can't be matched confidently goes to an unfiled folder instead of the most likely job. Past prices are examples, never a rate card.

## [EVIDENCE] The £300,000 gap

On a real tender pack, the first version of the tender skill came back about **£300,000 short**. I traced it to the skill not following the worked example's method; the data was fine. Version 2 fixed it with the exact output format plus matched input and output examples.

On the client's real setup, the CIS filer runs on their Gmail and Drive, tender v2 runs on real packs, the dashboards are published and the scheduled tasks are on.

[[image:th-highlights]]

## [STAGE] Delivered, in use

Delivered and in use by the client. Thorne & Hale stays as the public demo; the dashboards shown here hold fictional data.
