> Lots of people ask ChatGPT for a training plan. I wanted one built from my own data and the goals I set, and in front of me every day.

[[image:fw-video]]

## [THE PROBLEM] A generic plan, and nowhere to see it

My half-marathon block mixed running, football, strength and mobility. A generic plan didn't fit, and even a good plan is easy to ignore if you have to go looking for it.

## [MY PART] Product, design, direction

I did the product, the design and the direction of the build, in Codex. I'm also the user.

## [HOW IT WORKS] From my data to my lock screen

- **The plan starts from my data.** I exported my Strava history and my Apple Health data (body fat, and food logged in MyNetDiary), put the files into Codex, and set my goals in a ChatGPT chat. The result is a dated plan specific to me, kept in one source of truth in the code.
- **A weekly planner.** Exercise alternatives, weights logged per set, and what I lifted one and two weeks ago.
- **Progress you can see.** A running shoe that fills and tilts as the week completes, with a sparkle at 100%, and an interactive weight plate for each strength session.
- **Taper built in.** The two-week taper, with daily nutrition targets, switched on automatically for those dates.
- **Lock screen.** A Shortcut uploads a background photo once. The server draws today's session over it and sets it as the lock screen, and later runs reuse the saved photo.
- **iOS app.** A small SwiftUI app in TestFlight, just for me, runs workout Live Activities. The current set and a 90-second rest countdown show on the lock screen and Dynamic Island, with +30 sec, Skip and Next set controls.
- **Sharing.** Opt-in public profiles, plus a revocable read-only data link I can hand to a ChatGPT conversation to review the plan.

Built with Next.js, Neon Postgres, Drizzle, private Vercel Blob, SwiftUI and ActivityKit.

[[image:fw-phone]]

## [DESIGN DECISION] What counts as this week

>> Last week's ticks were showing up as done this week.

Progress is now scoped to a London-time Monday week. The fix added week-keyed rows and kept the old data, so nothing was lost.

[[image:fw-web]]

## [EVIDENCE] Live and checked

- Live at [the-full-week.vercel.app](https://the-full-week.vercel.app).
- I ran the Shoreditch Half in **1:44:36** at the end of the block.
- Week-boundary tests, type checks, lint and production builds pass.
- The Apple Health import is built on the server side but paused, because the iOS Shortcuts Health actions don't expose workouts properly yet.

## [STAGE] Live, personal use

Live and in daily personal use.
