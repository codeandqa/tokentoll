#!/bin/bash
# One Claude Code session in project "demo-app": 1,000,000 Sonnet output tokens, logged now.
# TokenToll's central estimate: 1,000 x 0.6 Wh x PUE 1.2 = 720 Wh -> 288 g CO2e at 400 g/kWh (range 96 g - 960 g).
set -euo pipefail
dir="$HOME/.claude/projects/-work-demo-app"
mkdir -p "$dir"
now=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)
printf '{"type":"custom-title","customTitle":"Demo app checkout flow","sessionId":"demo-1"}\n' > "$dir/demo-1.jsonl"
printf '{"type":"assistant","timestamp":"%s","requestId":"r1","sessionId":"demo-1","cwd":"/work/demo-app","message":{"id":"m1","model":"claude-sonnet-5-5","usage":{"input_tokens":0,"output_tokens":1000000}}}\n' "$now" >> "$dir/demo-1.jsonl"
