"""The `app` backend: Herdr's desktop app, a client of the herdr-core that runs
every terminal it shows. A session is a core terminal, made and found with `hc`
by the labels of README.md (Opening a session by hand); the window, which
only names and focuses it, is driven with `herdr-app`. Nothing here types into
a terminal or reads its screen, and no other file runs `hc` or `herdr-app`.

Only what `bin/open-session` asks of the layer is here: the other operations
fail with a message until the autopilot needs them."""
import json
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass

from . import Failed

HC = "hc"
HERDR_APP = "herdr-app"
WINDOW_COMMANDS = {"space.rename": ("id", "name"), "tab.rename": ("id", "name"), "agent.focus": ("terminal",)}
ATTEMPTS = 20
PAUSE = 0.25


@dataclass
class Session:
    address: str
    name: str


def call(*command):
    return subprocess.run(command, capture_output=True, text=True)


def explain(p):
    """What a failed command said: hc answers `{"error": {kind, message, hint}}`,
    herdr-app `{"error": text}`."""
    for text in (p.stdout, p.stderr):
        try:
            error = json.loads(text)["error"]
        except (ValueError, KeyError, TypeError):
            continue
        if not isinstance(error, dict):
            return str(error)
        hint = error.get("hint")
        return ": ".join(str(error[k]) for k in ("kind", "message") if error.get(k)) + (f" ({hint})" if hint else "")
    return (p.stderr or p.stdout).strip() or f"exit status {p.returncode}"


def run(*command):
    p = call(*command)
    if p.returncode:
        raise Failed(f"{' '.join(command[:3] if command[1] == 'do' else command[:2])}: {explain(p)}")
    return p.stdout


def parse(text, what):
    try:
        return json.loads(text)
    except ValueError:
        raise Failed(f"{what}: its answer is not JSON: {text[:80]!r}") from None


def show(command):
    print(shlex.join(command))


def missing():
    return [program for program in (HC, HERDR_APP) if shutil.which(program) is None]


def answers():
    # The command made to report the core: a terminal command may start one
    # that is not running, and a lookup must not.
    return call(HC, "server", "status", "--json").returncode == 0


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


def find_session(name):
    answer = parse(run(HC, "ls", "--label", f"oxc0.space={name}", "--label", "oxc0.role=session", "--json"),
                   "hc ls")
    try:
        terminals = answer["terminals"]
        if not terminals:
            return None
        addresses = [t["address"] for t in terminals]
    except (KeyError, TypeError):
        raise Failed("hc ls: its answer has no list of terminals") from None
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


def start_command(name, directory, args):
    """The session's terminal. `--keep`, `--no-parent`, `--no-notify` and
    `--rm` are why it is safe to leave unattended: README.md, Opening a session
    by hand."""
    space_and_tab = f"oxc0-{name}"
    return [HC, "run", "--bg", "--keep", "--rm", "--no-parent", "--no-notify", "--json",
            "--name", name, "--cwd", str(directory),
            "--label", f"herdr.space={space_and_tab}", "--label", f"herdr.tab={space_and_tab}",
            "--label", f"oxc0.space={name}", "--label", "oxc0.role=session",
            "--", "claude", *args]


def naming(name):
    space_and_tab = f"oxc0-{name}"
    return [[HERDR_APP, "do", kind, "--id", space_and_tab, "--name", name]
            for kind in ("space.rename", "tab.rename")]


def open_session(name, directory, args, dry=False):
    window = shows()
    if window:
        require()
    start = start_command(name, directory, args)
    if dry:
        show(start)
        if not window:
            print("# the app's window does not answer: nothing to name or focus")
            return
        for command in naming(name):
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
    # The window shows a new terminal a moment after `hc run` returns.
    for command in naming(name):
        p = call(*command)
        for _ in range(ATTEMPTS - 1):
            if p.returncode == 0:
                break
            time.sleep(PAUSE)
            p = call(*command)
        if p.returncode:
            raise Failed(f"{name} started as {session.address}, but the window did not show it: {explain(p)}")
    focus(session.address)
