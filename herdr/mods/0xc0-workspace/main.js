// The workspace's picker for Herdr's desktop app (herdr/README.md, The picker
// in the app): the workspace and the repos cloned in it, filtered as you type.
// Enter opens the session of the one marked, or focuses it; Ctrl+T turns its
// autopilot on or off. The scripts of herdr/bin decide and print, and this
// shows what they print.

import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, ScrollHandle } from "gpui-base";
import { exec, appHome, checking, theme, props, closeOverlay } from "herdr";

const NAME = "0xc0-workspace";
const TOGGLE = "t";
// A popup of the app takes its height from its content ("height" in mod.json
// only caps it), so the list sets its own: its rows, up to LIST_MAX.
const ROW = 34;
const LIST_MAX = 11 * ROW;
const ASK_APP = ["--frontend", "app"];
const STATE_COLOR = { on: "ansi2", dead: "ansi1" };

const said = (r) => `${r.stdout}\n${r.stderr}`.trim();
const script = (root, name, args) => exec(`${root}/herdr/bin/${name}`, args, { timeout: 120_000 });
const entriesOf = (text) =>
  text.split("\n").filter(Boolean).map((line) => {
    const [dir, label, state] = line.split("\t");
    return { dir, label, state };
  });

// A mod cannot ask where it is. The app holds it as a link under its own home
// to herdr/mods/<name> of the workspace, three levels below the workspace.
async function workspace() {
  const link = `${appHome()}/mods/${NAME}`;
  const r = await exec("sh", ["-c", 'dir="$(cd "$1" && pwd -P)" && cd "$dir/../../.." && [ -x herdr/bin/pick ] && pwd -P', "sh", link]);
  if (r.code !== 0 || !r.stdout.trim()) {
    throw new Error(`${link} is not a link to herdr/mods/${NAME} of the workspace (herdr/README.md, The picker in the app). ${said(r)}`.trim());
  }
  return r.stdout.trim();
}

export default class Workspace extends View {
  init(_props, cx) {
    this.filter = "";
    this.at = 0;
    this.entries = null;
    this.reading = true;
    this.busy = "";
    this.said = "";
    this.failed = false;
    this.scroll = ScrollHandle.new();
    this.handle = cx.focus_handle();
    this.input = InputState.new({ placeholder: "Filter the workspace and its repos…" });
    this.input.on("change", (_e, cx) => {
      this.filter = this.input.value();
      this.at = 0;
      if (this.shown().length) this.scroll.scroll_to_item(0);
      cx.notify();
    });
    this.input.on("submit", (_e, cx) => this.open(this.shown()[this.at], cx));
    this.input.focus();
    if (checking()) return;
    cx.timer.after(600, () => this.input.focus());
    cx.spawn(async (cx) => this.load(cx));
  }

  async load(cx) {
    try {
      this.root = await workspace();
      const listed = await script(this.root, "pick", ["--list"]);
      this.entries = entriesOf(listed.stdout);
      if (listed.code !== 0) this.report(listed);
      cx.notify();
      const states = await script(this.root, "pick", ["--autopilot", "--list", ...ASK_APP]);
      for (const { dir, state } of entriesOf(states.stdout)) {
        const entry = this.entries.find((e) => e.dir === dir);
        if (entry) entry.state = state;
      }
      if (states.code !== 0) this.report(states);
    } catch (error) {
      this.report({ code: 1, stdout: "", stderr: error?.message ?? String(error) });
    }
    this.reading = false;
    cx.notify();
  }

  report(r) {
    this.said = said(r);
    this.failed = r.code !== 0;
  }

  shown() {
    const f = this.filter.trim().toLowerCase();
    return (this.entries ?? []).filter((e) => !f || e.label.toLowerCase().includes(f));
  }

  leave() {
    closeOverlay(props().overlay);
  }

  open(entry, cx) {
    if (!entry || this.busy) return;
    this.busy = `Opening ${entry.label}…`;
    this.said = "";
    cx.notify();
    cx.spawn(async (cx) => {
      try {
        const r = await script(this.root, "open-session", [entry.dir, ...ASK_APP]);
        if (r.code === 0) return this.leave();
        this.report(r);
      } catch (error) {
        this.report({ code: 1, stdout: "", stderr: error?.message ?? String(error) });
      }
      this.busy = "";
      cx.notify();
    });
  }

  toggle(entry, cx) {
    if (!entry || this.busy || this.reading) return;
    this.busy = `Turning the autopilot of ${entry.label}…`;
    this.said = "";
    cx.notify();
    cx.spawn(async (cx) => {
      try {
        const toggled = await script(this.root, "autopilot", ["toggle", entry.dir, ...ASK_APP]);
        this.report(toggled);
        if (toggled.code === 0) {
          const now = await script(this.root, "autopilot", ["state", entry.dir, ...ASK_APP]);
          if (now.code === 0) entry.state = now.stdout.trim();
          else this.report(now);
        }
      } catch (error) {
        this.report({ code: 1, stdout: "", stderr: error?.message ?? String(error) });
      }
      this.busy = "";
      cx.notify();
    });
  }

  key(e, cx) {
    const n = this.shown().length;
    if (e.key === "escape") return this.leave();
    if (e.key === "down" && n) this.at = (this.at + 1) % n;
    else if (e.key === "up" && n) this.at = (this.at + n - 1) % n;
    else if (e.key === TOGGLE && e.modifiers.control) this.toggle(this.shown()[this.at], cx);
    else return;
    cx.stop_propagation();
    if (n) this.scroll.scroll_to_item(this.at);
    cx.notify();
  }

  render() {
    const t = theme();
    const rows = this.shown();
    this.at = Math.max(0, Math.min(this.at, rows.length - 1));
    const row = (entry, i) => {
      const on = i === this.at;
      return h_flex()
        .id(`ws-${i}`)
        .flex_none()
        .h(ROW)
        .px(10)
        .gap(10)
        .items_center()
        .rounded(7)
        .cursor_pointer()
        .when(on, (el) => el.bg(t.selected))
        .when(!on, (el) => el.hover((s) => s.bg(t.hover)))
        .on_click((_e, cx) => {
          this.at = i;
          this.open(entry, cx);
        })
        .child(div().flex_1().min_w(0).truncate().text_color(t.foreground).child(entry.label))
        .when(Boolean(entry.state), (el) => el.child(div().flex_none().text_size(11.5).text_color(t[STATE_COLOR[entry.state]] ?? t.dim).child(entry.state)));
    };
    const status = this.busy || this.said || (this.reading ? "Reading the autopilots…" : "");
    const statusColor = this.failed && !this.busy ? t.blocked : t.muted;

    return v_flex()
      .id("workspace-picker")
      .track_focus(this.handle)
      .on_key_down((e, cx) => this.key(e, cx))
      .w_full()
      .min_h(0)
      .p(18)
      .gap(10)
      .bg(t.popover)
      .text_size(13)
      .child(
        h_flex()
          .items_center()
          .child(div().flex_1().text_size(15).font_semibold().text_color(t.foreground).child("Sessions and autopilots"))
          .child(div().text_size(11).text_color(t.dim).child("Esc")),
      )
      .child(
        h_flex().h(36).flex_none().px(10).items_center().rounded(9).border_1().border_color(t.accent).bg(t.background)
          .child(Input.new(this.input).flex_1().h_full().text_size(12.8).text_color(t.foreground)),
      )
      .child(
        v_flex()
          .id("ws-list")
          .flex_none()
          .h(Math.min(LIST_MAX, Math.max(1, rows.length) * ROW))
          .overflow_y_scrollbar()
          .track_scroll(this.scroll)
          .children(rows.map(row))
          .when(this.entries === null && !this.failed, (el) => el.child(h_flex().flex_none().h(ROW).px(10).items_center().text_color(t.muted).child("…")))
          .when(this.entries !== null && rows.length === 0, (el) => el.child(h_flex().flex_none().h(ROW).px(10).items_center().text_color(t.dim).child("No matching repo."))),
      )
      .when(Boolean(status), (el) =>
        el.child(
          v_flex()
            .id("ws-status")
            .flex_none()
            .max_h(96)
            .overflow_y_scrollbar()
            .text_size(12)
            .text_color(statusColor)
            .children(status.split("\n").map((line) => div().child(line))),
        ),
      )
      .child(
        h_flex()
          .flex_none()
          .justify_end()
          .text_size(11)
          .text_color(t.dim)
          .child(`↑↓ choose · ↵ open the session · ctrl+${TOGGLE} turn the autopilot on or off · esc close`),
      );
  }
}
