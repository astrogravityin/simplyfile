# AlphaQuest — Requirements v0.1

Source: "AlphaQuest Agent Architecture & Hierarchy" diagram (v1.0), read 2026-10-07. Tagline: *Evidence first. Structured research. Smarter decisions.*

## 1. What it is

An equity-research portal for **Indian listed companies (NSE / BSE), focused on small and mid caps**. It covers two horizons:
- **Investment:** long-term, fundamentals first.
- **Swing / positional:** weeks to months, technicals and catalysts.

It turns raw evidence into ranked, explained decisions and reports. Every number and claim can be traced back to its source.

The pipeline climbs one step at a time, and no level may skip the one below it:

1. Raw evidence
2. Verified facts
3. Normalized data
4. Derived metrics
5. AI interpretation
6. Peer comparison
7. Forecast / valuation
8. Scores
9. Decision
10. Evidence-backed report

## 2. Decisions taken

These are calls I made, with the reason for each. Change any of them before build starts.

| # | Decision | Why |
|---|---|---|
| D1 | Build as a **ValueStream domain portal** from SimplyFile's boilerplate (`domain-portal` skill). Folder `D:\AlphaQuest`, site `aq.valuestream.in`. | You get login, tenants, History, Guide me, bottom bar, the demo site, the landing page and the rule watch for free, and it is kept in step with `sync_boilerplate.py`. |
| D2 | **An agent is a chip or a job, never free code.** COLLECTOR, NORMALIZER, CALCULATOR, SCORER and RANKER agents are chips plus ops, with test cases. AI_RESEARCH agents are AI calls whose prompts, output schemas and limits live in chips. REPORTER agents are chip templates. ORCHESTRATOR is `core/jobs`. | The "chips and ops only" rule: every formula, threshold and word can be checked and changed without code. |
| D3 | **Evidence store.** Each fact is stored as {value, unit, period, source URL or file, fetched_at, agent, confidence}. Derived values keep links to their inputs. A report line shows its chain on click. | "Evidence first" is the product. |
| D4 | **Deterministic before AI.** AI agents may read documents and explain them. They may never produce a number that a CALCULATOR can compute. AI output is checked against the facts by K03 and O03 before anything else uses it. | Trust; the same mistake the tax portal avoids. |
| D5 | **Freshness rules per fact kind** (price daily, results quarterly, shareholding quarterly, and so on), kept in a chip. When a fact goes stale, everything built on it is invalidated and re-runs. | The Master Orchestrator's "Freshness & Invalidation Control" box. |
| D6 | **Each person brings their own AI key**, the same as SimplyFile (Gemini or OpenAI, chosen per agent group in a chip). | Cost stays with the user; the pattern already exists. |
| D7 | **Not in scope:** placing orders, broker integration, intraday trading, F&O, and personal advice to the public. | See §7 (regulation). |

## 3. The 8 agent types

| Type | Job | How it is built |
|---|---|---|
| COLLECTOR | Gets data from sources | Job plus source chip (URL, schedule, parser) |
| NORMALIZER | Cleans the data and sets one unit, period and format | Chips plus ops |
| CALCULATOR | Computes fixed metrics | Chips plus ops |
| AI_RESEARCH | Researches and analyses with an AI | AI call; prompt and schema in a chip |
| SCORER | Applies scoring logic | Chips plus ops |
| RANKER | Ranks and compares | Chips plus ops |
| REPORTER | Generates reports | Chip template, exported to PDF and HTML |
| ORCHESTRATOR | Controls the workflow | `core/jobs` plus chips |

Each agent row in the catalogue chip (`agents.catalog`) carries:
- id, name, group, level and type;
- inputs (agent ids) and outputs (fact kinds);
- schedule and freshness;
- its chip or prompt id.

The orchestrator builds its dependency graph from these rows.

## 4. Agent catalogue (from the diagram)

### Level 0 — Orchestration: the Master Orchestrator
Four parts:
- **Dependency Manager:** builds the graph from `agents.catalog`.
- **Scheduler:** runs by event, by time or by hand.
- **Freshness & Invalidation Control.**
- **Run / State / Audit Management:** keeps every run, its inputs and outputs, and how long it took.

### Level 1 — Foundation: data acquisition and primary intelligence
- **A. Company & Universe:**
  - A01 Company Master
  - A02 Sector Classification
  - A03 Peer Universe
  - A04 Sector Universe
  - A05 Peer Mapping
- **B. Fundamental & Historical:**
  - B01 Financial Statements
  - B02 Key Financial Line Items
  - B03 Shareholding Pattern
  - B04 Corporate Actions
  - B05 Ratios (Basic)
  - B06 Historical Financials
  - B07 Auditor & Accounting
  - B08 Segment Information
  - B09 Life-Cycle & Milestones
- **D. Documents & Management:**
  - D01 Annual Reports
  - D02 Quarterly Results
  - D03 Investor Presentations
  - D04 Concall Analysis
  - D05 Management Commentary
  - D06 Guidance Extraction
  - D07 Management Background
  - D08 Strategy & Business Model
  - D09 ESG & Sustainability
  - *D10–D12 not named in the diagram (see §9).*
- **F. News / Events / External:**
  - F01 Exchange Announcements
  - F02 News Ingestion
  - F03 Event Categorization
  - F04 Rumor vs Fact Check
  - F05 Industry / Sector News
  - F06 Macroeconomic Indicators
  - F07 Policy & Regulatory News
  - F08 Event Impact Analysis
  - *F09 not named.*
- **G. Market Data & Technicals:**
  - G01 Historical Market Data
  - G02 EOD Price Processing
  - G03 Technical Indicators
  - G04 Volume & Delivery
  - G05 Trend Analysis
  - G07 Breakout Detection
  - G08 Momentum Indicators
  - G09 Volatility & ATR
  - G11 Sector Momentum
  - G12 Institutional Activity
  - G13 Corporate Actions (Price)
  - G14 Technical Signal Summary
  - *G06 and G10 not readable.*

### Level 2 — Execution & risk intelligence
- **C. Orders, Capex & Execution:**
  - C01 Order Book
  - C02 Order Inflow
  - C03 Order Execution
  - C04 Order Conversion to Revenue
  - C05 Capex Announcements
  - C06 Capex Progress
  - C07 Capex Spend & Commissioning
  - C08 Capacity & Utilization
  - C09 Execution Tracking Summary
- **E. Governance, Forensics & Risk:**
  - E01 Board & Management
  - E02 Related Party Analysis
  - E03 Corporate Governance
  - E04 Auditor & Audit Issues
  - E05 Regulatory Actions
  - E06 Forensics: Risk Indicators
  - E07 Litigation & Contingencies
  - E08 Governance Risk Summary
- **H. Peer Benchmarking & Sector Position:**
  - H01 Peer Selection (Direct)
  - H02 Peer Selection (Sector)
  - H03 Peer Selection (Size)
  - H04 Peer Selection (Business Model)
  - H05 Financial Peers
  - H06 Valuation Peer Comparison
  - H07 Financial Metrics Comparison
  - H08 Valuation Rankings
  - H09 Relative Ranking

### Level 3 — Derived research intelligence (I)
- I01 Business Quality
- I02 Growth Quality
- I03 Management Quality
- I04 Execution Quality
- I05 Cash-flow Quality
- I06 Balance-sheet Quality
- I07 Competitive Position
- I08 Growth Trajectory
- I09 Order Conversion Analysis
- I10 Earnings Momentum
- I11 Earnings Surprise Analysis
- I12 Estimate Revision Analysis
- I13 Risk Assessment

### Level 4 — Forecasting, valuation and scoring
- **J. Forecasting & Valuation:**
  - J01 Forecast Model
  - J02 Scenario Analysis
  - J03 Revenue Forecast
  - J04 EBITDA / Margin Forecast
  - J05 Earnings Forecast
  - J06 Cash Flow Forecast
  - J07 Valuation Models
  - J08 Fair-Price & AQP
  - J09 Expected Return Analysis
- **K. Scoring & Evidence Quality:**
  - K01 Parameter Processing
  - K02 Derived Metrics Engine
  - K03 Evidence Quality Checks
  - K04 QA-Criteria Scoring
  - K05 Coverage Analysis
  - K06 Confidence Scoring
  - K07 Confluence Scoring
  - K08 Freshness & Data Quality

### Level 5 — Decision layers
- **L. Investment:**
  - L01 Investment Score
  - L02 Sector Ranking (Investment)
  - L03 Growth Ranking
  - L04 Value Ranking
  - L05 Risk / Reward Analysis
  - L06 Investment Recommendation
- **M. Swing / Positional:**
  - M01 Technical Setup Analysis
  - M02 Momentum Scoring
  - M03 Breakout Analysis
  - M04 Volume & Delivery Analysis
  - M05 Catalyst Analysis
  - M06 Sector Momentum Ranking
  - M07 Swing Ranking
  - M08 Swing Recommendation

### Level 6 — Combined opportunity (N)
- N01 Fundamental + Technical Combination
- N02 Best Combined Opportunity
- N03 Watchlist Priority Ranking

### Level 7 — Research quality / Red Team (O)
- O01 Pre-Mortem Analysis
- O02 Short Thesis
- O03 Falsifier / Bear Case
- O04 Disconfirmation Analysis
- O05 Base Rate Analysis
- O06 Thesis Change Tracking
- O07 Forecast Calibration
- O08 Research Quality Summary
- O09 Red Team Review

Every Level 5 or 6 recommendation must pass O before it reaches a report. A recommendation whose bear case is not answered is shown as "challenged".

### Level 8 — Reporting (P)
- P01 Company Report
- P02 Peer Comparison Report
- P03 Sector Report
- P04 Investment Report
- P05 Swing Report
- P06 Daily Briefing
- P07 Watchlist Report
- P08 Research Summary

## 5. Data sources (public and official first)

| Need | Source |
|---|---|
| Prices, volume, delivery % | NSE and BSE end-of-day bhavcopy (public daily files) |
| Announcements, results, shareholding, corporate actions | NSE and BSE corporate filings (XBRL where available) |
| Annual reports, presentations, concall transcripts | Exchange filings and company IR pages |
| Regulatory actions | SEBI orders |
| Litigation | Company disclosures and contingent-liability notes |
| Macro indicators | RBI and MOSPI releases |
| News | RSS from licensed or free sources |

Collectors respect each site's terms and rate limits. There is no scraping behind logins, and no paid data unless the owner adds a key. Every source is a chip row.

## 6. Screens (first cut)

- **Universe:** companies, sectors and peers.
- **Company:** one page with the evidence tree, scores, forecasts, red team and History.
- **Screener / Rankings:** investment, swing and combined.
- **Watchlist:** with daily briefing.
- **Reports:** P01–P08, as PDF and HTML.
- **Agents:** the catalogue, the graph, runs, freshness and failures (the orchestrator console).
- **Rules:** the rule watch for anything regulatory, such as circuit limits and SEBI changes.
- **Boilerplate:** everything else the boilerplate brings.

## 7. Regulation

**Publishing buy/sell recommendations or research reports to other people in India requires SEBI Research Analyst registration** (SEBI (Research Analysts) Regulations, 2014, as amended). Until the owner holds it, the product is a personal research tool:
- every output carries a "not investment advice" notice;
- the demo shows only fictional companies or delayed, public data with no recommendation;
- there are no paid signals.

The exact wording, and whether a registration is planned, is the owner's call (see §9).

## 8. Build order (MVP first)

| Phase | What | Done when |
|---|---|---|
| 1 | Level 0, plus A, B and G (universe, financials, prices and technicals), K08 freshness, the evidence store | 200 small/mid caps loaded with 5 years of financials and 2 years of EOD prices; every fact links to its source |
| 2 | H, I (deterministic part), L, M, N and P01 / P05 / P07 | Investment and swing rankings with explained scores; company report |
| 3 | D, F and E with AI_RESEARCH (concall, guidance, governance, news) | AI findings stored as evidence with quotes and page numbers; K03 checks pass |
| 4 | C, J, O, and the rest of P | Forecasts with scenarios; red team on every recommendation; calibration tracked |
| 5 | Demo, landing page, Guide me, tours | Per the domain-portal "Done means" |

## 9. Open questions for the owner

1. **Counts in the diagram don't add up.** The panels show 139 agents, not 136: Level 1 is listed as 48 but the panels hold 49. D shows 9 names but says 12. F shows 8 but says 9. G shows 12 readable names but says 14, with codes G06 and G10 missing. The O group's codes are duplicated; I renumbered them O01–O09 in order. Send the PRD the diagram is based on ("Based on AlphaQuest PRD & Architecture") if you have it.
2. **Users:** is it you alone, or many users (subscribers, advisory firms as tenants)? This decides tenants and §7.
3. **SEBI RA registration:** do you hold it or plan to?
4. **"AQP" in J08 (Fair-Price & AQP):** what does it stand for?
5. **Universe:** what counts as small and mid cap? The AMFI list (ranks 101–250 mid, 251+ small) is assumed.
6. **Data budget:** free and public sources only, or a paid feed (for example a fundamentals API)?
