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
"""
import functools
import importlib
import inspect
from dataclasses import dataclass

ENDED = "ended"      # no program runs in the session's terminal any more
AT_REST = "at rest"  # idle or done
BUSY = "busy"

OPERATIONS = []


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
        return getattr(backend, contract.__name__)(*args, **kwargs)
    return call


def lacking(module):
    """The operations `module` has no function for, or one with another signature."""
    return [name for name in OPERATIONS
            if not callable(getattr(module, name, None))
            or inspect.signature(getattr(module, name)) != inspect.signature(globals()[name])]


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
    it to `workers` and `start_session`."""


@operation
def workers(space, dry=False):
    """The worker sessions of the space, one `Worker` per tab named
    `<space>-<n>`, an iterator: a backend may put a worker in order as it
    yields it, unless `dry`. `space` is what `find_space` returned, None
    included (a dry run on a space that is not open): it has none."""


@operation
def session_state(session):
    """ENDED, AT_REST or BUSY. A session just started, that the front end has
    not detected yet, is BUSY."""


@operation
def read_screen(session):
    """The last 80 lines its terminal shows, as text."""


@operation
def close_tab(tab):
    """Closes the tab, and its session with it."""


@operation
def start_session(space, name, directory, command, env):
    """Starts `command`, a command line, in `directory`, with the variables of
    the dict `env` in its environment, in a new tab called `name` of the
    space, not in front of the operator. The command is part of creating the
    session: nothing is typed into it afterwards."""


@operation
def pilot(name):
    """The tab of the autopilot of the space called `name`, or None."""


@operation
def pilot_alive(tab):
    """Whether a program still runs in the autopilot's tab."""


@operation
def start_pilot(name, directory, command):
    """Starts `command`, a command line, in `directory`, in a new tab of the
    space called `name`, created if there is none, not in front of the
    operator: the autopilot's, for the front end to find with `pilot`."""


@operation
def is_own_tab(tab):
    """Whether this very process runs in the tab."""


backend = importlib.import_module(f"{__name__}.tui")
