"""The `app` backend: Herdr's desktop app, a client of the herdr-core that runs
every terminal it shows. A session, a pilot's session and a pilot's loop are
core terminals, made and found with `hc` by the labels of README.md (In the
app); the window, which only names and focuses them, is driven with
`herdr-app`. No other file runs `hc` or `herdr-app`.

Nothing here types into a terminal: no `hc send`, `hc keys` or `hc attach`, and
nothing with `--force`. A terminal's screen is its whole text, so `hc get`'s is
dropped as its answer is read, and `hc read`'s goes to the caller and nowhere
else: no message here carries one."""
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import AT_REST, BUSY, ENDED, FRONTEND_ENV, Failed, Worker

HC = "hc"
HERDR_APP = "herdr-app"
WINDOW_COMMANDS = {"space.rename": ("id", "name"), "tab.rename": ("id", "name"), "agent.focus": ("terminal",)}
ATTEMPTS = 20
PAUSE = 0.25
WAIT = 10
LINES = 80
PILOT = "autopilot"
LOOP_SCRIPT = ("herdr", "bin", "autopilot")


@dataclass
class Space:
    name: str


@dataclass
class Session:
    address: str
    name: str
    row: dict = None


@dataclass
class Tab:
    """A terminal the autopilot closes or looks for: `live` as `hc ls` said it."""
    address: str
    name: str
    live: bool

    def __str__(self):
        return self.address


def call(*command):
    return subprocess.run(command, capture_output=True, text=True)


def explain(p, private=False):
    """What a failed command said: hc answers `{"error": {kind, message, hint}}`,
    herdr-app `{"error": text}`. When `private`, its output may be a terminal's
    text: what is not an `error` of that shape is not repeated, only the exit
    status is."""
    for text in (p.stdout, p.stderr):
        try:
            error = json.loads(text)["error"]
        except (ValueError, KeyError, TypeError):
            continue
        if not isinstance(error, dict):
            return str(error)
        hint = error.get("hint")
        return ": ".join(str(error[k]) for k in ("kind", "message") if error.get(k)) + (f" ({hint})" if hint else "")
    if private:
        return f"exit status {p.returncode}"
    return (p.stderr or p.stdout).strip() or f"exit status {p.returncode}"


def run(*command, private=False):
    """The standard output of `command`. A `private` one may be a terminal's
    text: when it fails, the message says nothing of it, as `parse` does not."""
    p = call(*command)
    if p.returncode:
        raise Failed(f"{' '.join(command[:3] if command[1] == 'do' else command[:2])}: {explain(p, private)}")
    return p.stdout


def parse(text, what, private=False):
    """The JSON `text` holds. A `private` answer may be a terminal's text: an
    error about it says nothing of it."""
    try:
        return json.loads(text)
    except ValueError:
        raise Failed(f"{what}: its answer is not JSON" + ("" if private else f": {text[:80]!r}")) from None


def show(command):
    print(shlex.join(command))


def missing():
    return [program for program in (HC, HERDR_APP) if shutil.which(program) is None]


def core_socket(environ=None, run_user=None):
    """Where `hc` looks for the core's socket. This mirrors herdr-core 0.1.21
    (`paths.rs`, `platform/unix.rs`), which may move it: there is no `hc`
    command that tells without starting a core.

    The config file is read for its top-level `socket = "…"` line alone, before
    the first table: the OS's python3 has no `tomllib`, so this is not a TOML
    parser, and a value with escapes is taken as written."""
    environ = os.environ if environ is None else environ
    if environ.get("HC_SOCKET"):
        return environ["HC_SOCKET"]
    home = environ.get("HOME") or os.path.expanduser("~")
    config = Path(environ.get("XDG_CONFIG_HOME") or f"{home}/.config") / "herdr-core" / "config.toml"
    try:
        for line in config.read_text().splitlines():
            if line.lstrip().startswith("["):
                break
            m = re.fullmatch(r"\s*socket\s*=\s*(?:\"([^\"]*)\"|'([^']*)')\s*(?:#.*)?", line)
            if m and (m.group(1) or m.group(2)):
                return m.group(1) or m.group(2)
    except (OSError, ValueError):
        pass
    session = environ.get("HC_SESSION") or "default"
    run_user = run_user or f"/run/user/{os.getuid()}"
    if environ.get("XDG_RUNTIME_DIR"):
        return f"{environ['XDG_RUNTIME_DIR']}/herdr-core/{session}.sock"
    if os.path.isdir(run_user):
        return f"{run_user}/herdr-core/{session}.sock"
    state = environ.get("XDG_STATE_HOME") or f"{home}/.local/state"
    return f"{state}/herdr-core/{session}/{session}.sock"


def answers():
    """Whether the core's socket accepts a connection, closed at once. Not
    `hc server status`: on macOS and Linux that starts a core that is not
    running, and so does every other `hc` command that asks."""
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(2)
        try:
            s.connect(core_socket())
        except OSError:
            return False
    return True


def shows():
    return call(HERDR_APP, "status").returncode == 0


def require():
    """Fails, before anything is made, when the window has no command used
    here, or one of its arguments."""
    try:
        commands = {c["name"]: {a["name"] for a in c["args"]}
                    for c in parse(run(HERDR_APP, "commands"), "herdr-app commands")}
    except (KeyError, TypeError):
        raise Failed("herdr-app commands: its answer is not a list of commands") from None
    for command, arguments in WINDOW_COMMANDS.items():
        if command not in commands or not set(arguments) <= commands[command]:
            raise Failed(f"herdr-app has no command {command} with {', '.join(arguments)} "
                         "(`herdr-app commands` lists them): was it changed?")


def listing(labels, finished):
    """The rows of `hc ls` that carry all the `labels`, the finished ones too
    when asked."""
    command = [HC, "ls", *(["--all"] if finished else []),
               *[arg for label in labels for arg in ("--label", label)], "--json"]
    try:
        rows = parse(run(*command), "hc ls")["terminals"]
        if not all(isinstance(row, dict) and "address" in row for row in rows):
            raise TypeError
    except (KeyError, TypeError):
        raise Failed("hc ls: its answer has no list of terminals") from None
    return rows


def find_session(name):
    terminals = listing((f"oxc0.space={name}", "oxc0.role=session"), finished=False)
    if not terminals:
        return None
    addresses = [t["address"] for t in terminals]
    if len(addresses) > 1:
        print(f"{name}: {len(addresses)} sessions carry its labels ({', '.join(addresses)}); "
              f"taking the first, {addresses[0]}")
    return Session(addresses[0], name)


def focus_session(session):
    if not shows():
        print(f"{session.name} runs as {session.address}, and the app's window is not there to show it")
        return
    require()
    focus(session.address)


def focus(address):
    run(HERDR_APP, "do", "agent.focus", "--terminal", address)


def run_command(space, name, directory, program, role, flags, labels=()):
    """The `hc run` that makes a terminal called `name` in the space called
    `space`: `herdr.space` and `herdr.tab` place it in the app, and the labels
    of ours are how it is found again. `--no-parent --no-notify`: started from
    inside a terminal, a new terminal is otherwise that terminal's sub-agent,
    ends with it, and has notes about it typed into it. README.md, In the app."""
    return [HC, "run", "--bg", *flags, "--no-parent", "--no-notify", "--json",
            "--name", name, "--cwd", str(directory),
            "--label", f"herdr.space=oxc0-{space}", "--label", f"herdr.tab=oxc0-{name}",
            "--label", f"oxc0.space={space}", "--label", f"oxc0.role={role}",
            *[arg for label in labels for arg in ("--label", label)],
            "--", *program]


def start_command(name, directory, args):
    """A session opened by hand. `--keep` and `--rm` are why it is safe to leave
    unattended: README.md, Opening a session by hand."""
    return run_command(name, name, directory, ["claude", *args], "session", ["--keep", "--rm"])


def naming(space, name, label):
    """The window's commands that call the space `space` and the tab of the
    terminal called `name` `label`."""
    return [[HERDR_APP, "do", "space.rename", "--id", f"oxc0-{space}", "--name", space],
            [HERDR_APP, "do", "tab.rename", "--id", f"oxc0-{name}", "--name", label]]


def name_in_window(commands):
    """Runs the window's `commands`, each retried until it answers: the window
    shows a new terminal a moment after `hc run` returns. None when all
    worked, else what the window last said."""
    for command in commands:
        p = call(*command)
        for _ in range(ATTEMPTS - 1):
            if p.returncode == 0:
                break
            time.sleep(PAUSE)
            p = call(*command)
        if p.returncode:
            return explain(p)
    return None


def open_session(name, directory, args, dry=False):
    window = shows()
    if window:
        require()
    start = start_command(name, directory, args)
    rename = naming(name, name, name)
    if dry:
        show(start)
        if not window:
            print("# the app's window does not answer: nothing to name or focus")
            return
        for command in rename:
            show(command)
        show([HERDR_APP, "do", "agent.focus", "--terminal", "<new terminal>"])
        return
    try:
        answer = parse(run(*start), "hc run")
    except Failed as e:
        if "name_taken" in str(e):
            raise Failed(f"{e}: a terminal has this name without the labels of a session; if it is the "
                         f"session, adopt it with `hc label <terminal> oxc0.space={name} oxc0.role=session`") from None
        raise
    try:
        session = Session(answer["address"], name)
    except (KeyError, TypeError):
        raise Failed("hc run: its answer has no address") from None
    if not window:
        print(f"{name} started as {session.address}, and the app's window was not there to name or show it")
        return
    why = name_in_window(rename)
    if why:
        raise Failed(f"{name} started as {session.address}, but the window did not show it: {why}")
    focus(session.address)


def begin(start, rename, name, dry):
    """Makes the terminal `start` describes, in the background, then names its
    space and tab through the window when it answers. The terminal runs
    whether or not the window names it: a window that does not show it is
    said, not an error."""
    window = shows()
    if dry:
        show(start)
        if not window:
            print("# the app's window does not answer: nothing to name")
            return
        for command in rename:
            show(command)
        return
    answer = parse(run(*start), "hc run")
    try:
        address = answer["address"]
    except (KeyError, TypeError):
        raise Failed("hc run: its answer has no address") from None
    why = name_in_window(rename) if window else None
    if why:
        print(f"{name} started as {address}, but the window did not show it to name it: {why}")


def find_space(name):
    return Space(name)


def issue_of(space, name):
    """The issue's number in a session's name, `<space>-<n>`; None if it has none."""
    m = re.fullmatch(rf"{re.escape(space)}-(\d+)", name or "")
    return int(m.group(1)) if m else None


def live(row):
    return row.get("state") != "finished"


def workers(space, dry=False):
    for row in listing((f"oxc0.space={space.name}", "oxc0.role=worker"), finished=True):
        n = issue_of(space.name, row.get("name"))
        if n is not None:
            yield Worker(n, row["name"], Tab(row["address"], row["name"], live(row)),
                         Session(row["address"], row["name"], row))


def terminal(address):
    """What `hc get` says of a terminal, without its screen, which is the
    terminal's whole text: none of it is kept, not even in an error."""
    answer = parse(run(HC, "get", address, "--json", private=True), "hc get", private=True)
    if not isinstance(answer, dict):
        raise Failed("hc get: its answer is not a terminal")
    answer.pop("screen", None)
    return answer


def in_front(address):
    """The command line of what runs in front of the terminal: empty when `hc
    get` has no `foreground` for it, as for one that just started. `hc get` has
    it, `hc ls` does not."""
    return (terminal(address).get("foreground") or {}).get("argv") or []


def left_as_shell(session):
    """Whether a session that reports nothing has lost its program. `--keep`
    puts a shell in its place (`hc run --help`), which never reports, so
    without this it would be taken for a session still starting for ever.
    What runs in front of the terminal tells: Claude Code's own command line
    carries the name the session was given, and `env` is Claude Code a moment
    before it becomes it."""
    argv = in_front(session.address)
    return bool(argv) and session.name not in argv and os.path.basename(argv[0]) not in ("claude", "env")


def session_state(session):
    row = session.row
    if not live(row):
        return ENDED
    status = row.get("status")
    if not status:
        # Nothing reported yet: starting, or no program left.
        return ENDED if left_as_shell(session) else BUSY
    # Claude Code reports `idle` once at turn 0, before it takes its prompt.
    if (row.get("turn") or 0) >= 1 and status in ("idle", "done"):
        return AT_REST
    return BUSY


def read_screen(session):
    answer = parse(run(HC, "read", session.address, "--json", "--lines", str(LINES), private=True),
                   "hc read", private=True)
    text = answer.get("text") if isinstance(answer, dict) else None
    if not isinstance(text, str):
        raise Failed("hc read: its answer has no text")
    return text


def remove(address):
    """`hc rm`, which takes a finished terminal only; one already gone is as
    good."""
    try:
        run(HC, "rm", address)
    except Failed as e:
        if "not_found" not in str(e):
            raise


def close_tab(tab, dry=False):
    """The terminal's end: `hc kill` while it is live, `hc wait` until it is
    finished, then `hc rm`. The app closes the tab with the terminal."""
    kill = [HC, "kill", tab.address]
    wait = [HC, "wait", tab.address, "--timeout", str(WAIT), "--json"]
    if dry:
        for command in (kill, wait) if tab.live else ():
            show(command)
        show([HC, "rm", tab.address])
        return
    if tab.live:
        try:
            run(*kill)
        except Failed as e:
            if "not_found" in str(e):
                return
            raise
        ended = parse(run(*wait), "hc wait")
        if not isinstance(ended, dict) or ended.get("ended") is not True:
            raise Failed(f"{tab.name} did not end {WAIT} seconds after hc kill")
    remove(tab.address)


def start_session(space, name, directory, command, env, dry=False):
    n = issue_of(space.name, name)
    if n is None:
        raise Failed(f"{name} is not a session of {space.name}: its name is {space.name}-<issue>")
    program = [*(["env", *[f"{k}={v}" for k, v in env.items()]] if env else []), *shlex.split(command)]
    start = run_command(space.name, name, directory, program, "worker", ["--keep"], [f"oxc0.issue={n}"])
    begin(start, naming(space.name, name, name), name, dry)


def pilot(name):
    rows = listing((f"oxc0.space={name}", "oxc0.role=autopilot"), finished=True)
    for row in rows:
        if not live(row) and row.get("exit_code") == 0:
            remove(row["address"])
    left = [row for row in rows if live(row) or row.get("exit_code") != 0]
    if not left:
        return None
    row = next((row for row in left if live(row)), left[0])
    return Tab(row["address"], row.get("name") or f"{name}-{PILOT}", live(row))


def runs_loop(argv):
    """Whether `argv` is the loop's command line: an interpreter, a path that
    ends in `herdr/bin/autopilot`, then `run`. The path is not compared whole:
    a loop started from another checkout of the workspace is the loop all the
    same."""
    return len(argv) > 2 and argv[2] == "run" and Path(argv[1]).parts[-3:] == LOOP_SCRIPT


def pilot_alive(tab):
    """Whether the loop itself runs in the autopilot's terminal. `live` says a
    program does, not which: a loop the core lost may be replaced by a shell in
    place, live with nothing of ours in it, and `start` must then close it and
    start another. What runs in front tells, as for a session: the loop, or
    `env`, which is it for a moment before it becomes it, or nothing yet; any
    other command line is not the loop."""
    if not tab.live:
        return False
    argv = in_front(tab.address)
    return not argv or os.path.basename(argv[0]) == "env" or runs_loop(argv)


def start_pilot(name, directory, command):
    terminal_name = f"{name}-{PILOT}"
    # The core gives a terminal its own environment, not the caller's.
    program = ["env", f"{FRONTEND_ENV}=app", *shlex.split(command)]
    start = run_command(name, terminal_name, directory, program, PILOT, [])
    begin(start, naming(name, terminal_name, PILOT), terminal_name, False)


def is_own_tab(tab):
    return False
