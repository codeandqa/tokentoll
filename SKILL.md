---
name: tokentoll
description: Estimate the carbon (CO2e), energy/heat (kWh) and cooling-water footprint of your AI coding (Claude Code, Codex, Gemini CLI, and any AI API logged to the usage file) from the token logs, and open a dashboard by day, session, project, model and tool. Use when the user asks about the environmental impact, carbon footprint, emissions, energy, heat or water of their AI coding, or says "ai carbon", "how green is my coding", "my AI footprint".
---

# TokenToll: the carbon footprint of your AI coding

Turns AI token usage into an energy, carbon, heat and water estimate, with a low–high range. It reads Claude Code (`~/.claude/projects`), Codex (`~/.codex/sessions`) and Gemini CLI (`~/.gemini/tmp`) automatically, plus `~/.tokentoll/usage.jsonl` for any API the user logs (README: "Log any AI API").

## Run it

```bash
python3 ~/.claude/skills/tokentoll/carbon.py --days 30
```

Then open the dashboard it prints (`open ~/.claude/tokentoll-report.html` on macOS) and give the user the one-line summary plus the top projects.

**Live mode** (when the user wants to watch it while they work): run it in the background and open the URL it prints.

```bash
python3 ~/.claude/skills/tokentoll/carbon.py --live --port 8765
```

It serves on 127.0.0.1 only. The page polls every 5 s, and each poll reads only the bytes appended to the logs since the last one. An animated AI chip heats from blue to red and gives off heat waves as the last 5 minutes' rate climbs to 50 g/min, while today's CO2e counter ticks up. Motion stops when the AI is idle or the viewer prefers reduced motion.

Flags:
- `--days N`: window (default 30).
- `--grid G`: grid carbon intensity in gCO2e/kWh (default 400; the 2023 world average was about 481 per Our World in Data / Ember). If the user names a region, look up its current figure from a primary source (Electricity Maps, Our World in Data / Ember) and cite it; never state one from memory. Anthropic doesn't publish which data centre served a request, so say that any grid figure is an assumption.
- `--wue L`: litres of water per kWh (default 1.0; Google's 2025 figures imply ~1.1).
- `--out PATH`: where to write the HTML.

The dashboard breaks usage down by session, project and model. Each session shows its full name: your rename if you gave one, otherwise Claude's AI title, otherwise the last prompt. Its project and short ID sit underneath. In live mode, sessions active in the last 5 minutes get a "● live" marker and are listed under the chip with their own g/min.

It reads `~/.claude/projects/**/*.jsonl` (subagents included), counts each API response once, and sends nothing over the network.

## Method (when asked "how do you know?")

Read `README.md` in this folder (sections Method and Assumptions you can change) and explain from it: it has every rate, its source and a worked example. Token counts are exact; energy per token is an estimate, so always quote the low–high range and call the result an order of magnitude. Not included: embodied hardware carbon, model training, the user's own machine.

## Tests

```bash
cd ~/.claude/skills/tokentoll && python3 -m unittest -q test_carbon
```
