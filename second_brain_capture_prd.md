# Second Brain — Capture, Media and Browsing
**Owner:** Toni Esan · **Date:** 2026-08-14 · **Status:** draft for build

Three things to build, in this order. Each one works on its own, so you can stop
after any of them and still be better off than you are now.

The graph itself is already built. 1,103 nodes, all embedded, 251 concepts, 11 doors
and 13 domains, an Explore tab and a Tagging tab. See `CURRENT_STATE.md`. This
document is only about what feeds it and how you look at it.

---

## 1. Own your media

### The problem

You own none of your images. All 1,014 of them are links to `pbs.twimg.com`, and
those die when a tweet is deleted, an account goes private, or Twitter changes
something. You would not find out until you went looking, and by then the picture
is gone. Everything else you have is in your own database. The pictures are the one
part still borrowed.

This is worth doing whether or not you ever tag an image, so it goes first.

### Where it goes: Cloudflare R2, not Supabase Storage

R2 is the better home here for three reasons.

It does not pause. Supabase pauses Free Plan projects after seven days of low
activity, and you run several projects. Media sitting outside that blast radius is
worth having.

Egress is free, on every storage class and access method. The visual grid in part 3
means loading hundreds of images repeatedly, which is exactly the access pattern
that costs money elsewhere.

The free tier is 10GB of storage a month, plus 1 million class A and 10 million
class B operations. A few hundred megabytes and a few thousand reads sits inside
that with room to spare.

**This does not solve the pausing problem, only moves the media out of it.** The
graph itself is Postgres on Supabase, so if that project pauses, everything is
offline regardless of where the pictures are. Decide separately whether this one
project goes on a paid plan. Daily use of the admin keeps it awake; a fortnight away
does not.

### What to build

A script that walks every capture with a `media_urls` entry, downloads the file,
puts it in R2, and records where it went.

- One private bucket, e.g. `capture-media`. No public bucket and no `r2.dev` domain
  — everything in this system is private, and media should not be the exception.
- Access via the S3-compatible API, so `boto3` works and there is nothing exotic to
  learn. Credentials go in `.env` next to the rest.
- Path by source and id, e.g. `twitter/<inbox_id>/0.jpg`, so it is obvious what
  belongs to what.
- No new table. Add a `stored_media` text array to `inbox` alongside `media_urls`,
  holding object keys rather than URLs, and leave the original URLs untouched so you
  can always see where something came from.
- The admin gets images through short-lived presigned URLs, generated on demand.
  Keys in the database, never permanent public links.
- Skip anything already stored, so it can be re-run.
- Record failures rather than dying. A dead link is information — it tells you that
  bookmark's image is already lost.

### Scope

- Roughly 740 items, 1,014 images, a few hundred megabytes.
- Images only for now. Audio arrives in part 2 and goes to the same bucket under
  `audio/`.

### Done when

Every fetchable image is in R2, the admin can display them, and you have a count of
how many were already dead.

---

## 2. Capture from anywhere, enrich when you can

### The problem

Everything in the pool came from Twitter, through a bulk export. You want to send
things in as you find them, from Instagram, TikTok and YouTube, and have them land
in the same pool with the same tags.

The obstacle is that enrichment cannot happen at capture time. yt-dlp has to run
somewhere with a normal home connection, because datacenter addresses get bot-checked.
Your laptop is not always on.

### The shape

Two stages, deliberately separated.

**Stage one, capture.** Always succeeds, always instant. The Telegram bot takes
whatever you send — a link, a photo, a voice note, a line of text — writes a row to
`inbox` with `source` set correctly and a status of `needs_enrichment`, and replies.
Nothing is fetched here. If you are on a train with no signal, the message queues in
Telegram and arrives later.

**Stage two, enrichment.** A worker polls for rows needing work and fills them in.
It runs on your laptop, or a Raspberry Pi at home if the laptop annoys you. It must
be safe to kill and restart at any point.

### What enrichment does, by source

| Source | What it fetches |
|---|---|
| Instagram photo, or any image you send | The image itself, into R2 as in part 1 |
| YouTube | Captions via `yt-dlp --write-auto-sub --skip-download`. Near universal coverage. |
| TikTok with captions | Subtitles via yt-dlp. Supported since PR #2185, but only when the creator enabled them. |
| TikTok without captions | Audio only, via `-x --audio-format m4a`, then Whisper. About 1MB a minute against 15MB for video. |
| A plain link | Page title and text |
| Voice note | Transcript, as it does today |

Video files are never downloaded. Audio only, and only when there is no caption track.

### Rules

- Capture never fails because enrichment might. A row with no transcript is still a
  row, and your own one-line note about why you saved it is worth more than a machine
  description anyway.
- Enrichment is retryable and idempotent. Record attempts and the last error, and
  back off rather than hammering a video that will never work.
- yt-dlp breaks when platforms change. Expect to update it. Do not treat it as
  infrastructure.
- Once enriched, the item goes through the tagging and embedding you already have.
  Nothing new is needed downstream.

### Where the worker runs

Laptop is free and works. A Pi is about £60 once and is always on, which is what I
would pick. A £5 cloud box will fight bot checks and is the worst of the three.
Transcripts alone are tiny, so bandwidth is never the constraint. The home address is.

### Done when

You can send a TikTok, an Instagram photo and a YouTube link from your phone, and
some time later all three appear in Explore, tagged, alongside your Twitter
bookmarks.

---

## 3. Look at things, and only tag what carries a fact

### The problem

460 captures are still untagged, and they are the visual ones — interaction design
133, MJ aesthetic 114, web design 109, hard pics 101. Text tagging correctly left
them empty, because the text is a handle and a link and the content is in the picture.

But they are not all the same, and treating them the same is the mistake.

### The rule

**Use vision where the image carries a fact the text lost.** A caption-less tweet
showing a drone. A screenshot of an interface pattern. A photo of a device. There
the picture is the only place the information exists, so tagging makes the item
findable. Interaction design and web design are the strongest case, because a bento
grid or a command palette is a real concept that connects to your own web and
creative work.

**Skip vision where the image is the point.** MJ aesthetic and hard pics are about
200 items you saved because they look good. You will never search them by concept.
Tagging them spends money producing labels you will not click.

So: tag interaction design, web design, and the caption-less items in Hard projects
and cool news. Leave the aesthetic folders alone.

### What to build

**A visual grid.** A new view in the admin showing stored images as a dense grid,
filtered by folder, domain or concept, with click to enlarge and a link to the
original. This is what the aesthetic folders actually needed. It depends on part 1,
which is another reason part 1 goes first.

**Selective vision tagging.** `scripts/tag_images.py` already exists and works. It
uses `gemini-3.7-flash`, sends the first image with the saved text and your
vocabulary, writes with `origin='gemini-image'` so you can always tell which pass
produced what, and adds without overwriting the text pass. Point it at the folders
above rather than at everything.

Cost is about £1 for all 740. Most of that is the 251-concept list being sent with
every image rather than the image itself, so if it ever matters, trim the vocabulary
sent for a visual pass.

### Done when

You can open a grid of every image you have saved and scroll it, and a search for
a bento grid or a drone returns the bookmark that shows one.

---

## Order and why

1. **Media first.** It stops loss that is happening now, and both of the others
   depend on having the files.
2. **Capture second.** It is the thing you actually asked for, and it makes the pool
   grow on its own instead of being a one-off Twitter import.
3. **Browsing third.** It is the payoff, and it needs the other two to be worth
   looking at.

## Deliberately not in scope

- No media table. Media hangs off `inbox` and the graph does not care.
- No video downloads. Audio only, and only when captions are absent.
- No image generation, no re-hosting anything publicly. The R2 bucket stays private
  and is read through presigned URLs, same as the rest of the graph.
- Nothing about the public site. This is all behind `/admin`.

## Known risks

- **yt-dlp is not stable infrastructure.** It reverse-engineers private APIs and
  breaks on a schedule. Budget for maintenance, keep a manual fallback.
- **TikTok is still the weakest source.** Captions depend on the creator, and plenty
  of TikToks are music over visuals with no speech at all. Some will never enrich.
  That is acceptable, not a bug to fix.
- **The worker being offline is normal, not an error.** The queue growing while your
  laptop is shut is the design working.
- **Storage grows quietly.** A few hundred megabytes now, but forward capture adds
  more forever. R2's free tier is 10GB, so check occasionally rather than being
  surprised.
- **The database can still pause.** Moving media to R2 protects the files, not the
  graph. A Free Plan Supabase project pauses after seven days of low activity, and
  everything here depends on that one project being awake. Either use it regularly
  or put it on a paid plan.
- **Two sets of credentials now.** R2 keys join the Supabase and Gemini keys in
  `.env`. Losing that file costs more than it used to.

---

## Where we are — 2026-08-18

**Part 1 — in progress.**
- `capture-media` bucket created in R2. Account `eb8193d2791bec64568e1115104e2e1d`, no jurisdiction prefix.
- `.env` needs: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET=capture-media`.
- Migration done: `inbox.stored_media` (text[]), `inbox.media_archived_at`, `inbox.media_error`.
- `scripts/archive_media.py` written and dry-run tested on 5 files. All fetched, keys correct
  (`twitter/<inbox_uuid>/0.jpg`).
- **Next command:** `python3 scripts/archive_media.py --limit 20`, then without `--limit` for all 740.
- Not started: presigned-URL display in the admin.

**Part 2 — not started.**

**Part 3 — partly done.**
- `scripts/tag_images.py` written, uses `gemini-3.7-flash`, never run.
- Visual grid not started, depends on part 1.

**Also worth knowing**
- R2 already holds `60thface-photos`, `wedding-uploads`, `timi-gallery`, `timi-audio`,
  `timi-brand-assets`, `timi-tiktok-screenshots`. Those are the same projects that are now
  nodes in the graph, and nothing links them. Worth wiring up at some point.
- Text tagging and embeddings are finished. 1,103 nodes embedded with `gemini-embedding-2`
  at 768 dims, 443 captures tagged, 251 concepts. See `CURRENT_STATE.md`.
- `generate_digest.py` and `generate_questions.py` still import the retired
  `google.generativeai` SDK and pin `gemini-2.5-flash`. Not yet moved over.
