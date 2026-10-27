import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Summary } from '../types'

const summary = atom({ plugin: 'tokentoll-band', key: 'summary' } as const, null)
// Why the last refresh failed, shown in place of "measuring…" until one succeeds.
const error = atom({ plugin: 'tokentoll-band', key: 'error' } as const, null)
const isStarting = atom({ plugin: 'tokentoll-band', key: 'isStarting' } as const, false)
const isHidden = atom({ plugin: 'tokentoll-band', key: 'isHidden' } as const, false)

const COMMAND = 'tokentoll-band'

// Closing is remembered across sessions; /tokentoll-band brings the band back.
async function setHidden($: EngineInterface, hidden: boolean) {
  await update($, isHidden, () => hidden)
  await $.store.set('hidden', hidden)
  if (!hidden) void refresh($)
}

const PORT = '8765'
const URL = `http://127.0.0.1:${PORT}/`

const script = async ($: EngineInterface) => `${(await $.env.get('HOME')) ?? '~'}/.claude/skills/tokentoll/carbon.py`

const fmtG = (g: number) => (g >= 1000 ? `${(g / 1000).toFixed(2)} kg` : `${Math.round(g)} g`)
const fmtKwh = (k: number) => (k >= 1 ? `${k.toFixed(2)} kWh` : `${Math.round(k * 1000)} Wh`)
const fmtL = (l: number) => (l >= 1 ? `${l.toFixed(1)} L` : `${Math.round(l * 1000)} mL`)

async function openUrl($: EngineInterface, url: string) {
  const windows = (await $.env.get('OS')) === 'Windows_NT'
  const mac = !windows && (await $.process.run(['uname'])).stdout.trim() === 'Darwin'
  await $.process.run(windows ? ['cmd', '/c', 'start', '', url] : [mac ? 'open' : 'xdg-open', url])
}

let isRefreshing = false
// The live server runs as this session's child; resolves once it serves (or found one already serving).
let ready: Promise<void> | undefined

// Re-reads the logs for this session and today (about a second), off the turn's path.
async function refresh($: EngineInterface) {
  if (isRefreshing) return
  isRefreshing = true
  try {
    const id = await $.session.id()
    const out = await $.process.run(['python3', await script($), '--json', '--session', id], { timeoutMs: 60000 })
    if (out.exitCode === 0) {
      await update($, summary, () => JSON.parse(out.stdout) as Summary)
      await update($, error, () => null)
    } else {
      // The last stderr line names the cause, e.g. "can't open file …/carbon.py: No such file or directory".
      const cause = out.stderr.trim().split('\n').pop() ?? ''
      await update($, error, () => `carbon.py failed: ${cause.slice(0, 120)} (see README)`)
      $.ui.log(`tokentoll-band: carbon.py exited ${out.exitCode}: ${out.stderr.slice(0, 300)}`, { to: 'debug' })
    }
  } catch (err) {
    // process.run rejects when the command cannot start at all: no python3 on PATH.
    await update($, error, () => 'could not start python3 (see README)')
    $.ui.log(`tokentoll-band: ${String(err)}`, { to: 'debug' })
  } finally {
    isRefreshing = false
  }
}

function startServer($: EngineInterface) {
  return (ready ??= new Promise<void>(resolve => {
    void keepServing($, resolve)
  }))
}

// Leaving this loop kills the server, so it runs for the session's life.
async function keepServing($: EngineInterface, resolve: () => void) {
  try {
    const argv = ['python3', await script($), '--live', '--port', PORT]
    for await (const { text } of $.process.spawn({ argv })) {
      if (text.includes('Live dashboard') || text.includes('is busy')) resolve()
    }
  } catch (err) {
    $.ui.log(`tokentoll-band: dashboard server: ${String(err)}`, { to: 'debug' })
  }
  // It ended: a busy port means another one already serves; anything else, the next click retries.
  ready = undefined
  resolve()
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({ name: COMMAND, description: 'Show or hide the TokenToll band above the prompt' })
    const hidden = (await $.store.get('hidden')) === true
    await update($, isHidden, () => hidden)
    if (!hidden) void refresh($)
    return started
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (!(await read($, isHidden))) void refresh($)
    return done
  })

  // /tokentoll-band toggles; /tokentoll-band show or /tokentoll-band hide sets it.
  on('command.run', { command: COMMAND }, async ($, e) => {
    const arg = (e.args ?? '').trim()
    const hidden = arg === 'hide' ? true : arg === 'show' ? false : !(await read($, isHidden))
    await setHidden($, hidden)
    return { text: hidden ? 'TokenToll band hidden. Type /tokentoll-band to show it again.' : 'TokenToll band shown.' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || (await read($, isHidden))) return next(e)
    // Other mods share this slot (ponytail's band): draw theirs beneath ours.
    const below = await next(e).catch(() => undefined)
    const s = await read($, summary)
    const failure = await read($, error)
    const starting = await read($, isStarting)

    const dashboard = async () => {
      if (await read($, isStarting)) return
      await update($, isStarting, () => true)
      if (!ready) $.ui.toast('Starting the carbon dashboard: the first scan takes about 15 s')
      try {
        await startServer($)
        await openUrl($, URL)
      } catch {
        $.ui.toast(`tokentoll: could not open ${URL}`)
      } finally {
        await update($, isStarting, () => false)
      }
    }
    const audit = () => $.command.run({ command: 'tokentoll' })
    const close = async () => {
      await setHidden($, true)
      $.ui.toast('TokenToll band hidden. Type /tokentoll-band to show it again.')
    }

    const { Box, Text, Button } = $.ui.resolve(e)
    const session = s?.session
    const mine = (
      <Box flexDirection="row" alignItems="center" gap={2} width={e.props.bodyColumns}>
        <Text color="success">● CO₂</Text>
        {s === null ? (
          failure ? <Text color="warning">{failure}</Text> : <Text dimColor>measuring…</Text>
        ) : (
          <>
            {session && <Text>this session {fmtG(session.g)}</Text>}
            {session && <Text dimColor>{fmtKwh(session.kwh)} heat</Text>}
            {session && <Text dimColor>{fmtL(session.water_l)} water</Text>}
            <Text dimColor>today {fmtG(s.today.g)}</Text>
          </>
        )}
        <Box flexGrow={1} />
        <Button key="dashboard" plain label={starting ? 'Starting…' : 'Dashboard'} onPress={dashboard} />
        <Button key="audit" plain label="Audit" onPress={audit} />
        <Button key="close" plain label="Close" onPress={close} />
      </Box>
    )
    return below ? (
      <Box flexDirection="column">
        {mine}
        {below}
      </Box>
    ) : (
      mine
    )
  })
}
