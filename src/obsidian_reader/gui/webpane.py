"""The hardened WebKit surface: no scripts, no network, vault-contained assets only."""

from urllib.parse import parse_qs, unquote, urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, GObject, WebKit

from ..core.render import build_message_page

ASSET_MIME_ALLOWLIST = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".svg": "image/svg+xml", ".webp": "image/webp", ".bmp": "image/bmp", ".avif": "image/avif",
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".wav": "audio/wav",
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".opus": "audio/opus",
    ".mp4": "video/mp4", ".webm": "video/webm", ".ogv": "video/ogg", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}


class ReaderView(GObject.Object):
    """Owns the WebView, its URI schemes, and its navigation policy."""

    __gsignals__ = {
        "navigate-note": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "navigate-note-new-tab": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "choose-ambiguous": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "open-external-file": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "open-external-uri": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "run-action": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "hover-link": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, share_from: "ReaderView | None" = None):
        super().__init__()
        self.current_note = ""
        self.last_render = None
        if share_from is not None:
            self.page_provider = share_from.page_provider
            self.asset_provider = share_from.asset_provider
            self.context = share_from.context
        else:
            self.page_provider = None
            self.asset_provider = None
            self.context = WebKit.WebContext()
            self.context.register_uri_scheme("reader", self._serve_reader, None)
            self.context.register_uri_scheme("vault", self._serve_vault, None)
            security = self.context.get_security_manager()
            security.register_uri_scheme_as_cors_enabled("vault")
            security.register_uri_scheme_as_secure("reader")
            security.register_uri_scheme_as_secure("vault")
        self.webview = WebKit.WebView(web_context=self.context)
        settings = self.webview.get_settings()
        # The no-script rule fails closed: if this WebKit cannot disable JavaScript,
        # the reader refuses to start rather than rendering hostile input with it on.
        critical = {"enable-javascript": False, "enable-javascript-markup": False}
        best_effort = {
            "enable-html5-local-storage": False,
            "enable-html5-database": False,
            "enable-webgl": False,
            "enable-media-stream": False,
            "enable-developer-extras": False,
            "allow-file-access-from-file-urls": False,
            "allow-universal-access-from-file-urls": False,
        }
        for name, value in critical.items():
            if settings.find_property(name) is None:
                raise RuntimeError(f"this WebKitGTK has no {name} setting; refusing to render")
            settings.set_property(name, value)
        for name, value in best_effort.items():
            if settings.find_property(name) is not None:
                settings.set_property(name, value)
        self.webview.connect("decide-policy", self._decide_policy)
        self.webview.connect("mouse-target-changed", self._on_hover)
        self.webview.connect("context-menu", self._trim_context_menu)

    def load_note(self, rel: str, anchor: str = "") -> None:
        """Navigates the surface to a vault note, letting WebKit keep the history."""
        uri = f"reader:///note/{GLib.uri_escape_string(rel, '/', True)}"
        if anchor:
            uri = f"{uri}#{GLib.uri_escape_string(anchor, None, True)}"
        self.webview.load_uri(uri)

    def load_page(self, name: str) -> None:
        """Navigates to an app page such as `welcome` or `source`."""
        self.webview.load_uri(f"reader:///page/{name}")

    def _serve_reader(self, request, _data) -> None:
        """Serves rendered pages for `reader:` URIs out of the window's page provider."""
        uri = urlparse(request.get_uri())
        path = unquote(uri.path)
        page = ""
        if self.page_provider is not None:
            page = self.page_provider(path, request.get_web_view())
        if not page:
            page = build_message_page("Not found", f"Nothing is served at {path}")
        self._finish(request, page.encode("utf-8"), "text/html")

    def _serve_vault(self, request, _data) -> None:
        """Serves a vault asset when, and only when, the provider proves containment."""
        rel = unquote(urlparse(request.get_uri()).path).lstrip("/")
        resolved = self.asset_provider(rel) if self.asset_provider is not None else None
        suffix = "." + rel.rsplit(".", 1)[-1].casefold() if "." in rel else ""
        mime = ASSET_MIME_ALLOWLIST.get(suffix)
        if resolved is None or mime is None:
            request.finish_error(GLib.Error.new_literal(
                GLib.quark_from_string("reader"), f"Refused asset: {rel}", 1
            ))
            return
        try:
            data = resolved.read_bytes()
        except OSError:
            request.finish_error(GLib.Error.new_literal(
                GLib.quark_from_string("reader"), f"Unreadable asset: {rel}", 1
            ))
            return
        self._finish(request, data, mime)

    def _finish(self, request, data: bytes, mime: str) -> None:
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data))
        request.finish(stream, len(data), mime)

    def _decide_policy(self, _view, decision, decision_type) -> bool:
        """Allows internal pages and assets; routes everything else out or blocks it."""
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            decision.use()
            return True
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        parsed = urlparse(uri)
        scheme = parsed.scheme.casefold()
        wants_new_tab = (
            decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION
            or action.get_mouse_button() == 2
            or bool(action.get_modifiers() & Gdk.ModifierType.CONTROL_MASK)
        )
        if scheme == "reader":
            return self._route_reader(decision, parsed, wants_new_tab)
        if scheme in ("http", "https", "mailto"):
            decision.ignore()
            self.emit("open-external-uri", uri)
            return True
        decision.ignore()
        return True

    def _route_reader(self, decision, parsed, wants_new_tab: bool = False) -> bool:
        segments = [unquote(part) for part in parsed.path.split("/") if part]
        head = segments[0] if segments else ""
        if head == "note" and wants_new_tab:
            decision.ignore()
            self.emit("navigate-note-new-tab", "/".join(segments[1:]), unquote(parsed.fragment))
            return True
        if head in ("note", "page"):
            decision.use()
            return True
        decision.ignore()
        rest = "/".join(segments[1:])
        if head == "ambiguous":
            query = parse_qs(parsed.query)
            source = query.get("from", [""])[0]
            self.emit("choose-ambiguous", rest, source)
        elif head == "external":
            self.emit("open-external-file", rest)
        elif head == "action":
            query = parse_qs(parsed.query)
            self.emit("run-action", rest, query.get("arg", [""])[0])
        return True

    def _on_hover(self, _view, hit_result, _modifiers) -> None:
        uri = hit_result.get_link_uri() if hit_result.context_is_link() else ""
        self.emit("hover-link", uri or "")

    def _trim_context_menu(self, _view, menu, _hit) -> bool:
        """Removes browser actions that make no sense in a read-only reader."""
        unwanted = {
            WebKit.ContextMenuAction.GO_BACK,
            WebKit.ContextMenuAction.GO_FORWARD,
            WebKit.ContextMenuAction.RELOAD,
            WebKit.ContextMenuAction.STOP,
            WebKit.ContextMenuAction.DOWNLOAD_LINK_TO_DISK,
            WebKit.ContextMenuAction.DOWNLOAD_IMAGE_TO_DISK,
            WebKit.ContextMenuAction.DOWNLOAD_VIDEO_TO_DISK,
            WebKit.ContextMenuAction.DOWNLOAD_AUDIO_TO_DISK,
            WebKit.ContextMenuAction.OPEN_LINK_IN_NEW_WINDOW,
            WebKit.ContextMenuAction.OPEN_IMAGE_IN_NEW_WINDOW,
            WebKit.ContextMenuAction.OPEN_FRAME_IN_NEW_WINDOW,
        }
        for item in list(menu.get_items()):
            if item.get_stock_action() in unwanted:
                menu.remove(item)
        return False
