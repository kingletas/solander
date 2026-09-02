"""The first-run setup window, shown when WebKit's sandbox cannot start.

This runs plain GTK only — no WebKit — so it works exactly in the situation the
reader itself cannot. It explains the one-time step, hands over a single
copy-paste command, and relaunches the app once the system says yes. The app
never runs privileged commands itself; the user pastes them into a terminal.
"""

import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

SETUP_APP_ID = "com.kingletas.Solander.Setup"

INTRO = (
    "Ubuntu's security policy blocks the sandbox this app uses to render your "
    "notes safely. A one-time system change fixes it: copy the command below, "
    "paste it into a Terminal, and enter your password when asked. It installs "
    "a security profile that only lets this app's sandbox start — it grants "
    "nothing else, to nothing else."
)

SHEBANG_INTRO = (
    "The security profile for this app is already installed, but it did not "
    "attach to this process because the app was started around its launcher. "
    "Start it from your applications grid, or run `solander` in a "
    "terminal — the launcher starts the app in the way the profile covers."
)


def setup_command(profile: str, profile_path: str) -> str:
    """One paste-able command: write the profile, then reload AppArmor."""
    marker = "SOLANDER_PROFILE"
    return (
        f"sudo tee {profile_path} > /dev/null << '{marker}'\n"
        f"{profile}\n"
        f"{marker}\n"
        f"sudo apparmor_parser -r {profile_path}"
    )


class SetupWindow(Adw.ApplicationWindow):
    """Explains the sandbox situation and walks the user through the fix."""

    def __init__(self, application, command: str, shebang: bool, recheck, relaunch):
        super().__init__(application=application, title="Solander — Setup")
        self.set_default_size(680, 560)
        self._recheck = recheck
        self._relaunch = relaunch

        page = Adw.StatusPage(
            icon_name="com.kingletas.Solander",
            title="One-time setup needed",
            description=SHEBANG_INTRO if shebang else INTRO,
        )
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_bottom(24)

        if not shebang:
            view = Gtk.TextView(editable=False, monospace=True)
            view.get_buffer().set_text(command)
            view.set_top_margin(10)
            view.set_bottom_margin(10)
            view.set_left_margin(10)
            view.set_right_margin(10)
            frame = Gtk.ScrolledWindow(
                child=view, min_content_height=180, max_content_height=260
            )
            frame.add_css_class("card")
            content.append(frame)

            copy_button = Gtk.Button(label="Copy Command")
            copy_button.add_css_class("suggested-action")
            copy_button.connect("clicked", self._copy, command)
            terminal_hint = Gtk.Label(
                label="Then come back here and press “I ran it”.",
                xalign=0.5,
            )
            terminal_hint.add_css_class("dim-label")
            done_button = Gtk.Button(label="I ran it — check again")
            done_button.connect("clicked", self._check_again)
            buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
            buttons.append(copy_button)
            buttons.append(done_button)
            content.append(buttons)
            content.append(terminal_hint)
        else:
            quit_button = Gtk.Button(label="Close", halign=Gtk.Align.CENTER)
            quit_button.connect("clicked", lambda *_: self.close())
            content.append(quit_button)

        page.set_child(content)
        view_box = Adw.ToolbarView()
        view_box.add_top_bar(Adw.HeaderBar())
        view_box.set_content(page)
        self.toasts = Adw.ToastOverlay(child=view_box)
        self.set_content(self.toasts)

    def _copy(self, _button, command: str) -> None:
        self.get_clipboard().set(command)
        self.toasts.add_toast(Adw.Toast(title="Copied — paste it into a Terminal"))

    def _check_again(self, _button) -> None:
        if self._recheck():
            self.toasts.add_toast(Adw.Toast(title="Sandbox ready — starting the reader"))
            GLib.timeout_add(600, self._relaunch)
        else:
            self.toasts.add_toast(
                Adw.Toast(title="Still blocked — did the command run without errors?")
            )


def run_setup(command: str, shebang: bool, recheck) -> int:
    """Shows the setup window; relaunching execs this same interpreter fresh."""

    def relaunch() -> bool:
        # A fresh exec of our own interpreter, no shell involved: the AppArmor
        # profile attaches at exec time, which is the entire point of restarting.
        os.execv(  # noqa: S606 — fixed argv, own interpreter, no shell
            sys.executable, [sys.executable, "-m", "solander.cli", *sys.argv[1:]]
        )
        return False

    app = Adw.Application(
        application_id=SETUP_APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE
    )

    def activate(application):
        SetupWindow(application, command, shebang, recheck, relaunch).present()

    app.connect("activate", activate)
    return app.run([sys.argv[0]])
