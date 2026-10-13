# Decisions

Why the bot is built the way it is, so a settled choice is not reopened: each entry is the
choice, then its reason. How each part works is in `docs/manual.md`; the longer story of
each is in git history.

**Contents:** The detector · Delivery · Data and providers · The sources' vote · The stored
history · The repository · Rejected · Open questions

---

## The detector

**An established test, not a home-made one.** The intraday jump test of Lee & Mykland
(2008, *Review of Financial Studies* 21:6): every setting has a published or a measured
reason; a hand-made threshold table has only taste.

**Bipower σ, not a standard deviation.** It averages products of neighbouring moves (L&M
eq. 8), so a jump in the window never pairs with itself. With squares, one 0.05 jump among
0.001 moves inflates σ more than 1.5× (`tests/test_jump_jumps.py`).

**Half a year of calendar time, for every instrument.** Volatility regimes follow the
world's calendar, not a market's hours; half a year is inside the paper's valid range for
every calendar (880 bars for a fund, 4,380 for a coin).

**A young series scores from the paper's minimum** (42 bars for a fund, 78 for a 24-hour
market), marked `young`. A half-year warm-up would have left thirteen funds blind through
March 2020.

**Words at 4.5 / 6.4 / 9 / 12.7σ** (the user's, 2026-10-11). Doubling a move's size in σ
makes it about ten times rarer on this basket, so words √2 apart are each about three times
rarer to reach than the one below: over the 58's history, 9,604, 3,227, 1,056 and 304
events at or above them. The bottom is a volume choice - moves of every size hold at the
close alike (76–80%), so a higher bottom buys fewer messages, not better ones - set at the
lowest whose volume is at or below the old basket's: 3.6 pushes and 10.0 note rows a week
against 4.0 and 10.8, over the year to 2026-10-05 (`docs/basket-proposal.md`, gate D). The
ladder began at 3.9σ (2026-09-28) and was 6σ for the 172 (2026-10-04).

**Rarity is measured, not read off the bell curve.** Against its own half-year σ, an hour
of every class reaches 3.9σ about once in 115, not once in 10,000.

**Gaps are read against their own kind.** Nights against nights, weekends against weekends,
over the same half-year: clock time does not scale a gap (a 65-hour weekend moves only 1.17×
a 17.5-hour night, French & Roll 1986), and σ borrowed from trading hours predicted the next
gap worst of all yardsticks measured.

**A stock index's night runs to its first hour's close** (the user's, 2026-10-11). Its first
value is computed from its stocks' last closes before most of them trade, so the night's
move comes in during the first hour: read as an hour, an ordinary opening gap was a 13σ hour
(FTSE 100, 2026-03-03), and 15 of FTSE's 16 events in the year to 2026-10-05 were first
hours. A fund's first price is a trade, and its night ends there.

**A missing hour is skipped, not stretched.** The bar after a hole is its own hour; measured
across the hole, three quiet hours read as one violent one. Only closures the calendar knows
are gaps.

**Beyond 1,000σ is a broken print, and so is the stretch after it**, until the price is back
within half of it, at most 24 hours. The largest real readings sit far below (PFF −207σ,
2015-08-24); dropping one shrinks later yardsticks, so the check repeats until none is left.

**One event per 24 real hours.** A storm of hours is one story; real hours, not a trading
day, give every instrument the same span.

**Rarest since: the last move at least 95% as large, of the same kind and direction**, in σ
so the line and the colour speak one ladder; elapsed time rounded down, so the claim stays
true.

**Held at the close: one check, at the first NYSE close after the move, for everything.**
That close shows a real fade above the noise (a fund's `high` hour: 79% half held, against
95% for a random walk); further out a random walk alone says "gave back" for 14–26% of moves.

**A detector update restarts the week only if it changes the week's events.** The version
hashes parsed code, so a comment does not count, and a change that moves no event keeps the
week's messages.

---

## Delivery

**Rarity is the instrument's; interruption is the reader's.** A word depends only on its
instrument, so adding instruments changes no word's meaning; how often the reader is
interrupted is set by which words push.

**No weekly cap.** A detector that falls silent after its third alert fails in exactly the
week records cluster.

**`high` and up push; `noticeable` goes into the weekly note**: two thirds of events, worth
reading in a batch.

**The week turns at the run after its last NYSE close**, so a week holds all its moves'
checks. The economic calendar is its own message, just before the note.

**The open week is curated; earlier weeks are history**, so a cold rebuild cannot rewrite a
closed record or post its difference as new alerts.

**The note is read by block, in time inside** (the user's, 2026-10-08): what moved together
is read together. It is cut between blocks; only a block longer than a message is cut,
"continued".

**Rarer rings again inside the 24 hours; milder never rings.** A change says so on one line
(`✏️ ⬜ 6.2×σ 10:00 → 🟧 12.4×σ 12:00 bigger jump`); after the 24 hours a fix corrects
silently, and a lifted doubt comes off by an edit.

**The moves one run finds share messages, biggest first, and only the first rings.** News
moves dozens of instruments at once (91 events in the FOMC hour of 2024-12-18), and Telegram
takes about twenty messages a minute into a channel.

**Size in σ, word as the colour.** A percentage means nothing across a basket where short
Treasuries move 0.024% in a usual hour and a coin several per cent.

**Names**: a pair against the dollar by its other currency (`USD/JPY · Yen`: the ticker
already says which way it is quoted); a stock index abroad by its own name and place
(`Nikkei 225 · Japan`), as Yahoo's ticker (^N225) is Yahoo's only; anything else by its
ticker, what a reader types into a chart.

**A reading is judged only once its bar has ended.** The run at :05 holds five minutes of
the current hour.

**Quality is recall on the obvious, not precision.** Of each instrument's top 0.01% of
hours, how many are flagged and at which word (`tools/stage_report.py`); precision rewards
delay.

---

## Data and providers

**The basket of stage 1: each market in its own hours, each story told once** (the user's,
2026-10-10/11, `docs/basket-proposal.md`). The 172 came from a paper; it saw the world
through 132 New York funds, so the Nikkei's worst day since 1987 reached it at New York's
open, and it was crowded by coins and look-alikes. Stage 1 holds 58: 16 stock indices in
their own hours beside SPY and IWM, four sectors, copper beside the LME's other metals,
seven pairs, spot gold and silver round the clock, four coins. **Stage 2** (2026-10-12)
puts the futures in place of the funds that stood in for them - Brent, the 2-, 10- and
30-year Treasuries, corn, wheat, soybeans, sugar and platinum for BNO, SHY, IEF, TLT,
CORN, WEAT, SOYB, CANE and PPLT - and leaves out the Bund, JGB, gilt and TTF, which no
free source carries live (the user's). The 134 that left in stage 1 and the nine funds
keep their bars on disk; the code only they used went with them. The rates block (the 2-,
10- and 30-year) is kept as it measures (the user's, 2026-10-13: "it is ok"): 9 pushes a
year as funds, 31 as futures, mostly the 08:00 ET hour of a data release and FOMC's 14:00,
their 23-hour sessions reading a release hour at 10-13σ.

**The Bund, the long gilt, TTF and Japan's 10-year yield join from MarketWatch**
(2026-10-13; the user's: "add everything good, if something missing - we could try and
find later"). The only free live source of each, hourly about nine trading days back,
without volume, so no thin-bar rule:
- the Bund and the gilt one contract at a time, rolled where their volume moves (the
  Bund three business days before its last trading day, the gilt five before first
  notice), each session's hours what the live source or the history holds (08:00-18:00
  Frankfurt, 08:00-18:00 London); their history from Dukascopy's CFDs (the Bund's 0.4 bp
  from MarketWatch's contract on 20 shared hours); the Bund voted by the FT's S&P
  Euro-Bund futures index (0.95, four bars a day), the gilt by none;
- TTF as MarketWatch's continuous series (it names no single month), its roll nights
  unscored from the exchange's rule; no hourly history anywhere, so it scores once it has
  its half-year window (about 2027-04);
- the JGB as its yield, as no source carries the future: its move read and said in basis
  points (`unit: bp`). Wallstreetcn's yield is 0.4 bp from MarketWatch's at the median but
  holds only 104 days and moves with it at 0.70 hour by hour (both a bp or so an hour);
  not spliced. Like TTF it scores from about 2027-04.

The rates block then holds six beside TIP.

**One provider per instrument, chosen by measurement**, against the stored bars hour by
hour in basis points: a feed a few bp off on a thin fund sends alerts for moves that did
not happen.

**A candidate source answers four questions, cheapest first:** does it serve the :00 bar by
:05; does its allowance cover the load; does it match the consolidated tape on thin names;
which tickers, how far back.

**A fund goes to an IEX-only feed only if IEX prices it like the tape** (median ≤ 2 bp,
p90 ≤ 5, ≤ 2% of hours missing, over 28 days): IEX is one exchange.

**Documented APIs first, undocumented endpoints last, no quota past about 85%.** Sina and
Yahoo alternate within each block, so an outage of either leaves every block reporting.

**The store is unadjusted; corporate actions are declared**, Yahoo's every morning and
Tiingo's on a full refresh: adjusted series change with every dividend, and a ratio of
adjusted to unadjusted cannot see a split (USHY's undeclared 6-for-5 read as a −103σ night).

**History from another source is written only where it agrees with the store**: returns
correlated ≥ 0.90 and a median level gap ≤ 25 bp over ≥ 200 shared hours (29 sessions for a
five-hour market). The level test catches dividend-adjusted imports; only missing hours are
written.

**A pair's weekend that opens exactly at Friday's close is no measurement**: a source's
stitched open, and scored, it reads the next real weekend as hundreds of σ. A future's or a
fund's zero night is real (cattle's official gaps agree; since 2023, 98% of the funds' zero
gaps match the official open within 5 bp).

**Futures are read one contract at a time.** Yahoo's continuous series interleaves months;
the softs' history is Dukascopy's single-contract CFDs from 2018, spliced at measured seams;
the night across a roll is not scored, and a bar under 5% of usual volume is a quote, so a
hole. Live cattle rolls twelve business days before its delivery month, when its traders
do: held to its last trading day it sat on a contract hardly trading (October 2026's 3,097
contracts on 10-07 against December's 18,822). Its history was judged against the single
contracts; its old import is not to be re-run.

**Stage 2's futures roll where their volume moves** (`jump/futures.py`, 2026-10-12): each
onto the contract held now on the day Yahoo's own series came onto it - Brent and platinum
09-28, the Treasuries 08-27, wheat 08-12, sugar 09-09 - and corn and soybeans before July's
first notice, past September (and August), as Yahoo's series went straight to December and
November. Brent's last trading day is two months before delivery and sugar's the month
before, so they roll on business days before it, not before the delivery month.

**Stage 2's history is by series** (`tools/futures_history.py`, run once on 2026-10-12 and
deleted; the user's: Dukascopy where it reaches further). Yahoo keeps no expired contract,
and its continuous series switches on its own days, inside an hour (the 10-year 2026-08-27
07:00 UTC opened on September's price and closed on December's: -26 bp against the
contract's -3), and prints the other month for hours around it (corn -7.4% and back on
2026-06-25). So:

- Dukascopy's CFDs, one contract at a time - Brent from 2011-01, the 30-year bond from
  2019-01 (its 2018 is not the market: a -19.6% hour and back, a zero), soybeans from
  2018-03, platinum from 2021-11. Each switch is a roll night, unscored; a window where
  none stands out is dropped. The bond's and platinum's switch in the weeks before this
  series' rolls and were looked for there: 14 and 9 nights, 16 and 11 windows dropped
  (422 and 293 days). Soybeans' moves to each of the seven listed months 5 business days
  before the month ends (on its last business day to 2019-07), weeks after this series'
  mid-month rolls, so its windows held none of them: looked for in the last 12 business
  days of those months, 26 nights, each where its gap to Yahoo's daily series jumps; 31
  windows dropped (645 days). Brent's moves every month, on ICE's last trading day or the
  session after; in the 18 business days before each roll the month's news stood out
  instead (2020-03-09's -24%, 2019-09-16's Abqaiq) and 3,037 days went. So it is looked
  for from 2 business days before the expiry to 3 after, and a night is taken only if the
  CFD's gap to Yahoo's daily close moves with it - a switch moves the CFD, the market moves
  both: 44 of the 84 nights that stood out (2023-04-03's OPEC+ cut, 580 bp, moved the gap
  21); 142 windows dropped (1,136 days). Against Yahoo's daily series at the settlement
  hour, no lasting step is left unmarked in the four. Their volume is a tick count whose
  scale changes over the years (Brent's hour a median 22 million in 2012, a few hundred
  from 2013-03), so each month is scaled to the contract's median: against one factor the
  thin-bar rule left out 56% of Brent's 2013-Q2.
- Yahoo's continuous series to 2024-10 for the 2- and 10-year notes, which Dukascopy does
  not carry, their switches looked for within a business day of each roll - in a wider
  window they did not stand out from the data releases, and 341-349 of 730 days went. A
  switch missed leaves a step of 5-30 bp a quarter; the largest readings there are data
  releases and the Fed, none within three days of a roll.
- Corn, wheat and sugar: the contract held now, from the first month it traded at least
  5% of its volume as front (2026-01/02), past the detector's half-year: one contract, no
  switch. Dukascopy's sugar is London's white sugar, and it has no corn or wheat.

**Each provider's calls are counted, not estimated** (`jump/usage.py`, 2026-10-12; the
user's). The keyed providers vote within the room their limits leave. Whether they fit
can't be judged without knowing what is spent. The keys are used only by this
repository's workflows, so our own count is the truth for what we spend:
- every run writes it, by day and purpose, into its workflow's usage file;
- the limits and their shares are one table (`config/provider_limits.csv`), which the
  caps are read from;
- the providers' own figures are checked against ours where they exist: Twelve Data's
  day, from its usage endpoint once a day (its `api-credits-left` is the minute's).
  SiftingIO's month is on its account page only, and Tiingo sends none.
- The 30 days before the files existed are added up from the runs' logs
  (`tools/usage_from_logs.py`, run once and deleted).

**The LME's metals are the LME's own, from Sina**: the right instrument with a short record
(from 2026-04-22) over a longer record of another (Shanghai tin, Kitco, COMEX aluminium).

**Wallstreetcn for the LME**: their voter, and the history below Sina's last 1,023 bars,
about 170 days. Against Sina, 0 bp apart at the median, hourly moves correlated 0.96–0.99:
in part one upstream, the only other feed a runner reaches. Its votes count 79 days, not its
whole reach, where it would vote on its own bars; its openings of 2026-04 to 07 that sat 1%
off and came back within the hour (11) were left out at import.

**Wallstreetcn on cocoa, cotton and the pairs**: a second voter for cocoa and cotton, a
third for the pairs. Its quotes are its own (at most 2% of its closes equal the store's):
cocoa 7.0 bp and cotton 2.4 bp off at the median, the pairs 0.8–3.4 bp; its own changes of
contract are treated as Sina's.

**The FT for live cattle and coffee**: their second voter, hourly bars by an instrument's
xid, 24 trading days back - cattle by the contract the store holds, coffee only
continuous. Of the largest moves of 2026-09-10 to 10-09 it saw 10 of cattle's 11 and 19 of
coffee's 20, and denied none.

**Gold and silver from SiftingIO**, its commodities endpoint, spot round the clock: asked at
04:02 UTC on 2026-10-12 it held the bar that ended at 04:00, and over 799 hours it moved
with Dukascopy's at 0.9992 and 0.9980 (medians 0.25 and 1.06 bp). Twelve Data's plan
refuses silver, and its gold fills the weekends with bars. Their history is Dukascopy's from
2003; it leaves the daily break (an hour from 17:00 New York) empty where SiftingIO serves
a thin bar, so the hour after it scores its own hour in the history - a small difference,
left as served. They keep the pairs' week but are voted on by Wallstreetcn and Sina.

**Every coin is its USDT pair on Binance**: one exchange, one quote currency; before 2018,
the deepest dollar exchange that passes the splice gates.

**A market abroad keeps its exchange's own calendar**: a table per exchange from
`exchange_calendars`, as fixed hours fail sixteen exchanges (Tokyo's close moved on
2024-11-05, Riyadh trades Sunday to Thursday, Golden Week shuts Shanghai nine days). A night
is whole when it runs from the table's trading day before, however long. Mexico City is on
New York's clock; where the library and Yahoo's bars disagree the wider session is kept,
since an empty hour is skipped and a cut one is lost (São Paulo to 18:00, Yahoo's bars ending
at 17:00); Sydney's and Hong Kong's include the closing auction, ten minutes past.

**Their history is Yahoo's, where it agrees with Yahoo's own folded bars**: two years of
hourly bars, kept where they pass the import gate against 58 days of folded 30-minute ones
(12 of 16; the CSI 300, BIST 100, TSX and IPC start with the 58 days). A half-hour market's
first bar, filed under the hour it ends in, still opens its night.

**A failing provider costs its instruments, not the run.** Two unanswered requests in a row
stop it for the run (one costs about 96 s of the job's 20 minutes; one silence is a blip);
a missing key skips its instruments and is named every run; a lone refusal waits for the
stale check, a spent quota is told every run; the run goes red only when nothing at all was
fetched.

**An open month is repaired by hand, inside the hourly run**: only the hourly run saves the
open months, and holes are rare.

---

## The sources' vote

**The sources vote, and the store's provider is one vote that saw it.** A majority of every
feed that has the hour, weighed alike: "any feed saw it" keeps bad prints, "all must agree"
lets one feed's bad tick take a real move out.

**A move not real is not scored, and a sent message is marked, not deleted**: out of the
yardstick it cannot inflate σ; marked, a wrong vote costs a line.

**A tie is uncertain, and stays scored** (the user's, 2026-10-08): nothing tells which side
is wrong.

**An outage is left out of the count** (the user's, 2026-10-10): counted against, one source
down turns a clear vote into a tie. When none can answer, the move is uncertain.

**A vote is taken when the move is found, then at each end of its market's session, while
its closest source still reaches the hour**: 9 days wherever MarketWatch votes, 29 for
coins, 79 for the LME. Further back the further sources would vote alone. The record keeps
a vote 90 days. Kept when MarketWatch joined gold, silver and the softs (the user's,
2026-10-12: "keep the shortest reach"), which cut their recount from 60, 30 and 79 days to
9.

**A provider's corrections come in through its ordinary request**: on a vote's run the fetch
reaches back to the voted hour; a separate request would spend allowances the live run
needs.

**The vote is said as each source's own move** (`❌ Binance(+2.03%), Coinbase(-0.10%),
Kraken(-0.10%)`), so a reader weighs it without a key.

**A vote is taken with what the sources serve at the time**: a source that has not shown
the move yet counts against until the next count.

**A source sees a move on its own two bars of it** (the user's, 2026-10-12): its price at the
store's previous bar and at this one moved the same way at least half as far. No bar at
either end - none served, or no price - is an outage, left out; with nobody left, the move
is uncertain. A one-hour window and a 12-hour bridge stood here until then, each from one
case (a late feed, a hole), not a measured rule. Measured on the 58's voters' bars of
2026-09-07 to 10-09: every one of 142 source-instrument pairs moves with the store on the
same hour (median correlation 0.998; an hour off, 0.007), and of 119 moves at 4σ or more no
verdict or answer changed without them. Half: answers sat at 0.8 or more or under 0.2
(3,704 answers, 2026-10-08, under the window). Which feed was wrong is not asked. The
overnight first-hour check reads the same exact bars, and the reading is close to close
everywhere: an open-to-close hour would lose the steps between bars, which another feed
also saw in 16 of the 31 over 2σ in the 35 days to 2026-10-12 (thin funds, LME tin, Tokyo
after lunch).

**A source with its own contract months is not asked across its own change of contract**
(Sina's and Wallstreetcn's softs): found as a step of 50 bp or more in the session's median
offset, which a one-hour bad print cannot make.

**Every source that moves with the instrument is asked, except its own provider** and a
source that mended that stretch of the store (`verify.SUPPLIED`, empty since TUR left). The
same price from two vendors is agreement, not a copy: vendors of one tape print identical
bars on many hours.

**Every source on every instrument** (the source audit, 2026-10-13; the user's: "take
everything possible, from 1 to 99999999 voters per asset"). Each of 13 clients and 4 new
fetches tried on each of the 58 and on the Bund, gilt, JGB and TTF, from a runner with the
keys, on its last ~30 days against the store (a one-off tool, deleted): 507 pairs, then 199
again after the Yahoo funds were asked as the vote asks them. Accepted, as the vote judges:
- hourly moves correlated 0.90 or more with the store's;
- nine in ten of the store's big moves (2.5 robust σ or more) confirmed, the same way and
  at least half as far;
- no local hour where three or more big moves were not.

A local hour under 0.5 is another grid's (the FT's last hour in Europe); the pairs' 20:00-22:00
UTC hours are weak for every voter, from the store's own thin rollover bars, and do not
count against one.

- **Added:** Tiingo and Twelve Data on the pairs (Twelve Data not USD/CNH) and gold, Tiingo
  on silver, UNG and REMX; MarketWatch's, Yahoo's COMEX gold and silver; SiftingIO on SPY,
  UNG and platinum (spot); Wallstreetcn's natural gas future on UNG and Brent on Brent; the
  FT's Brent and cocoa; MarketWatch's coffee, cocoa and cotton; Yahoo's copper (COMEX) on
  the LME's; Alpaca's, Bitstamp's, Bitfinex's and Yahoo's dollar pairs on the coins;
  MarketWatch's KOSPI, JSE Top 40 and Bovespa; Naver's KOSPI; the Taiwan exchange's TAIEX.
- **A bad hour skipped, not the source** (the user's): the FT on the Euro Stoxx 50 (17:00
  local, 0.19), FTSE 100 (16:00, 0.08) and SMI (17:00, 0.15), whose last bar ends before
  the closing auction Yahoo's holds (0.92-0.94 overall, that hour in); the Taiwan
  exchange at 13:00 (0.50, the 13:30 auction; 1.00 in its other hours); Sina's CSI 300 at
  11:00 (0.69, the lunch break; 0.98 at 14:00). Each votes in every other hour.
- **Dropped** (the user's): the FT on the funds (0.91-0.93 overall, its 15:00 hour -0.47 to
  0.14; each fund keeps four to seven voters without it); Wallstreetcn's Nikkei (0.67, its
  last bar 3.5 days old).
- **Left out:** MarketWatch's Bitcoin, Kraken's own pair under another vendor's name, which
  would give Kraken two votes; Sina's COMEX gold and silver and natural gas, a second Sina
  voice where its spot or the fund itself votes; MarketWatch's TAIEX (0.86, its 13:00 hour
  0.47), not in the user's skipped hours; the keyed providers on the coins, which keep six
  free voters each.
- **Still none or one:** the TAIEX, JSE Top 40, Nikkei, ASX 200, Hang Seng, BIST 100,
  sugar and the Treasuries have one voter; MarketWatch is often Yahoo's upstream to the cent.

**The keyed providers vote within a share of their allowance** (the user's, 2026-10-12).
Whether an instrument has enough voters cannot be judged without knowing the limits hold,
with room left for manual fetches. The shares are in `config/provider_limits.csv`, enforced
(`usage.votes_left`): past one, the provider is an outage for the rest of the run.

| provider | limit | the live run | manual | dashboard | the vote | the vote's use |
|---|---|---|---|---|---|---|
| Tiingo | 50/hour, 1,000/day | 10, 240 | 15, 200 | 11, 110 | 14, 100 | 11 instruments: about 9 at 00:05 UTC, 15-30 a day |
| Twelve Data | 8/minute, 800/day | 1, 24 | 7, 600 | 6, 70 | 6, 50 | 7 instruments: about 7 at 00:05 UTC |
| SiftingIO | 10,000/month | 4,700 | 1,000 | 300 | 300 | 3 instruments: 3-5 a day |
| Alpaca | 200/minute | 0 | 100 | 50 | 50 | 12 funds' tape and 4 coins |

The vote asks a keyed provider once a run per instrument, on the run that finds a far move
and the runs after its market's session ends. A minute's shares do not add up: the hourly
batch spends its credit at about :05, the vote in the minutes after it, which a history
walk waits out (`LIVE_SLOT_MINUTES`); a dashboard run on a push can meet a 429, an outage
there.

**Alpaca's consolidated tape votes on every fund**: every exchange's trades, against the IEX
feeds' one. Fifteen minutes behind, it is asked once it serves the move's hour whole.

**A first hour the feeds saw happen overnight is moved into the night**: a fund's stale first
print puts the night's move in its first hour; marked "not seen", the real move would be
gone.

**Candidates are the detector's own readings at ≥ 4σ**, on the raw yardstick and on the
detector's (moves voted not real out, nights moved), so every reading it can flag is asked
about.

**History is not voted again** (the user's, 2026-10-08). Older than its recount, a vote
stands as recorded, and the history's one-off check of 2026-10-07, from the sources that
reach it, stands too. A replay of the vote over all history was tried and dropped: with one
other source the vote cannot call a move not real, and most of history has one at most. Do
not reopen without a second source for those stretches.

Hourly-move correlation with the store over its last ~30 days, from the source audit
(2026-10-13) unless dated:

| instruments | verified against | why |
|---|---|---|
| FX pairs | Yahoo, MarketWatch, Wallstreetcn, Tiingo, Twelve Data (not USD/CNH) | Tiingo 0.996–0.999, MarketWatch 0.98–0.999 (every hour; Yahoo 21–72%, 2026-10-04), Yahoo 0.94–0.997, Wallstreetcn 0.93–0.99 (its own quotes), Twelve Data 0.91–0.98 |
| gold, silver | Yahoo's and MarketWatch's COMEX futures, Sina's and Wallstreetcn's spot, Tiingo, Twelve Data (gold) | 0.985–0.999 |
| funds | Yahoo 30-minute, Sina 30-minute and MarketWatch hourly, but the fund's own, and Alpaca's consolidated tape; UNG also Wallstreetcn's natural gas future, Tiingo, SiftingIO; SPY SiftingIO; REMX Tiingo | 0.994–1.000; Tiingo 0.95–0.995, Wallstreetcn 0.985; Sina matches the tape to 0.0 bp |
| coffee, cocoa, cotton | Sina global futures, MarketWatch continuous; Wallstreetcn for cocoa and cotton; the FT for coffee and cocoa | MarketWatch 0.998–1.000, Sina and Wallstreetcn 0.989–0.992, the FT 0.92–0.99 |
| live cattle | MarketWatch continuous; the FT's bars of the store's contract | MarketWatch 1.00 (0.92 on 2026-10-07); the FT 2.3 bp off |
| stage 2's futures (Brent, the Treasuries, corn, wheat, soybeans, sugar, platinum) | MarketWatch continuous, each; the FT's bars of the store's contract for the grains and platinum, its continuous Brent; Sina's Brent and spot platinum; Wallstreetcn's Brent; SiftingIO's spot platinum | MarketWatch 0.995–1.000, the FT 0.97–0.99, Sina, Wallstreetcn and SiftingIO 0.98–0.99; under 0.90 and left out (2026-10-12): Wallstreetcn's grains (0.11–0.58), Sina's grains (0.78–0.85), the FT's Treasuries (0.885–0.89) |
| coins | Coinbase, Kraken, Bitstamp, Bitfinex, Alpaca, Yahoo | other exchanges' dollar pairs, 0.997–1.000 with Binance's |
| LME metals | Wallstreetcn; copper also Yahoo's COMEX future | Wallstreetcn 0.99; COMEX copper 0.93 |
| stock indices abroad | MarketWatch (14), Wallstreetcn (3), the FT (5), Naver's KOSPI, the Taiwan exchange's TAIEX, Sina for the CSI 300 | MarketWatch 0.96–1.00, Naver 1.00, the FT 0.92–0.98, Wallstreetcn 0.95–0.99 (the TSX too few hours to judge, kept); the Taiwan exchange 0.85 and Sina 0.80 with their skipped hour in, 0.98–1.00 without; under the bar: Wallstreetcn's KOSPI (0.84, another grid at 03:00–04:00 UTC), the FT's Top 40 (its official close in the bar ending 14:00 UTC) and Nikkei (0.80) |

---

## The stored history

Settled once, and not to be reopened. **Stored bars are not rewritten**: a bad bar found
since 2026-10-09 is a row in `data/jump/verified.csv` (the user's), undone by deleting it and
out of any fetch's reach. Done before then, and kept:

- **The majors' 2012 Sunday opens are Dukascopy's**: that year's source opened every bar at
  the previous close, and the zero weekends collapsed the yardstick.
- **The funds' wrong opens of 2016–2022 were mended from the tape**: 9,783 first bars took
  Alpaca's tape open where the two closes agree within 10 bp and an independent referee (the
  most similar funds' nights) chose the tape's open; the bond funds' ordinary mornings, where
  it came out even, were left.
- **From 2023 the funds' opens are left as stored** (the user's, 2026-10-09): far cleaner
  there, and a mend moved the year's pushes 209 → 206 and would not stay mended.
- **The funds' 2016–2019 price levels are left off the tape's**: a steady offset moves no
  reading but a few ex-dividend nights (REM's four).
- **14 shifted fund days are held as hours with no price**, so no fetch fills them again.
- **Two futures stretches are the next contract's**: cocoa's 2026-07-21 to 08-10, where no
  CFD switch could be located, and live cattle's September from 09-15, after its roll.
- **A dividend refresh keeps the splits already declared**, or a split Tiingo does not list
  is lost for good.

---

## The repository

**Derived data is not tracked**: it rebuilds from the bars in under a minute.

**A one-off tool is deleted once its work is done**: a rerun of a history builder would undo
later fixes. Git keeps them; what they established is here.

**The open month lives on a release; a month enters git once, settled** - plain CSV a
month, Parquet a finished year. Hourly commits into per-instrument files cost 124 MiB a
year, a release file nothing; the Actions cache evicts after seven idle days.

**Health reaches the chat from wherever the run can still speak**: the workflow's last step
says what happens outside the monitor; an outage is timed by the last committed run
(`last_run_utc`); a problem of one instrument goes out every run or daily, never through
the streak.

---

## Rejected

Measured or weighed, and not to be raised again.

| option | why not |
|---|---|
| time-of-day factor (Boudt, Croux & Laurent 2011) | flags it removes reverse no more often than the rest; flags it adds reverse more |
| labelling scheduled news | release-hour jumps are real; a push already lists nearby releases |
| block co-jumps, a block-residual move, a size floor | blocks are tight, so a common move shows in its members |
| a Student-t tail per class | every class has nearly the same tail against its own σ |
| per-instrument "N times a year" levels | sends the biggest crisis hours out as note rows |
| σ·√k across a hole | needs a clock of expected hours |
| a level check (30% off the two-day median) | drops real crypto crashes |
| "isolated and taken back" as a bad print | marks real moves, misses a feed sitting off for hours |
| a longer window for weekend gaps | a small gain, real shocks read quieter; one window for every instrument |
| a fund's night from Yahoo's daily official open | the feeds carry the same tape, so the opening price is no referee |
| a stale first print found from the bar alone | caught at best 7% of stale prints at 66% precision |
| holding isolated moves an hour | a third of alerts would be an hour late |
| a watchdog for the trigger's silence | the external scheduler is the party that knows a call stopped |
| Finnhub, Metal Sentinel, FXEmpire, Business Insider | quotes, not bars |
| Financial Modeling Prep, Massive (Polygon) free tiers | daily bars, or today's only after the close |
| Eulerpool, London Strategic Edge | no hourly bars for the funds |
| Kitco, Shanghai tin, COMEX aluminium, WisdomTree metal ETCs | not the LME's market |
| TradingView | ~6,300 bars without a login; its terms |
| Investing.com, the LME, CNBC, Barchart, Boursorama, CME, Xueqiu | refuse or forbid automated readers; not bypassed |
| Eastmoney, cngold | refuse requests not from China or not from their own pages; not bypassed |
| cnyes, SMM | daily bars only; prices filled in the browser |
| DailyFX, Stooq | gone; login required |
| Sina forex; Sina live cattle | six months of hourly bars; quotes without volume |
| api.binance.com | HTTP 451 from US runners; the market-data mirror is used |
| FXCM history | spliced blind; Dukascopy gates on a measured overlap |
| Interactive Brokers, paid Barchart | a funded account or about $500 a month |

---

## Open questions

Known and left alone on purpose.

**Repository size**, about 921 MiB as GitHub counts it (2026-10-09), mostly superseded
Parquet in history; GitHub warns at 1 GB. To act: a history rewrite, which force-pushes the
live branch irreversibly.

**Undocumented endpoints carry most of the basket** (Yahoo, Sina, MarketWatch,
Wallstreetcn, the FT). A changed shape raises and the health chat names the provider. To
act: paid feeds.

**KOSPI's last half hour** (15:00–15:30 Seoul, the closing auction) is not in Yahoo's bars,
live or history: its close is the 15:00 price and the last half hour falls into its night.
To act: a source that carries it. The JSE Top 40's closing auction (16:50–17:00
Johannesburg) is missing the same way: 2026-10-07 closed the store's day at 99,353 against
the official 99,394.

**The Bund, JGB, gilt and TTF** (stage 2, deferred by the user, 2026-10-12, and searched in
the source audit of 2026-10-13):
- the Bund: MarketWatch's single contract live (FGBLZ26, about 13 days back, no volume),
  Dukascopy's history from 2018, the FT's contract as a voter (0.95 hour by hour, 33 days
  back); Wallstreetcn's yield moves opposite (-0.99);
- the gilt: MarketWatch's single contract live (RLIZ26), Dukascopy's history from 2018; no
  voter (the FT's candidates 0.15-0.23);
- the JGB: no future anywhere; MarketWatch's 10-year yield live, Wallstreetcn's at 0.68
  against it; the TSE bond funds move weakly and opposite (-0.32 to -0.64);
- TTF: MarketWatch's ICE Endex series only, about 13 days back; NYMEX's look-alike 0.77-0.80.

The user's, 2026-10-13: add everything good, and look for what is missing later.

**What else Wallstreetcn carries**, hourly, about 170 days back, without volume (2026-10-10):
sugar, lean hogs, wheat, corn, soybeans and soybean oil, the LME's lead and zinc, 38 stock
indices and index futures, 52 government bond yields (codes in
`price_monitor/wallstreetcn.py`). One added has a young yardstick for its first months and
no other voter unless another feed carries it; a yield would have to be scored in basis
points, which the detector does not do.

**History no free source reaches.**

| instruments | missing before | tried |
|---|---|---|
| 2 US funds (XLK, XLE) | 2016-01 | HF Data, Twelve Data, Alpaca's tape |
| the 2- and 10-year notes | 2024-10 | Yahoo (730 days, no expired contract), Dukascopy (no note) |
| corn, wheat, sugar | 2026-01/02 | Yahoo (its continuous series mixes two months around each switch), Dukascopy (no corn or wheat; its sugar is London's white) |
| live cattle | 2024-05 | Yahoo (730 days), Dukascopy |
| coffee, cocoa, cotton | 2018-01 | Dukascopy |
| LME tin, nickel, aluminium, copper | 2026-04-22 | Sina (last 1,023 bars), Wallstreetcn (about 170 days; taken), Eastmoney |
| 12 stock indices abroad | 2024-10 | Yahoo (two years of hourly bars) |
| CSI 300, BIST 100, TSX, IPC | 2026-08 | Yahoo (its older hourly bars failed the import gate) |
