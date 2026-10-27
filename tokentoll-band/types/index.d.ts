// Central estimates from `carbon.py --json`: grams CO2e, kWh (= heat released), litres of cooling water.
export type Figures = { g: number; kwh: number; water_l: number }
export type Summary = { today: Figures; session?: Figures & { tokens: number } }

declare module 'claude-code' {
  interface PluginState {
    'tokentoll-band': { summary: Summary | null; error: string | null; isStarting: boolean; isHidden: boolean }
  }
}
