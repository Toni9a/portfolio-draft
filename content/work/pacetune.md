> Strava knows your splits. Spotify knows your songs. PaceTune shows which song was playing on which split.

## [THE PROBLEM] Two apps that don't talk

Running data and listening history live in separate apps, so you can't see what was playing during each part of a run.

## [MY PART] Product, design, build direction

I did the product, the design and the direction of the build.

## [HOW IT WORKS] Match by overlap

- **No sign-up form.** You connect Spotify and Strava, and your identity comes from linking them. Refresh tokens are encrypted.
- **Matching by overlap.** Songs are matched to runs by time. Each song goes to the one split it overlaps most, with padding at the start and end so edge tracks aren't missed.
- **The Messages view.** Each split is a message bubble listing its songs, set over a photo from the run, with bubble colours and opacity you can change. It exports as a PNG card. There is also a plain List view.
- **Saved runs.** They reload later, and a thinner sync never overwrites a richer saved result.

[[image:pt-messages]]

## [DESIGN DECISION] Designed around the gaps

>> Spotify doesn't always log a song you skipped.

Spotify's recently-played list doesn't always catch songs that weren't played to the end. So the matching is built around the gaps: padding at the edges, assigning each song by greatest overlap, and never overwriting good history.

## [EXPLORATIONS] Where the cards were going

Before I stopped, I was exploring new share cards beyond the Messages view: a cassette tape with an A and B side, rings for each split, a track list with paces, and a "run tour" where each song is a stop on the route. None of these shipped.

[[image:pt-explore]]

[[image:pt-tour]]

## [EVIDENCE] Friends, and a race playlist

- Live at [pacetune.vercel.app](https://pacetune.vercel.app). Friends used it until Strava restricted API access.
- For the Shoreditch Half, I had it build a Spotify playlist of the songs from my fastest splits, run through Codex remote. Most were songs from my interval sessions, and they helped on the day. I finished in **1:44:36**.

## [STAGE] Live

Live. Song timing is approximate, and Spotify's history is limited. Track Tunes does something similar; PaceTune's difference is the interface and the shareable cards.
