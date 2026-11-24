> I've saved nearly 2,000 things across X, TikTok, Instagram and Telegram. Tonidex lets me find any of them from my phone when I'm out, for design ideas or something to write about.

## [THE PROBLEM] Saves I couldn't get back to

My saves are spread over four apps, and most of them I never saw again. When I wanted inspiration for a design or a blog post, the good stuff was buried. I wanted to refer to my own saves quickly, even away from my laptop.

## [MY PART] Design and build

I built it on top of my second brain, the system that captures my saves, tags them with Gemini and links them into a graph. Tonidex is how I look at that graph.

## [HOW IT WORKS] Three ways in

- **Map.** Every save sits in a map of concepts. Tap a concept to see what's under it and what it connects to, or search by meaning instead of exact words.
- **Visuals.** A wall of every saved image, captioned by Gemini so I can search it like a mood board.
- **Algorithm.** What I actually keep compared with what the platforms think I like: rising interests, top topics per app, and when I save things.

[[image:td-map]]

[[image:td-visuals]]

## [DESIGN DECISION] Built for a phone in my hand

>> If I can't find it standing in a shop, it doesn't help.

The whole thing works on a phone. Search is by meaning, so "warm minimal packaging" finds things I never tagged that way.

[[image:td-algo]]

## [WHAT IT SHOWED ME] The feed versus what I keep

Since August 2025 I've watched 88,842 TikToks, about 197 a day. I kept 469 of them, about 0.5%.

[[image:td-data]]

## [STACK] How it's built

An HTML canvas front end, Supabase with SQL functions and Edge Functions, Gemini for tagging, captions and embeddings, and Cloudflare R2 for media. It sits behind a sign-in because the saves are mine.
