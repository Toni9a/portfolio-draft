> People covering the stock count in a corner shop didn't always know where anything was. I scanned the shop into 3D and built the count tools around it.

## [THE PROBLEM] Counting a shop you don't know

Different people came in to do the stock count and didn't know where to find items. The count also had to go onto a printed supplier sheet, in the sheet's order, not the order of the shelves.

## [MY PART] Scanned, modelled, built

I scanned the shop with LiDAR in Polycam, rebuilt the layout in Blender and built two tools: a 3D digital twin of the shop and a count manager. I built them with Google AI Studio and Google Antigravity, with Gemini handling the vision and voice parts.

[[image:cs-scan]]

## [HOW IT WORKS] A digital twin and a count manager

- **The 3D shop.** Every fridge, shelf and island sits where it really is. Search for "Coke" and the matching items glow, everything else fades, and the camera flies over to them.
- **Snap a stock list.** A photo of a handwritten or printed list goes to Gemini, which reads back names, quantities and expiry dates. You check them in a table before anything is saved, and a match updates the existing item rather than adding a duplicate.
- **Count by voice.** Click a shelf, pick a row and say "Red Bull, Red Bull, empty, Monster". The row fills left to right.
- **Expiring soon.** A sidebar lists anything within seven days of its date.
- **Two views of the count.** Shelf view is laid out like the real shelves, because that's fastest to count. Supplier view follows the paper sheet, so the numbers can be copied straight across.
- **Snake import.** Paste a note from your phone. It anchors on a shelf and an item, then the numbers flow along the row the way you walk the aisle.

[[image:cs-layout]]

[[image:cs-manager]]

## [DESIGN DECISION] Built for whoever is on shift

>> The easiest way to count is the way you walk past the shelves.

I had to think like a normal member of staff, not a technical one: left to right, front to back. Matching shelf names to supplier names was fuzzy, so I added a Check Data screen that flags one supplier item linked to several shelves. When you unlink something by hand, the tool remembers and doesn't relink it.

[[image:cs-check]]

## [EVIDENCE] Checked against the real count

- The model comes from a real LiDAR scan of the shop, split into zones: fridge, freezer, crisps, chocolate and bars, cereal, snacks, toiletries and medicines, and water.
- 366 stock lines, each tied to a shelf, row and column.
- I used it alongside the printed supplier sheets during a count.
- Known issue: a few items still display in the wrong slot.

[[image:cs-paper]]

## [NEXT] Corner.OS

Ideas for a customer-facing screen on a display the shop already has: a meal deal suggested from your outfit and the weather, with where to find it; voice questions at the door like "do you have milk?"; and a log of things customers ask for that the shop doesn't stock.

[[image:cs-concept]]

## [STAGE] Prototype

A working prototype, tried on a real count. Not in daily use.
