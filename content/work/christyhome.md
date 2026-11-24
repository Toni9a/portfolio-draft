> Furnishing my cousin's house meant measuring the same rooms over and over. I scanned the house in 3D and built her a private app to plan furniture, track the house and keep every manual in one place.

## [THE PROBLEM] Measure, guess, measure again

Choosing furniture for a new house meant measuring the same rooms again and again, then guessing whether a sofa from a shop or a screenshot would fit. Decor decisions dragged on. The boiler, thermostat and bills lived on bits of paper.

## [MY PART] Scan, model and build

I built all of it for my cousin, who uses it. I scanned the house with LiDAR in Polycam, imported the scan into Blender, measured each room from it, and built the web app around those measurements.

[[image:ch-scan]]

## [FROM SCAN TO PLAN] Measurements she can trust

- **The scan.** One Polycam capture of both floors, about 78 m².
- **Blender.** I imported the scan into Blender to work with the model directly, then used Claude to build the floor plans in Blender from the measured dimensions.
- **Cross-sections.** Wall lengths are read from cross-sections of the scan, to about 2 cm. Door and window positions come from Polycam's floor plan.
- **Room models.** A script turns those measurements into a clean 3D model of each room, with doors and windows cut out and a dimension on every wall.
- **Phone friendly.** The original scan crashed iPhone Safari because of its huge textures, so the viewer uses a lighter copy.

[[image:ch-plans]]

## [HOW IT WORKS] Ideas, a fit check and the house manual

- **Ideas per room.** Anyone in the family can add a photo or screenshot of a sofa, bed or lamp with a price and size, then love it, comment or compare up to four side by side.
- **Find it cheaper.** Drop in a photo or describe a piece. Gemini searches the web for the same thing within a budget and size.
- **Try it in the room.** Pick an idea and a room photo. The size and position come from the measured plan, and Gemini draws the piece in and matches the light.
- **Manuals and bills.** The boiler panel, thermostat, meters, energy tariff and broadband, with photos and the key details.

[[image:ch-ideas]]

[[image:ch-try]]

## [DESIGN DECISION] The plan sets the size, not the AI

>> Gemini only draws the piece. The measured room decides how big it is.

Vision models are bad at keeping an item's exact scale. So the size and position come from the room's measured plan, and Gemini only places the piece and matches the light. Even so, I tell her to take the previews with a pinch of salt and use a tape measure when fit really matters.

[[image:ch-find]]

## [WHERE IT IS] In use

It's private, behind an invite link, and my cousin uses it to check furniture and find household details. I also tried a custom GPT she could use from her ChatGPT account, but that didn't work, so the website is where she uses it.

[[image:ch-manuals]]

Built with Next.js, Neon Postgres, Vercel Blob, Gemini for search, previews and meter reading, Polycam, Blender, Claude and Codex.
