import { expect, mock, test } from 'claude-code/testing'

const BAND = {
  plugin: 'tokentoll-band',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 100, scroll: { offset: 0, bodyRows: 10 }, view: {} },
} as const

const SUMMARY = { today: { g: 2104.2, kwh: 5.26, water_l: 5.26 }, session: { g: 377.08, kwh: 0.9427, water_l: 0.943, tokens: 18187465 } }

test('the band shows this session and today after session start, and names itself', async ($, on) => {
  const runs: string[][] = []
  mock.store(on)
  on('command.register', () => ({ value: { command: 'tokentoll-band' } }))
  on('session.id', () => ({ value: 'b5c1e717' }))
  on('env.get', () => ({ value: '/home/me' }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('process.run', (_, e) => {
    runs.push([...e.argv])
    return { value: { exitCode: 0, stdout: JSON.stringify(SUMMARY), stderr: '' } }
  })

  const before = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await before.find({ type: 'Text', text: /TokenToll/ })).toBeDefined()
  expect(await before.find({ type: 'Text', text: /measuring/ })).toBeDefined()
  await before.unmount()

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  for (let i = 0; i < 50 && runs.length === 0; i++) await new Promise(r => setTimeout(r, 10))
  await new Promise(r => setTimeout(r, 20))
  expect(runs[0]).toEqual(['python3', '/home/me/.claude/skills/tokentoll/carbon.py', '--json', '--session', 'b5c1e717'])

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.find({ type: 'Text', text: /this session/ }))?.text).toBe('this session 377 g')
    expect((await ui.find({ type: 'Text', text: /today/ }))?.text).toBe('today 2.10 kg')
    expect((await ui.find({ type: 'Text', text: /heat/ }))?.text).toBe('943 Wh heat')
    expect(await ui.find({ type: 'Text', text: /measuring/ })).toBeUndefined()
    for (const key of ['dashboard', 'audit', 'close']) expect(await ui.find({ key })).toBeDefined()
    await ui.unmount()
  }
})

test('Carbon audit sends Claude a prompt that starts a turn', async ($, on) => {
  const prompts: string[] = []
  mock.store(on)
  on('session.id', () => ({ value: 'b5c1e717' }))
  on('env.get', () => ({ value: '/home/me' }))
  on('process.run', () => ({ value: { exitCode: 0, stdout: JSON.stringify(SUMMARY), stderr: '' } }))
  on('prompt.submit', (_, e) => {
    prompts.push(e.text)
    return { text: e.text }
  })
  on('command.run', () => {
    throw new Error('Carbon audit must not use $.command.run: it starts no turn')
  })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await ui.press({ key: 'audit' })
  expect(prompts).toHaveLength(1)
  expect(prompts[0]).toContain('tokentoll skill')
  await ui.unmount()
})

test('Close hides the band until /tokentoll-band, and the choice is remembered', async ($, on) => {
  mock.store(on)
  on('process.run', () => ({ value: { exitCode: 0, stdout: JSON.stringify(SUMMARY), stderr: '' } }))
  on('session.id', () => ({ value: 'b5c1e717' }))
  on('env.get', () => ({ value: '/home/me' }))
  on('command.register', () => ({ value: { command: 'tokentoll-band' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  // Stands for the engine's own band slot, drawn when the band passes.
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  const shown = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await shown.find({ type: 'Text', text: /TokenToll/ })).toBeDefined()
  await shown.press({ key: 'close' })
  await shown.unmount()

  const closed = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await closed.find({ type: 'Text', text: /TokenToll/ })).toBeUndefined()
  await closed.unmount()

  // A new session reads the remembered choice.
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const later = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await later.find({ type: 'Text', text: /TokenToll/ })).toBeUndefined()
  await later.unmount()

  expect((await $.command.run({ command: 'tokentoll-band' })).text).toBe('TokenToll band shown.')
  const back = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await back.find({ type: 'Text', text: /TokenToll/ })).toBeDefined()
  await back.unmount()
})

test('the band says why it has no numbers when carbon.py cannot run', async ($, on) => {
  const cases = [
    {
      run: () => ({
        value: { exitCode: 2, stdout: '', stderr: "python3: can't open file '/home/me/.claude/skills/tokentoll/carbon.py': [Errno 2] No such file or directory\n" },
      }),
      shows: /carbon\.py failed: .*can't open file.*\(see README\)/,
    },
    {
      run: () => {
        throw new Error('spawn python3 ENOENT')
      },
      shows: /could not start python3 \(see README\)/,
    },
  ]
  mock.store(on)
  on('command.register', () => ({ value: { command: 'tokentoll-band' } }))
  on('session.id', () => ({ value: 'b5c1e717' }))
  on('env.get', () => ({ value: '/home/me' }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  let current = cases[0]!
  on('process.run', () => current.run())

  for (const c of cases) {
    current = c
    await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
    for (let i = 0; i < 20; i++) await new Promise(r => setTimeout(r, 10))
    for (const surface of ['terminal', 'desktop'] as const) {
      const ui = await $.ui.mount({ ...BAND, surface })
      expect(await ui.find({ type: 'Text', text: c.shows })).toBeDefined()
      expect(await ui.find({ type: 'Text', text: /measuring/ })).toBeUndefined()
      await ui.unmount()
    }
  }
})
