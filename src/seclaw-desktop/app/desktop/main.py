from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from string import hexdigits

from app.bootstrap import ServiceContainer
from app.desktop.state import DesktopWorkbenchState
from domain import ToolKind, session_snapshot_to_dict


NAV_ITEMS = [
    ("chat", "Chat", "CHAT_BUBBLE_OUTLINE_ROUNDED"),
    ("audit", "Audit", "FACT_CHECK_ROUNDED"),
    ("tools", "Tools", "HANDYMAN_ROUNDED"),
    ("sessions", "Sessions", "HISTORY_ROUNDED"),
    ("settings", "Settings", "TUNE_ROUNDED"),
]

THEME_PRESETS = [
    ("Slate", "#3566D6", "#F3F6FB"),
    ("Mist", "#5C7CFA", "#F5F7FD"),
    ("Sage", "#2F8F6B", "#F2FAF7"),
    ("Sand", "#A56A1E", "#FBF7F0"),
]

DEFAULT_THEME_ACCENT = "#3566D6"
DEFAULT_THEME_SURFACE = "#F3F6FB"
DEFAULT_PANEL_OPACITY = 0.92
DEFAULT_CHROME_OPACITY = 0.97


@dataclass(slots=True)
class ThemeConfig:
    accent: str = DEFAULT_THEME_ACCENT
    surface_tint: str = DEFAULT_THEME_SURFACE
    panel_opacity: float = DEFAULT_PANEL_OPACITY
    chrome_opacity: float = DEFAULT_CHROME_OPACITY


@dataclass(slots=True)
class ThemeTokens:
    page_bg: str
    gradient_start: str
    gradient_end: str
    shell: str
    shell_alt: str
    panel: str
    panel_alt: str
    editor: str
    border: str
    border_soft: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_soft: str
    accent_fill: str
    accent_text: str
    on_accent: str
    info: str
    warning: str
    success: str
    shadow: list


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_hex(value: str | None, fallback: str) -> str:
    candidate = (value or "").strip().lstrip("#")
    if len(candidate) == 3:
        candidate = "".join(part * 2 for part in candidate)
    if len(candidate) != 6 or any(char not in hexdigits for char in candidate):
        return fallback.upper()
    return f"#{candidate.upper()}"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = _normalize_hex(value, "#000000").lstrip("#")
    return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))


def _blend_hex(base: str, tint: str, amount: float) -> str:
    weight = _clamp(amount, 0.0, 1.0)
    base_rgb = _hex_to_rgb(base)
    tint_rgb = _hex_to_rgb(tint)
    blended = [
        round(channel + (target - channel) * weight) for channel, target in zip(base_rgb, tint_rgb, strict=True)
    ]
    return f"#{blended[0]:02X}{blended[1]:02X}{blended[2]:02X}"


def _parse_opacity(value: str | None, fallback: float) -> float:
    try:
        parsed = float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback
    if 0.0 <= parsed <= 1.0:
        return parsed
    return fallback


def _load_theme_config() -> ThemeConfig:
    return ThemeConfig(
        accent=_normalize_hex(os.environ.get("SECLAW_THEME_ACCENT"), DEFAULT_THEME_ACCENT),
        surface_tint=_normalize_hex(os.environ.get("SECLAW_THEME_SURFACE"), DEFAULT_THEME_SURFACE),
        panel_opacity=_parse_opacity(os.environ.get("SECLAW_THEME_PANEL_OPACITY"), DEFAULT_PANEL_OPACITY),
        chrome_opacity=_parse_opacity(os.environ.get("SECLAW_THEME_CHROME_OPACITY"), DEFAULT_CHROME_OPACITY),
    )


def _build_theme(ft, config: ThemeConfig) -> ThemeTokens:
    accent = _normalize_hex(config.accent, DEFAULT_THEME_ACCENT)
    surface = _normalize_hex(config.surface_tint, DEFAULT_THEME_SURFACE)
    panel_opacity = _clamp(config.panel_opacity, 0.55, 0.98)
    chrome_opacity = _clamp(config.chrome_opacity, 0.76, 1.0)

    return ThemeTokens(
        page_bg=_blend_hex("#F3F5F8", surface, 0.45),
        gradient_start=_blend_hex("#F7F9FC", accent, 0.03),
        gradient_end=_blend_hex(surface, accent, 0.02),
        shell=ft.Colors.with_opacity(chrome_opacity, "#FBFCFE"),
        shell_alt=ft.Colors.with_opacity(min(chrome_opacity + 0.01, 0.99), _blend_hex("#F9FBFE", surface, 0.30)),
        panel=ft.Colors.with_opacity(panel_opacity, "#FAFBFD"),
        panel_alt=ft.Colors.with_opacity(min(panel_opacity + 0.02, 0.99), _blend_hex("#F7F9FC", surface, 0.55)),
        editor=ft.Colors.with_opacity(min(panel_opacity + 0.03, 0.99), "#F8FAFD"),
        border=ft.Colors.with_opacity(0.82, _blend_hex("#D5DCE7", accent, 0.10)),
        border_soft=ft.Colors.with_opacity(0.60, _blend_hex("#E2E8F0", surface, 0.22)),
        text_primary="#182230",
        text_secondary="#607083",
        text_muted="#8C98A8",
        accent=accent,
        accent_soft=ft.Colors.with_opacity(0.08, accent),
        accent_fill=ft.Colors.with_opacity(0.14, accent),
        accent_text=_blend_hex("#27467A", accent, 0.52),
        on_accent="#FFFFFF",
        info=_blend_hex("#3B82F6", accent, 0.4),
        warning="#9A6700",
        success="#18794E",
        shadow=[
            ft.BoxShadow(
                blur_radius=14,
                color=ft.Colors.with_opacity(0.05, "#64748B"),
                offset=ft.Offset(0, 2),
            ),
            ft.BoxShadow(
                blur_radius=4,
                color=ft.Colors.with_opacity(0.04, "#94A3B8"),
                offset=ft.Offset(0, 1),
            ),
        ],
    )


def build_page(page, services: ServiceContainer) -> None:
    import flet as ft

    state = DesktopWorkbenchState()
    theme_config = _load_theme_config()
    default_theme = ThemeConfig(
        accent=theme_config.accent,
        surface_tint=theme_config.surface_tint,
        panel_opacity=theme_config.panel_opacity,
        chrome_opacity=theme_config.chrome_opacity,
    )
    theme = _build_theme(ft, theme_config)
    server_url = f"http://{services.env.host}:{services.env.port}"

    if not page.web:
        page.window_width = 1600
        page.window_height = 980
    page.title = "SEClaw IDE"
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT

    workspace_dropdown = ft.Dropdown(width=300, label="Workspace", border_radius=16, filled=True, text_size=13)
    workspace_path_text = ft.Text("No workspace selected", size=12)
    workspace_meta_text = ft.Text("0 open tabs", size=12)
    appearance_meta_text = ft.Text("", size=12)
    editor_meta_text = ft.Text("No file open", size=12)
    server_status = ft.Text(value=f"Server stopped ({server_url})", size=12)
    server_status_chip = ft.Container(border_radius=999, padding=ft.padding.symmetric(horizontal=12, vertical=7))

    tool_name_input = ft.TextField(label="Tool name", border_radius=16, filled=True, hint_text="e.g. semgrep-mcp")
    tool_source_input = ft.TextField(
        label="Source",
        border_radius=16,
        filled=True,
        hint_text="GitHub repo, package, or local path",
    )
    accent_input = ft.TextField(label="Accent", value=theme_config.accent, width=160, border_radius=16, filled=True)
    surface_input = ft.TextField(
        label="Surface tint",
        value=theme_config.surface_tint,
        width=160,
        border_radius=16,
        filled=True,
    )
    panel_opacity_text = ft.Text(size=12)
    panel_opacity_slider = ft.Slider(min=0.55, max=0.98, divisions=43, round=2, value=theme_config.panel_opacity)
    chrome_opacity_text = ft.Text(size=12)
    chrome_opacity_slider = ft.Slider(min=0.76, max=1.0, divisions=24, round=2, value=theme_config.chrome_opacity)
    theme_message = ft.Text("Light theme is active.", size=12)

    nav_column = ft.Column(spacing=10)
    project_list = ft.ListView(spacing=0, expand=True)
    editor_tabs = ft.Row(scroll=ft.ScrollMode.AUTO, wrap=False, spacing=8)
    editor_host = ft.Container(expand=True)
    main_area = ft.Container(expand=True)
    workspace_area = ft.Container()

    def panel(
        content,
        *,
        bgcolor: str | None = None,
        padding=14,
        radius: int = 18,
        border_color: str | None = None,
        expand: bool | int | None = None,
        width: int | float | None = None,
        blur: int | float | None = 0,
        shadow=None,
    ):
        return ft.Container(
            expand=expand,
            width=width,
            bgcolor=bgcolor or theme.panel,
            blur=blur,
            shadow=theme.shadow if shadow is None else shadow,
            border=ft.border.all(1, border_color) if border_color else None,
            border_radius=radius,
            padding=padding,
            content=content,
        )

    def chip(
        label: str | ft.Control,
        *,
        fg: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        icon=None,
    ):
        content = label if not isinstance(label, str) else ft.Text(label, size=11, color=fg or theme.text_secondary)
        row_controls = []
        if icon is not None:
            row_controls.append(ft.Icon(icon, size=14, color=fg or theme.accent_text))
        row_controls.append(content)
        return ft.Container(
            bgcolor=fill or theme.panel_alt,
            border=ft.border.all(1, stroke) if stroke else None,
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row(row_controls, spacing=6, tight=True),
        )

    def button_style(
        *,
        fg: str | None = None,
        bg_fill: str | None = None,
        stroke: str | None = None,
        compact: bool = False,
    ):
        return ft.ButtonStyle(
            color=fg or theme.text_primary,
            bgcolor=bg_fill or theme.panel_alt,
            overlay_color=theme.accent_soft,
            elevation=0,
            padding=ft.padding.symmetric(horizontal=10 if compact else 12, vertical=6 if compact else 9),
            side=ft.BorderSide(1, stroke or theme.border),
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=11, weight=ft.FontWeight.W_600),
        )

    def section_heading(title: str, subtitle: str, *, eyebrow: str = "Workbench"):
        return ft.Column(
            [
                ft.Text(eyebrow.upper(), size=11, color=theme.text_muted, weight=ft.FontWeight.W_600),
                ft.Text(title, size=18, color=theme.text_primary, weight=ft.FontWeight.W_700),
                ft.Text(subtitle, size=12, color=theme.text_secondary),
            ],
            spacing=2,
        )

    def current_workspace():
        if state.selected_workspace_id is None:
            return None
        try:
            return services.workspace_service.get_workspace(state.selected_workspace_id)
        except KeyError:
            state.selected_workspace_id = None
            return None

    def current_document():
        if state.active_document_path is None:
            return None
        return state.document_cache.get(state.active_document_path)

    def append_log(message: str) -> None:
        state.append_log(message)

    def apply_page_theme() -> None:
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(
            color_scheme_seed=theme.accent,
            font_family="Segoe UI",
            use_material3=True,
            scaffold_bgcolor=theme.page_bg,
            canvas_color=theme.page_bg,
            card_bgcolor=theme.panel,
            divider_color=theme.border_soft,
            hint_color=theme.text_muted,
            hover_color=theme.accent_soft,
            focus_color=theme.accent_soft,
            splash_color=theme.accent_soft,
        )
        page.bgcolor = theme.page_bg

    def apply_input_theme() -> None:
        for control in [workspace_dropdown, tool_name_input, tool_source_input, accent_input, surface_input]:
            control.border_color = theme.border
            control.focused_border_color = theme.accent
            control.color = theme.text_primary
            control.bgcolor = theme.panel_alt
        panel_opacity_slider.active_color = theme.accent
        panel_opacity_slider.thumb_color = theme.accent
        panel_opacity_slider.inactive_color = theme.border_soft
        chrome_opacity_slider.active_color = theme.accent
        chrome_opacity_slider.thumb_color = theme.accent
        chrome_opacity_slider.inactive_color = theme.border_soft
        workspace_path_text.color = theme.text_secondary
        workspace_meta_text.color = theme.text_secondary
        appearance_meta_text.color = theme.text_secondary
        editor_meta_text.color = theme.text_secondary
        panel_opacity_text.color = theme.text_secondary
        chrome_opacity_text.color = theme.text_secondary
        theme_message.color = theme.text_secondary
        panel_opacity_text.value = f"Panel transparency: {theme_config.panel_opacity:.2f}"
        chrome_opacity_text.value = f"Chrome transparency: {theme_config.chrome_opacity:.2f}"
        appearance_meta_text.value = (
            f"Accent {theme_config.accent}  •  Panels {theme_config.panel_opacity:.2f}  •  Chrome {theme_config.chrome_opacity:.2f}"
        )

    def refresh_meta() -> None:
        workspace = current_workspace()
        workspace_path_text.value = workspace.root_path if workspace else "No workspace selected"
        workspace_meta_text.value = f"{len(state.open_document_paths)} open tabs"
        editor_meta_text.value = state.active_document_path or "No file open"

    def set_server_status() -> None:
        if services.server.running:
            server_status.value = f"Server running at {server_url}"
            server_status.color = theme.success
            server_status_chip.bgcolor = theme.accent_fill
        else:
            server_status.value = f"Server stopped ({server_url})"
            server_status.color = theme.warning
            server_status_chip.bgcolor = theme.panel_alt
        server_status_chip.border = None
        server_status_chip.content = server_status

    def refresh_workspace_selector() -> None:
        workspaces = services.workspace_service.list_workspaces()
        workspace_dropdown.options = [ft.dropdown.Option(workspace.id, workspace.name) for workspace in workspaces]
        workspace_dropdown.value = state.selected_workspace_id
        refresh_meta()

    def build_tree_controls(relative_path: str | None = None, depth: int = 0) -> list:
        workspace = current_workspace()
        if workspace is None:
            return []
        try:
            nodes = services.ide_service.list_project_files(workspace.id, relative_path)
        except (FileNotFoundError, ValueError) as exc:
            append_log(str(exc))
            return []
        controls = []
        for node in nodes:
            is_directory = node.node_type == "directory"
            is_expanded = node.relative_path in state.expanded_tree_nodes
            is_active = node.relative_path == state.active_document_path
            toggle_icon = (
                ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
                if is_directory and is_expanded
                else ft.Icons.CHEVRON_RIGHT_ROUNDED
            )
            icon_name = (
                ft.Icons.FOLDER_OPEN_ROUNDED
                if is_directory and is_expanded
                else ft.Icons.FOLDER_ROUNDED
                if is_directory
                else ft.Icons.DESCRIPTION_OUTLINED
            )
            icon_color = theme.text_secondary if is_directory else theme.text_muted
            controls.append(
                ft.Container(
                    bgcolor=theme.accent_soft if is_active else None,
                    border_radius=4,
                    content=ft.TextButton(
                        content=ft.Row(
                            [
                                (
                                    ft.Icon(toggle_icon, size=14, color=theme.text_muted)
                                    if is_directory
                                    else ft.Container(width=14)
                                ),
                                ft.Icon(icon_name, size=14, color=icon_color),
                                ft.Text(
                                    node.name,
                                    color=theme.text_primary,
                                    size=12,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                            ],
                            spacing=4,
                            tight=True,
                        ),
                        style=ft.ButtonStyle(
                            overlay_color=theme.accent_soft,
                            padding=ft.padding.only(left=8 + depth * 12, right=8, top=4, bottom=4),
                            shape=ft.RoundedRectangleBorder(radius=4),
                            alignment=ft.Alignment(-1, 0),
                        ),
                        on_click=(
                            (lambda _, path=node.relative_path: toggle_directory(path))
                            if is_directory
                            else (lambda _, path=node.relative_path: open_document(path))
                        ),
                    ),
                )
            )
            if is_directory and is_expanded:
                controls.extend(build_tree_controls(node.relative_path, depth + 1))
        return controls

    def refresh_project_tree() -> None:
        workspace = current_workspace()
        if workspace is None:
            project_list.controls = []
            return
        project_list.controls = build_tree_controls()

    def toggle_directory(relative_path: str) -> None:
        if relative_path in state.expanded_tree_nodes:
            state.expanded_tree_nodes.remove(relative_path)
        else:
            state.expanded_tree_nodes.add(relative_path)
        refresh_project_tree()
        page.update()

    def open_document(relative_path: str) -> None:
        workspace = current_workspace()
        if workspace is None:
            append_log("Open a workspace before opening files.")
            return
        try:
            document = services.ide_service.open_file(workspace.id, relative_path)
        except (FileNotFoundError, ValueError) as exc:
            append_log(str(exc))
            return
        state.open_document(document)
        state.selected_nav_tab = "chat"
        append_log(f"Opened file {relative_path}")
        refresh_nav()
        refresh_meta()
        refresh_editor()
        render_shell()
        page.update()

    def switch_document(relative_path: str) -> None:
        state.active_document_path = relative_path
        refresh_meta()
        refresh_editor()
        refresh_right_panel()
        page.update()

    def close_document(relative_path: str) -> None:
        state.close_document(relative_path)
        refresh_meta()
        refresh_editor()
        refresh_right_panel()
        page.update()

    def on_editor_change(event) -> None:
        if state.active_document_path is not None:
            state.update_document_content(state.active_document_path, event.control.value)

    def refresh_editor_tabs() -> None:
        editor_tabs.controls = []
        for relative_path in state.open_document_paths:
            is_active = relative_path == state.active_document_path
            editor_tabs.controls.append(
                ft.Container(
                    bgcolor=theme.accent_fill if is_active else theme.panel_alt,
                    border=ft.border.all(1, theme.accent if is_active else theme.border_soft),
                    border_radius=16,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row(
                        [
                            ft.TextButton(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE_ROUNDED, size=16, color=theme.accent_text if is_active else theme.info),
                                        ft.Text(
                                            Path(relative_path).name,
                                            color=theme.accent_text if is_active else theme.text_secondary,
                                            size=12,
                                        ),
                                    ],
                                    spacing=8,
                                    tight=True,
                                ),
                                style=ft.ButtonStyle(
                                    overlay_color=theme.accent_soft,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=10),
                                ),
                                on_click=lambda _, path=relative_path: switch_document(path),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_size=14,
                                icon_color=theme.accent_text if is_active else theme.text_muted,
                                hover_color=theme.accent_soft,
                                splash_color=theme.accent_soft,
                                on_click=lambda _, path=relative_path: close_document(path),
                            ),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                )
            )

    def refresh_editor() -> None:
        refresh_editor_tabs()
        document = current_document()
        if document is None:
            editor_host.content = panel(
                ft.Column(
                    [
                        ft.Icon(ft.Icons.CODE_ROUNDED, size=32, color=theme.accent_text),
                        ft.Text("No file open", size=24, color=theme.text_primary, weight=ft.FontWeight.W_700),
                        ft.Text("Use Explorer to open a file from the current workspace.", size=13, color=theme.text_secondary),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                expand=True,
                bgcolor=theme.panel_alt,
                padding=24,
                blur=12,
            )
            return
        editor_host.content = panel(
            expand=True,
            bgcolor=theme.panel_alt,
            padding=12,
            border_color=theme.border_soft,
            blur=12,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            chip(document.relative_path, fg=theme.accent_text, fill=theme.accent_soft, stroke=theme.accent, icon=ft.Icons.DESCRIPTION_ROUNDED),
                            chip(f"{len(document.content.splitlines())} lines", fg=theme.text_secondary, fill=theme.panel_alt, stroke=theme.border_soft),
                        ],
                        wrap=True,
                        spacing=8,
                    ),
                    ft.Container(
                        expand=True,
                        border=ft.border.all(1, theme.border_soft),
                        border_radius=18,
                        bgcolor=theme.editor,
                        padding=10,
                        content=ft.TextField(
                            value=document.content,
                            multiline=True,
                            expand=True,
                            min_lines=34,
                            max_lines=40,
                            border_color=ft.Colors.TRANSPARENT,
                            focused_border_color=ft.Colors.TRANSPARENT,
                            bgcolor=theme.editor,
                            color=theme.text_primary,
                            cursor_color=theme.accent,
                            selection_color=theme.accent_soft,
                            border_radius=16,
                            text_style=ft.TextStyle(font_family="Cascadia Code", size=13),
                            on_change=on_editor_change,
                        ),
                    ),
                ],
                expand=True,
                spacing=12,
            ),
        )

    def install_tool(_: ft.ControlEvent) -> None:
        name = (tool_name_input.value or "").strip()
        source = (tool_source_input.value or "").strip()
        if not name or not source:
            append_log("Tool name and source are required.")
            refresh_right_panel()
            page.update()
            return
        tool = services.tools_service.install_tool(name=name, kind=state.selected_tool_kind, source=source)
        state.selected_tool_id = tool.id
        tool_name_input.value = ""
        tool_source_input.value = ""
        append_log(f"Installed {tool.kind.value.upper()} tool {tool.name}")
        refresh_right_panel()
        page.update()

    def bind_selected_tool(_: ft.ControlEvent) -> None:
        if state.selected_tool_id is None or state.selected_workspace_id is None:
            append_log("Select both a workspace and a tool before binding.")
            refresh_right_panel()
            page.update()
            return
        tool = services.tools_service.bind_tool(state.selected_tool_id, state.selected_workspace_id)
        append_log(f"Bound {tool.name} to workspace {state.selected_workspace_id}")
        refresh_right_panel()
        page.update()

    def toggle_selected_tool_enabled(_: ft.ControlEvent) -> None:
        if state.selected_tool_id is None:
            append_log("Select a tool first.")
            refresh_right_panel()
            page.update()
            return
        tool = next((item for item in services.tools_service.list_tools() if item.id == state.selected_tool_id), None)
        if tool is None:
            append_log("Selected tool no longer exists.")
            refresh_right_panel()
            page.update()
            return
        updated = services.tools_service.set_enabled(tool.id, not tool.enabled)
        append_log(f"{'Enabled' if updated.enabled else 'Disabled'} tool {updated.name}")
        refresh_right_panel()
        page.update()

    def save_active_file(_: ft.ControlEvent) -> None:
        workspace = current_workspace()
        document = current_document()
        if workspace is None or document is None:
            append_log("Open a workspace and a file before saving.")
            refresh_right_panel()
            page.update()
            return
        saved = services.ide_service.save_file(workspace.id, document.relative_path, document.content)
        state.open_document(saved)
        append_log(f"Saved file {saved.relative_path}")
        refresh_meta()
        refresh_right_panel()
        page.update()

    def select_workspace(workspace_id: str | None) -> None:
        state.selected_workspace_id = workspace_id or None
        refresh_workspace_selector()
        refresh_project_tree()
        refresh_right_panel()
        page.update()

    def handle_workspace_change(event) -> None:
        select_workspace(event.control.value)

    def select_session(session_id: str) -> None:
        state.selected_session_id = session_id
        refresh_right_panel()
        page.update()

    def select_tool(tool_id: str) -> None:
        state.selected_tool_id = tool_id
        refresh_right_panel()
        page.update()

    def switch_nav(tab_name: str) -> None:
        state.selected_nav_tab = tab_name
        render_shell()
        page.update()

    def switch_tool_kind(kind: ToolKind) -> None:
        state.selected_tool_kind = kind
        state.selected_tool_id = None
        refresh_right_panel()
        page.update()

    def start_audit(_: ft.ControlEvent) -> None:
        workspace = current_workspace()
        if workspace is None:
            append_log("Select or open a workspace first.")
            refresh_right_panel()
            page.update()
            return
        snapshot = services.session_service.start_session(workspace.id)
        state.selected_session_id = snapshot.session.id
        state.selected_nav_tab = "audit"
        append_log(
            f"Audit finished for {workspace.name}: status={snapshot.session.status.value} rounds={snapshot.session.current_round}"
        )
        render_shell()
        page.update()

    def toggle_server(_: ft.ControlEvent) -> None:
        if services.server.running:
            services.server.stop()
            append_log("Desktop server stopped.")
        else:
            try:
                services.server.start()
                append_log(f"Desktop server started at {server_url}")
            except RuntimeError as exc:
                append_log(str(exc))
        set_server_status()
        refresh_right_panel()
        page.update()

    def render_explorer_panel():
        workspace = current_workspace()
        document = current_document()
        controls = [
            section_heading("Explorer", "Workspace structure and current document context.", eyebrow="Files"),
            chip(
                workspace.name if workspace else "No workspace selected",
                fg=theme.text_primary,
                fill=theme.panel_alt,
                stroke=theme.border_soft,
                icon=ft.Icons.FOLDER_ROUNDED,
            ),
            ft.Text(
                workspace.root_path if workspace else "Select a workspace to browse files.",
                color=theme.text_secondary,
                size=12,
            ),
        ]
        if document is not None:
            controls.extend(
                [
                    ft.Divider(color=theme.border_soft),
                    ft.Text("Current Document", size=16, color=theme.text_primary, weight=ft.FontWeight.W_700),
                    chip(document.relative_path, fg=theme.accent_text, fill=theme.accent_soft, stroke=theme.accent, icon=ft.Icons.DESCRIPTION_ROUNDED),
                    ft.Text(f"{len(document.content.splitlines())} lines", color=theme.text_secondary, size=12),
                ]
            )
        return ft.Column(controls, spacing=10, expand=True)

    def render_audit_panel():
        sessions = services.session_service.list_sessions(state.selected_workspace_id)
        controls = [section_heading("Audit", "Recent runs, payloads, and the local audit log.", eyebrow="Analysis")]
        controls.append(ft.Text("Recent Sessions", color=theme.text_secondary))
        for session in sessions[:8]:
            selected = session.id == state.selected_session_id
            controls.append(
                ft.Container(
                    bgcolor=theme.accent_fill if selected else theme.panel_alt,
                    border=ft.border.all(1, theme.accent if selected else theme.border_soft),
                    border_radius=18,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.TextButton(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=16, color=theme.accent_text if selected else theme.info),
                                        ft.Text(
                                            f"{session.status.value} · round {session.current_round}",
                                            color=theme.accent_text if selected else theme.text_primary,
                                        ),
                                    ],
                                    spacing=8,
                                    tight=True,
                                ),
                                style=ft.ButtonStyle(
                                    overlay_color=theme.accent_soft,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=10),
                                ),
                                on_click=lambda _, session_id=session.id: select_session(session_id),
                            ),
                            ft.Text(session.id, color=theme.text_secondary, size=11),
                        ],
                        tight=True,
                    ),
                )
            )
        if state.selected_session_id:
            snapshot = session_snapshot_to_dict(services.session_service.get_session_snapshot(state.selected_session_id))
            controls.extend(
                [
                    ft.Divider(color=theme.border_soft),
                    ft.Text("Session Detail", size=16, color=theme.text_primary, weight=ft.FontWeight.W_700),
                    ft.TextField(
                        value=json.dumps(snapshot, indent=2),
                        multiline=True,
                        read_only=True,
                        min_lines=12,
                        max_lines=18,
                        border_color=theme.border_soft,
                        bgcolor=theme.editor,
                        color=theme.text_secondary,
                        border_radius=16,
                        text_style=ft.TextStyle(font_family="Cascadia Code", size=12),
                    ),
                ]
            )
        controls.extend(
            [
                ft.Divider(color=theme.border_soft),
                ft.Text("Audit Log", size=16, color=theme.text_primary, weight=ft.FontWeight.W_700),
                ft.TextField(
                    value="\n".join(state.audit_log[-30:]),
                    multiline=True,
                    read_only=True,
                    min_lines=8,
                    max_lines=12,
                    border_color=theme.border_soft,
                    bgcolor=theme.editor,
                    color=theme.text_secondary,
                    border_radius=16,
                    text_style=ft.TextStyle(font_family="Cascadia Code", size=12),
                ),
            ]
        )
        return ft.Column(controls, spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def render_tools_panel():
        workspace = current_workspace()
        tools = services.tools_service.list_tools(workspace_id=state.selected_workspace_id, kind=state.selected_tool_kind)
        selected_tool = next((item for item in tools if item.id == state.selected_tool_id), None)
        controls = [
            section_heading("Tools", "Install, inspect, and bind MCP servers or skills.", eyebrow="Integrations"),
            ft.Row(
                [
                    ft.FilledButton(
                        "MCP",
                        on_click=lambda _: switch_tool_kind(ToolKind.MCP),
                        style=button_style(
                            fg=theme.accent_text if state.selected_tool_kind == ToolKind.MCP else theme.text_secondary,
                            bg_fill=theme.accent_fill if state.selected_tool_kind == ToolKind.MCP else theme.panel_alt,
                            stroke=theme.accent if state.selected_tool_kind == ToolKind.MCP else theme.border_soft,
                            compact=True,
                        ),
                    ),
                    ft.FilledButton(
                        "Skills",
                        on_click=lambda _: switch_tool_kind(ToolKind.SKILL),
                        style=button_style(
                            fg=theme.accent_text if state.selected_tool_kind == ToolKind.SKILL else theme.text_secondary,
                            bg_fill=theme.accent_fill if state.selected_tool_kind == ToolKind.SKILL else theme.panel_alt,
                            stroke=theme.accent if state.selected_tool_kind == ToolKind.SKILL else theme.border_soft,
                            compact=True,
                        ),
                    ),
                ],
                wrap=True,
                spacing=8,
            ),
            tool_name_input,
            tool_source_input,
            ft.FilledButton(
                f"Install {state.selected_tool_kind.value.upper()}",
                on_click=install_tool,
                style=button_style(fg=theme.on_accent, bg_fill=theme.accent, stroke=theme.accent),
            ),
            ft.Divider(color=theme.border_soft),
            ft.Text("Installed", color=theme.text_secondary),
        ]
        for tool in tools:
            selected = tool.id == state.selected_tool_id
            controls.append(
                ft.Container(
                    bgcolor=theme.accent_fill if selected else theme.panel_alt,
                    border=ft.border.all(1, theme.accent if selected else theme.border_soft),
                    border_radius=18,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.TextButton(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.HANDYMAN_ROUNDED, size=16, color=theme.accent_text if selected else theme.info),
                                        ft.Text(tool.name, color=theme.accent_text if selected else theme.text_primary),
                                    ],
                                    spacing=8,
                                    tight=True,
                                ),
                                style=ft.ButtonStyle(
                                    overlay_color=theme.accent_soft,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=10),
                                ),
                                on_click=lambda _, tool_id=tool.id: select_tool(tool_id),
                            ),
                            ft.Text(tool.source, color=theme.text_secondary, size=11),
                        ],
                        tight=True,
                    ),
                )
            )
        if selected_tool is not None:
            controls.extend(
                [
                    ft.Divider(color=theme.border_soft),
                    ft.Text("Selected Tool", size=16, color=theme.text_primary, weight=ft.FontWeight.W_700),
                    chip(selected_tool.name, fg=theme.text_primary, fill=theme.panel_alt, stroke=theme.border_soft, icon=ft.Icons.HANDYMAN_ROUNDED),
                    ft.Text(f"Kind: {selected_tool.kind.value.upper()}", color=theme.info),
                    ft.Text(f"Health: {selected_tool.health.value}", color=theme.text_primary),
                    ft.Text(
                        f"Scope: {'global' if not selected_tool.workspace_ids else ', '.join(selected_tool.workspace_ids)}",
                        color=theme.text_secondary,
                    ),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Bind To Workspace",
                                disabled=workspace is None,
                                on_click=bind_selected_tool,
                                style=button_style(fg=theme.text_primary, bg_fill=theme.panel_alt, stroke=theme.border),
                            ),
                            ft.OutlinedButton(
                                "Disable" if selected_tool.enabled else "Enable",
                                on_click=toggle_selected_tool_enabled,
                                style=button_style(fg=theme.text_secondary, bg_fill=theme.panel_alt, stroke=theme.border_soft),
                            ),
                        ],
                        wrap=True,
                        spacing=8,
                    ),
                ]
            )
        return ft.Column(controls, spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def render_sessions_panel():
        sessions = services.session_service.list_sessions(state.selected_workspace_id)
        controls = [section_heading("Sessions", "Historical runs scoped to the current workspace.", eyebrow="History")]
        if not sessions:
            controls.append(ft.Text("No sessions yet.", color=theme.text_secondary))
        for session in sessions:
            selected = session.id == state.selected_session_id
            controls.append(
                ft.Container(
                    bgcolor=theme.accent_fill if selected else theme.panel_alt,
                    border=ft.border.all(1, theme.accent if selected else theme.border_soft),
                    border_radius=18,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.TextButton(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.HISTORY_ROUNDED, size=16, color=theme.accent_text if selected else theme.info),
                                        ft.Text(session.id, color=theme.accent_text if selected else theme.text_primary),
                                    ],
                                    spacing=8,
                                    tight=True,
                                ),
                                style=ft.ButtonStyle(
                                    overlay_color=theme.accent_soft,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=10),
                                ),
                                on_click=lambda _, session_id=session.id: select_session(session_id),
                            ),
                            ft.Text(f"Status: {session.status.value}", color=theme.text_primary, size=12),
                            ft.Text(f"Rounds: {session.current_round}", color=theme.text_secondary, size=11),
                        ],
                        tight=True,
                    ),
                )
            )
        return ft.Column(controls, spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def render_settings_panel():
        preset_buttons = [
            ft.OutlinedButton(
                name,
                on_click=lambda _, preset_name=name, preset_accent=accent, preset_surface=surface: apply_theme_settings(
                    preset_name, preset_accent, preset_surface
                ),
                style=button_style(fg=theme.text_primary, bg_fill=theme.panel_alt, stroke=theme.border_soft, compact=True),
            )
            for name, accent, surface in THEME_PRESETS
        ]
        return ft.Column(
            [
                section_heading("Settings", "Runtime and appearance details for this local workbench.", eyebrow="Config"),
                ft.Text("Appearance", size=16, color=theme.text_primary, weight=ft.FontWeight.W_700),
                ft.Row([accent_input, surface_input], wrap=True, spacing=8),
                ft.Column([panel_opacity_text, panel_opacity_slider], spacing=2),
                ft.Column([chrome_opacity_text, chrome_opacity_slider], spacing=2),
                ft.Row(preset_buttons, wrap=True, spacing=8, run_spacing=8),
                ft.Row(
                    [
                        ft.FilledButton("Apply Theme", on_click=commit_theme, style=button_style(fg=theme.on_accent, bg_fill=theme.accent, stroke=theme.accent)),
                        ft.OutlinedButton("Reset", on_click=reset_theme, style=button_style(fg=theme.text_secondary, bg_fill=theme.panel_alt, stroke=theme.border_soft)),
                    ],
                    wrap=True,
                    spacing=8,
                ),
                chip(theme_message, fg=theme.text_secondary, fill=theme.panel_alt, stroke=theme.border_soft, icon=ft.Icons.PALETTE_ROUNDED),
                ft.Divider(color=theme.border_soft),
                ft.Text("Environment", size=16, color=theme.text_primary, weight=ft.FontWeight.W_700),
                chip(f"State directory: {services.env.state_dir}", fg=theme.text_primary, fill=theme.panel_alt, stroke=theme.border_soft, icon=ft.Icons.FOLDER_ROUNDED),
                chip(f"Server URL: {server_url}", fg=theme.text_primary, fill=theme.panel_alt, stroke=theme.border_soft, icon=ft.Icons.LAN_ROUNDED),
                chip(
                    f"Server running: {'yes' if services.server.running else 'no'}",
                    fg=theme.accent_text if services.server.running else theme.warning,
                    fill=theme.accent_fill if services.server.running else theme.panel_alt,
                    stroke=theme.accent if services.server.running else theme.border_soft,
                    icon=ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED,
                ),
                ft.Text(
                    "Env vars: SECLAW_THEME_ACCENT, SECLAW_THEME_SURFACE, SECLAW_THEME_PANEL_OPACITY, SECLAW_THEME_CHROME_OPACITY",
                    color=theme.text_secondary,
                    size=12,
                ),
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def render_chat_panel():
        return panel(
            ft.Container(expand=True),
            expand=True,
            bgcolor=theme.panel_alt,
            padding=16,
            radius=0,
            shadow=[],
        )

    def render_workspace_panel():
        workspace = current_workspace()
        root_label = workspace.name.upper() if workspace else "NO FOLDER OPENED"
        return panel(
            ft.Column(
                [
                    ft.Container(
                        padding=ft.padding.only(left=10, right=6, top=8, bottom=8),
                        content=ft.Row(
                            [
                                ft.Text("EXPLORER", size=11, color=theme.text_muted, weight=ft.FontWeight.W_600),
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                            icon_size=15,
                                            icon_color=theme.text_secondary,
                                            hover_color=theme.accent_soft,
                                            splash_color=theme.accent_soft,
                                            tooltip="Open folder",
                                            on_click=browse_directory,
                                        ),
                                    ],
                                    spacing=0,
                                    tight=True,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Container(height=1, bgcolor=theme.border_soft),
                    ft.Container(
                        padding=ft.padding.only(left=10, right=10, top=6, bottom=6),
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if workspace else ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                    size=14,
                                    color=theme.text_secondary,
                                ),
                                ft.Text(root_label, size=11, color=theme.text_secondary, weight=ft.FontWeight.W_600),
                            ],
                            spacing=4,
                            tight=True,
                        ),
                    ),
                    ft.Container(height=1, bgcolor=theme.border_soft),
                    (
                        ft.Container(
                            expand=True,
                            padding=ft.padding.only(left=14, right=14, top=14, bottom=12),
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Open a folder to start browsing and editing project files.",
                                        size=12,
                                        color=theme.text_muted,
                                    ),
                                ],
                                spacing=12,
                            ),
                        )
                        if workspace is None
                        else ft.Container(
                            expand=True,
                            padding=ft.padding.only(top=4, left=4, right=4, bottom=6),
                            content=project_list,
                        )
                    ),
                ],
                expand=True,
                spacing=0,
            ),
            bgcolor=theme.panel_alt,
            padding=0,
            radius=0,
            shadow=[],
        )

    def refresh_right_panel() -> None:
        if state.selected_nav_tab == "chat":
            main_area.content = render_chat_panel()
            workspace_area.content = render_workspace_panel()
            workspace_area.visible = True
        else:
            content = {
                "audit": render_audit_panel,
                "tools": render_tools_panel,
                "sessions": render_sessions_panel,
                "settings": render_settings_panel,
            }[state.selected_nav_tab]()
            main_area.content = panel(
                content,
                expand=True,
                bgcolor=theme.panel_alt,
                padding=16,
                radius=14,
                shadow=[],
            )
            workspace_area.visible = False

    def refresh_nav() -> None:
        nav_column.controls = []
        for tab_name, label, icon_name in NAV_ITEMS:
            selected = state.selected_nav_tab == tab_name
            nav_column.controls.append(
                ft.Container(
                    width=64,
                    bgcolor=theme.accent_fill if selected else theme.panel_alt,
                    border=None,
                    border_radius=14,
                    content=ft.TextButton(
                        tooltip=label,
                        content=ft.Column(
                            [
                                ft.Icon(getattr(ft.Icons, icon_name), size=18, color=theme.accent_text if selected else theme.text_secondary),
                                ft.Text(
                                    label,
                                    size=10,
                                    color=theme.accent_text if selected else theme.text_secondary,
                                    weight=ft.FontWeight.W_600,
                                ),
                            ],
                            spacing=4,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        style=ft.ButtonStyle(
                            overlay_color=theme.accent_soft,
                            padding=ft.padding.symmetric(horizontal=8, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=14),
                            alignment=ft.Alignment(0, 0),
                        ),
                        on_click=lambda _, tab=tab_name: switch_nav(tab),
                    ),
                )
            )

    def refresh_all() -> None:
        apply_input_theme()
        set_server_status()
        refresh_workspace_selector()
        refresh_nav()
        refresh_project_tree()
        refresh_editor()
        refresh_right_panel()

    def open_workspace_path(path: str) -> None:
        if not path:
            return
        try:
            workspace = services.workspace_service.open_workspace(path)
        except FileNotFoundError as exc:
            append_log(str(exc))
            refresh_right_panel()
            page.update()
            return
        state.selected_workspace_id = workspace.id
        append_log(f"Opened workspace {workspace.name}")
        refresh_all()
        page.update()

    async def browse_directory(_: ft.ControlEvent) -> None:
        selected_path = await picker.get_directory_path(dialog_title="Open a project workspace")
        if selected_path:
            open_workspace_path(selected_path)

    def render_shell() -> None:
        refresh_nav()
        refresh_meta()
        set_server_status()
        viewport_width = page.width or 1440
        viewport_height = page.height or 920
        workspace_height = max(680, int(viewport_height))
        sidebar_width = 78 if viewport_width >= 980 else 68
        directory_width = 330 if viewport_width >= 1320 else 296
        divider_vertical = ft.Container(width=1, bgcolor=theme.border_soft)
        divider_horizontal = ft.Container(height=1, bgcolor=theme.border_soft)

        left_sidebar = panel(
            ft.Column(
                [
                    ft.Container(
                        padding=ft.padding.only(top=8),
                        content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18, color=theme.accent_text),
                    ),
                    nav_column,
                    ft.Container(expand=True),
                ],
                expand=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=sidebar_width if viewport_width >= 980 else None,
            expand=viewport_width < 980,
            bgcolor=theme.shell,
            padding=ft.padding.only(left=10, right=10, bottom=10, top=0),
            radius=0,
            shadow=[],
        )

        refresh_right_panel()
        center_panel = main_area
        directory_panel = workspace_area
        is_chat_view = state.selected_nav_tab == "chat"
        show_workspace = is_chat_view and directory_panel.visible

        directory_panel.width = directory_width if viewport_width >= 1180 and show_workspace else None
        directory_panel.expand = viewport_width < 1180 and show_workspace

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                padding=0,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, -1),
                    end=ft.Alignment(1, 1),
                    colors=[theme.gradient_start, theme.gradient_end],
                ),
                content=ft.Container(
                    height=workspace_height,
                    content=(
                        ft.Column(
                            [
                                left_sidebar,
                                divider_horizontal,
                                center_panel,
                                divider_horizontal,
                                directory_panel,
                            ]
                            if show_workspace
                            else [left_sidebar, center_panel],
                            spacing=0,
                            expand=True,
                        )
                        if viewport_width < 980
                        else ft.Column(
                            [
                                ft.Row(
                                    [left_sidebar, divider_vertical, center_panel],
                                    expand=True,
                                    spacing=0,
                                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                                ),
                                ft.Container(height=1, bgcolor=theme.border_soft) if show_workspace else ft.Container(),
                                ft.Container(height=280, content=directory_panel) if show_workspace else ft.Container(),
                            ],
                            spacing=0,
                            expand=True,
                        )
                        if viewport_width < 1180
                        else ft.Row(
                            [left_sidebar, divider_vertical, center_panel, divider_vertical, directory_panel]
                            if show_workspace
                            else [left_sidebar, divider_vertical, center_panel],
                            expand=True,
                            spacing=0,
                            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                        )
                    ),
                ),
            )
        )

    def apply_theme(message: str | None = None) -> None:
        nonlocal theme
        theme = _build_theme(ft, theme_config)
        apply_page_theme()
        apply_input_theme()
        set_server_status()
        render_shell()
        refresh_all()
        if message is not None:
            theme_message.value = message
        page.update()

    def commit_theme(_: ft.ControlEvent | None = None) -> None:
        theme_config.accent = _normalize_hex(accent_input.value, theme_config.accent)
        theme_config.surface_tint = _normalize_hex(surface_input.value, theme_config.surface_tint)
        apply_theme("Applied custom theme.")

    def apply_theme_settings(name: str, accent: str, surface: str) -> None:
        theme_config.accent = accent
        theme_config.surface_tint = surface
        apply_theme(f"Loaded {name} preset.")

    def update_panel_opacity(event) -> None:
        theme_config.panel_opacity = float(event.control.value)
        apply_theme("Updated panel transparency.")

    def update_chrome_opacity(event) -> None:
        theme_config.chrome_opacity = float(event.control.value)
        apply_theme("Updated chrome transparency.")

    def reset_theme(_: ft.ControlEvent) -> None:
        theme_config.accent = default_theme.accent
        theme_config.surface_tint = default_theme.surface_tint
        theme_config.panel_opacity = default_theme.panel_opacity
        theme_config.chrome_opacity = default_theme.chrome_opacity
        apply_theme("Restored default light theme.")

    picker = ft.FilePicker()
    page.services.append(picker)

    workspace_dropdown.on_change = handle_workspace_change
    accent_input.on_submit = commit_theme
    surface_input.on_submit = commit_theme
    panel_opacity_slider.on_change_end = update_panel_opacity
    chrome_opacity_slider.on_change_end = update_chrome_opacity

    apply_theme()


def _require_flet():
    try:
        import flet as ft
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Flet is required to run the SEClaw desktop application.") from exc

    return ft


def _run_app(*, view=None) -> None:
    ft = _require_flet()
    services = ServiceContainer.default()
    app_kwargs = {}
    if view is not None:
        app_kwargs["view"] = view
    ft.app(target=lambda page: build_page(page, services), **app_kwargs)


def run() -> None:
    _run_app()


def run_web() -> None:
    ft = _require_flet()
    _run_app(view=ft.AppView.WEB_BROWSER)


if __name__ == "__main__":
    run()
