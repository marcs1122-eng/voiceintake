# Clean TradingView chart

Pine can't change how the chart itself looks -- candle colours, grid and
background live in **Chart settings** (gear icon, or right-click the chart ->
Settings). Set them once, save them as a template, apply everywhere.

## 1. Symbol tab -- the candles
- Body, Borders, Wick: all **on**. Up `#26A69A`, down `#EF5350` for all three.
  Wicks the same colour as the body, not grey -- wicks are where support and
  resistance show up, so they need to be as visible as the bodies.
- **Color bars based on previous close: off.**
- Session: **Regular trading hours** (intraday). Pre-market is thin and draws
  fake highs and lows.

## 2. Canvas tab -- remove the noise
- Background: solid, `#131722`.
- **Grid lines: off, both.** Horizontal grid lines look like price levels and
  hide the real ones. This is the biggest single fix.
- Watermark: off.
- Scales text size: 14 (bigger if it's hard to read).
- Margins: top 10%, bottom 10%, right 15 bars -- the last candle gets breathing
  room from the price scale.

## 3. Status line tab
- Indicators: turn off **Inputs** and **Values**. Keep Titles.

## 4. Events tab
- Keep **Earnings** (the 5-day earnings rule). Turn off Ideas and News.

## 5. Trading tab (if a broker is connected)
- Buy/Sell buttons: off.

## 6. Save it
Bottom-left of Chart settings: **Template -> Save as... -> "Clean"**.
New chart: open Chart settings -> Template -> Clean.

## Reading support and resistance with no lines
- Use the **daily**, zoomed to 6-12 months, to find the levels. Lower
  timeframes are for timing, not for finding levels.
- Support is where **several wicks stop at the same price**. One wick is
  noise; three or four at the same level is a floor. Same above for resistance.
- Zoom so there's a small gap between candles -- about 80-150 on screen. Too
  many and it's mush; too few and you can't see the history.
- Round numbers ($50, $100, $250) act as levels on their own.
- **Don't use Heikin Ashi.** It looks smooth because it averages prices -- the
  highs, lows and closes it shows are not real prices, so levels drawn off it
  are wrong.

## Where the EMA box fits
Use `ema_cloud_pro.pine` (Pine Editor -> New -> paste -> Save -> Add to chart)
and set **Show -> Box only**. Nothing is drawn on the chart, including the
"Color bars by stack" recolouring, so the clean candle colours above stay put.
Switch to **Full chart** for the cloud and arrows. Alerts work either way.
