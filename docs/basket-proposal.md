# The new basket

Agreed with the user over 2026-10-10/11, and built in two stages. **Stage 1** (58
instruments) is in `config/basket.yaml` on the development branch; before it goes live:
gold and silver round the clock, the final before/after with them, and the user's go.
**Stage 2** comes after the user's pause. Why each choice holds is in `docs/decisions.md`.

## Why change it

The basket of 172 came from a paper and a round of additions. Measured on its stored
events:

- **It saw the world late.** 132 instruments were New York-listed funds. On 2024-08-05 the
  Nikkei had its worst day since 1987, trading 00:00-06:00 UTC; the basket saw Japan at
  14:00 UTC, when EWJ opened, as a `noticeable` weekend gap - not a push.
- **Coins crowded the channel.** Over the year to 2026-10-05 the 16 coins made 88 of the
  247 pushes; 30 of them were one small coin moving alone.
- **Look-alikes.** 62 funds fell in 21 groups holding nearly the same thing, flagging in the
  same hour as their twins: more lines, the same story.

## What a basket like this should watch

1. **Four connected markets** - stocks, bonds, commodities, currencies (Murphy's
   intermarket analysis); the news is often when the usual pattern breaks.
2. **Growth or inflation** (Bridgewater's All Weather): every move answers growth,
   inflation, or fear?
3. **Fear gauges and havens**: the dollar, yen, franc, Treasuries and gold - though not
   always (March 2026's energy shock: the dollar alone).
4. **The world by size**: the US about 64% of world stocks, then Japan 5%, Taiwan, the UK
   and Canada about 3% each (MSCI ACWI, 2026-08-31).
5. **Each market in its own hours**, not through a New York fund.

## The basket (version 5, the user's answers of 2026-10-10)

| group | what it tells | instruments |
|---|---|---|
| stock indices, each in its own hours | how each region feels, as it happens | ASX 200, Nikkei 225, KOSPI, TAIEX, CSI 300, Hang Seng, Nifty 50; Euro Stoxx 50, FTSE 100, SMI; BIST 100, Tadawul, JSE Top 40; S&P 500 (SPY), Russell 2000 (IWM), TSX, Bovespa, IPC |
| US sectors | what leads the biggest market | XLK, XLF, XLE, XLV |
| the price of money | the Fed; inflation; Europe's, Japan's and Britain's own | 2-, 10- and 30-year Treasury futures; TIP; Bund, JGB, gilt |
| credit | do lenders still trust borrowers? | LQD, HYG, EMB |
| currencies | where money runs | EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CAD, USD/CHF, USD/CNH |
| energy | inflation and war | Brent futures; UNG; Europe's gas, TTF |
| metals | fear (gold) and industry (copper) | gold, silver and platinum round the clock; the LME's copper, tin, nickel, aluminium; REMX |
| food | weather, harvests, prices | corn, wheat, soybeans and sugar futures; coffee, cocoa, cotton, live cattle |
| crypto | risk appetite, every hour | Bitcoin, Ethereum, Solana, XRP |

62 instruments; the VIX stays the weekly note's daily line. 142 of the 172 go (the list is
in `config/basket.yaml`'s history).

## Stage 1: built on the development branch (2026-10-11)

**58 instruments**: 30 kept; 9 funds standing in for stage 2's futures (BNO, SHY, IEF, TLT,
CORN, WEAT, SOYB, CANE, PPLT); 19 new - the 16 indices, LME copper, and XAU/USD and
XAG/USD. 133 of the 172, DBC, GLD and SLV left; their bars stay on disk.

Built: a calendar per exchange for the 16 markets; their history from Yahoo (12 back to
2024-10, the CSI 300, BIST 100, TSX and IPC 58 days); copper from Sina with Wallstreetcn's
bars below; voters for 13 indices; the indices named by their own name in messages; the
levels at 4.5 / 6.4 / 9 / 12.7σ; an index's night run to its first hour's close; the code
only the departed instruments used removed; spot gold and silver from SiftingIO (the probe
of 2026-10-12: on time, 0.998-0.999 against Dukascopy; Twelve Data refuses silver), their
history from Dukascopy, Wallstreetcn and Sina as voters.

**Gate B** (the user's): a keyed probe for gold and silver, yes; platinum to stage 2 with
PPLT standing in, yes; the KOSPI, TAIEX and JSE Top 40 without a voter, fine for now.

**Left**: the final before/after with gold and silver in, and the user's go.

## The levels, thought through again (2026-10-11)

- **The test sets a floor, not a level.** Lee & Mykland's 1% line is 3.9σ for a day of 24
  hourly readings (the first ladder's origin), 4.95σ for a coin's year, 5.6σ for the whole
  basket's year. But real hours are not the bell curve: 3.9σ comes once in about 115 hours,
  not once in 10,396 (`docs/decisions.md`, "Rarity is measured"), so at every candidate
  almost every flag is beyond ordinary trading.
- **The tails set the steps.** Large moves thin out about as their size cubed (the inverse
  cubic law); on this basket doubling a move makes it about ten times rarer (`docs/decisions.md`,
  "Words at…"), so √2 steps make each word about three times rarer.
- **Volume sets the bottom.** An alert system wants strong signal and little noise (Google's
  SRE book), and moves of every size hold at the close alike, so a lower bottom brings more
  messages of the same quality: take the lowest bottom whose volume is at or below the old
  basket's. A trader's σ is a standard deviation of daily returns, swollen by the moves it
  measures; the bot's bipower σ leaves them out (`docs/decisions.md`, "Bipower σ"), so its
  "6σ" is not the news's.

## Gate D: the measured before/after (2026-10-11)

By the stage report's scoring and 24-hour events, pushes at `high` and up, young readings
counted, no vote; GLD and SLV standing in for gold and silver. Each cell: the year to
2026-10-05 / the year to 2025-10-05 (2025-04's crash).

| | pushes a week | note rows a week | busiest week's pushes |
|---|---|---|---|
| the 172 at 6 / 8.5 / 12 / 17 | 4.0 / 7.1 | 10.8 / 10.8 | 22 / 151 |
| stage 1 at 3.9 / 5.5 / 7.8 / 11.0 | 6.5 / 6.6 | 15.4 / 9.3 | 21 / 79 |
| stage 1 at 4.5 / 6.4 / 9.0 / 12.7 | 3.7 / 4.5 | 9.9 / 6.3 | 14 / 66 |
| stage 1 at 5 / 7.1 / 10 / 14.1 | 2.4 / 3.4 | 6.8 / 5.0 | 12 / 56 |
| stage 1 at 6 / 8.5 / 12 / 17 | 1.3 / 2.1 | 3.1 / 3.2 | 6 / 38 |

Stage 1 is measured with two index faults fixed, found here: an index's first value is
yesterday's close, so its night now runs to its first hour's close (left in, the indices
pushed 67 times a year at 4.5, not 21); and Hang Seng's and Nifty's history had no nights
(Hang Seng 39 of 490), as a half-hour market's first bar is filed an hour late.

**Read back, 2025-04-07 at 4.5**: the crash is seen in each market's own hours, before New
York's open at 13:00 UTC - Tadawul's Sunday −5.5% (extreme); at 00:00-04:00 UTC the ASX 200
−5.9% (major), Nikkei −7.3%, TAIEX −10.2% (major), Hang Seng −9.6%, Nifty −4.4%; Europe at
07:00, the SMI −6.6% (extreme), FTSE −5.2% and Euro Stoxx −6.6% (major). The 172 saw it at
New York's open.

**The user's answer**: 4.5 / 6.4 / 9.0 / 12.7, both faults fixed. Measured again with
exactly those levels and the fixed code: 3.6 pushes and 10.0 note rows a week (4.4 and 6.3
the year before), the busiest week 14 (65).

## Stage 2: after the pause

- **Futures for the stand-ins**: Brent; the 2-, 10- and 30-year Treasuries; corn, wheat,
  soybeans, sugar; platinum - each read by contract, as the softs are.
- **Bund, JGB, gilt**: as their futures, or as yields once the detector scores a move in
  basis points, which it does not today.
- **TTF**, Europe's gas.
- **Voters** for the KOSPI, the TAIEX and the JSE Top 40.
- **The standing risk**: undocumented endpoints carry most of the basket.

## Sources

- StockCharts, intermarket relationships (Murphy):
  https://articles.stockcharts.com/article/articles-chartwatchers-2011-04-intermarket-picture-points-to-change-in-market-directions/
- SSGA, the All Weather portfolio:
  https://www.ssga.com/us/en/individual/insights/the-all-weather-portfolio-built-for-any-forecast
- Advisor Perspectives, havens failing (March 2026):
  https://www.advisorperspectives.com/articles/2026/03/07/long-trusted-haven-trades-failing-gold-treasuries-fall
- MSCI ACWI factsheet: https://www.msci.com/documents/10199/255599/msci-acwi-net.pdf
- Which high-frequency jump test (Lee & Mykland's constants): https://arxiv.org/abs/1708.09520
- Gopikrishnan et al., the inverse cubic law: https://arxiv.org/abs/cond-mat/9803374
- Google SRE book, monitoring distributed systems:
  https://sre.google/sre-book/monitoring-distributed-systems/
- CFA Institute, the S&P 500's sigma events:
  https://rpc.cfainstitute.org/blogs/enterprising-investor/2012/fact-file-sp-500s-sigma-events?page=1
