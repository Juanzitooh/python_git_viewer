#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timezone
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..core.cherry_pick_ops import (
    cherry_pick_commit as core_cherry_pick_commit,
    fetch_commit_from_source as core_fetch_commit_from_source,
    load_unmerged_conflict_files as core_load_unmerged_conflict_files,
)
from ..core.conflict_ops import (
    abort_conflict_operation as core_abort_conflict_operation,
    continue_conflict_operation as core_continue_conflict_operation,
    git_ref_exists as core_git_ref_exists,
    is_conflict_operation_in_progress as core_is_conflict_operation_in_progress,
    is_rebase_in_progress as core_is_rebase_in_progress,
    resolve_active_conflict_operation as core_resolve_active_conflict_operation,
)
from ..core.commit_content import get_commit_patch as core_get_commit_patch, list_commit_files as core_list_commit_files
from ..core.git_client import is_git_repo, load_commit_details, load_commit_summaries
from ..core.history_local_ops import (
    apply_local_commit_reorder as core_apply_local_commit_reorder,
    load_local_only_commit_hashes as core_load_local_only_commit_hashes,
    load_reorderable_local_commits as core_load_reorderable_local_commits,
)
from ..core.models import CommitFilters, CommitInfo, CommitSummary, FileStat
from ..core.repo_state import list_tags as core_list_tags
from .diff_render import render_patch_to_widget


LARGE_PATCH_THRESHOLD = 1000


class HistoryTabMixin:
    def _build_history_tab(self) -> None:
        self.history_tab.grid_columnconfigure(0, weight=1)
        self.history_tab.grid_rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self.history_tab)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top_bar.grid_columnconfigure(0, weight=1)

        history_actions = ttk.Frame(top_bar)
        history_actions.grid(row=0, column=0, sticky="w")
        self.export_commits_button = ttk.Button(
            history_actions,
            text="Exportar",
            command=self._open_cherry_pick_window,
        )
        self.export_commits_button.grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        self.export_commits_button.bind("<Enter>", self._on_export_button_hover, add=True)
        self.export_commits_button.bind("<Leave>", self._hide_hover_tooltip, add=True)
        self.reorder_local_button = ttk.Button(
            history_actions,
            text="Reordenar locais",
            command=self._open_reorder_local_commits_window,
        )
        self.reorder_local_button.grid(
            row=0,
            column=1,
            padx=(0, 6),
        )
        self.reorder_local_button.grid_remove()

        # Ações de merge/rebase/squash agora vivem na aba Comparar.
        self.filter_text_var = tk.StringVar(value="")
        self.filter_author_var = tk.StringVar(value="")
        self.filter_path_var = tk.StringVar(value="")
        self.filter_since_var = tk.StringVar(value="")
        self.filter_until_var = tk.StringVar(value="")
        self.filter_branch_var = tk.StringVar(value="(todas)")
        self.filter_tag_var = tk.StringVar(value="(todas)")
        self.filter_repo_status_var = tk.StringVar(value="Todos")
        self.filter_branch_values = ["(todas)"]
        self.filter_tag_values = ["(todas)"]
        self.filter_modal: tk.Toplevel | None = None
        self.filter_branch_combo: ttk.Combobox | None = None
        self.filter_tag_combo: ttk.Combobox | None = None
        self.filter_repo_status_combo: ttk.Combobox | None = None
        self.local_only_commit_hashes: set[str] = set()
        self.history_has_upstream = False

        filter_row = ttk.Frame(top_bar)
        filter_row.grid(row=1, column=0, columnspan=1, sticky="ew", pady=(6, 0))
        filter_row.grid_columnconfigure(2, weight=1)

        ttk.Button(filter_row, text="Busca filtrada", command=self._open_filter_modal).grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.clear_filter_button = ttk.Button(
            filter_row,
            text="Tirar filtro",
            command=self._clear_commit_filters,
        )
        self.clear_filter_button.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.clear_filter_button.grid_remove()

        self.filter_status_var = tk.StringVar(value="Sem filtro ativo.")
        self.filter_status_label = ttk.Label(filter_row, textvariable=self.filter_status_var)
        self.filter_status_label.grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Label(filter_row, text="Legenda commits: [L] local | [L+O] local+online").grid(
            row=0,
            column=3,
            sticky="e",
            padx=(12, 0),
        )

        paned = ttk.PanedWindow(self.history_tab, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew")
        self._history_paned = paned

        self.left_frame = ttk.Frame(paned)
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(1, weight=0)

        self.commit_listbox = tk.Listbox(
            self.left_frame,
            activestyle="dotbox",
            selectmode="extended",
            exportselection=False,
        )
        self.commit_listbox.grid(row=0, column=0, sticky="nsew")
        self.commit_listbox.bind("<<ListboxSelect>>", self._on_commit_select)
        self.commit_listbox.bind("<MouseWheel>", self._on_history_mousewheel)
        self.commit_listbox.bind("<Button-4>", self._on_history_mousewheel)
        self.commit_listbox.bind("<Button-5>", self._on_history_mousewheel)
        self.commit_listbox.bind("<Button-3>", self._on_commit_context_menu_request, add=True)
        self.commit_listbox.bind("<Motion>", self._on_commit_list_hover)
        self.commit_listbox.bind("<Leave>", self._on_commit_list_leave)
        self.commit_listbox.bind("<FocusOut>", self._on_commit_list_leave)
        self.commit_listbox.bind("<Configure>", self._on_commit_list_leave)
        self.commit_tooltip_window: tk.Toplevel | None = None
        self.commit_tooltip_index: int = -1
        self.commit_context_menu: tk.Menu | None = None

        self.commit_scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=self._on_history_scrollbar)
        self.commit_scrollbar.grid(row=0, column=1, sticky="ns")
        self.commit_listbox.configure(yscrollcommand=self._on_history_yscroll)

        self._build_right_panel()
        paned.add(self.left_frame, weight=1)
        paned.add(self.right_frame, weight=3)
        self.conflicts_refresh_job: str | None = None
        self.conflict_operation_key = ""
        self.conflict_source_label = ""
        self.conflict_continue_message = ""
        self._build_conflicts_tab()

    def _on_export_button_hover(self, event: tk.Event) -> None:
        self._show_hover_tooltip(
            "history_export_button",
            "Exportar commits selecionados",
            event.x_root + 12,
            event.y_root + 12,
        )

    def _build_right_panel(self) -> None:
        parent = getattr(self, "_history_paned", self.history_tab)
        self.right_frame = ttk.Frame(parent)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        details_paned = ttk.PanedWindow(self.right_frame, orient="vertical")
        details_paned.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 8))
        self._history_details_paned = details_paned

        meta_frame = ttk.Frame(details_paned)
        meta_frame.grid_columnconfigure(0, weight=1)
        meta_frame.grid_rowconfigure(1, weight=1)

        self.commit_info = tk.Text(meta_frame, height=6, wrap="word")
        self.commit_info.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        self.commit_info.configure(state="disabled")

        files_frame = ttk.Frame(meta_frame)
        files_frame.grid(row=1, column=0, sticky="nsew")
        files_frame.grid_rowconfigure(1, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)
        files_frame.grid_columnconfigure(1, weight=0)

        self.files_listbox = tk.Listbox(files_frame, height=6, activestyle="dotbox")
        self.files_listbox.grid(row=1, column=0, sticky="nsew")
        self.files_listbox.bind("<<ListboxSelect>>", self._on_file_select)
        self.files_listbox.bind("<Double-Button-1>", self._open_selected_file_in_vscode)
        self.files_listbox.bind("<Button-3>", self._on_history_file_context_menu_request, add=True)

        files_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_listbox.yview)
        files_scroll.grid(row=1, column=1, sticky="ns")
        self.files_listbox.configure(yscrollcommand=files_scroll.set)

        self.file_stats_by_index: dict[int, FileStat] = {}
        self.history_file_context_menu: tk.Menu | None = None

        patch_frame = ttk.Frame(details_paned)
        patch_frame.grid_rowconfigure(1, weight=1)
        patch_frame.grid_columnconfigure(0, weight=1)

        patch_header = ttk.Frame(patch_frame)
        patch_header.grid(row=0, column=0, sticky="ew")
        patch_header.grid_columnconfigure(0, weight=1)
        ttk.Label(patch_header, text="Patch do arquivo").grid(row=0, column=0, sticky="w")
        self.load_patch_button = ttk.Button(
            patch_header,
            text="Carregar patch grande",
            command=self._load_full_patch_for_selected_file,
            state="disabled",
        )
        self.load_patch_button.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.load_patch_button.grid_remove()
        self.open_patch_button = ttk.Button(
            patch_header,
            text="Abrir em janela",
            command=self._open_patch_window,
        )
        self.open_patch_button.grid(row=0, column=2, sticky="e", padx=(0, 8))
        ttk.Checkbutton(
            patch_header,
            text="Diff por palavra",
            variable=self.word_diff_var,
            command=self._toggle_word_diff,
        ).grid(row=0, column=3, sticky="e")
        ttk.Checkbutton(
            patch_header,
            text="Modo leitura",
            variable=self.read_mode_var,
            command=self._toggle_read_mode,
        ).grid(row=0, column=4, sticky="e", padx=(8, 0))
        self.patch_read_mode_var = tk.StringVar(value="")
        ttk.Label(patch_header, textvariable=self.patch_read_mode_var).grid(
            row=0, column=5, sticky="e", padx=(8, 0)
        )

        self.patch_text = tk.Text(patch_frame, wrap="none")
        self.patch_text.grid(row=1, column=0, sticky="nsew")
        patch_scroll = ttk.Scrollbar(patch_frame, orient="vertical", command=self.patch_text.yview)
        patch_scroll.grid(row=1, column=1, sticky="ns")
        self.patch_text.configure(yscrollcommand=patch_scroll.set)
        self.patch_text.tag_configure("added", foreground="#1a7f37")
        self.patch_text.tag_configure("removed", foreground="#d1242f")
        self.patch_text.tag_configure("meta", foreground="#57606a")
        self.patch_text.tag_configure("added_word", foreground="#1a7f37", background="#dafbe1")
        self.patch_text.tag_configure("removed_word", foreground="#d1242f", background="#ffebe9")
        self.patch_text.configure(font="TkFixedFont")
        self.patch_text.configure(state="disabled")

        details_paned.add(meta_frame, weight=1)
        details_paned.add(patch_frame, weight=3)

    def _build_conflicts_tab(self) -> None:
        if not hasattr(self, "tabs"):
            return
        self.conflicts_tab = ttk.Frame(self.tabs)
        self.conflicts_tab.grid_columnconfigure(0, weight=1)
        self.conflicts_tab.grid_rowconfigure(2, weight=1)

        header = ttk.Frame(self.conflicts_tab)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(1, weight=1)
        self.conflict_header_var = tk.StringVar(value="Conflitos")
        ttk.Label(header, textvariable=self.conflict_header_var).grid(row=0, column=0, sticky="w")
        self.conflict_count_var = tk.StringVar(value="Conflitos: 0")
        ttk.Label(header, textvariable=self.conflict_count_var).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(header, text="Atualizar", command=self._refresh_conflicts_tab_manual).grid(row=0, column=2, sticky="e")

        self.conflict_status_var = tk.StringVar(value="Sem conflitos ativos.")
        ttk.Label(self.conflicts_tab, textvariable=self.conflict_status_var).grid(
            row=1,
            column=0,
            sticky="w",
            padx=8,
            pady=(0, 4),
        )

        list_frame = ttk.Frame(self.conflicts_tab)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        self.conflict_files_listbox = tk.Listbox(list_frame, activestyle="dotbox", exportselection=False)
        self.conflict_files_listbox.grid(row=0, column=0, sticky="nsew")
        self.conflict_files_listbox.bind("<<ListboxSelect>>", self._on_conflict_file_select)
        self.conflict_files_listbox.bind("<Double-Button-1>", self._on_conflict_file_double_click)
        conflict_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.conflict_files_listbox.yview)
        conflict_scroll.grid(row=0, column=1, sticky="ns")
        self.conflict_files_listbox.configure(yscrollcommand=conflict_scroll.set)

        actions = ttk.Frame(self.conflicts_tab)
        actions.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 8))
        self.conflicts_open_vscode_button = ttk.Button(
            actions,
            text="Abrir no VS Code",
            command=self._open_selected_conflict_files_in_vscode,
            state="disabled",
        )
        self.conflicts_open_vscode_button.grid(row=0, column=0, padx=(0, 6))
        self.conflicts_abort_button = ttk.Button(
            actions,
            text="Abortar",
            command=self._abort_conflict_operation,
            state="disabled",
        )
        self.conflicts_abort_button.grid(row=0, column=1, padx=(0, 6))
        self.conflicts_continue_button = ttk.Button(
            actions,
            text="Continuar",
            command=self._continue_conflict_operation,
            state="disabled",
        )
        self.conflicts_continue_button.grid(row=0, column=2, padx=(0, 6))

    def _open_filter_modal(self) -> None:
        existing = getattr(self, "filter_modal", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self)
        window.title("Busca filtrada")
        window.geometry("860x250")
        window.transient(self)
        self.filter_modal = window

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(3, weight=1)
        frame.grid_columnconfigure(5, weight=1)

        ttk.Label(frame, text="Texto:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=4)
        filter_text_entry = ttk.Entry(frame, textvariable=self.filter_text_var, width=24)
        filter_text_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        ttk.Label(frame, text="Autor:").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=4)
        filter_author_entry = ttk.Entry(frame, textvariable=self.filter_author_var, width=20)
        filter_author_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=4)

        ttk.Label(frame, text="Arquivo:").grid(row=0, column=4, sticky="w", padx=(0, 4), pady=4)
        filter_path_entry = ttk.Entry(frame, textvariable=self.filter_path_var, width=24)
        filter_path_entry.grid(row=0, column=5, sticky="ew", pady=4)

        ttk.Label(frame, text="Desde:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=4)
        filter_since_entry = ttk.Entry(frame, textvariable=self.filter_since_var, width=14)
        filter_since_entry.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(frame, text="Ate:").grid(row=1, column=2, sticky="w", padx=(0, 4), pady=4)
        filter_until_entry = ttk.Entry(frame, textvariable=self.filter_until_var, width=14)
        filter_until_entry.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(frame, text="Branch:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=4)
        self.filter_branch_combo = ttk.Combobox(
            frame,
            textvariable=self.filter_branch_var,
            state="readonly",
            width=20,
            values=self.filter_branch_values,
        )
        self.filter_branch_combo.grid(row=2, column=1, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(frame, text="Tag:").grid(row=2, column=2, sticky="w", padx=(0, 4), pady=4)
        self.filter_tag_combo = ttk.Combobox(
            frame,
            textvariable=self.filter_tag_var,
            state="readonly",
            width=20,
            values=self.filter_tag_values,
        )
        self.filter_tag_combo.grid(row=2, column=3, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(frame, text="Status repo:").grid(row=2, column=4, sticky="w", padx=(0, 4), pady=4)
        self.filter_repo_status_combo = ttk.Combobox(
            frame,
            textvariable=self.filter_repo_status_var,
            state="readonly",
            width=22,
            values=["Todos", "Somente limpo", "Somente com alteracoes"],
        )
        self.filter_repo_status_combo.grid(row=2, column=5, sticky="w", pady=4)

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, columnspan=6, sticky="e", pady=(10, 0))

        ttk.Button(actions, text="Aplicar", command=self._apply_commit_filters_from_modal).grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        ttk.Button(actions, text="Limpar", command=self._clear_commit_filters).grid(
            row=0,
            column=1,
            padx=(0, 6),
        )
        ttk.Button(actions, text="Fechar", command=self._close_filter_modal).grid(row=0, column=2)

        for entry in (
            filter_text_entry,
            filter_author_entry,
            filter_path_entry,
            filter_since_entry,
            filter_until_entry,
        ):
            entry.bind("<Return>", lambda _e: self._apply_commit_filters_from_modal())
        for combo in (
            self.filter_branch_combo,
            self.filter_tag_combo,
            self.filter_repo_status_combo,
        ):
            combo.bind("<Return>", lambda _e: self._apply_commit_filters_from_modal())

        def on_destroy(event: tk.Event) -> None:
            if event.widget is not window:
                return
            self.filter_modal = None
            self.filter_branch_combo = None
            self.filter_tag_combo = None
            self.filter_repo_status_combo = None

        window.bind("<Destroy>", on_destroy, add=True)
        window.protocol("WM_DELETE_WINDOW", self._close_filter_modal)
        self._refresh_filter_refs()
        filter_text_entry.focus_set()

    def _close_filter_modal(self) -> None:
        window = getattr(self, "filter_modal", None)
        if window is None or not window.winfo_exists():
            self.filter_modal = None
            return
        window.destroy()

    def _apply_commit_filters_from_modal(self) -> None:
        self._apply_commit_filters()
        self._close_filter_modal()

    def _set_clear_filter_button_visible(self, visible: bool) -> None:
        if not hasattr(self, "clear_filter_button"):
            return
        if visible:
            self.clear_filter_button.grid()
        else:
            self.clear_filter_button.grid_remove()

    @staticmethod
    def _parse_commit_datetime(summary: CommitSummary) -> datetime | None:
        if summary.timestamp > 0:
            return datetime.fromtimestamp(summary.timestamp, tz=timezone.utc).astimezone()
        if not summary.date:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(summary.date, fmt)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc).astimezone()
            return parsed.astimezone()
        return None

    def _format_commit_relative_date(self, summary: CommitSummary) -> str:
        commit_dt = self._parse_commit_datetime(summary)
        if commit_dt is None:
            return "--:--"
        now = datetime.now(tz=commit_dt.tzinfo)
        elapsed_seconds = max((now - commit_dt).total_seconds(), 0.0)
        if elapsed_seconds < 86400:
            return commit_dt.strftime("%H:%M")
        return commit_dt.strftime("%Y-%m-%d")

    def _format_commit_tooltip(self, summary: CommitSummary) -> str:
        commit_dt = self._parse_commit_datetime(summary)
        if commit_dt is None:
            full_date = summary.date or "(data indisponível)"
        else:
            full_date = commit_dt.strftime("%Y-%m-%d %H:%M:%S %z")
        presence = self._get_commit_presence(summary)
        presence_label = "Local (ainda não enviado)" if presence == "L" else "Local + online"
        return f"{summary.commit_hash}\n{full_date}\n{presence_label}"

    def _get_commit_presence(self, summary: CommitSummary) -> str:
        if not self.history_has_upstream:
            return "L"
        if summary.commit_hash in self.local_only_commit_hashes:
            return "L"
        return "L+O"

    def _format_commit_line(self, summary: CommitSummary) -> str:
        short_hash = summary.commit_hash[:7]
        relative_date = self._format_commit_relative_date(summary)
        presence = self._get_commit_presence(summary)
        return f"[{presence}] {short_hash} | {relative_date} | {summary.subject}"

    def _show_commit_tooltip(self, index: int, text: str, x: int, y: int) -> None:
        window = getattr(self, "commit_tooltip_window", None)
        if window is not None and window.winfo_exists() and self.commit_tooltip_index == index:
            window.geometry(f"+{x}+{y}")
            return
        self._hide_commit_tooltip()
        tip_window = tk.Toplevel(self)
        tip_window.wm_overrideredirect(True)
        try:
            tip_window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        label = ttk.Label(tip_window, text=text, justify="left", padding=(8, 4))
        label.pack(fill="both", expand=True)
        tip_window.geometry(f"+{x}+{y}")
        self.commit_tooltip_window = tip_window
        self.commit_tooltip_index = index

    def _hide_commit_tooltip(self) -> None:
        window = getattr(self, "commit_tooltip_window", None)
        self.commit_tooltip_window = None
        self.commit_tooltip_index = -1
        if window is None:
            return
        if not window.winfo_exists():
            return
        window.destroy()

    def _on_commit_list_hover(self, event: tk.Event) -> None:
        if not self.commit_summaries:
            self._hide_commit_tooltip()
            return
        index = self.commit_listbox.nearest(event.y)
        if index < 0 or index >= len(self.commit_summaries):
            self._hide_commit_tooltip()
            return
        bbox = self.commit_listbox.bbox(index)
        if not bbox:
            self._hide_commit_tooltip()
            return
        y_top = bbox[1]
        y_bottom = y_top + bbox[3]
        if event.y < y_top or event.y > y_bottom:
            self._hide_commit_tooltip()
            return
        summary = self.commit_summaries[index]
        tooltip = self._format_commit_tooltip(summary)
        self._show_commit_tooltip(index, tooltip, event.x_root + 12, event.y_root + 12)

    def _on_commit_list_leave(self, _event: tk.Event) -> None:
        self._hide_commit_tooltip()

    def _get_filters_from_ui(self) -> CommitFilters:
        if not hasattr(self, "filter_text_var"):
            return CommitFilters()
        ref = ""
        if hasattr(self, "filter_tag_var"):
            tag_value = self.filter_tag_var.get().strip()
            if tag_value and tag_value != "(todas)":
                ref = tag_value
        if not ref and hasattr(self, "filter_branch_var"):
            branch_value = self.filter_branch_var.get().strip()
            if branch_value and branch_value != "(todas)":
                ref = branch_value
        repo_status = ""
        if hasattr(self, "filter_repo_status_var"):
            status_value = self.filter_repo_status_var.get().strip()
            if status_value and status_value != "Todos":
                repo_status = status_value
        return CommitFilters(
            text=self.filter_text_var.get().strip(),
            author=self.filter_author_var.get().strip(),
            path=self.filter_path_var.get().strip(),
            since=self.filter_since_var.get().strip(),
            until=self.filter_until_var.get().strip(),
            ref=ref,
            repo_status=repo_status,
        )

    @staticmethod
    def _shorten_filter_value(value: str, limit: int = 24) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    def _update_filter_status(self) -> None:
        if not hasattr(self, "filter_status_var"):
            return
        if not self.repo_ready:
            self.filter_status_var.set("Sem repositorio selecionado.")
            self._set_clear_filter_button_visible(False)
            return
        if not self.commit_filters.is_active():
            self.filter_status_var.set("Sem filtro ativo.")
            self._set_clear_filter_button_visible(False)
            return
        self._set_clear_filter_button_visible(True)
        parts: list[str] = []
        if self.commit_filters.ref:
            parts.append(f"ref='{self._shorten_filter_value(self.commit_filters.ref)}'")
        if self.commit_filters.text:
            parts.append(f"texto='{self._shorten_filter_value(self.commit_filters.text)}'")
        if self.commit_filters.author:
            parts.append(f"autor='{self._shorten_filter_value(self.commit_filters.author)}'")
        if self.commit_filters.path:
            parts.append(f"arquivo='{self._shorten_filter_value(self.commit_filters.path)}'")
        if self.commit_filters.since:
            parts.append(f"desde='{self._shorten_filter_value(self.commit_filters.since, 16)}'")
        if self.commit_filters.until:
            parts.append(f"ate='{self._shorten_filter_value(self.commit_filters.until, 16)}'")
        if self.commit_filters.repo_status:
            current_status = "sujo" if self._is_dirty() else "limpo"
            parts.append(f"status={current_status}")
            if not self._repo_status_matches_filter(self.commit_filters.repo_status):
                parts.append("status fora do filtro")
        summary = ", ".join(parts)
        self.filter_status_var.set(f"Filtro ativo: {summary}. {len(self.commit_summaries)} commits.")

    def _repo_status_matches_filter(self, repo_status: str) -> bool:
        if not repo_status:
            return True
        is_dirty = self._is_dirty()
        if repo_status == "Somente limpo":
            return not is_dirty
        if repo_status == "Somente com alteracoes":
            return is_dirty
        return True

    def _apply_commit_filters(self) -> None:
        self.commit_filters = self._get_filters_from_ui()
        if self.repo_ready:
            self._reload_commits()
        else:
            self._update_filter_status()

    def _clear_commit_filters(self) -> None:
        if hasattr(self, "filter_text_var"):
            self.filter_text_var.set("")
            self.filter_author_var.set("")
            self.filter_path_var.set("")
            self.filter_since_var.set("")
            self.filter_until_var.set("")
            if hasattr(self, "filter_branch_var"):
                self.filter_branch_var.set("(todas)")
            if hasattr(self, "filter_tag_var"):
                self.filter_tag_var.set("(todas)")
            if hasattr(self, "filter_repo_status_var"):
                self.filter_repo_status_var.set("Todos")
        self.commit_filters = CommitFilters()
        if self.repo_ready:
            self._reload_commits()
        else:
            self._update_filter_status()

    def _load_commit_summaries(self, skip: int = 0) -> list[CommitSummary]:
        if self.commit_filters.repo_status and not self._repo_status_matches_filter(self.commit_filters.repo_status):
            return []
        return load_commit_summaries(
            self.repo_path,
            self.commit_limit,
            skip=skip,
            filters=self.commit_filters,
        )

    def _load_local_only_commit_hashes(self) -> tuple[set[str], bool]:
        if not self.repo_ready:
            return set(), False
        upstream = self._get_upstream()
        if not upstream:
            return set(), False
        hashes = core_load_local_only_commit_hashes(self.repo_path, upstream)
        return hashes, True

    def _update_reorder_local_button_visibility(self) -> None:
        if not hasattr(self, "reorder_local_button"):
            return
        visible = self.repo_ready and self.history_has_upstream and len(self.local_only_commit_hashes) >= 2
        if visible:
            self.reorder_local_button.grid()
        else:
            self.reorder_local_button.grid_remove()

    def _populate_commit_list(self) -> None:
        self._hide_commit_tooltip()
        self.commit_listbox.delete(0, tk.END)
        for summary in self.commit_summaries:
            self.commit_listbox.insert(tk.END, self._format_commit_line(summary))
        if self.commit_summaries:
            self.commit_listbox.selection_set(0)
            self._show_commit(0)
        self.commit_offset = len(self.commit_summaries)
        self.no_more_commits = len(self.commit_summaries) < self.commit_limit

    def _append_commit_summaries(self, summaries: list[CommitSummary]) -> None:
        if not summaries:
            self.no_more_commits = True
            return
        for summary in summaries:
            self.commit_listbox.insert(tk.END, self._format_commit_line(summary))
        self.commit_summaries.extend(summaries)
        self.commit_offset = len(self.commit_summaries)
        if len(summaries) < self.commit_limit:
            self.no_more_commits = True

    def _load_more_commits(self) -> None:
        if not self.repo_ready or self.loading_commits or self.loading_more or self.no_more_commits:
            return
        self.loading_more = True
        epoch = self.commit_list_epoch
        skip = self.commit_offset

        def task() -> list[CommitSummary]:
            return self._load_commit_summaries(skip=skip)

        def success(more: object) -> None:
            self.loading_more = False
            if epoch != self.commit_list_epoch:
                return
            self._append_commit_summaries(list(more))  # type: ignore[list-item]

        def error(exc: Exception) -> None:
            self.loading_more = False
            messagebox.showerror("Erro", str(exc))

        self._run_async("commit_more", "Carregar mais", task, success, error)

    def _maybe_load_more(self) -> None:
        if self.loading_more or self.no_more_commits:
            return
        first, last = self.commit_listbox.yview()
        if float(last) >= 0.98:
            self._load_more_commits()

    def _on_history_scrollbar(self, *args: str) -> None:
        self._hide_commit_tooltip()
        self.commit_listbox.yview(*args)
        self._maybe_load_more()

    def _on_history_yscroll(self, first: str, last: str) -> None:
        if hasattr(self, "commit_scrollbar"):
            self.commit_scrollbar.set(first, last)
        if float(last) >= 0.98:
            self._maybe_load_more()

    def _on_history_mousewheel(self, event: tk.Event) -> None:
        self._hide_commit_tooltip()
        self.after(0, self._maybe_load_more)

    def _on_commit_select(self, _event: tk.Event) -> None:
        self._dismiss_commit_context_menu()
        self._dismiss_history_file_context_menu()
        self._hide_commit_tooltip()
        selection = self.commit_listbox.curselection()
        if not selection:
            return
        self._show_commit(selection[-1])

    def _dismiss_commit_context_menu(self, event: tk.Event | None = None) -> None:
        if event is not None and self._is_event_inside_commit_context_menu(event):
            return
        menu = getattr(self, "commit_context_menu", None)
        self.commit_context_menu = None
        if menu is None:
            return
        try:
            menu.unpost()
        except tk.TclError:
            pass
        try:
            menu.destroy()
        except tk.TclError:
            pass

    def _is_event_inside_commit_context_menu(self, event: tk.Event) -> bool:
        menu = getattr(self, "commit_context_menu", None)
        if menu is None:
            return False
        menu_path = str(menu).strip()
        if not menu_path:
            return False
        candidate_paths: list[str] = []
        widget = getattr(event, "widget", None)
        if widget is not None:
            widget_path = str(widget).strip()
            if widget_path:
                candidate_paths.append(widget_path)
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if isinstance(x_root, int) and isinstance(y_root, int):
            try:
                contained = self.tk.call("winfo", "containing", x_root, y_root)
            except tk.TclError:
                contained = ""
            contained_path = str(contained).strip()
            if contained_path:
                candidate_paths.append(contained_path)
        for path in candidate_paths:
            if path == menu_path or path.startswith(f"{menu_path}."):
                return True
        return False

    def _show_commit_context_menu(self, event: tk.Event, commit_hash: str) -> None:
        self._dismiss_commit_context_menu()
        if not commit_hash:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Copiar hash completo",
            command=lambda selected_hash=commit_hash: self._copy_selected_commit_hash(selected_hash),
        )
        menu.add_command(
            label="Abrir commit no GitHub",
            command=lambda selected_hash=commit_hash: self._open_commit_in_github(selected_hash, self.repo_path),
        )
        menu.add_command(
            label="Copiar URL do commit no GitHub",
            command=lambda selected_hash=commit_hash: self._copy_commit_github_url(selected_hash, self.repo_path),
        )
        menu.add_command(
            label="Copiar lista de arquivos",
            command=lambda selected_hash=commit_hash: self._copy_files_list(selected_hash),
        )
        menu.add_command(
            label="Copiar patch completo",
            command=lambda selected_hash=commit_hash: self._copy_full_patch(selected_hash),
        )
        self.commit_context_menu = menu
        menu.bind("<Unmap>", self._on_commit_context_menu_unmap, add=True)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _on_commit_context_menu_unmap(self, _event: tk.Event | None = None) -> None:
        self.commit_context_menu = None

    def _commit_hash_from_listbox_y(self, y: int) -> str:
        if not hasattr(self, "commit_listbox"):
            return ""
        size = self.commit_listbox.size()
        if size <= 0:
            return ""
        index = self.commit_listbox.nearest(y)
        if index < 0 or index >= size:
            return ""
        bbox = self.commit_listbox.bbox(index)
        if bbox:
            top = bbox[1]
            bottom = bbox[1] + bbox[3]
            if y < top or y > bottom:
                return ""
        if index < 0 or index >= len(self.commit_summaries):
            return ""
        return self.commit_summaries[index].commit_hash

    def _on_commit_context_menu_request(self, event: tk.Event) -> str:
        commit_hash = self._commit_hash_from_listbox_y(int(event.y))
        if not commit_hash:
            commit_hash = self._get_selected_commit_hash() or ""
        if not commit_hash:
            return "break"
        self._show_commit_context_menu(event, commit_hash)
        return "break"

    def _move_commit_selection(self, delta: int) -> None:
        if not hasattr(self, "commit_listbox"):
            return
        size = self.commit_listbox.size()
        if size == 0:
            return
        selection = self.commit_listbox.curselection()
        if selection:
            index = selection[-1] + delta
        else:
            index = 0 if delta >= 0 else size - 1
        index = max(0, min(index, size - 1))
        self.commit_listbox.selection_clear(0, tk.END)
        self.commit_listbox.selection_set(index)
        self.commit_listbox.activate(index)
        self.commit_listbox.see(index)
        self._show_commit(index)

    def _show_commit(self, index: int) -> None:
        summary = self.commit_summaries[index]
        self.current_commit_hash = summary.commit_hash
        cached = self.commit_details_cache.get(summary.commit_hash)
        if cached is not None:
            self._render_commit_details(cached)
            return
        self._set_text(self.commit_info, "Carregando detalhes do commit...")
        self.files_listbox.delete(0, tk.END)
        self.file_stats_by_index.clear()
        self._set_text(self.patch_text, "")
        self.load_patch_button.configure(state="disabled")
        self.load_patch_button.grid_remove()
        self._request_commit_details(summary.commit_hash)

    def _format_commit_info(self, commit: CommitInfo) -> str:
        return (
            f"Hash: {commit.commit_hash}\n"
            f"Autor: {commit.author}\n"
            f"Data: {commit.date}\n"
            f"Título: {commit.subject}\n"
            f"Descrição:\n{commit.body or '(sem descrição)'}\n"
            f"Total linhas: +{commit.total_added} -{commit.total_deleted}"
        )

    def _render_commit_details(self, commit: CommitInfo) -> None:
        self._set_text(self.commit_info, self._format_commit_info(commit))
        self._populate_files_list(commit)
        self.load_patch_button.configure(state="normal")
        self.load_patch_button.grid_remove()

    def _populate_files_list(self, commit: CommitInfo) -> None:
        self.files_listbox.delete(0, tk.END)
        self.file_stats_by_index.clear()
        for idx, stat in enumerate(commit.file_stats):
            if stat.is_binary:
                label = f"{stat.path} (binário)"
            else:
                label = f"{stat.path} (+{stat.added} -{stat.deleted})"
            self.files_listbox.insert(tk.END, label)
            self.file_stats_by_index[idx] = stat
        if commit.file_stats:
            selected_index = self.selected_file_by_commit.get(commit.commit_hash, 0)
            if selected_index >= len(commit.file_stats):
                selected_index = 0
            self.files_listbox.selection_set(selected_index)
            self._show_file_patch(selected_index)
        else:
            self._set_text(self.patch_text, "(nenhum arquivo alterado)")
            self.load_patch_button.configure(state="disabled")
            self.load_patch_button.grid_remove()
            if hasattr(self, "patch_read_mode_var"):
                self.patch_read_mode_var.set("")

    def _get_patch(self, commit_hash: str, path: str | None = None, word_diff: bool | None = None) -> str:
        if word_diff is None:
            word_diff = self._word_diff_enabled()
        return core_get_commit_patch(
            self.repo_path,
            commit_hash,
            path=path,
            word_diff=word_diff,
            unified_zero=True,
        )

    def _on_file_select(self, _event: tk.Event) -> None:
        self._dismiss_history_file_context_menu()
        selection = self.files_listbox.curselection()
        if not selection:
            return
        self._show_file_patch(selection[0])

    def _dismiss_history_file_context_menu(self, event: tk.Event | None = None) -> None:
        if event is not None and self._is_event_inside_history_file_context_menu(event):
            return
        menu = getattr(self, "history_file_context_menu", None)
        self.history_file_context_menu = None
        if menu is None:
            return
        try:
            menu.unpost()
        except tk.TclError:
            pass
        try:
            menu.destroy()
        except tk.TclError:
            pass

    def _is_event_inside_history_file_context_menu(self, event: tk.Event) -> bool:
        menu = getattr(self, "history_file_context_menu", None)
        if menu is None:
            return False
        menu_path = str(menu).strip()
        if not menu_path:
            return False
        candidate_paths: list[str] = []
        widget = getattr(event, "widget", None)
        if widget is not None:
            widget_path = str(widget).strip()
            if widget_path:
                candidate_paths.append(widget_path)
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if isinstance(x_root, int) and isinstance(y_root, int):
            try:
                contained = self.tk.call("winfo", "containing", x_root, y_root)
            except tk.TclError:
                contained = ""
            contained_path = str(contained).strip()
            if contained_path:
                candidate_paths.append(contained_path)
        for path in candidate_paths:
            if path == menu_path or path.startswith(f"{menu_path}."):
                return True
        return False

    def _on_history_file_context_menu_unmap(self, _event: tk.Event | None = None) -> None:
        self.history_file_context_menu = None

    def _history_file_index_from_y(self, y: int) -> int | None:
        if not hasattr(self, "files_listbox"):
            return None
        size = self.files_listbox.size()
        if size <= 0:
            return None
        index = self.files_listbox.nearest(y)
        if index < 0 or index >= size:
            return None
        bbox = self.files_listbox.bbox(index)
        if bbox:
            top = bbox[1]
            bottom = bbox[1] + bbox[3]
            if y < top or y > bottom:
                return None
        if index not in self.file_stats_by_index:
            return None
        return index

    def _copy_history_file_patch(self, commit_hash: str, stat: FileStat) -> None:
        if stat.is_binary:
            messagebox.showinfo("Patch", "Arquivo binário: sem diff textual para copiar.")
            return
        try:
            patch = self._get_patch(commit_hash, stat.path)
        except RuntimeError as exc:
            messagebox.showerror("Patch", str(exc))
            return
        payload = patch.strip()
        if not payload:
            messagebox.showinfo("Patch", "Sem diff textual para copiar neste arquivo.")
            return
        self._copy_to_clipboard(payload)
        self._set_status(f"Patch do arquivo copiado: {stat.path}")

    def _show_history_file_context_menu(self, event: tk.Event, index: int) -> None:
        self._dismiss_history_file_context_menu()
        stat = self.file_stats_by_index.get(index)
        commit_hash = self._get_selected_commit_hash() or ""
        if stat is None or not commit_hash:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Abrir arquivo no VS Code",
            command=lambda path=stat.path: self._open_repo_file_in_vscode(path),
        )
        menu.add_command(
            label="Abrir na Pasta",
            command=lambda path=stat.path: self._open_repo_file_in_file_manager(path),
        )
        menu.add_command(
            label="Copiar caminho relativo",
            command=lambda path=stat.path: self._copy_to_clipboard(path),
        )
        menu.add_separator()
        menu.add_command(
            label="Copiar patch do arquivo",
            command=lambda selected_hash=commit_hash, selected_stat=stat: self._copy_history_file_patch(
                selected_hash, selected_stat
            ),
        )
        menu.add_command(
            label="Copiar patch completo do commit",
            command=lambda selected_hash=commit_hash: self._copy_full_patch(selected_hash),
        )
        self.history_file_context_menu = menu
        menu.bind("<Unmap>", self._on_history_file_context_menu_unmap, add=True)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _on_history_file_context_menu_request(self, event: tk.Event) -> str:
        index = self._history_file_index_from_y(int(event.y))
        if index is None:
            selection = self.files_listbox.curselection()
            if selection:
                index = selection[0]
        if index is None:
            return "break"
        self._show_history_file_context_menu(event, index)
        return "break"

    def _open_selected_file_in_vscode(self, event: tk.Event) -> None:
        if self.files_listbox.size() == 0:
            return
        index = self.files_listbox.nearest(event.y)
        if index >= self.files_listbox.size():
            return
        stat = self.file_stats_by_index.get(index)
        if not stat:
            return
        self._open_repo_file_in_vscode(stat.path)

    def _show_file_patch(self, file_index: int) -> None:
        commit = self._get_selected_commit()
        stat = self.file_stats_by_index.get(file_index)
        if not commit or not stat:
            return
        self.selected_file_by_commit[commit.commit_hash] = file_index
        if stat.is_binary:
            self._set_text(self.patch_text, "Arquivo binário: sem diff disponível.")
            self.load_patch_button.configure(state="disabled")
            self.load_patch_button.grid_remove()
            if hasattr(self, "patch_read_mode_var"):
                self.patch_read_mode_var.set("")
            return
        total_lines = stat.added + stat.deleted
        cache_key = (commit.commit_hash, stat.path)
        cached = self.patch_cache.get(cache_key)
        if cached is None:
            cached = self._get_patch(commit.commit_hash, stat.path)
            self.patch_cache[cache_key] = cached
        self._render_patch(cached)
        if total_lines >= LARGE_PATCH_THRESHOLD:
            self.load_patch_button.configure(state="normal")
            self.load_patch_button.grid()
        else:
            self.load_patch_button.configure(state="disabled")
            self.load_patch_button.grid_remove()

    def _get_selected_commit_hash(self) -> str | None:
        if self.current_commit_hash is not None:
            return self.current_commit_hash
        selection = self.commit_listbox.curselection()
        if not selection:
            return None
        return self.commit_summaries[selection[0]].commit_hash

    def _get_commit_details(self, commit_hash: str) -> CommitInfo | None:
        cached = self.commit_details_cache.get(commit_hash)
        if cached is not None:
            return cached
        self._request_commit_details(commit_hash)
        return None

    def _request_commit_details(self, commit_hash: str) -> None:
        if commit_hash in self.commit_details_cache:
            return
        if commit_hash in self.commit_details_pending:
            return
        self.commit_details_pending.add(commit_hash)
        expected = commit_hash

        def task() -> CommitInfo:
            return load_commit_details(self.repo_path, expected)

        def success(details: object) -> None:
            self.commit_details_pending.discard(expected)
            commit = details  # type: ignore[assignment]
            self.commit_details_cache[expected] = commit  # type: ignore[arg-type]
            if self.current_commit_hash == expected:
                self._render_commit_details(commit)  # type: ignore[arg-type]

        def error(exc: Exception) -> None:
            self.commit_details_pending.discard(expected)
            if self.current_commit_hash == expected:
                messagebox.showerror("Erro", str(exc))

        self._run_async(f"commit_detail:{expected}", "Detalhes commit", task, success, error)

    def _get_selected_commit(self) -> CommitInfo | None:
        commit_hash = self._get_selected_commit_hash()
        if not commit_hash:
            return None
        return self._get_commit_details(commit_hash)

    def _get_selected_commits(self) -> list[CommitSummary]:
        selection = self.commit_listbox.curselection()
        if not selection:
            return []
        indices = sorted(selection, reverse=True)
        return [self.commit_summaries[index] for index in indices]

    def _get_selected_file_stat(self) -> FileStat | None:
        selection = self.files_listbox.curselection()
        if not selection:
            return None
        return self.file_stats_by_index.get(selection[0])

    def _copy_files_list(self, commit_hash: str | None = None) -> None:
        selected_hash = (commit_hash or "").strip()
        if not selected_hash:
            selected_hash = self._get_selected_commit_hash() or ""
        commit_hash = selected_hash
        if not commit_hash:
            return
        commit = self.commit_details_cache.get(commit_hash)
        if commit is not None:
            paths = [stat.path for stat in commit.file_stats]
        else:
            try:
                paths = core_list_commit_files(self.repo_path, commit_hash)
            except RuntimeError as exc:
                messagebox.showerror("Erro", str(exc))
                return
        content = ", ".join(paths)
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()

    def _copy_full_patch(self, commit_hash: str | None = None) -> None:
        selected_hash = (commit_hash or "").strip()
        if not selected_hash:
            selected_hash = self._get_selected_commit_hash() or ""
        commit_hash = selected_hash
        if not commit_hash:
            return
        try:
            patch = self.full_patch_cache.get(commit_hash)
            if patch is None:
                patch = self._get_patch(commit_hash)
                self.full_patch_cache[commit_hash] = patch
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self.clipboard_clear()
        self.clipboard_append(patch)
        self.update()

    def _copy_selected_commit_hash(self, commit_hash: str | None = None) -> None:
        selected_hash = (commit_hash or "").strip()
        if not selected_hash:
            selected_hash = self._get_selected_commit_hash() or ""
        commit_hash = selected_hash
        if not commit_hash:
            return
        self.clipboard_clear()
        self.clipboard_append(commit_hash)
        self.update()

    def _copy_patch(self) -> None:
        content = self.patch_text.get("1.0", tk.END).strip()
        if not content:
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()

    def _open_patch_window(self) -> None:
        commit = self._get_selected_commit()
        if not commit:
            return
        stat = self._get_selected_file_stat()
        if stat and stat.is_binary:
            messagebox.showinfo("Patch", "Arquivo binário: sem diff disponível.")
            return
        try:
            if stat:
                patch = self._get_patch(commit.commit_hash, stat.path)
                title = f"Patch: {stat.path}"
                show_file_headers = False
            else:
                patch = self._get_patch(commit.commit_hash)
                title = f"Patch: {commit.commit_hash[:7]}"
                show_file_headers = True
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self._open_text_window(title, patch, render_patch=True, show_file_headers=show_file_headers)

    def _load_full_patch_for_selected_file(self) -> None:
        commit = self._get_selected_commit()
        stat = self._get_selected_file_stat()
        if not commit or not stat:
            return
        try:
            patch = self._get_patch(commit.commit_hash, stat.path)
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        cache_key = (commit.commit_hash, stat.path)
        self.patch_cache[cache_key] = patch
        self._render_patch(patch)
        self.load_patch_button.configure(state="normal")
        self.load_patch_button.grid()

    def _open_cherry_pick_window(self) -> None:
        if not self.repo_ready:
            messagebox.showinfo("Exportar", "Selecione um repositório primeiro.")
            return
        commits = self._get_selected_commits()
        if not commits:
            messagebox.showinfo("Exportar", "Selecione commits na aba Histórico.")
            return
        try:
            branches = self._get_branches()
        except RuntimeError as exc:
            messagebox.showerror("Exportar", str(exc))
            return
        if len(branches) < 2:
            messagebox.showinfo("Exportar", "É necessário ter pelo menos duas branches para exportar commits.")
            return
        current = self._get_current_branch()
        branch_options = [branch for branch in branches if branch != current]
        if not branch_options:
            messagebox.showinfo("Exportar", "Selecione uma branch de destino diferente da branch atual.")
            return

        window = tk.Toplevel(self)
        window.title("Exportar commits")
        window.geometry("700x500")

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ttk.Label(frame, text=f"Origem: {current}").grid(row=0, column=0, sticky="w")

        listbox = tk.Listbox(frame, height=10)
        listbox.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        listbox.configure(yscrollcommand=scroll.set)

        for commit in commits:
            listbox.insert(tk.END, f"{commit.commit_hash[:7]} | {commit.subject}")

        target_row = ttk.Frame(frame)
        target_row.grid(row=2, column=0, sticky="w", pady=(8, 0))

        ttk.Label(target_row, text="Destino:").grid(row=0, column=0, sticky="w")
        target_var = tk.StringVar(value=branch_options[0] if branch_options else "")
        target_combo = ttk.Combobox(target_row, textvariable=target_var, state="readonly", width=30)
        target_combo["values"] = branch_options
        target_combo.grid(row=0, column=1, sticky="w", padx=(6, 0))

        badge_var = tk.StringVar(value="")
        badge_label = tk.Label(target_row, textvariable=badge_var, padx=8, pady=2)
        badge_label.grid(row=0, column=2, sticky="w", padx=(8, 0))

        def update_badge() -> None:
            target = target_var.get().strip()
            if not target:
                badge_var.set("Destino não definido")
                badge_label.configure(fg="#b42318")
                return
            badge_var.set(f"Destino atual: {target}")
            badge_label.configure(fg="#1a7f37")

        update_badge()
        target_combo.bind("<<ComboboxSelected>>", lambda _e: update_badge())

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, sticky="w", pady=(8, 0))

        def copy_hashes() -> None:
            hashes = "\n".join(commit.commit_hash for commit in commits)
            window.clipboard_clear()
            window.clipboard_append(hashes)
            window.update()

        def run_export() -> None:
            target = target_var.get().strip()
            if not target:
                messagebox.showwarning("Exportar", "Selecione a branch de destino.")
                return
            if not self._checkout_to_branch(target):
                return
            applied: list[str] = []
            perf_trigger = "history_export:run"
            start = self._perf_start("Exportar commits", perf_trigger)
            try:
                for commit in commits:
                    try:
                        core_cherry_pick_commit(self.repo_path, commit.commit_hash)
                    except RuntimeError as exc:
                        messagebox.showerror(
                            "Exportar",
                            f"Falha ao exportar {commit.commit_hash[:7]}.\n{exc}\n"
                            "Resolva conflitos e finalize ou aborte o cherry-pick.",
                        )
                        self._show_conflicts_window(operation="cherry-pick", source_label="Exportar")
                        break
                    applied.append(commit.commit_hash)
                if applied:
                    if hasattr(self, "_bump_repo_state"):
                        self._bump_repo_state()
                    self._reload_commits(trigger="post_history_cherry_pick")
                    self._refresh_status(trigger="post_history_cherry_pick")
                    self._update_pull_push_labels()
                    self._set_status(f"Exportação aplicada em {target}.")
                window.destroy()
            finally:
                self._perf_end("Exportar commits", start, perf_trigger)

        ttk.Button(actions, text="Copiar hashes", command=copy_hashes).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Confirmar exportação", command=run_export).grid(row=0, column=1, padx=(0, 6))

    def _load_reorderable_local_commits(self) -> tuple[str, list[CommitSummary]]:
        if not self.repo_ready:
            return "", []
        upstream = self._get_upstream()
        if not upstream:
            return "", []
        commits = core_load_reorderable_local_commits(self.repo_path, upstream)
        return upstream, commits

    def _apply_local_commit_reorder(self, upstream: str, ordered_commits: list[CommitSummary]) -> bool:
        if not self.repo_ready or not upstream or not ordered_commits:
            return False
        if self._is_dirty():
            messagebox.showwarning(
                "Reordenar commits",
                "Working tree com alterações locais. Limpe a árvore antes de reordenar.",
            )
            return False
        perf_trigger = "history_reorder:apply"
        start = self._perf_start("Reordenar commits", perf_trigger)
        try:
            try:
                current_branch = self._get_current_branch()
            except RuntimeError as exc:
                messagebox.showerror("Reordenar commits", str(exc))
                return False
            try:
                result = core_apply_local_commit_reorder(
                    self.repo_path,
                    upstream,
                    ordered_commits,
                    current_branch=current_branch,
                )
            except RuntimeError as exc:
                messagebox.showerror("Reordenar commits", str(exc))
                return False

            backup_branch = result.backup_branch
            if not result.ok:
                if result.restore_error_message:
                    messagebox.showerror(
                        "Reordenar commits",
                        (
                            f"Falha ao reordenar commits:\n{result.error_message}\n\n"
                            f"Também falhou ao restaurar backup automaticamente:\n{result.restore_error_message}\n\n"
                            f"Backup disponível em: {backup_branch}"
                        ),
                    )
                    return False
                if hasattr(self, "_bump_repo_state"):
                    self._bump_repo_state()
                self._reload_commits(trigger="post_history_reorder_restore")
                self._refresh_status(trigger="post_history_reorder_restore")
                self._refresh_branches(trigger="post_history_reorder_restore")
                self._update_pull_push_labels()
                self._set_status(f"Reordenação falhou. Estado restaurado a partir de {backup_branch}.")
                messagebox.showerror(
                    "Reordenar commits",
                    f"Falha ao reordenar commits:\n{result.error_message}\n\nEstado restaurado com backup: {backup_branch}",
                )
                return False

            if hasattr(self, "_bump_repo_state"):
                self._bump_repo_state()
            self._reload_commits(trigger="post_history_reorder_apply")
            self._refresh_status(trigger="post_history_reorder_apply")
            self._refresh_branches(trigger="post_history_reorder_apply")
            self._update_pull_push_labels()
            self._set_status(f"Commits locais reordenados. Backup: {backup_branch}")
            messagebox.showinfo(
                "Reordenar commits",
                f"Reordenação concluída com sucesso.\nBackup criado em: {backup_branch}",
            )
            return True
        finally:
            self._perf_end("Reordenar commits", start, perf_trigger)

    def _open_reorder_local_commits_window(self) -> None:
        if not self.repo_ready:
            messagebox.showinfo("Reordenar commits", "Selecione um repositório primeiro.")
            return
        if self._is_dirty():
            messagebox.showwarning(
                "Reordenar commits",
                "Working tree com alterações locais. Faça commit/stash/descartes antes de reordenar.",
            )
            return
        try:
            upstream, commits = self._load_reorderable_local_commits()
            current_branch = self._get_current_branch()
        except RuntimeError as exc:
            messagebox.showerror("Reordenar commits", str(exc))
            return
        if not upstream:
            messagebox.showinfo(
                "Reordenar commits",
                "A branch atual não possui upstream configurado. Configure upstream para reordenar commits locais.",
            )
            return
        if len(commits) < 2:
            messagebox.showinfo(
                "Reordenar commits",
                "É necessário ao menos 2 commits locais [L] para reordenar.",
            )
            return

        window = tk.Toplevel(self)
        window.title("Reordenar commits locais")
        window.geometry("880x520")
        window.transient(self)

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        info = (
            f"Branch atual: {current_branch}\n"
            f"Upstream: {upstream}\n"
            "Lista em ordem de aplicação (mais antigo -> mais novo)."
        )
        ttk.Label(frame, text=info, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 6))

        commit_rows = list(commits)
        listbox = tk.Listbox(frame, selectmode="browse", exportselection=False, font="TkFixedFont")
        listbox.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        listbox.configure(yscrollcommand=scroll.set)

        def render_list(selected_index: int | None = None) -> None:
            listbox.delete(0, tk.END)
            for idx, summary in enumerate(commit_rows, start=1):
                listbox.insert(tk.END, f"{idx:>2}. {summary.commit_hash[:7]} | {summary.subject}")
            if selected_index is None:
                return
            if selected_index < 0 or selected_index >= len(commit_rows):
                return
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(selected_index)
            listbox.activate(selected_index)
            listbox.see(selected_index)

        def move_selected(delta: int) -> None:
            selection = listbox.curselection()
            if not selection:
                return
            index = selection[0]
            new_index = index + delta
            if new_index < 0 or new_index >= len(commit_rows):
                return
            commit_rows[index], commit_rows[new_index] = commit_rows[new_index], commit_rows[index]
            render_list(new_index)

        def copy_hashes() -> None:
            payload = "\n".join(summary.commit_hash for summary in commit_rows)
            window.clipboard_clear()
            window.clipboard_append(payload)
            window.update()

        def apply_reorder() -> None:
            original_order = [summary.commit_hash for summary in commits]
            new_order = [summary.commit_hash for summary in commit_rows]
            if new_order == original_order:
                messagebox.showinfo("Reordenar commits", "A ordem não foi alterada.")
                return
            confirm = messagebox.askyesno(
                "Reordenar commits",
                (
                    "Isto vai reescrever o histórico local [L] da branch atual.\n"
                    "Pode exigir push com --force-with-lease.\n\n"
                    "Deseja continuar?"
                ),
            )
            if not confirm:
                return
            if self._apply_local_commit_reorder(upstream, commit_rows):
                window.destroy()

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(actions, text="Subir", command=lambda: move_selected(-1)).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Descer", command=lambda: move_selected(1)).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(actions, text="Copiar hashes", command=copy_hashes).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(actions, text="Aplicar ordem", command=apply_reorder).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(actions, text="Fechar", command=window.destroy).grid(row=0, column=4)

        render_list(0)

    def _open_import_commits_window(self) -> None:
        self._open_import_tab()
        return
        if not self.repo_ready:
            messagebox.showinfo("Importar", "Selecione um repositório primeiro.")
            return
        current = self._get_current_branch()
        if not self.branch_list:
            self._refresh_branches()

        window = tk.Toplevel(self)
        window.title("Importar commits")
        window.geometry("750x550")

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        ttk.Label(frame, text="Repositório de origem:").grid(row=0, column=0, sticky="w")
        source_var = tk.StringVar()
        source_entry = ttk.Entry(frame, textvariable=source_var)
        source_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        def browse_repo() -> None:
            path = filedialog.askdirectory()
            if path:
                source_var.set(path)

        ttk.Button(frame, text="Procurar", command=browse_repo).grid(row=0, column=2, padx=(6, 0))

        ttk.Label(frame, text="Commits (um hash por linha):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        hashes_text = tk.Text(frame, height=8)
        hashes_text.grid(row=2, column=0, columnspan=3, sticky="nsew")

        target_row = ttk.Frame(frame)
        target_row.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(target_row, text=f"Destino (branch atual): {current}").grid(row=0, column=0, sticky="w")

        actions = ttk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

        def parse_hashes() -> list[str]:
            raw = hashes_text.get("1.0", tk.END)
            tokens = [token.strip() for token in raw.replace(",", " ").split()]
            return [token for token in tokens if token]

        def run_import() -> None:
            source_path = source_var.get().strip()
            if not source_path:
                messagebox.showwarning("Importar", "Selecione o repositório de origem.")
                return
            hashes = parse_hashes()
            if not hashes:
                messagebox.showwarning("Importar", "Informe ao menos um hash.")
                return
            if not self._is_git_repo(source_path):
                messagebox.showerror("Importar", "Repositório de origem inválido.")
                return
            target = self._get_current_branch()
            if not target:
                messagebox.showwarning("Importar", "Branch atual não encontrada.")
                return

            applied: list[str] = []
            for commit_hash in hashes:
                try:
                    core_fetch_commit_from_source(self.repo_path, source_path, commit_hash)
                except RuntimeError as exc:
                    messagebox.showerror("Importar", f"Falha ao buscar {commit_hash[:7]}.\n{exc}")
                    break
                try:
                    core_cherry_pick_commit(self.repo_path, commit_hash)
                except RuntimeError as exc:
                    messagebox.showerror(
                        "Importar",
                        f"Falha ao aplicar {commit_hash[:7]}.\n{exc}\n"
                        "Resolva conflitos e finalize ou aborte o cherry-pick.",
                    )
                    self._show_conflicts_window(operation="cherry-pick", source_label="Importar")
                    break
                applied.append(commit_hash)

            if applied:
                self._reload_commits()
                self._refresh_status()
                self._update_pull_push_labels()
                self._set_status(f"Importado em {target}: {len(applied)} commit(s).")
            window.destroy()

        def open_hashes() -> None:
            hashes = "\n".join(parse_hashes())
            self._open_text_window("Hashes informados", hashes, render_patch=False)

        ttk.Button(actions, text="Ver hashes", command=open_hashes).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Importar", command=run_import).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(actions, text="Fechar", command=window.destroy).grid(row=0, column=2)

    def _is_git_repo(self, path: str) -> bool:
        return is_git_repo(path)

    def _is_conflicts_tab_visible(self) -> bool:
        if not hasattr(self, "tabs") or not hasattr(self, "conflicts_tab"):
            return False
        try:
            tab_ids = tuple(str(tab_id) for tab_id in self.tabs.tabs())
        except tk.TclError:
            return False
        return str(self.conflicts_tab) in tab_ids

    def _ensure_conflicts_tab_visible(self, select: bool = True) -> None:
        if not hasattr(self, "tabs") or not hasattr(self, "conflicts_tab"):
            return
        if not self._is_conflicts_tab_visible():
            self.tabs.add(self.conflicts_tab, text="Conflitos")
        if select:
            self.tabs.select(self.conflicts_tab)
            if hasattr(self, "_on_notebook_tab_changed"):
                self._on_notebook_tab_changed()

    def _hide_conflicts_tab(self, select_history: bool = True) -> None:
        if self.conflicts_refresh_job is not None:
            try:
                self.after_cancel(self.conflicts_refresh_job)
            except tk.TclError:
                pass
            self.conflicts_refresh_job = None
        was_selected = False
        if self._is_conflicts_tab_visible():
            try:
                was_selected = str(self.tabs.select()) == str(self.conflicts_tab)
            except tk.TclError:
                was_selected = False
            try:
                self.tabs.forget(self.conflicts_tab)
            except tk.TclError:
                pass
        self.conflict_operation_key = ""
        self.conflict_source_label = ""
        self.conflict_continue_message = ""
        if hasattr(self, "conflict_files_listbox"):
            self.conflict_files_listbox.delete(0, tk.END)
        if hasattr(self, "conflict_header_var"):
            self.conflict_header_var.set("Conflitos")
        if hasattr(self, "conflict_count_var"):
            self.conflict_count_var.set("Conflitos: 0")
        if hasattr(self, "conflict_status_var"):
            self.conflict_status_var.set("Sem conflitos ativos.")
        if hasattr(self, "conflicts_open_vscode_button"):
            self.conflicts_open_vscode_button.configure(state="disabled")
        if hasattr(self, "conflicts_abort_button"):
            self.conflicts_abort_button.configure(state="disabled")
        if hasattr(self, "conflicts_continue_button"):
            self.conflicts_continue_button.configure(state="disabled")
        if was_selected and select_history and hasattr(self, "_open_history_tab"):
            self._open_history_tab()

    def _schedule_conflicts_refresh(self, delay_ms: int = 1400) -> None:
        if self.conflicts_refresh_job is not None:
            try:
                self.after_cancel(self.conflicts_refresh_job)
            except tk.TclError:
                pass
            self.conflicts_refresh_job = None
        if not self._is_conflicts_tab_visible():
            return
        self.conflicts_refresh_job = self.after(delay_ms, self._on_conflicts_refresh_timer)

    def _on_conflicts_refresh_timer(self) -> None:
        self.conflicts_refresh_job = None
        if not self._is_conflicts_tab_visible():
            return
        self._refresh_conflicts_tab(select_tab=False)

    def _refresh_conflicts_tab_manual(self) -> None:
        self._refresh_conflicts_tab(select_tab=False)

    def _load_unmerged_conflict_files(self) -> list[str]:
        return core_load_unmerged_conflict_files(self.repo_path)

    def _git_ref_exists(self, ref_name: str) -> bool:
        return core_git_ref_exists(self.repo_path, ref_name)

    def _is_rebase_in_progress(self) -> bool:
        return core_is_rebase_in_progress(self.repo_path)

    def _is_conflict_operation_in_progress(self, operation: str) -> bool:
        key = operation.strip().lower()
        if not self.repo_ready or not key:
            return False
        return core_is_conflict_operation_in_progress(self.repo_path, key)

    def _resolve_active_conflict_operation(self) -> str:
        preferred = self.conflict_operation_key.strip().lower()
        return core_resolve_active_conflict_operation(self.repo_path, preferred=preferred)

    @staticmethod
    def _conflict_operation_display_label(operation: str) -> str:
        labels = {
            "cherry-pick": "Cherry-pick",
            "rebase": "Rebase",
            "merge": "Merge",
            "squash_merge": "Squash merge",
        }
        return labels.get(operation.strip().lower(), "Operação")

    def _update_conflict_header(self, operation: str) -> None:
        label = self._conflict_operation_display_label(operation)
        source = self.conflict_source_label.strip()
        if source:
            self.conflict_header_var.set(f"Conflitos - {label} ({source})")
        else:
            self.conflict_header_var.set(f"Conflitos - {label}")

    def _render_conflict_files(self, files: list[str]) -> None:
        self.conflict_files_listbox.delete(0, tk.END)
        for path in files:
            self.conflict_files_listbox.insert(tk.END, path)
        self._on_conflict_file_select(None)

    def _refresh_conflicts_tab(self, select_tab: bool = False) -> None:
        if not self.repo_ready:
            self._hide_conflicts_tab(select_history=False)
            return
        try:
            files = self._load_unmerged_conflict_files()
        except RuntimeError as exc:
            self.conflict_status_var.set("Falha ao atualizar conflitos.")
            messagebox.showerror("Conflitos", str(exc))
            return
        operation = self._resolve_active_conflict_operation()
        if operation:
            self.conflict_operation_key = operation
        elif not self.conflict_operation_key:
            self.conflict_operation_key = "cherry-pick"
        in_progress = bool(operation)
        self._ensure_conflicts_tab_visible(select=select_tab)
        self._update_conflict_header(self.conflict_operation_key)
        self.conflict_count_var.set(f"Conflitos: {len(files)}")
        self._render_conflict_files(files)
        if files:
            self.conflict_status_var.set(
                f"{len(files)} arquivo(s) em conflito. Resolva e use duplo clique para abrir no VS Code."
            )
        elif in_progress:
            self.conflict_status_var.set("Sem conflitos pendentes. Clique em Continuar para finalizar a operação.")
        else:
            self.conflict_status_var.set("Sem conflitos ativos.")
            self._hide_conflicts_tab(select_history=True)
            return
        self.conflicts_abort_button.configure(state="normal" if in_progress else "disabled")
        self.conflicts_continue_button.configure(state="normal" if in_progress and not files else "disabled")
        self._schedule_conflicts_refresh()

    def _show_conflicts_window(
        self,
        operation: str = "cherry-pick",
        source_label: str = "",
        continue_message: str = "",
    ) -> None:
        if not self.repo_ready:
            return
        normalized_operation = operation.strip().lower() or "cherry-pick"
        if normalized_operation not in {"cherry-pick", "rebase", "merge", "squash_merge"}:
            normalized_operation = "cherry-pick"
        self.conflict_operation_key = normalized_operation
        self.conflict_source_label = source_label.strip()
        self.conflict_continue_message = continue_message.strip()
        self._refresh_conflicts_tab(select_tab=True)

    def _on_conflict_file_select(self, _event: tk.Event | None) -> None:
        if not hasattr(self, "conflicts_open_vscode_button"):
            return
        selected = bool(self._selected_conflict_files())
        self.conflicts_open_vscode_button.configure(state="normal" if selected else "disabled")

    def _selected_conflict_files(self) -> list[str]:
        if not hasattr(self, "conflict_files_listbox"):
            return []
        selected_files: list[str] = []
        for index in self.conflict_files_listbox.curselection():
            selected_files.append(str(self.conflict_files_listbox.get(index)))
        return selected_files

    def _on_conflict_file_double_click(self, event: tk.Event) -> None:
        if not hasattr(self, "conflict_files_listbox"):
            return
        size = self.conflict_files_listbox.size()
        if size <= 0:
            return
        index = self.conflict_files_listbox.nearest(event.y)
        if index < 0 or index >= size:
            return
        path = str(self.conflict_files_listbox.get(index)).strip()
        if not path:
            return
        self._open_repo_file_in_vscode(path)

    def _open_selected_conflict_files_in_vscode(self) -> None:
        paths = self._selected_conflict_files()
        if not paths:
            messagebox.showinfo("Conflitos", "Selecione arquivos para abrir.")
            return
        for path in paths:
            if not self._open_repo_file_in_vscode(path):
                return

    def _sync_after_conflict_operation(self, trigger: str) -> None:
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._reload_commits(trigger=trigger)
        self._refresh_status(trigger=trigger)
        self._refresh_branches(trigger=trigger)
        self._update_pull_push_labels()
        if hasattr(self, "_refresh_branch_comparison"):
            self._refresh_branch_comparison()
        if hasattr(self, "_update_import_controls_state"):
            self._update_import_controls_state()

    def _continue_conflict_operation(self) -> None:
        operation = self._resolve_active_conflict_operation()
        if not operation:
            self._refresh_conflicts_tab(select_tab=False)
            return
        perf_trigger = f"conflicts:{operation}:continue"
        start = self._perf_start("Continuar conflitos", perf_trigger)
        try:
            message = ""
            if operation == "squash_merge":
                message = self.conflict_continue_message.strip()
                if not message and hasattr(self, "branch_message_var"):
                    message = self.branch_message_var.get().strip()
                if not message:
                    messagebox.showwarning("Conflitos", "Informe a mensagem do commit de squash.")
                    return
            try:
                core_continue_conflict_operation(self.repo_path, operation, squash_message=message)
            except RuntimeError as exc:
                messagebox.showerror("Conflitos", str(exc))
                self._refresh_conflicts_tab(select_tab=False)
                return
            self._set_status(f"{self._conflict_operation_display_label(operation)} continuado.")
            self._sync_after_conflict_operation(trigger=f"post_conflicts_continue_{operation}")
            self._refresh_conflicts_tab(select_tab=False)
        finally:
            self._perf_end("Continuar conflitos", start, perf_trigger)

    def _abort_conflict_operation(self) -> None:
        operation = self._resolve_active_conflict_operation()
        if not operation:
            self._refresh_conflicts_tab(select_tab=False)
            return
        confirm = messagebox.askyesno(
            "Conflitos",
            f"Abortar {self._conflict_operation_display_label(operation)} em andamento?",
        )
        if not confirm:
            return
        perf_trigger = f"conflicts:{operation}:abort"
        start = self._perf_start("Abortar conflitos", perf_trigger)
        try:
            try:
                core_abort_conflict_operation(self.repo_path, operation)
            except RuntimeError as exc:
                messagebox.showerror("Conflitos", str(exc))
                self._refresh_conflicts_tab(select_tab=False)
                return
            self._set_status(f"{self._conflict_operation_display_label(operation)} abortado.")
            self._sync_after_conflict_operation(trigger=f"post_conflicts_abort_{operation}")
            self._refresh_conflicts_tab(select_tab=False)
        finally:
            self._perf_end("Abortar conflitos", start, perf_trigger)

    def _get_tags(self) -> list[str]:
        return core_list_tags(self.repo_path)

    def _refresh_filter_refs(self) -> None:
        if not self.repo_ready:
            self.filter_branch_values = ["(todas)"]
            self.filter_tag_values = ["(todas)"]
            self.filter_branch_var.set("(todas)")
            self.filter_tag_var.set("(todas)")
            self.filter_repo_status_var.set("Todos")
            if self.filter_branch_combo is not None:
                self.filter_branch_combo.configure(values=self.filter_branch_values, state="disabled")
            if self.filter_tag_combo is not None:
                self.filter_tag_combo.configure(values=self.filter_tag_values, state="disabled")
            if self.filter_repo_status_combo is not None:
                self.filter_repo_status_combo.configure(state="disabled")
            return

        branch_values = ["(todas)"] + self.branch_list
        self.filter_branch_values = branch_values
        if self.filter_branch_var.get() not in self.filter_branch_values:
            self.filter_branch_var.set("(todas)")

        self.tag_list = self._get_tags()
        tag_values = ["(todas)"] + self.tag_list
        self.filter_tag_values = tag_values
        if self.filter_tag_var.get() not in self.filter_tag_values:
            self.filter_tag_var.set("(todas)")

        if self.filter_branch_combo is not None:
            self.filter_branch_combo.configure(values=self.filter_branch_values, state="readonly")
        if self.filter_tag_combo is not None:
            self.filter_tag_combo.configure(values=self.filter_tag_values, state="readonly")
        if self.filter_repo_status_combo is not None:
            self.filter_repo_status_combo.configure(state="readonly")

    def _reload_commits(self, trigger: str = "") -> None:
        if not self.repo_ready:
            return
        normalized_trigger = self._normalize_perf_trigger(trigger) or "internal"
        perf_trigger = f"commit_list:{normalized_trigger}"
        self.commit_list_epoch += 1
        epoch = self.commit_list_epoch
        self.loading_commits = True
        self.loading_more = False
        self.no_more_commits = False
        self._hide_commit_tooltip()
        self.commit_listbox.delete(0, tk.END)
        self.commit_listbox.insert(tk.END, "(carregando commits...)")

        def task() -> tuple[list[CommitSummary], set[str], bool]:
            summaries = self._load_commit_summaries()
            local_only_hashes, has_upstream = self._load_local_only_commit_hashes()
            return summaries, local_only_hashes, has_upstream

        def success(result: object) -> None:
            self.loading_commits = False
            if epoch != self.commit_list_epoch:
                return
            summaries, local_only_hashes, has_upstream = result  # type: ignore[misc]
            self.commit_summaries = list(summaries)
            self.local_only_commit_hashes = set(local_only_hashes)
            self.history_has_upstream = bool(has_upstream)
            self._update_reorder_local_button_visibility()
            self.commit_details_cache.clear()
            self.current_commit_hash = None
            self._populate_commit_list()
            self._update_filter_status()

        def error(exc: Exception) -> None:
            self.loading_commits = False
            self.local_only_commit_hashes = set()
            self.history_has_upstream = False
            self._update_reorder_local_button_visibility()
            messagebox.showerror("Erro", str(exc))
            self._update_filter_status()

        self._run_async("commit_list", "Recarregar commits", task, success, error, perf_trigger=perf_trigger)

    def _refresh_history_patch_view(self) -> None:
        selection = self.files_listbox.curselection()
        if selection:
            self._show_file_patch(selection[0])

    def _open_text_window(
        self,
        title: str,
        content: str,
        render_patch: bool,
        show_file_headers: bool = False,
    ) -> None:
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry("900x600")

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        text_widget = tk.Text(frame, wrap="none")
        text_widget.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text_widget.configure(yscrollcommand=scroll.set)
        text_widget.configure(font="TkFixedFont")

        palette = getattr(self, "theme_palette", None)
        if palette and hasattr(self, "_apply_text_widget_theme"):
            self._apply_text_widget_theme(text_widget, palette)
            self._apply_diff_tags(text_widget, palette)


        if render_patch:
            render_patch_to_widget(
                text_widget,
                content,
                read_only=False,
                show_file_headers=show_file_headers,
                word_diff=self._word_diff_enabled(),
            )
        else:
            text_widget.insert(tk.END, content)
            text_widget.configure(state="normal")

        actions = ttk.Frame(window)
        actions.pack(fill="x", padx=8, pady=(0, 8))

        def copy_all() -> None:
            window.clipboard_clear()
            window.clipboard_append(text_widget.get("1.0", tk.END))
            window.update()

        ttk.Button(actions, text="Copiar tudo", command=copy_all).pack(side="right")

    def _render_patch(self, patch: str) -> None:
        display_patch, truncated, shown, total = self._apply_read_mode_to_diff(patch)
        render_patch_to_widget(
            self.patch_text,
            display_patch,
            read_only=True,
            show_file_headers=False,
            word_diff=self._word_diff_enabled(),
        )
        if hasattr(self, "patch_read_mode_var"):
            if truncated:
                self.patch_read_mode_var.set(f"Modo leitura: {shown}/{total} linhas")
            else:
                self.patch_read_mode_var.set("")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualiza commits do Git em uma interface Tkinter.")
    parser.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Caminho do repositório Git (default: diretório atual)",
    )
    parser.add_argument("--limit", type=int, default=100, help="Quantidade de commits (default: 100)")
    parser.add_argument(
        "--patch-limit",
        type=int,
        default=0,
        help="(ignorado) mantido por compatibilidade",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_path = os.path.abspath(args.repo)
    commits: list[CommitSummary] = []
    if os.path.isdir(repo_path) and is_git_repo(repo_path):
        try:
            commits = load_commit_summaries(repo_path, args.limit)
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            repo_path = ""
    else:
        repo_path = ""
    app = CommitsViewer(repo_path, commits, args.patch_limit, args.limit)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
