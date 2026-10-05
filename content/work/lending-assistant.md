> A broker's deal information lived in handwritten notes, emails and attachments. I built skills that pull it into one sourced record and a draft credit paper, and tested them against a case with known answers.

## [THE PROBLEM] Retyping every deal

A UK specialist-lending broker worked from handwritten call notes, with details scattered across emails and attachments. Writing a credit paper meant retyping and reconciling all of it by hand.

## [MY PART] Requirements to handover

I ran discovery with the broker and wrote the product requirements. Then I built **Northgate Specialist Lending**, a fictional test pack, so no real borrower data was touched. I designed and tested the skills and a deal dashboard, then delivered a session and handover.

## [HOW IT WORKS] Eight skills

- The core four: digitise phone notes, capture split context (email plus attachments), cross-reference lenders and draft a credit paper.
- Four more came out of testing, including a live-market lender search and a planning-portal lookup.
- Every extracted value keeps its source, where it was found and how well it's evidenced.
- There are credit-paper templates and worked examples for four deal types: residential bridging, commercial, development and portfolio buy-to-let.
- A deal dashboard sits on top.

[[image:la-dashboard]]

## [DESIGN DECISION] Check the live market, keep his judgement

>> The tool narrows the field. The broker decides.

The live-market lender search goes online and finds UK lenders currently advertising a product. It opens each link to check the page is live before returning it, and the results feed the broker's own lender spreadsheet. It doesn't replace his red, amber and green view of which lenders actually deliver.

## [EVIDENCE] A gold case with traps

The gold case is a full fictional deal: emails, notes, documents and expected outputs, with inconsistencies planted on purpose. The saved validation run passed **10 of 10** assertions. They included:

- resolving a GDV conflict
- not treating an agent's opinion as a formal valuation
- separating stated equity from proof
- flagging an unallocated £775,000 facility balance

[[image:la-queue]]

## [STAGE] Delivered as a tested build

Delivered with a session and handover; day-to-day use isn't known. The 10/10 comes from one saved gold-case run, not a general accuracy score, and the lender data is fictional.
