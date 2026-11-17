"""The `tui` backend: Herdr's terminal app, through its `herdr` command. A
space is its workspace, a tab its tab, a session its agent."""
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass

from . import AT_REST, BUSY, ENDED, Failed, Worker

HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
TAB = "autopilot"


@dataclass
class Space:
    id: str
    name: str


@dataclass
class Tab:
    id: str
    space: str

    def __str__(self):
        return self.id


@dataclass
class Session:
    name: str = None
    agent: dict = None
    pane: str = None


def run(*args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode:
        raise Failed(f"{' '.join(args[:3])}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def herdr(*args):
    return json.loads(run(HERDR, *args))["result"]


def act(*args, quiet=False):
    """A `herdr` command whose own output is the operator's to see."""
    command = [HERDR, *args]
    p = subprocess.run(command, stdout=subprocess.DEVNULL if quiet else None)
    if p.returncode:
        raise Failed(f"{' '.join(command[:3])}: exit status {p.returncode}")


def show(command):
    print(shlex.join(command) + " ")


def find_session(name):
    p = subprocess.run([HERDR, "agent", "get", name], capture_output=True)
    return Session(name=name) if p.returncode == 0 else None


def focus_session(session):
    act("agent", "focus", session.name)


def open_session(name, directory, args, dry=False):
    # The autopilot may have opened the repo's workspace already: the session
    # then gets a tab in it.
    space = find_space(name)
    if space:
        create = ["tab", "create", "--workspace", space.id, "--cwd", str(directory),
                  "--label", name, "--focus"]
    else:
        create = ["workspace", "create", "--cwd", str(directory), "--label", name, "--focus"]
    if dry:
        show([HERDR, *create])
        pane = "<new root pane>"
    else:
        pane = herdr(*create)["root_pane"]["pane_id"]
    start = ["agent", "start", name, "--kind", "claude", "--pane", pane, "--", *args]
    if dry:
        show([HERDR, *start])
        return
    act(*start)
    if space:
        act("agent", "focus", name, quiet=True)


def find_space(name):
    for w in herdr("workspace", "list")["workspaces"]:
        if w["label"] == name:
            return Space(w["workspace_id"], name)
    return None


def tabs(space):
    return herdr("tab", "list", "--workspace", space.id)["tabs"] if space else []


def workers(space, dry=False):
    agents = {a["tab_id"]: a for a in herdr("agent", "list")["agents"]}
    panes = {p["tab_id"]: p["pane_id"] for p in herdr("pane", "list", "--workspace", space.id)["panes"]} if space else {}
    for tab in tabs(space):
        m = re.fullmatch(rf"{re.escape(space.name)}-(\d+)", tab["label"])
        if not m:
            continue
        agent = agents.get(tab["tab_id"])
        if agent is not None and not agent.get("name") and not dry:
            subprocess.run([HERDR, "agent", "rename", agent["pane_id"], tab["label"]], capture_output=True)
        yield Worker(int(m.group(1)), tab["label"], Tab(tab["tab_id"], space.name),
                     Session(agent=agent, pane=panes.get(tab["tab_id"])))


def at_shell(pane):
    """Whether the pane is back at its shell, with no program in front."""
    info = herdr("pane", "process-info", "--pane", pane)["process_info"]
    return info["foreground_process_group_id"] == info["shell_pid"]


def session_state(session):
    if session.agent is None:
        # Herdr may not have detected a session that just started.
        if session.pane is None or not at_shell(session.pane):
            return BUSY
        return ENDED
    if session.agent["agent_status"] in ("idle", "done"):
        return AT_REST
    return BUSY


def read_screen(session):
    return run(HERDR, "agent", "read", session.agent["pane_id"], "--source", "recent-unwrapped", "--lines", "80")


def close_tab(tab):
    herdr("tab", "close", tab.id)


def start_session(space, name, directory, command, env):
    pane = herdr("tab", "create", "--workspace", space.id, "--cwd", str(directory),
                 "--label", name, "--no-focus",
                 *[arg for key, value in env.items() for arg in ("--env", f"{key}={value}")])["root_pane"]["pane_id"]
    # Not `agent start`: it waits for the agent to be ready for input, and a
    # session given a prompt goes straight to work (#112).
    run(HERDR, "pane", "run", pane, command)


def pilot(name):
    tab = next((t for t in tabs(find_space(name)) if t["label"] == TAB), None)
    return Tab(tab["tab_id"], name) if tab else None


def pilot_alive(tab):
    """Whether the tab's pane still has the loop in front of its shell."""
    panes = herdr("pane", "list", "--workspace", find_space(tab.space).id)["panes"]
    pane = next((p["pane_id"] for p in panes if p["tab_id"] == tab.id), None)
    return pane is not None and not at_shell(pane)


def start_pilot(name, directory, command):
    env = ["--env", f"HERDR_BIN_PATH={HERDR}"]
    space = find_space(name)
    if space:
        pane = herdr("tab", "create", "--workspace", space.id, "--cwd", str(directory),
                     "--label", TAB, "--no-focus", *env)["root_pane"]["pane_id"]
    else:
        created = herdr("workspace", "create", "--cwd", str(directory), "--label", name, "--no-focus", *env)
        herdr("tab", "rename", created["tab"]["tab_id"], TAB)
        pane = created["root_pane"]["pane_id"]
    run(HERDR, "pane", "run", pane, command)  # prints nothing on success, unlike the rest


def is_own_tab(tab):
    return tab.id == os.environ.get("HERDR_TAB_ID")
