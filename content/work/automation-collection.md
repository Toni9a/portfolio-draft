> Small tools I built for myself. The one I use most finds the cheapest petrol near me.

## [FUEL FINDER] Cheapest E10, one tap

I wanted the cheapest nearby E10 without opening several apps. **Toni Fuel Finder** is an iPhone Shortcut plus a Scriptable script. It pulls the UK government fuel-price feed and finds me by GPS, or by a town or postcode through Postcodes.io. Then it shows the five cheapest stations with:

- price and distance
- opening hours
- how fresh each price is
- the local average and the saving on a 45-litre fill

Tap a station to open it in Google Maps. A cache covers bad signal.

>> A cheap price from last week isn't worth the drive, so every result shows how old it is.

Version 3.0.1 fixed town and postcode search, which had been calling a location function Scriptable doesn't have. The fix was tested with Petts Wood, Milton Keynes and MK9 1AA. I use it every time I fill up. It ranks by advertised price and straight-line distance, not total trip cost.

[[image:ff-results]]

## [BOSE] An old sound system on the home network

A Python controller drives two BroadLink IR units that run an older Bose system: volume, mute, inputs and power. I took the IR codes from the original remote-control files. One room is verified working.

| Command | Protocol | Device | Subdevice | Function |
|---|---|---|---|---|
| Mute | NEC2 | 186 | 160 | 1 |
| Volume − | NEC2 | 186 | 160 | 2 |
| Volume + | NEC2 | 186 | 160 | 3 |
| TV | NEC2 | 186 | 160 | 14 |
| AUX | NEC2 | 186 | 160 | 15 |
| Power toggle | NEC2 | 186 | 160 | 76 |
| Power on | NEC2 | 186 | 160 | 140 |
| Power off | NEC2 | 186 | 160 | 204 |

## [GALLERY] Two photos in, a calendar out

I built this one for my brother. A workflow turns two of his photos into a scrapbook-style weekly calendar on vintage sheet music. It uploads the result to Drive and texts the link. The log shows three runs: two sent the link, and one uploaded but couldn't send because the Mac was locked. It logged that instead of failing silently.

[[image:gallery]]

## [STEPS] Daily 10K Steps

A signed Shortcut that sends a daily steps text. It works; it's just not switched on at the moment.

Credit: I used Shortcuts Playground, a third-party tool, to build some of these shortcuts. It isn't mine.
