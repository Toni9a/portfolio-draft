> A local florist in Northampton sold through Instagram. I turned her image library into a bouquet chooser that customers can use on their phone, with a stock admin behind it.

## [THE PROBLEM] A great Instagram, hard to shop from

Years of bouquets lived in posts and Highlights. A customer who wanted "something pink under £60" had to scroll and message. The florist also had no way to show what was in season or in the shop that day, and no presence on Google beyond Instagram.

## [MY PART] Archive, tagging, design and build

I pulled the archive down, tested the AI tagging locally, built the front end and the admin, and took the design through three rounds with the florist. Claude Code orchestrated the build.

[[image:lf-v1v2]]

## [HOW IT WORKS] From posts to a chooser

- **Archive.** An actor and Playwright downloaded her posts and Highlights onto my Mac, with Highlights split by when they were posted.
- **Tagging.** Each image was tagged for flower type, colour, wrapping paper and any visible price, with OCR for text.
- **Bouquet chooser.** Customers pick colour, flower type and budget and see real bouquets she has made.
- **Admin.** The florist marks what's in stock and what's in season, so the chooser only shows what she can make.
- **Shopify version.** A Shopify theme of the same site, ready if she wants to switch later.

[[image:lf-chooser]]

## [DESIGN DECISION] Run the bulk pass locally

>> Spend nothing on the first pass, then check it against the paid models.

I compared three vision approaches. I ran Qwen3-VL 8B locally overnight for the bulk tagging so I wasn't spending credits, after tuning it on a couple of flowers myself. Then I checked samples against OpenAI vision in Codex and against Gemini. Gemini was the most accurate in my tests. I treated the tags as a first pass and spent my time building with them, not correcting every flower name by hand.

[[image:lf-bouquet]]

## [DESIGN] Two versions, three rounds

The site has two versions she can switch between with the V1 / V2 toggle in the header. V1 opens on her bouquets and goes straight to browsing. V2 opens on her pink shopfront: as you scroll, you walk through the door and into the shop, then reach the same chooser.

[[image:lf-walk]]

Both are designed for a phone first. Over three rounds with the florist we worked through details like music and sales. Her own video drives the scroll effects, and the logo animates with a pen-stroke reveal of the original artwork.

[[image:lf-peonies]]

## [EVIDENCE] What's in it

- 487 bouquets live in the chooser.
- 1,200 still images in the final library: 689 from posts and 511 from Highlights.
- Three design rounds with the florist.
- OCR picked up prices on some images, not all.
- Still in development. The florist may start using it soon.

Built with an actor, Playwright, Qwen3-VL 8B, OCR, OpenAI vision, Gemini, Claude Code, Vite, Vercel and Shopify Online Store 2.0.
