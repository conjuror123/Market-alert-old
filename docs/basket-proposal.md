# A new basket: proposal

A working proposal, under discussion with the user since 2026-10-10. Nothing here is in
`config/basket.yaml` yet. Before it goes in: a source for each new instrument, then the
whole basket's measured before/after for the user's go, and one cold rebuild.

## Why change it

The basket of 172 came from a paper and a round of additions. Measured on the stored
events (`data/jump/jumps.parquet`):

- **It sees the world late.** 132 instruments are New York-listed funds, so a market
  abroad is seen only in New York's hours. On 2024-08-05 the Nikkei had its worst day
  since 1987, trading 00:00-06:00 UTC; the basket saw Japan at 14:00 UTC, when EWJ
  opened, as a `noticeable` weekend gap in the note - not a push.
- **Coins crowd the channel.** Over the year to 2026-10-05 the 16 coins made 88 of the
  247 pushes; 30 of them were one small coin moving alone.
- **Look-alikes.** 62 funds fall in 21 groups that hold nearly the same thing (three gold
  funds, five mortgage-bond funds, four TIPS funds, ...). They mostly flag in the same
  hour as their twin: more lines, the same story.

## What a basket like this should watch

From the sources below, five ideas:

1. **Four connected markets** - stocks, bonds, commodities, currencies (Murphy's
   intermarket analysis). They move in known ways together; the news is often when the
   usual pattern breaks.
2. **Growth or inflation** (Bridgewater's All Weather): stocks, commodities and credit
   like growth; government bonds like a slowdown; commodities, inflation-linked bonds and
   gold like inflation. Every move answers: growth, inflation, or fear?
3. **Fear gauges and havens**: the dollar, yen, franc, Treasuries and gold in a crisis -
   though not always (March 2026's energy shock: the dollar alone).
4. **The world by size**: the US about 64% of world stocks, then Japan 5%, Taiwan, the UK
   and Canada about 3% each (MSCI ACWI, 2026-08-31).
5. **Each market in its own hours**: a price that trades round the clock, or in Tokyo's
   or London's day, is watched there, not through a New York fund.

## The basket (version 5, the user's answers of 2026-10-10)

| group | what it tells | instruments |
|---|---|---|
| stock indices, each in its own hours | how each region feels, as it happens | ASX 200, Nikkei 225, KOSPI, TAIEX, CSI 300, Hang Seng, Nifty 50; Euro Stoxx 50, FTSE 100, SMI; BIST 100, Tadawul, JSE Top 40; S&P 500 (SPY), Russell 2000 (IWM), TSX, Bovespa, IPC (18; 16 new) |
| US sectors | what leads the biggest market | tech, financials, energy, health care (XLK, XLF, XLE, XLV) (4) |
| the price of money | the Fed; inflation; trust in debt; Europe's, Japan's and Britain's own | 2-, 10- and 30-year Treasury futures, read by contract (new); TIP; Germany's, Japan's and Britain's 10-year bonds - Bund, JGB, gilt (new) (7) |
| credit | do lenders still trust borrowers? | LQD, HYG, EMB (3) |
| currencies | where money runs | EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CAD, USD/CHF, USD/CNH (7) |
| energy | inflation and war | Brent futures, read by contract (new); UNG; Europe's gas, TTF (new) (3) |
| metals | fear (gold) and industry (copper) | gold, silver and platinum round the clock, XAU/USD, XAG/USD, XPT/USD (new); the LME's copper (new), tin, nickel, aluminium; REMX (8) |
| food | weather, harvests, prices | corn, wheat, soybeans and sugar futures (new, for CORN, WEAT, SOYB, CANE); coffee, cocoa, cotton, live cattle (8) |
| crypto | risk appetite, every hour | Bitcoin, Ethereum, Solana, XRP (4) |

62 instruments: 30 of today's, and 32 new. VIX stays as it is today, the daily line on the
weekly note, not an hourly instrument.

The 142 of today's that go:

| block | out |
|---|---|
| equity (55) | XLY, XLP, XLI, XLB, XLU, XLRE, XLC, SMH, KRE, XBI, ITB, IYT, QQQ, DIA, RSP, MDY, XRT, XME, XPH, IHI, VDC, VHT, VPU, SOXX, IGV, FDN, CIBR, SKYY; the country and region funds EFA, EEM, EWJ, EWG, EWU, EWQ, EWC, EWA, EWL, EWN, EZU, FXI, EWZ, EWW, INDA, EPI, EWY, EWT, EZA, TUR; real estate VNQ, IYR, RWR, SCHH, REM, VNQI, RWX |
| rates (19) | SHY, IEF, TLT, IEI, TLH, MBB, GOVT, SCHO, VGIT, VGLT, SPTL, BWX, VTIP, SCHP, STIP, VMBS, SPMB, LMBS, JMBS |
| credit (23) | EMLC, JNK, BKLN, PFF, VCIT, VCSH, IGIB, SPIB, USIG, QLTA, GIGB, SLQD, SHYG, USHY, ANGL, SRLN, FALN, VWOB, PCY, EBND, LEMB, EMHY, CEMB |
| energy (6) | USO, BNO, UGA, DBO, DBE, UNL |
| precious metals (8) | GLD, SLV, PPLT, PALL, IAU, SGOL, SIVR, GLTR |
| industrial metals (4) | DBB, CPER, LIT, SLX |
| agriculture (5) | CORN, WEAT, SOYB, CANE, DBA |
| pairs (10) | USD/NOK, USD/MXN, USD/BRL, USD/INR, USD/KRW, USD/ZAR, USD/TRY, NZD/USD, USD/SEK, USD/PLN |
| coins (12) | LTC, BCH, LINK, ADA, DOGE, AVAX, DOT, POL, UNI, ATOM, FIL, AAVE |

## The user's answers

Each was the proposal's own critique, measured where it could be.

**Round 1** (on version 1, 2026-10-10):

| | change | answer | evidence |
|---|---|---|---|
| 1 | one oil, in its own hours | yes: Brent futures, read by contract | USO and BNO flagged in the same hour 18 of 22 times (three years to 2026-10-05); 4 of Wallstreetcn Brent's 8 moves of 6 sd or more, 2026-04-22 to 10-09, were Monday-morning gaps after a weekend |
| 2 | copper from the LME | yes: LME copper for CPER; DBB and LIT go; tin, nickel, aluminium, platinum, rare earths stay | LME copper's two big moves in that window were in London's morning |
| 3 | gold and silver | round the clock, XAU/USD and XAG/USD (the user's; the proposal had kept the funds) | gold's four big moves in that window were in New York's hours |
| 4 | drop QQQ | yes | the S&P 500 and Nasdaq 100: hourly correlation 0.95, 33 of 53 big hours together (Yahoo, 2023-11 to 2026-10); XLK flagged in each of QQQ's 8 hours |
| 5 | one of Euro Stoxx 50 and DAX | yes: Euro Stoxx 50 | hourly correlation 0.93 (the CAC 0.92); the FTSE its own (0.75) |
| 6 | sectors 11 → 4 | yes: tech, financials, energy, health care | of 20 sector pushes in three years, 16 came with SPY, QQQ or IWM flagging too |
| 7 | drop the dollar index | yes | with EUR/USD: correlation −0.92, 76 of 139 big hours together |
| 8 | the giants (Nvidia, Apple, ...) | no | - |
| 9 | drop LIT | yes | battery makers, already in tech; not measured |
| 10 | drop BKLN, keep HYG | yes | BKLN 23 flags in three years to HYG's 12, together 7; its lone flags not checked |
| 11 | Asian indices ring at night; no quiet hours | fine as it is | - |

**Round 2** (on version 2, 2026-10-10; none of it measured):

| | change | answer |
|---|---|---|
| 1 | Treasuries as futures, in their own hours | yes: 2-, 10- and 30-year futures; TIP stays a fund |
| 2 | platinum round the clock | yes: XPT/USD for PPLT |
| 3 | grains and sugar as futures, like coffee | yes; sources later |
| 4 | drop gasoline (UGA) | yes; UNG stays |
| 5 | drop EMLC | yes, EMB stays; and the pairs cut to seven: EUR, JPY, GBP, AUD, CAD, CHF, CNH (the user's) |
| 6 | VIX and MOVE | MOVE dropped; VIX stays as today |
| 7 | the pairs as the loudest group | no longer, at seven |
| 8 | iron ore | no |
| 9 | Saudi Arabia's index | yes, with the index list above: Tadawul, JSE Top 40 and SMI added (the user's) |

**Round 3** (on version 3, 2026-10-10): VIX stays the note's daily line, not an hourly
instrument (confirmed); of the US sectors and industries only tech, financials, energy and
health care stay - SMH, KRE, XBI, ITB and IYT go.

**Round 4** (on version 4, 2026-10-10): the Bund, the JGB and the gilt added, for the gap
the proposal named: no bonds outside the US, though Britain's gilt crisis (2022) and
Japan's rising yields (since 2024) were among the largest stories of recent years. Not
taken: bringing back the emerging-market pairs (the lira first), offered for the local
indices' blind spot - an index in local money can hide its currency's crash. The user's:
the Turkish index carries Turkey.

Version 1's trim alone (the 86 of today's that it kept, nothing added) moved the year to
2026-10-05 from 247 pushes to 135.

## Version 5, measured (2026-10-10)

**The 30 it keeps**, from the stored events - exact:

| year to | today's 172: pushes | the 30 kept: pushes | of them, the 7 pairs and 4 coins |
|---|---|---|---|
| 2026-10-05 | 247 | 52 | 22 and 20 |
| 2025-10-05 | 421 | 95 | - |

**The 16 new indices**, from Yahoo's hourly bars - rough. A rough copy of the detector:
bipower σ over the 182.6 days before, hours against hours and the night (with its first
hour, since an index's first open on Yahoo can sit at the last close) against nights,
one event per 24 hours, a push at 8.5σ; no vote, no held check. Checked on 16 funds the
store holds (SPY, IWM, four sectors, ten country funds): 61 events and 13 pushes to the
store's 62 and 15 in the year to 2026-10-05; 61 and 25 to 81 and 29 in the year before,
so an undercount in a stormy year.

| year to | events | pushes | the loudest |
|---|---|---|---|
| 2026-10-05 | 36 | 8 | BIST 100 (5 events, 3 pushes), KOSPI (5, 0) |
| 2025-10-05 | 52 | 26 | BIST 100 (7, 4); Euro Stoxx 50, Tadawul, TSX (3 pushes each) |

The Hang Seng had no event in the year to 2026-10-05: its largest hour reached 5.6σ.

**Not measured**: the other 16 new instruments - the Treasury, Bund, JGB, gilt, Brent,
TTF, grain and sugar futures, the three metals round the clock, LME copper - until their
sources are chosen.

So in all, before those 16: about 60 pushes in the year to 2026-10-05 against today's
247, and about 120 or more in the year before against 421 - a quarter of today's.

**The lira** (the user's no, round 4). The proposal said a lira crash could leave the
Turkish index flat or even up. In the one lira crash within Yahoo's hourly reach,
2025-03-19 (USD/TRY +5.7% in an hour, 95σ), BIST 100 fell 10.1% over two days, its
hours down to 11.5σ: it would have pushed. The proposal's claim was wrong for it. Yahoo's
USD/TRY otherwise flags on the lira's managed crawl: most of its other 6σ hours are a
0.3-0.4% tick and its reversal the hour after.

## Still to do

- **Sources** for the 32 new instruments, each with voters (to be worked out with the
  user). Seen on 2026-10-10: Yahoo serves about three years of hourly bars for the indices
  it was asked for (from late 2023) and TTF from 2024-05, without volume, each on its own
  minute (:00, :30, Nifty :45). `exchange_calendars`, which builds the NYSE and B3 tables,
  has all 16 exchanges abroad.
- **How the three foreign bonds are read**: as their futures (Eurex's Bund, Osaka's JGB,
  ICE's long gilt), prices scored as any other; or as yields, once the detector scores a
  move in basis points rather than as a return, which it does not today.
- **The measured before/after** of version 5, for the user's go.
- **The standing risk**: undocumented endpoints carry most of it, as they do today.

## Stage 1: the build (planned 2026-10-11)

Version 5 will not all be built before the user's long pause, so it comes in two stages.
Its levels are set again, since version 5 pushes about a quarter of today's volume: the
user's first wish is the ladder the detector started with on 2026-09-28, **3.9 / 5.5 /
7.8 / 11.0σ** (3.9σ and √2 steps), raised to today's 6 / 8.5 / 12 / 17 on 2026-10-04 for
volume (29.1 messages a week at 3.9 against 9.0, the delivery replayed over the year to
2026-10-01). The ladder is researched again (task 9) and chosen at gate D.

**Stage 1: 58 instruments.** The 30 kept; 9 funds standing in for what is not built yet -
BNO (Brent), SHY, IEF, TLT (Treasuries), CORN, WEAT, SOYB, CANE (grains, sugar), PPLT
(platinum, gate B) - so nothing goes blind over the pause; 19 new: the 16 indices, LME
copper, and XAU/USD, XAG/USD (GLD and SLV stay if no round-the-clock source passes). 133
of today's go; their stored bars stay on disk.

**Stage 2, after the pause**: the 11 futures (Brent, 2-, 10- and 30-year Treasuries,
corn, wheat, soybeans, sugar, Bund, JGB, gilt), platinum's futures and TTF, in place of
their stand-ins.

All of it is built and measured on the development branch; nothing reaches the channel
before the measured before/after and the user's go.

| | task | gate |
|---|---|---|
| 0 | this record | |
| 1 | baseline: `tools/stage_report.py` on today's 172 at today's levels | |
| 2 | the 38 existing instruments of stage 1 at both ladders (a scratch worktree with an edited, uncommitted basket: the report reads `config/basket.yaml`) | A: shown to the user |
| 3 | sessions for the 16 markets (`jump/sessions.py`, `DAILY_SESSIONS`): trading-day tables from `exchange_calendars` so a long closure is a gap, not a source out; Tadawul's Sunday-Thursday week; hours that change by date (Tokyo's close 15:00 → 15:30 on 2024-11-05, B3 with US daylight saving) | |
| 4 | the indices from Yahoo: live at 30 minutes (15 for Nifty) folded onto the round hour (`jump/bars.py`, `to_hourly`); 1-hour history, the :30 and :45 markets' bars labelled by the hour they end in, checked against 59 days of folded 30-minute bars | |
| 5 | LME copper: Sina's, Wallstreetcn's UKCA.OTC as voter and history below | |
| 6 | gold and silver round the clock: a provider by the four questions, from a keyed probe of SiftingIO and Twelve Data (gate B; about ten requests - the 7 pairs leave SiftingIO about 3,600 of 10,000 calls a month, the two metals would add about 1,000); history from Dukascopy | |
| 7 | voters: an `indices` class and a round-the-clock metals class in `jump/verify.py`; copper joins `lme` | B: each new instrument has bars and a voter, or is named |
| 8 | `config/basket.yaml`: 133 out, 19 in, one commit | |
| 9 | the levels thought through again: search the web (the jump test's own critical values, how alerting systems set thresholds, how traders read sigma moves) and propose a ladder with reasons; candidates at least the first 3.9 / 5.5 / 7.8 / 11.0, a 5σ ladder and today's 6 / 8.5 / 12 / 17 | |
| 10 | delivery read with the new instruments; a cold rebuild on the development branch for measuring only - not committed, the live run rebuilds after the merge; the new instruments' open month comes from the first live fetch (`tools/hot_bars.sh`); a cold first run of 58 inside the hourly job's 20 minutes | |
| 11 | measured before/after: today (172 at 6σ) against stage 1 at each candidate ladder, by block, with windows | D: the user's go and ladder |
| 12 | `detector.levels` to the chosen ladder, a commit of its own; the vote's candidates and its 40-request budget checked | |
| 13 | docs: manual, decisions, README | |
| 14 | `pytest -q`, alone | |
| 15 | the live branch, on the user's go only; a week of watching | |

### Gate A: the levels on the 38 existing instruments (measured 2026-10-11)

By the stage report's own scoring and 24-hour events (`tools/stage_report.py`), only the
instruments and the levels changed; young readings counted, as live delivers them; no
vote. Today's basket by this method: 211 pushes in the year to 2026-10-05 (the live
store, with the vote and delivery, holds 247) - so compare within the table only.

| | pushes a week | note rows a week | pushes, of them coins + pairs | busiest week's pushes |
|---|---|---|---|---|
| **year to 2026-10-05** | | | | |
| today's 172 at 6σ | 4.0 | 10.8 | 211: 68 + 47 | 22 |
| stage 1's 38 at 6σ | 1.0 | 2.5 | 54: 15 + 18 | 5 |
| stage 1's 38 at 5σ (5 / 7.07 / 10 / 14.14) | 2.0 | 5.2 | 104: 23 + 38 | 7 |
| stage 1's 38 at 4σ (4 / 5.66 / 8 / 11.31; not the first ladder, which began at 3.9) | 4.7 | 11.2 | 243: 74 + 74 | 13 |
| **year to 2025-10-05** | | | | |
| today's 172 at 6σ | 7.1 | 10.8 | 368 | 151 |
| stage 1's 38 at 6σ | 1.8 | 2.8 | 93 | 26 |
| stage 1's 38 at 5σ | 2.9 | 4.3 | 149: 31 + 66 | 38 |
| stage 1's 38 at 4σ | 5.3 | 7.2 | 278 | 54 |

A lower ladder raises the round-the-clock markets most, as they have the most hours: at
4σ the four coins push 74 times in the year to 2026-10-05, today's sixteen 68; the seven
pairs 74, today's seventeen 47. The 20 new instruments are not in these numbers.

### Gate B: bars and voters for the new instruments (answered 2026-10-11)

| | state | the user's answer |
|---|---|---|
| the 16 indices | Yahoo's bars: 12 back to 2024-10; the CSI 300, BIST 100, TSX and IPC 58 days, their older hours having failed the import gate; voters for 13 | the KOSPI, TAIEX and JSE Top 40 without a voter: fine for now |
| LME copper | Sina's bars, Wallstreetcn's below them back to 2026-04-23; Wallstreetcn votes | |
| gold and silver | no round-the-clock source measured: Dukascopy has their history, Wallstreetcn a voter's bars; SiftingIO's catalogue lists XAUUSD and XAGUSD, Twelve Data XAU/USD and XAG/USD, both behind keys | a keyed probe of the two, about ten requests: yes |
| platinum | no round-the-clock source: Dukascopy and Wallstreetcn have no spot platinum, Yahoo only the futures | to stage 2, PPLT standing in: yes |

### Task 9: the levels, thought through again (2026-10-11)

Four questions, each from its own source.

**What the test itself says.** Lee & Mykland's test asks whether the largest move among n
readings is too big for ordinary trading, at a chosen error rate. In the bot's σ (bipower,
already scaled to an ordinary σ), their 1% line is:

| readings judged together | n | the 1% line |
|---|---|---|
| one day of a market abroad | 7 | 3.85σ |
| one day of a 24-hour market | 24 | 3.89σ |
| one week of a 24-hour market | 168 | 4.20σ |
| one year of a fund or index | 1,750 | 4.65σ |
| one year of a coin | 8,760 | 4.95σ |
| one year of the whole stage 1 basket | about 350,000 | 5.60σ |

The first ladder's 3.9 is the line for one day of 24 hourly readings: its first commit
(a100623) set it "for now, to be tuned at the end against the exact 99% level". The line
comes from an asymptotic formula, and at 24 readings it is conservative: on the bell curve
the exact 1% is 3.53σ. The comparison of jump tests finds the test undersized at low
frequencies (Maneesoonthorn et al.), and its norming constants have been argued over and
upheld (Nunes & Ruas 2024).

But the bell curve is not what real hours do. On it, an hour reaches 3.9σ once in 10,396
hours. In the bot's records, an hour of every class does so once in about 115, 90 times as
often (docs/decisions.md, "Rarity is measured"). So at every candidate bottom, almost
every move flagged is beyond what ordinary trading explains. **The test sets a floor, not
a level**: below about 3.9σ a move cannot be told from an ordinary hour, even within a
single day. Above it, the test cannot choose between 3.9, 5 and 6.

**What the tails say.** Large moves thin out as a power of their size. In US stocks the
chance of a move falls about as its size cubed: the "inverse cubic law" (Gopikrishnan et
al. 1998, tail exponents 2.8–3.1, over 5–120 minute returns). On this basket, doubling a
move in σ makes it about ten times rarer (docs/decisions.md, "Words at…"). So words √2
apart are each about three times rarer than the one below, whatever the bottom: **keep the
√2 steps.**

**What alerting practice says.** An alert system should have "strong signal and very
little noise", and a page is costly because it takes a person away from their work
(Google's SRE book, ch. 6). Alerts that need no action are cut, and only what needs
attention should ring (PagerDuty, Squadcast). The bot already found that moves of every
size hold at the close alike (76–80%, docs/decisions.md). A lower bottom therefore brings
more messages of the same quality, not worse ones: **the bottom is a volume choice.**

**What traders mean by "σ".** Not this bot's σ. For the S&P 500's daily closes, moves of
5σ or more came 0.68 times a year over 1950–2012, and 56% of them fell in 1987 and 2008
(CFA Institute). A trader's σ is a standard deviation of daily returns, swollen by the very
moves it measures. The bot's bipower σ leaves them out (docs/decisions.md, "Bipower σ"), so
the same move reads as more σ here. "6σ" in this channel and "6σ" in the news are
different scales; neither is wrong.

**The proposal.** Keep √2 steps. Choose the bottom by volume, as the 6σ bottom was chosen
(2026-10-04). Task 11 measures four bottoms on the whole stage 1 basket:
- 3.9 / 5.5 / 7.8 / 11.0: the first ladder, at the test's floor
- 4.5 / 6.4 / 9.0 / 12.7
- 5 / 7.1 / 10 / 14.1: about the test's 1% line for one instrument's year
- 6 / 8.5 / 12 / 17: today's

The recommendation: **the lowest bottom whose stage 1 volume is at or below today's**,
about 4 pushes and 10 note rows a week (docs/manual.md, "Expected volume"). The channel
carries that volume now, and the complaint was what it is about, not how much of it there
is.

Gate A already puts the first ladder near that volume before the 19 new instruments: the
38 kept at 4σ gave 4.7 pushes and 11.2 note rows a week, against today's 172 at 4.0 and
10.8 (year to 2026-10-05). So 3.9 will likely land above today's volume once the indices,
copper, gold and silver are in, and 4.5 or 5 near it. That is a guess until task 11
measures it.

## Sources

- StockCharts, intermarket relationships (Murphy):
  https://articles.stockcharts.com/article/articles-chartwatchers-2011-04-intermarket-picture-points-to-change-in-market-directions/
- LuxAlgo, intermarket analysis: https://www.luxalgo.com/library/concept/intermarket-analysis/
- A macro panel: https://www.thetrading.tools/macro-panel
- SSGA, the All Weather portfolio:
  https://www.ssga.com/us/en/individual/insights/the-all-weather-portfolio-built-for-any-forecast
- Banque de France, safe assets:
  https://www.banque-france.fr/en/publications-and-statistics/publications/have-us-treasuries-lost-their-momentum-evidence-new-taxonomy-safe-assets
- Advisor Perspectives, havens failing (March 2026):
  https://www.advisorperspectives.com/articles/2026/03/07/long-trusted-haven-trades-failing-gold-treasuries-fall
- MSCI ACWI factsheet: https://www.msci.com/documents/10199/255599/msci-acwi-net.pdf
- S&P 500 concentration:
  https://landmarkwealthmgmt.com/articles/the-evolution-of-sp-500-top-10-companies-how-tech-giants-captured-nearly-40-of-the-index-by-2026/
- The yen carry trade, August 2024:
  https://www.advisorperspectives.com/commentaries/2024/08/12/understanding-yen-carry-trade-impact-world-markets
- TTF's record, 2022:
  https://www.spglobal.com/energy/en/news-research/latest-news/natural-gas/081622-dutch-ttf-prices-hit-all-time-high-with-no-signs-of-slowing
- Which high-frequency jump test (Lee & Mykland's norming constants; its size at low
  frequencies): https://arxiv.org/abs/1708.09520
- Nunes & Ruas, the Gumbel convergence of the Lee-Mykland tests (Finance Research Letters,
  2024): https://repositorio.iscte-iul.pt/bitstream/10071/31168/1/article_100198.pdf
- Gopikrishnan et al., the inverse cubic law: https://arxiv.org/abs/cond-mat/9803374
- Google SRE book, monitoring distributed systems:
  https://sre.google/sre-book/monitoring-distributed-systems/
- PagerDuty, alert fatigue: https://www.pagerduty.com/blog/uncategorized/lets-talk-about-alert-fatigue-2/
- Squadcast, alert noise: https://www.squadcast.com/blog/optimizing-your-alerts-to-reduce-alert-noise
- CFA Institute, the S&P 500's sigma events:
  https://rpc.cfainstitute.org/blogs/enterprising-investor/2012/fact-file-sp-500s-sigma-events?page=1
