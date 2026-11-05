// dev.mjs -- the one place the npm scripts in package.json go through.
//
// The repo has no JavaScript: package.json is only a front door to the launchers
// that already exist, so `npm run start` and `npm test` work the same on every
// machine. This picks the right launcher for the OS and passes the rest of the
// command line through untouched, e.g. `npm test -- theme icons -k hover`.
//
//   node scripts/dev.mjs start   [app args]   the app from this tree
//   node scripts/dev.mjs tool    <tool> ...   a bundled tool (calibredb, calibre-debug, ...)
//   node scripts/dev.mjs test    [modules]    the tests, headless
//   node scripts/dev.mjs seed    [options]    build the generated dev library
//   node scripts/dev.mjs gutenberg [options]  build the Project Gutenberg dev library
import { spawnSync } from 'node:child_process'
import { existsSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const win = process.platform === 'win32'
const [command, ...args] = process.argv.slice(2)

function die(message) {
  console.error(`dev: ${message}`)
  process.exit(1)
}

function run(file, fileArgs, env = {}) {
  const result = spawnSync(file, fileArgs, { cwd: repo, stdio: 'inherit', env: { ...process.env, ...env } })
  if (result.error) die(`cannot run ${file}: ${result.error.message}`)
  process.exit(result.status ?? 1)
}

// calibre-zen.ps1 on Windows (run through PowerShell without touching its
// execution policy, like calibre-zen.cmd does), ./calibre-zen elsewhere.
function launcher(launcherArgs, env = {}) {
  if (win) {
    return run('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', join(repo, 'calibre-zen.ps1'), ...launcherArgs], env)
  }
  return run(join(repo, 'calibre-zen'), launcherArgs, env)
}

// A bundled tool. PowerShell would read a tool's own `-e` or `--` as a
// parameter of calibre-zen.ps1 (and call it ambiguous), so on Windows the
// arguments travel as JSON and are bound to -Rest by name, as plain values.
function tool(name, toolArgs) {
  if (!win) return launcher(['--tool', name, ...toolArgs])
  const script = join(repo, 'calibre-zen.ps1').replaceAll("'", "''")
  return run(
    'powershell',
    ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', `$a = [string[]](ConvertFrom-Json $env:ZEN_DEV_ARGS); & '${script}' -Tool '${name}' -Rest $a; exit $LASTEXITCODE`],
    { ZEN_DEV_ARGS: JSON.stringify(toolArgs) },
  )
}

// ./zen-test is a POSIX shell script. On Windows that means Git Bash: a bare
// `bash` on PATH is often WSL's launcher, which cannot see the Windows paths.
function posixShell() {
  if (!win) return 'sh'
  // Git for Windows can be installed anywhere, so look beside git.exe on PATH
  // (<root>\cmd\git.exe, <root>\bin\bash.exe) before the default locations.
  const roots = (process.env.PATH ?? '')
    .split(';')
    .filter((dir) => existsSync(join(dir, 'git.exe')))
    .map((dir) => dirname(dir))
  for (const dir of [process.env.ProgramFiles, process.env['ProgramFiles(x86)'], process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Programs')]) {
    if (dir) roots.push(join(dir, 'Git'))
  }
  const found = roots.map((root) => join(root, 'bin', 'bash.exe')).find(existsSync)
  if (!found) die('the tests need Git Bash (https://git-scm.com/download/win); it was not found next to git.exe or in the usual places')
  return found
}

// zen-test finds calibre-debug itself on macOS and on PATH. On Windows it
// would not, so default to the installed Calibre Zen, as calibre-zen.ps1 does.
function testEnv() {
  if (!win || process.env.CALIBRE_ZEN_CALIBRE_DEBUG) return {}
  const bundle = process.env.CALIBRE_ZEN_BUNDLE || join(process.env.ProgramFiles || 'C:\\Program Files', 'Calibre Zen')
  const debug = join(bundle, 'calibre-debug.exe')
  if (!existsSync(debug)) die(`cannot find calibre-debug.exe in '${bundle}'. Install Calibre Zen, or set CALIBRE_ZEN_CALIBRE_DEBUG.`)
  return { CALIBRE_ZEN_CALIBRE_DEBUG: debug }
}

switch (command) {
  case 'start': {
    // --lang <code> and --fresh mean the same everywhere. calibre-zen.ps1 has
    // them as -Lang / -Fresh; ./calibre-zen has neither, so there the language
    // goes through calibre's own override and fresh means deleting the settings.
    const rest = []
    let lang = ''
    let fresh = false
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--lang') lang = args[++i] ?? die('--lang needs a language code')
      else if (args[i] === '--fresh') fresh = true
      else rest.push(args[i])
    }
    if (win) launcher([...(lang ? ['-Lang', lang] : []), ...(fresh ? ['-Fresh'] : []), ...rest])
    if (fresh) rmSync(join(repo, '.calibre-zen', 'config'), { recursive: true, force: true })
    launcher(rest, lang ? { CALIBRE_OVERRIDE_LANG: lang } : {})
    break
  }
  case 'tool':
    if (!args.length) die('usage: npm run tool -- <calibredb|calibre-debug|...> [args]')
    tool(args[0], args.slice(1))
    break
  case 'test':
    run(posixShell(), [join(repo, 'zen-test'), ...args], testEnv())
    break
  case 'seed':
  case 'gutenberg': {
    const script = join('.calibre-zen', command === 'seed' ? 'seed-library.py' : 'gutenberg-library.py')
    tool('calibre-debug', ['-e', script, ...(args.length ? ['--', ...args] : [])])
    break
  }
  default:
    die(`unknown command '${command ?? ''}'. Use one of: start, tool, test, seed, gutenberg`)
}
