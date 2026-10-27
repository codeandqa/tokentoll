# TokenToll: the carbon footprint of your AI coding

> **POV: you vibe-coded all month and your AI was lowkey on a 2,740 km road trip 🚗💨**
>
> No cap, every prompt has a carbon footprint. TokenToll spills the tea:
> CO₂, heat and water, live, on your own machine. It's giving main-character
> energy, but make it accountable. 🌱✨ Touch grass, then check your number. 💀

## Your AI pair programmer runs on electricity. Now you can see how much.

Every prompt you send lights up a GPU in a data centre somewhere. It draws
power, gives off heat, and uses water to stay cool. **TokenToll** turns your
Claude Code sessions into numbers you can feel:

> 🚗 **km driven** · 🔋 **phone charges** · 💧 **bottles of cooling water**

Here's one real month of heavy Claude Code use (the author's own, 30 days):

| | |
|---|---|
| **CO₂e** | **≈ 466 kg**, about **2,740 km in a petrol car** |
| **Energy (all of it ends up as heat)** | **≈ 1,165 kWh**, about **77,700 phone charges** |
| **Cooling water** | **≈ 1,165 L**, about **2,330 half-litre bottles** |
| **The surprise** | **~80%** came from the AI *re-reading* context it had already seen (27 billion cached tokens), not from writing code |

*Central estimates. The honest range is about 4× either way; see [Method](#method).*

### Why you'll want it

- **👀 See it live.** An animated AI chip heats from blue to red while your
  sessions run, and a counter ticks up as you code.
- **🧾 Every session, by name.** Find which task, project or model cost the most.
- **💬 Right above your chat.** A one-line band shows this session's footprint
  after every turn.
- **🔒 Nothing leaves your machine.** It reads Claude Code's local logs, makes
  no outbound network calls, and needs no account, no API key and no
  `pip install`: one Python file.
- **📚 Sources, not vibes.** Every rate is based on published research (Epoch AI,
  Google) or labelled as an assumption you can change.
- **🆓 Open source, MIT.**

### Share your number

Run it, then post your own month:

> My AI coding last month: **≈ ___ kg CO₂e**, the same as driving ___ km. ___% of it was
> the AI re-reading context. Measure yours: TokenToll for Claude Code 🌱 github.com/codeandqa/tokentoll

Or the unhinged version:

> not me finding out my AI pair programmer drove ___ km last month 💀 ___% of it was just
> re-reading my code. the audacity. TokenToll for Claude Code, check yours bestie 🌱 github.com/codeandqa/tokentoll

---

## What it is

**TokenToll** estimates how much energy, CO₂, heat and cooling water your
[Claude Code](https://claude.com/claude-code) sessions cost, using the token
counts Claude Code already writes to disk. It has three parts:

| Part | What it does |
|---|---|
| **Skill** (`/tokentoll`) | Ask "how green is my coding?" and Claude runs the estimator and explains the result. |
| **Dashboard** | An HTML page with animated tiles, a daily chart, and breakdowns by session, project and model. It can run live, updating every 5 seconds while you work. |
| **Chat band** (optional) | A one-line strip above the Claude Code prompt with this session's and today's totals, plus **Dashboard** and **Audit** buttons. |

> **These are estimates, not measurements.** The token counts are exact; they
> come from your own logs. The energy each token uses is not published by
> Anthropic, so the tool converts tokens to energy with rates based on public
> research (see [Method](#method)). Every figure is shown with a low–high
> range of roughly 4× either side. Read it as an order of magnitude.

---

## What you see

**Dashboard** (`carbon.py`, or `carbon.py --live`):

- **Three animated tiles**, each with its everyday equivalent:
  - **Carbon**, in g/kg CO₂e: a car driving, with "≈ N km in a petrol car".
  - **Energy = heat released**, in kWh: a phone battery charging, with "≈ N phone charges".
  - **Cooling water**, in litres: a drop falling into a glass, with "≈ N half-litre bottles".
- **Daily CO₂e** as a bar chart, one bar per day. Hovering or keyboard focus shows a day's value, and a table view lists every day.
- **By session**, **By project** and **By model** tables with tokens, CO₂e and share. Each table shows the top 10 rows and folds the rest into "Other (N)".
  - Sessions are listed by their full name: your rename if you gave one, otherwise Claude Code's AI title, otherwise the last prompt (cut to 120 characters). The project folder and short session ID sit underneath.
- **Live mode only:** an AI chip that heats from blue to orange to red as the last 5 minutes' rate climbs toward 50 g CO₂e per minute. Heat waves rise off it, a counter of today's CO₂e ticks up, and every session active in the last 5 minutes is listed with its own rate and marked **● live**.
- **Light and dark themes.** With "reduce motion" on, the animations stop.

**Chat band:**

```
● CO₂  this session 483 g   1.21 kWh heat   1.2 L water   today 3.11 kg        Dashboard   Audit   Close
```

- **Dashboard** starts the live dashboard and opens it in your browser.
- **Audit** runs `/tokentoll` in the chat for a written breakdown.
- **Close** hides the band, and stays hidden in new sessions. Type `/tokentoll-band` to show it again (`/tokentoll-band show` and `/tokentoll-band hide` also work).
- **If the script can't run** (not installed at the path below, or no `python3`), the band shows the reason in place of the numbers.

---

## Requirements

- **Claude Code**, which writes the session logs this tool reads: `~/.claude/projects/**/*.jsonl`.
- **Python 3**, standard library only (no `pip install`). Tested with Python 3.14 on macOS.
- **The band only:** a Claude Code build with hooks modules ("mods"). That API is marked early access and may change between releases.

---

## Install

Clone the repo into your Claude Code skills folder. The folder must be named
`tokentoll`, because the band looks for the script at this path:

```bash
git clone https://github.com/codeandqa/tokentoll.git ~/.claude/skills/tokentoll
```

That gives you:

```
~/.claude/skills/tokentoll/
├── SKILL.md            # tells Claude when and how to use the tool
├── carbon.py           # the estimator, dashboard and live server
├── test_carbon.py      # unit tests
├── README.md
├── LICENSE
└── band/               # the optional chat band
    ├── .claude-plugin/plugin.json
    ├── hooks/hooks.json
    ├── hooks/register.tsx   # the band
    ├── hooks/band.test.tsx  # its tests
    └── types/index.d.ts     # the state it keeps
```

Claude Code picks up skills from `~/.claude/skills/`, so `/tokentoll` is
available in your next session.

**The chat band (optional).** Start Claude Code with the band folder:

```bash
claude --plugin-dir ~/.claude/skills/tokentoll/band
```

or list that folder in the `CLAUDE_CODE_PLUGIN_DIRS` environment variable.

**Update** with `git -C ~/.claude/skills/tokentoll pull`.

---

## Usage

**Ask Claude:**
- "How green is my coding?"
- "What's my AI carbon footprint this month?"
- `/tokentoll`

**Or run it yourself:**

```bash
# 30-day report written to ~/.claude/tokentoll-report.html
python3 ~/.claude/skills/tokentoll/carbon.py

# Live dashboard at http://127.0.0.1:8765/ (Ctrl+C to stop)
python3 ~/.claude/skills/tokentoll/carbon.py --live

# Today's totals and one session's totals, as JSON (what the band uses)
python3 ~/.claude/skills/tokentoll/carbon.py --json --session <session-id>
```

| Flag | Default | Meaning |
|---|---|---|
| `--days N` | `30` | How many days back to include (1 or more) |
| `--grid G` | `400` | Grid carbon intensity, gCO₂e per kWh (see [Assumptions](#assumptions-you-can-change)) |
| `--wue L` | `1.0` | Litres of cooling water per kWh (`--grid` and `--wue` can't be negative) |
| `--out PATH` | `~/.claude/tokentoll-report.html` | Where the static report is written |
| `--live` | off | Serve a live dashboard instead of writing a file |
| `--port P` | `8765` | Port for `--live`. If it's taken, the script says so and exits |
| `--json` | off | Print `{"today": …, "session": …}` and exit |
| `--session ID` | none | With `--json`: the session to total |
| `--root PATH` | `~/.claude/projects` | Where the Claude Code logs are |

The JSON looks like this. `g` is grams CO₂e, `kwh` is energy (= heat) and `water_l` is litres; all are central estimates:

```json
{"today": {"g": 3105.05, "kwh": 7.7626, "water_l": 7.763},
 "session": {"g": 482.81, "kwh": 1.207, "water_l": 1.207, "tokens": 23889066}}
```

---

## Method

The calculation follows the shape of the Green Software Foundation's
[Software Carbon Intensity (SCI)](https://greensoftware.foundation/standards/sci/)
specification, published as ISO/IEC 21031:2024: carbon = energy × grid
intensity. It leaves out SCI's embodied-hardware term.

### 1. Tokens: read from your logs (exact)

For every API response Claude Code logged, the script reads `message.usage`
and sorts the tokens into three kinds:

| Kind | Fields in the log |
|---|---|
| Output | `output_tokens` (includes thinking tokens) |
| Fresh input | `input_tokens` + `cache_creation_input_tokens` |
| Cache read | `cache_read_input_tokens` |

Claude Code writes the same response on several lines, and resumed sessions
copy earlier history. Each response is therefore counted once, keyed by
`message.id` + `requestId`. Subagent logs are included.

### 2. Energy per token (estimated)

Watt-hours per 1,000 tokens for a Sonnet-class model:

| Token kind | Low | **Central** | High |
|---|---|---|---|
| Output | 0.2 | **0.6** | 2.0 |
| Fresh input and cache writes | 0.05 | **0.2** | 0.6 |
| Cache read | 0.005 | **0.02** | 0.06 |

Where the central figures come from:

- **Output, 0.6 Wh per 1k.** Epoch AI estimates a typical GPT-4o query at
  about 0.3 Wh, assuming 500 output tokens
  ([Epoch AI, 7 Feb 2025](https://epoch.ai/gradient-updates/how-much-energy-does-chatgpt-use)).
- **Fresh input, 0.2 Wh per 1k.** The same article estimates about 2.4–2.5 Wh
  for a query with 10,000 input tokens, which is roughly 0.2 Wh per 1k input
  tokens above the base query.
- **Cache read, 0.02 Wh per 1k.** An assumption: 10% of a fresh input token,
  the same ratio as Anthropic's list price for cached input. No provider
  publishes this figure.
- **Cross-check.** Google reports 0.24 Wh, 0.03 gCO₂e and 0.26 mL of water for
  the median Gemini Apps text prompt, counting idle capacity, CPU/RAM and
  data-centre overhead. Counting active accelerators only, it reports 0.10 Wh
  ([Google Cloud blog, 21 Aug 2025](https://cloud.google.com/blog/products/infrastructure/measuring-the-environmental-impact-of-ai-inference)).
  These are Google's own measurements and have not been independently
  verified.

Two adjustments then apply:

- **Model size**, taken from relative list price because no model sizes are
  published: Haiku × 0.33, Sonnet × 1.0, Opus and Fable × 1.7, any other model × 1.0.
- **Data-centre overhead (PUE)** × 1.2, for cooling and power conversion.
  Google reports a fleet-wide PUE of 1.09 in the post above, so 1.2 leans
  conservative.

### 3. Carbon, heat and water (arithmetic)

| Result | Formula |
|---|---|
| CO₂e | kWh × grid intensity (default 400 gCO₂e/kWh) |
| Heat | ≈ kWh. Almost all electricity a data centre draws ends up as heat |
| Water | kWh × water use per kWh (default 1.0 L/kWh; Google's figures above work out to about 1.08) |
| Car km | CO₂e ÷ 170 g/km |
| Phone charges | Wh ÷ 15 Wh |
| Bottles | litres ÷ 0.5 |

### Worked example: one real response (Opus)

| Step | Calculation | Result |
|---|---|---|
| Output | 2,961 tokens × 0.6 Wh/1k | 1.78 Wh |
| Fresh input | 45,047 tokens × 0.2 Wh/1k | 9.01 Wh |
| Cache read | 44,766 tokens × 0.02 Wh/1k | 0.90 Wh |
| Subtotal | | 11.68 Wh |
| × Opus 1.7 × PUE 1.2 | | **23.8 Wh** |
| × 400 g/kWh | | **≈ 9.5 g CO₂e** |

---

## Assumptions you can change

Every constant sits near the top of `carbon.py`:

| Constant | Value | Status |
|---|---|---|
| `WH_PER_1K` | see the table above | Output and input are based on Epoch AI; cache read is an assumption |
| `MODEL_SCALE` | Haiku 0.33, Sonnet 1, Opus/Fable 1.7 | Assumption, from list price |
| `PUE` | 1.2 | Assumption, conservative next to Google's reported 1.09 |
| `--grid` | 400 gCO₂e/kWh | Assumption. The 2023 world average was about 481 g/kWh ([Our World in Data / Ember](https://ourworldindata.org/grapher/carbon-intensity-electricity)). Anthropic doesn't say which data centres or grids served a request, so set your own figure if you know better |
| `--wue` | 1.0 L/kWh | Assumption, close to Google's implied 1.08 |
| `CAR_G_PER_KM` | 170 | Rough assumption for a petrol car, used only for the comparison |
| `PHONE_CHARGE_WH` | 15 | Rough assumption, used only for the comparison |
| `LIVE_WINDOW_S` | 300 | The "right now" rate covers the last 5 minutes |
| `HOT_G_PER_MIN` | 50 | The rate at which the live chip is drawn fully red |

---

## What it does not include

- **Embodied carbon:** manufacturing the chips and servers.
- **Training:** this counts using the model, not training it.
- **Your own machine,** network transfer, and other tools you run.
- **Location-specific data:** the grid mix and water use of the actual data
  centre that served each request.

---

## Privacy and security

- **Nothing leaves your machine.** The script reads local files only and makes no outbound network requests.
- **The live server listens on `127.0.0.1` only.** The page shows your project names and session titles, so it isn't exposed to your network.
- **It refuses requests addressed to any other host name** (HTTP 403). This stops DNS rebinding, where a web page points its own name at your computer to read local servers.
- **Session titles are escaped.** They are text from your own logs, and the page escapes them so they can't inject markup.
- **The band runs only `python3 carbon.py`** and, when you click Dashboard, your operating system's URL opener: `open`, `xdg-open` or `start`.

---

## Performance

Measured on one macOS machine with about 4.2 GB of Claude Code logs:

| Operation | Time |
|---|---|
| 30-day scan (static report, or live mode's first load) | about 16 s |
| `--json` for today plus one session (what the band runs after each turn) | about 1.4 s |
| Each live poll after the first | reads only bytes added since the previous poll |

- **Skipped files:** logs not modified since the start of the window aren't opened.
- **Half-written lines:** a line still being written is left for the next poll.

---

## How the band works

- **Refreshing.** On session start and after every turn, the band runs
  `carbon.py --json --session <this session>` off the turn's path, then
  redraws with the result.
- **Dashboard.** Starts `carbon.py --live --port 8765` as a child of the
  session and opens `http://127.0.0.1:8765/` once it's serving. The server
  stops when the session ends. If another dashboard already holds the port,
  the band opens that one.
- **Audit.** Runs the `/tokentoll` skill.
- **Close and `/tokentoll-band`.** Hide and show the band. The choice is saved in the mod's store, so it carries over to new sessions, and a hidden band stops refreshing.
- **Sharing the slot.** If another mod also draws above the prompt (for
  example ponytail's band), it's shown beneath this one, not replaced.
- **Where it looks for the script.** `~/.claude/skills/tokentoll/carbon.py`,
  the install path above.

---

## Tests

```bash
# Estimator: deduplication, model scaling, incremental reads, session filter,
# session titles (escaped), cache-read ordering, the --json keys the band reads,
# flag checks, and the live server refusing other host names
cd ~/.claude/skills/tokentoll && python3 -m unittest -v test_carbon

# Band: numbers on terminal and desktop, Audit runs /tokentoll,
# Close and /tokentoll-band (remembered across sessions), error messages
claude plugin test ~/.claude/skills/tokentoll/band
```

---

## Known limitations

- **It depends on Claude Code's log format.** The tool reads Claude Code's
  internal session logs: `message.usage`, `message.id`, `requestId`,
  `timestamp`, `cwd`, `sessionId`, and the `custom-title`, `ai-title` and
  `last-prompt` records. That format isn't a documented API and may change.
- **Every rate is an estimate** whose range spans more than an order of
  magnitude. Cache reads usually dominate the total and have the least-known
  rate.
- **One project per session.** A session that moved between folders is listed
  under the first one it ran in.
- **Limited testing.** Tested on macOS only. The band's Windows and Linux
  browser-opening code has not been run.

---

## Contributing better numbers

If a provider publishes measured energy per token, or per request split by
input, output and cache, update `WH_PER_1K` and `MODEL_SCALE` in `carbon.py`.
Run the tests, and cite the source in this README. That is the single change
that would make these estimates most accurate.

---

## License

[MIT](LICENSE). Copyright (c) 2026 Aditya Kumar.
