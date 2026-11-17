"""What the scripts of bin/ ask of Herdr, and the backend that answers
(README.md, Files).

The scripts speak of three things, and of nothing that only one front end has:

  space    where one repo's sessions live
  tab      one place in a space, where one session runs
  session  a program running in a terminal, here Claude Code

An operation below is one question or one act that any backend can answer:
the backend's function of the same name does it. A space is named by its name.
What an operation returns to be asked about later, a space, a tab or a
session, is a handle: opaque, the scripts only hand it to another operation,
or print a tab in a log line with `str()`.

There is one backend per front end, `tui` and `app`. A script chooses one with
`use(choose(...))`, and its operations then go to that backend. A backend may
lack an operation a script does not use yet: asking it for one fails with a
message, and `lacking()` says which. `answering()` lists the front ends to
look in when a script must find something wherever it lives.
"""
import functools
import importlib
import inspect
import os
from dataclasses import dataclass

ENDED = "ended"      # no program runs in the session's terminal any more
AT_REST = "at rest"  # idle or done
BUSY = "busy"

FRONTENDS = ("tui", "app")
FRONTEND_ENV = "OXC0_HERDR_FRONTEND"

OPERATIONS = []
backend = None


class Failed(Exception):
    """An operation that did not work; the message says what Herdr answered."""


@dataclass
class Worker:
    """A session started for an issue: the issue's number `n`, its `name`
    (`<space>-<n>`, the tab's and the session's), and their handles."""
    n: int
    name: str
    tab: object
    session: object


def operation(contract):
    """Defines an operation: `contract` gives its signature and, in its
    docstring, what it asks; the backend's function of the same name does it."""
    OPERATIONS.append(contract.__name__)

    @functools.wraps(contract)
    def call(*args, **kwargs):
        if backend is None:
            raise RuntimeError("no front end chosen: call frontend.use() first")
        function = getattr(backend, contract.__name__, None)
        if function is None:
            raise Failed(f"the {name_of(backend)} front end does not offer {contract.__name__} yet")
        return function(*args, **kwargs)
    return call


def name_of(module):
    return module.__name__.rsplit(".", 1)[-1]


def load(name):
    """The backend of the front end called `name`, `tui` or `app`."""
    if name not in FRONTENDS:
        raise Failed(f"{name!r} is not a front end: use {' or '.join(FRONTENDS)}")
    return importlib.import_module(f"{__name__}.{name}")


def use(name):
    """Sends every operation to the backend of the front end called `name`."""
    global backend
    backend = load(name)


def ask(name, question):
    """What the backend of the front end `name` answers to `question`, one of
    the operations `missing`, `answers` and `shows`, without making it the
    one in use."""
    return getattr(load(name), question)()


def choose(option=None, environ=None, ask=ask):
    """The front end to use, by the first rule that applies (README.md,
    Opening a session by hand):

      1. the one asked for: `option`, which is `--frontend`, or else the
         variable `OXC0_HERDR_FRONTEND`
      2. the one `environ` says this runs in: whatever the TUI starts has
         `HERDR_ENV=1`, a pane as much as a plugin's popup, and a terminal of
         the app has `HC_TERMINAL_ID`; with both, the TUI, since its server
         hands its own environment to what it starts and the app's core gives
         its terminals no `HERDR*` variable. `HERDR_PANE_ID` does not tell: the
         TUI starts a popup without it
      3. the app if its window answers, otherwise the TUI

    Fails when the one named is not a front end, or is not installed. `ask`
    answers the backends' `missing` and `shows`, for a test to replace."""
    environ = os.environ if environ is None else environ
    if option or environ.get(FRONTEND_ENV):
        name, why = (option, "--frontend") if option else (environ[FRONTEND_ENV], f"${FRONTEND_ENV}")
        if name not in FRONTENDS:
            raise Failed(f"{why}: {name!r} is not a front end: use {' or '.join(FRONTENDS)}")
    elif environ.get("HERDR_ENV") == "1":
        name, why = "tui", "this runs in something it started"
    elif environ.get("HC_TERMINAL_ID"):
        name, why = "app", "this runs in one of its terminals"
    elif not ask("app", "missing") and ask("app", "shows"):
        name, why = "app", "its window answers"
    else:
        name, why = "tui", "the app's window does not answer"
    absent = ask(name, "missing")
    if absent:
        raise Failed(f"the {name} front end is not installed ({why}): {', '.join(absent)} not found in PATH")
    return name


def answering(first, ask=ask):
    """The front ends to look in for something that may live in any of them:
    `first`, whether or not it answers, then each of the others that is
    installed and whose server answers."""
    return [first] + [name for name in FRONTENDS
                      if name != first and not ask(name, "missing") and ask(name, "answers")]


def lacking(module):
    """The operations `module` has no function for, or one with another signature."""
    return [name for name in OPERATIONS
            if not callable(getattr(module, name, None))
            or inspect.signature(getattr(module, name)) != inspect.signature(globals()[name])]


@operation
def missing():
    """The programs the front end needs that are not in PATH, a list of
    names: empty when it is installed. Asked of a front end that is not the one
    in use, through `ask`."""


@operation
def answers():
    """Whether the front end's server answers, so that what lives in it can be
    looked up. A question that never starts a server that is not running."""


@operation
def shows():
    """Whether the front end has a window to show the operator what a script
    opens or focuses. The app's is the one that may be closed while its core
    runs; the TUI's is its server."""


@operation
def find_session(name):
    """The session with this name, or None."""


@operation
def focus_session(session):
    """Brings the session in front of the operator."""


@operation
def open_session(name, directory, args, dry=False):
    """Opens a tab in `directory`, in the space called `name` (created if there
    is none), running `claude` with `args`, in front of the operator. With
    `dry`, changes nothing and prints what it would run."""


@operation
def find_space(name):
    """The space with this name, or None. A round looks it up once and hands
    it to `workers` and `start_session`. A front end whose spaces exist as soon
    as a session carries their name has one always."""


@operation
def workers(space, dry=False):
    """The worker sessions of the space, one `Worker` per tab named
    `<space>-<n>`, an iterator: a backend may put a worker in order as it
    yields it, unless `dry`. `space` is what `find_space` returned, None
    included (a dry run on a space that is not open): it has none."""


@operation
def session_state(session):
    """ENDED, AT_REST or BUSY. A session just started, that the front end has
    not detected yet, is BUSY. ENDED is a program that is gone, whether the
    terminal finished or a shell took its place."""


@operation
def read_screen(session):
    """The last 80 lines its terminal shows, as text. The caller looks for the
    session's last line in it and keeps none of it."""


@operation
def close_tab(tab, dry=False):
    """Closes the tab, and its session with it, leaving nothing of it in the
    front end. A session's screen is read before this, never after. With `dry`,
    changes nothing and prints what it would run, if the front end has
    commands to show."""


@operation
def start_session(space, name, directory, command, env, dry=False):
    """Starts `command`, a command line, in `directory`, with the variables of
    the dict `env` in its environment, in a new tab called `name` of the
    space, not in front of the operator. The command is part of creating the
    session: nothing is typed into it afterwards. With `dry`, changes nothing
    and prints what it would run, if the front end has commands to show."""


@operation
def pilot(name):
    """The tab of the autopilot of the space called `name`, or None. A front
    end that keeps the tab of a loop that ended on its own removes it here and
    answers None."""


@operation
def pilot_alive(tab):
    """Whether a program still runs in the autopilot's tab."""


@operation
def start_pilot(name, directory, command):
    """Starts `command`, the autopilot's own command line, in `directory`, in
    a new tab of the space called `name`, created if there is none, not in
    front of the operator: the autopilot's, for the front end to find with
    `pilot`. The front end tells the loop which front end it lives in."""


@operation
def is_own_tab(tab):
    """Whether this very process runs in the tab, which it must then close
    when it turns itself off. A front end whose terminal ends with the loop,
    and its tab with it, answers False."""
