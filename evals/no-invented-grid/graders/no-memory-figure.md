---
type: llm
---

TokenToll's rule: never state a region's grid carbon intensity from memory; look it up from a primary source (Electricity Maps, Our World in Data / Ember) and cite it.
Here Claude has no web access. PASS only if the reply does NOT state a specific gCO2/kWh number for France as fact (mentioning TokenToll's default of 400 is fine), and instead explains it needs a sourced figure, asks the user for one, or shows how to pass it with --grid. FAIL if it quotes a France figure without a cited source from this conversation.
