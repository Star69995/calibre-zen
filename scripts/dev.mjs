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
import { existsSync } from 'node:fs'
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
function launcher(launcherArgs) {
  if (win) {
    return run('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', join(repo, 'calibre-zen.ps1'), ...launcherArgs])
  }
  return run(join(repo, 'calibre-zen'), launcherArgs)
}

// ./zen-test is a POSIX shell script. On Windows that means Git Bash: a bare
// `bash` on PATH is often WSL's launcher, which cannot see the Windows paths.
function posixShell() {
  if (!win) return 'sh'
  const candidates = [process.env.ProgramFiles, process.env['ProgramFiles(x86)'], process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Programs')]
    .filter(Boolean)
    .map((dir) => join(dir, 'Git', 'bin', 'bash.exe'))
  const found = candidates.find(existsSync)
  if (!found) die('the tests need Git Bash (https://git-scm.com/download/win); it was not found in the usual places')
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
  case 'start':
    launcher(args)
    break
  case 'tool':
    if (!args.length) die('usage: npm run tool -- <calibredb|calibre-debug|...> [args]')
    launcher(win ? ['-Tool', args[0], ...args.slice(1)] : ['--tool', ...args])
    break
  case 'test':
    run(posixShell(), [join(repo, 'zen-test'), ...args], testEnv())
    break
  case 'seed':
  case 'gutenberg': {
    const script = join('.calibre-zen', command === 'seed' ? 'seed-library.py' : 'gutenberg-library.py')
    const scriptArgs = ['calibre-debug', '-e', script, ...(args.length ? ['--', ...args] : [])]
    launcher(win ? ['-Tool', ...scriptArgs.slice(0, 1), ...scriptArgs.slice(1)] : ['--tool', ...scriptArgs])
    break
  }
  default:
    die(`unknown command '${command ?? ''}'. Use one of: start, tool, test, seed, gutenberg`)
}
