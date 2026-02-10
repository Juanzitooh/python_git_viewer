#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import os
import subprocess
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from ..core.diff_utils import build_line_map, build_patch_for_hunk, build_patch_for_line, parse_diff_data
from ..core.git_client import run_git
from ..core.models import DiffData, DiffHunk, DiffLineInfo
from .diff_render import render_patch_to_widget


class CommitTabMixin:
    def _build_branch_tab(self) -> None:
        self.branch_tab.grid_columnconfigure(0, weight=1)
        self.branch_tab.grid_rowconfigure(0, weight=1)

        paned = ttk.PanedWindow(self.branch_tab, orient="horizontal")
        paned.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))

        left_column = ttk.Frame(paned)
        left_column.grid_columnconfigure(0, weight=1)
        left_column.grid_rowconfigure(0, weight=3)
        left_column.grid_rowconfigure(1, weight=1)

        status_frame = ttk.Frame(left_column)
        status_frame.grid(row=0, column=0, sticky="nsew")
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=0)
        status_frame.grid_rowconfigure(2, weight=1)

        header_row = ttk.Frame(status_frame)
        header_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        header_row.grid_columnconfigure(0, weight=1)
        header_row.grid_columnconfigure(1, weight=0)
        ttk.Label(header_row, text="Arquivos em aberto:").grid(row=0, column=0, sticky="w")
        self.stage_count_var = tk.StringVar(value="Selecionados: 0/0")
        ttk.Label(header_row, textvariable=self.stage_count_var).grid(row=0, column=1, sticky="e", padx=(8, 0))

        controls_row = ttk.Frame(status_frame)
        controls_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Button(
            controls_row,
            text="Atualizar status",
            command=lambda: self._refresh_status(trigger="manual_button"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )

        self.status_listbox = tk.Listbox(
            status_frame,
            selectmode="browse",
            exportselection=False,
            font="TkFixedFont",
        )
        self.status_listbox.grid(row=2, column=0, sticky="nsew")

        status_scroll = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_listbox.yview)
        status_scroll.grid(row=2, column=1, sticky="ns")
        self.status_listbox.configure(yscrollcommand=status_scroll.set)
        self.status_listbox.bind("<<ListboxSelect>>", self._on_status_select)
        self.status_listbox.bind("<ButtonRelease-1>", self._on_status_list_single_click, add=True)
        self.status_listbox.bind("<Double-Button-1>", self._on_status_list_double_click, add=True)

        commit_frame = ttk.Frame(left_column)
        commit_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        commit_frame.grid_columnconfigure(0, weight=1)
        commit_frame.grid_rowconfigure(3, weight=1)

        ttk.Label(commit_frame, text="Título do commit:").grid(row=0, column=0, sticky="w")
        self.commit_title_var = tk.StringVar()
        self.commit_title_entry = ttk.Entry(commit_frame, textvariable=self.commit_title_var)
        self.commit_title_entry.grid(row=1, column=0, sticky="ew")

        ttk.Label(commit_frame, text="Descrição do commit:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.commit_body_text = tk.Text(commit_frame, height=6, wrap="word")
        self.commit_body_text.grid(row=3, column=0, sticky="nsew")

        commit_buttons = ttk.Frame(commit_frame)
        commit_buttons.grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Button(commit_buttons, text="Commit", command=self._commit_changes).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(commit_buttons, text="Commit + Push", command=self._commit_and_push).grid(row=0, column=1)
        ttk.Button(commit_buttons, text="Stash", command=self._open_stash_window).grid(row=0, column=2, padx=(6, 0))
        self.undo_commit_button = ttk.Button(commit_buttons, text="Undo commit", command=self._open_undo_commit_window)
        self.undo_commit_button.grid(
            row=0,
            column=3,
            padx=(6, 0),
        )
        self.undo_commit_button.bind("<Enter>", self._on_undo_commit_button_hover, add=True)
        self.undo_commit_button.bind("<Leave>", self._hide_hover_tooltip, add=True)
        self.open_pr_button = ttk.Button(commit_buttons, text="Abrir PR", command=self._open_commit_pr_in_github)
        self.open_pr_button.grid(row=0, column=4, padx=(6, 0))
        self.open_pr_button.grid_remove()

        diff_frame = ttk.Frame(paned)
        diff_frame.grid_columnconfigure(0, weight=1)
        diff_frame.grid_rowconfigure(1, weight=1)

        diff_header = ttk.Frame(diff_frame)
        diff_header.grid(row=0, column=0, sticky="ew")
        diff_header.grid_columnconfigure(0, weight=1)
        ttk.Label(diff_header, text="Diff do arquivo selecionado:").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            diff_header,
            text="Diff por palavra",
            variable=self.word_diff_var,
            command=self._toggle_word_diff,
        ).grid(row=0, column=1, padx=(8, 0))
        self.worktree_diff_text = tk.Text(diff_frame, wrap="none")
        self.worktree_diff_text.grid(row=1, column=0, sticky="nsew")
        diff_scroll = ttk.Scrollbar(diff_frame, orient="vertical", command=self.worktree_diff_text.yview)
        diff_scroll.grid(row=1, column=1, sticky="ns")
        self.worktree_diff_text.configure(yscrollcommand=diff_scroll.set)
        self.worktree_diff_text.tag_configure("added", foreground="#1a7f37")
        self.worktree_diff_text.tag_configure("removed", foreground="#d1242f")
        self.worktree_diff_text.tag_configure("meta", foreground="#57606a")
        self.worktree_diff_text.tag_configure("added_word", foreground="#1a7f37", background="#dafbe1")
        self.worktree_diff_text.tag_configure("removed_word", foreground="#d1242f", background="#ffebe9")
        self.worktree_diff_text.tag_configure("selected_hunk", background="#e8f0ff")
        self.worktree_diff_text.tag_configure("selected_line", background="#cfe0ff")
        self.worktree_diff_text.configure(font="TkFixedFont")
        self.worktree_diff_text.configure(state="disabled")
        self.worktree_diff_text.bind("<ButtonRelease-1>", self._on_worktree_diff_single_click, add=True)
        self.worktree_diff_text.bind("<Double-Button-1>", self._on_worktree_diff_double_click, add=True)

        self.diff_interaction_hint_var = tk.StringVar(value="")
        self.diff_interaction_hint_label = ttk.Label(diff_frame, textvariable=self.diff_interaction_hint_var)
        self.diff_interaction_hint_label.grid(row=2, column=0, sticky="w", pady=(6, 0))

        paned.add(left_column, weight=1)
        paned.add(diff_frame, weight=2)

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self.branch_tab, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, sticky="w", padx=8, pady=(6, 8))

        self.status_items: dict[str, dict[str, str | bool]] = {}
        self.status_header_actions: dict[int, tuple[str, str]] = {}
        self.status_toggle_columns: dict[int, tuple[int, int]] = {}
        self.worktree_hunk_marker_map: dict[int, tuple[str, int]] = {}
        self.worktree_hunk_patch_map: dict[int, str] = {}
        self.worktree_line_scope_map: dict[int, str] = {}
        self.worktree_line_patch_map: dict[int, str] = {}
        self.worktree_diff_data_by_scope: dict[str, DiffData] = {}
        self.preserve_worktree_diff_on_status_refresh = False
        self.worktree_toggle_busy = False
        self.status_refresh_pending_trigger = ""
        self.status_refresh_debounce_job: str | None = None
        self.status_refresh_debounce_trigger = ""
        self.status_auto_stage_disabled = False
        self.status_focus_path = ""
        self.status_click_job: str | None = None
        self.status_click_path = ""
        self.diff_click_job: str | None = None
        self.diff_click_line_no = 0
        self._refresh_branches()
        self._refresh_status(trigger="commit_tab_init")

    def _refresh_status(self, trigger: str = "") -> None:
        if not self.repo_ready:
            return
        normalized_trigger = self._normalize_perf_trigger(trigger) or "internal"
        if self.status_loading:
            self.status_refresh_pending_trigger = normalized_trigger
            return
        self.status_loading = True
        perf_trigger = f"status:{normalized_trigger}"

        def task() -> tuple[list[dict[str, str | bool]], str]:
            entries = self._get_status_entries()
            try:
                head_hash = run_git(self.repo_path, ["rev-parse", "HEAD"]).strip()
            except RuntimeError:
                head_hash = ""
            return entries, head_hash

        def success(entries: object) -> None:
            self.status_loading = False
            preserve_flag = bool(getattr(self, "preserve_worktree_diff_on_status_refresh", False))
            status_entries, head_hash = entries  # type: ignore[misc]
            normalized_entries = self._maybe_stage_entries_by_default(list(status_entries))
            self._render_status_entries(normalized_entries)
            self._handle_status_head_update(str(head_hash))
            pending = self.status_refresh_pending_trigger.strip()
            self.status_refresh_pending_trigger = ""
            if pending:
                if preserve_flag:
                    self.preserve_worktree_diff_on_status_refresh = True
                self._refresh_status(trigger=pending)

        def error(exc: Exception) -> None:
            self.status_loading = False
            pending = self.status_refresh_pending_trigger.strip()
            self.status_refresh_pending_trigger = ""
            if pending:
                self._refresh_status(trigger=pending)
            messagebox.showerror("Erro", str(exc))

        self._run_async("status", "Atualizar status", task, success, error, perf_trigger=perf_trigger)

    def _render_status_entries(self, entries: list[dict[str, str | bool]]) -> None:
        self.status_listbox.delete(0, tk.END)
        self.status_items.clear()
        self.status_headers = set()
        self.status_header_actions = {}
        self.status_toggle_columns: dict[int, tuple[int, int]] = {}
        signature = "|".join(
            f"{entry.get('status')}:{entry.get('path_for_git')}:{'1' if entry.get('staged') else '0'}"
            for entry in entries
        )
        if hasattr(self, "status_signature"):
            if signature != self.status_signature:
                self.status_signature = signature
                if hasattr(self, "_bump_repo_state"):
                    self._bump_repo_state()

        grouped: dict[str, list[dict[str, str | bool]]] = {}
        for entry in entries:
            path_for_group = str(entry["path_for_git"])
            folder = os.path.dirname(path_for_group) if path_for_group else ""
            grouped.setdefault(folder, []).append(entry)

        sorted_folders = sorted(grouped.keys())

        total = len(entries)
        staged_count = 0
        for entry in entries:
            if self._entry_has_staged_part(entry):
                staged_count += 1

        all_index = self.status_listbox.size()
        all_marker = self._entries_stage_marker(entries)
        self.status_listbox.insert(tk.END, f"{all_marker} (todos)")
        self.status_headers.add(all_index)
        self.status_header_actions[all_index] = ("all", "")

        for folder in sorted_folders:
            folder_entries = grouped[folder]
            folder_marker = self._entries_stage_marker(folder_entries)
            folder_text = f"{folder}/" if folder else "(root)"
            header_text = f"{folder_marker} {folder_text}"
            header_index = self.status_listbox.size()
            self.status_listbox.insert(tk.END, header_text)
            self.status_headers.add(header_index)
            self.status_header_actions[header_index] = ("folder", folder)

            folder_entries.sort(key=lambda item: str(item["path_for_git"]))
            visible_chars = self._status_list_visible_char_capacity()
            for entry in folder_entries:
                staged_label = self._entry_stage_marker(entry)
                display_path = str(entry["path"])
                leaf = display_path.split("/")[-1]
                if " -> " in display_path:
                    leaf = display_path
                line_prefix = f"{staged_label} {entry['status']:>2} "
                max_leaf_chars = max(8, visible_chars - len(line_prefix))
                if len(leaf) > max_leaf_chars:
                    leaf = leaf[: max(3, max_leaf_chars - 3)] + "..."
                line = f"{line_prefix}{leaf}"
                item_index = self.status_listbox.size()
                self.status_listbox.insert(tk.END, line)
                self.status_items[item_index] = entry
                self.status_toggle_columns[item_index] = (0, len(staged_label))
        if hasattr(self, "stage_count_var"):
            self.stage_count_var.set(f"Selecionados: {staged_count}/{total}")
        self._update_open_pr_button_visibility(total)
        if total == 0:
            self.status_auto_stage_disabled = False
        selected_index: int | None = None
        preferred_path = self.status_focus_path.strip() if hasattr(self, "status_focus_path") else ""
        if preferred_path:
            selected_index = self._find_status_index_by_path(preferred_path)
        if selected_index is None and self.status_items:
            selected_index = min(self.status_items.keys())
        if selected_index is not None:
            self._select_status_index(selected_index)
        else:
            self.status_listbox.selection_clear(0, tk.END)
        preserve_diff = bool(getattr(self, "preserve_worktree_diff_on_status_refresh", False))
        self.preserve_worktree_diff_on_status_refresh = False
        if preserve_diff:
            self._update_worktree_diff_actions()
        else:
            self._update_worktree_diff_from_selection()
        self._update_operation_preview()
        if hasattr(self, "_refresh_repo_status_panel"):
            self._refresh_repo_status_panel()

    @staticmethod
    def _stage_marker(staged_count: int, total_count: int) -> str:
        if total_count <= 0 or staged_count <= 0:
            return "[ ]"
        if staged_count >= total_count:
            return "[x]"
        return "[~]"

    @staticmethod
    def _entry_has_staged_part(entry: dict[str, str | bool]) -> bool:
        return bool(entry.get("staged", False))

    @staticmethod
    def _entry_has_unstaged_part(entry: dict[str, str | bool]) -> bool:
        return bool(entry.get("unstaged", False))

    def _entry_is_fully_staged(self, entry: dict[str, str | bool]) -> bool:
        return self._entry_has_staged_part(entry) and not self._entry_has_unstaged_part(entry)

    def _entry_stage_marker(self, entry: dict[str, str | bool]) -> str:
        staged = self._entry_has_staged_part(entry)
        unstaged = self._entry_has_unstaged_part(entry)
        if staged and unstaged:
            return "[~]"
        if staged:
            return "[x]"
        return "[ ]"

    def _entries_stage_marker(self, entries: list[dict[str, str | bool]]) -> str:
        if not entries:
            return "[ ]"
        all_fully_staged = all(self._entry_is_fully_staged(entry) for entry in entries)
        if all_fully_staged:
            return "[x]"
        has_any_staged = any(self._entry_has_staged_part(entry) for entry in entries)
        if not has_any_staged:
            return "[ ]"
        return "[~]"

    def _handle_status_head_update(self, head_hash: str) -> None:
        current_head = head_hash.strip()
        previous_head = str(getattr(self, "status_head_hash", "")).strip()
        if current_head == previous_head:
            return
        self.status_head_hash = current_head
        if not previous_head:
            # Primeira leitura de HEAD para o repo atual: evita recarga redundante.
            return
        if hasattr(self, "_reload_commits"):
            self._reload_commits()
        if hasattr(self, "_refresh_branches"):
            self._refresh_branches()
        if hasattr(self, "_update_pull_push_labels"):
            self._update_pull_push_labels()

    def _update_open_pr_button_visibility(self, total_entries: int | None = None) -> None:
        if not hasattr(self, "open_pr_button"):
            return
        if not self.repo_ready:
            self.open_pr_button.grid_remove()
            return
        if total_entries is None:
            total_entries = len(getattr(self, "status_items", {}))
        if total_entries == 0:
            self.open_pr_button.grid()
            self.open_pr_button.configure(state="normal")
            return
        self.open_pr_button.grid_remove()

    def _find_status_index_by_path(self, path_for_git: str) -> int | None:
        if not path_for_git:
            return None
        for index, entry in self.status_items.items():
            if str(entry.get("path_for_git", "")).strip() == path_for_git:
                return index
        return None

    def _select_status_index(self, index: int) -> None:
        self.status_listbox.selection_clear(0, tk.END)
        self.status_listbox.selection_set(index)
        self.status_listbox.activate(index)
        self.status_listbox.see(index)

    def _status_entry_index_from_event(self, event: tk.Event) -> int | None:
        if self.status_listbox.size() == 0:
            return None
        index = self.status_listbox.nearest(event.y)
        if index < 0 or index >= self.status_listbox.size():
            return None
        bbox = self.status_listbox.bbox(index)
        if not bbox:
            return None
        y_top = bbox[1]
        y_bottom = y_top + bbox[3]
        if event.y < y_top or event.y > y_bottom:
            return None
        if index not in self.status_items and index not in self.status_header_actions:
            return None
        return index

    def _status_click_hits_toggle_marker(self, event: tk.Event, index: int) -> bool:
        if index not in self.status_items:
            return False
        marker_range = self.status_toggle_columns.get(index)
        if not marker_range:
            return False
        bbox = self.status_listbox.bbox(index)
        if not bbox:
            return False
        relative_x = event.x - bbox[0]
        if relative_x < 0:
            return False
        try:
            font = tkfont.nametofont(str(self.status_listbox.cget("font")))
            char_width = max(1, font.measure("0"))
        except tk.TclError:
            return False
        char_index = relative_x // char_width
        marker_start, marker_end = marker_range
        return marker_start <= char_index < marker_end

    def _status_list_visible_char_capacity(self) -> int:
        try:
            font = tkfont.nametofont(str(self.status_listbox.cget("font")))
            char_width = max(1, font.measure("0"))
        except tk.TclError:
            return 80
        width_px = int(self.status_listbox.winfo_width())
        if width_px <= 1:
            width_px = int(self.status_listbox.winfo_reqwidth())
        return max(24, (width_px // char_width) - 1)

    def _on_status_select(self, _event: tk.Event) -> None:
        if self.suspend_stage_sync:
            return
        selected = set(self.status_listbox.curselection())
        file_selected = [index for index in selected if index in self.status_items]
        if not file_selected:
            self.status_listbox.selection_clear(0, tk.END)
            self.status_focus_path = ""
            self._update_worktree_diff_from_selection()
            return
        focus_index = file_selected[-1]
        if len(file_selected) != len(selected):
            self._select_status_index(focus_index)
        entry = self.status_items.get(focus_index)
        if entry:
            self.status_focus_path = str(entry.get("path_for_git", "")).strip()
        self._update_worktree_diff_from_selection()

    def _on_status_list_single_click(self, event: tk.Event) -> str:
        index = self._status_entry_index_from_event(event)
        if index is None:
            return "break"
        if self.status_click_job is not None:
            try:
                self.after_cancel(self.status_click_job)
            except tk.TclError:
                pass
            self.status_click_job = None
        self.status_click_path = ""
        header_action = self.status_header_actions.get(index)
        if header_action is not None:
            self._select_status_index(index)
            self._toggle_status_group_stage(header_action)
            return "break"
        self._select_status_index(index)
        self._on_status_select(None)
        entry = self.status_items.get(index)
        if not entry:
            return "break"
        if not self._status_click_hits_toggle_marker(event, index):
            return "break"
        self.status_click_path = str(entry.get("path_for_git", "")).strip()
        self.status_click_job = self.after(220, self._execute_status_single_click)
        return "break"

    def _on_status_list_double_click(self, event: tk.Event) -> str:
        if self.status_click_job is not None:
            try:
                self.after_cancel(self.status_click_job)
            except tk.TclError:
                pass
            self.status_click_job = None
        self.status_click_path = ""
        self._open_status_file_in_vscode(event)
        return "break"

    def _execute_status_single_click(self) -> None:
        self.status_click_job = None
        path = self.status_click_path.strip()
        self.status_click_path = ""
        if not path:
            return
        index = self._find_status_index_by_path(path)
        if index is None:
            return
        entry = self.status_items.get(index)
        if not entry:
            return
        self._toggle_status_entry_stage(entry)

    def _toggle_status_entry_stage(self, entry: dict[str, str | bool]) -> None:
        path_for_git = str(entry.get("path_for_git", "")).strip()
        if not path_for_git:
            return
        self.status_auto_stage_disabled = True
        fully_staged = self._entry_is_fully_staged(entry)
        perf_trigger = "stage:file_unstage" if fully_staged else "stage:file_stage"
        refresh_trigger = "post_stage_file_unstage" if fully_staged else "post_stage_file_stage"
        start = self._perf_start("Stage/Unstage arquivo", perf_trigger)
        try:
            if fully_staged:
                run_git(self.repo_path, ["reset", "--", path_for_git])
                self._set_status(f"Arquivo removido do stage: {path_for_git}")
            else:
                run_git(self.repo_path, ["add", "--", path_for_git])
                self._set_status(f"Arquivo adicionado ao stage: {path_for_git}")
        except RuntimeError as exc:
            messagebox.showerror("Stage", str(exc))
            return
        finally:
            self._perf_end("Stage/Unstage arquivo", start, perf_trigger)
        self.status_focus_path = path_for_git
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._refresh_status(trigger=refresh_trigger)

    def _collect_status_entries_for_folder(self, folder: str) -> list[dict[str, str | bool]]:
        entries: list[dict[str, str | bool]] = []
        for entry in self.status_items.values():
            path_for_git = str(entry.get("path_for_git", "")).strip()
            entry_folder = os.path.dirname(path_for_git) if path_for_git else ""
            if entry_folder == folder:
                entries.append(entry)
        return entries

    def _toggle_status_group_stage(self, action: tuple[str, str]) -> None:
        action_type, folder = action
        if action_type == "all":
            has_unstaged = any(self._entry_has_unstaged_part(entry) for entry in self.status_items.values())
            if has_unstaged:
                self._stage_all_status_entries()
            else:
                self._unstage_all_status_entries()
            return

        entries = self._collect_status_entries_for_folder(folder)
        if not entries:
            return
        paths = sorted(
            {
                str(entry.get("path_for_git", "")).strip()
                for entry in entries
                if str(entry.get("path_for_git", "")).strip()
            }
        )
        if not paths:
            return
        all_staged = all(self._entry_is_fully_staged(entry) for entry in entries)
        self.status_auto_stage_disabled = True
        folder_label = f"{folder}/" if folder else "(root)"
        if all_staged:
            perf_trigger = "stage:folder_unstage"
            start = self._perf_start("Unstage pasta", perf_trigger)
            try:
                run_git(self.repo_path, ["reset", "--", *paths])
            except RuntimeError as exc:
                messagebox.showerror("Unstage", str(exc))
                return
            finally:
                self._perf_end("Unstage pasta", start, perf_trigger)
            self._set_status(f"Pasta desselecionada: {folder_label}")
            refresh_trigger = "post_unstage_folder"
        else:
            perf_trigger = "stage:folder_stage"
            start = self._perf_start("Stage pasta", perf_trigger)
            try:
                run_git(self.repo_path, ["add", "--", *paths])
            except RuntimeError as exc:
                messagebox.showerror("Stage", str(exc))
                return
            finally:
                self._perf_end("Stage pasta", start, perf_trigger)
            self._set_status(f"Pasta selecionada: {folder_label}")
            refresh_trigger = "post_stage_folder"
        self.status_focus_path = ""
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._refresh_status(trigger=refresh_trigger)

    def _move_status_selection(self, delta: int) -> None:
        if not hasattr(self, "status_listbox"):
            return
        size = self.status_listbox.size()
        if size == 0:
            return
        selection = self.status_listbox.curselection()
        if selection:
            index = selection[-1] + delta
        else:
            index = 0 if delta >= 0 else size - 1
        index = max(0, min(index, size - 1))
        step = 1 if delta >= 0 else -1
        while 0 <= index < size and index not in self.status_items:
            index += step
        if index < 0 or index >= size or index not in self.status_items:
            return
        self.status_listbox.selection_clear(0, tk.END)
        self.status_listbox.selection_set(index)
        self.status_listbox.activate(index)
        self.status_listbox.see(index)
        self._on_status_select(None)

    def _open_status_file_in_vscode(self, event: tk.Event) -> None:
        index = self._status_entry_index_from_event(event)
        if index is None:
            selection = self.status_listbox.curselection()
            if not selection:
                return
            index = selection[-1]
        entry = self.status_items.get(index)
        if not entry:
            return
        path = str(entry.get("path_for_git") or entry.get("path") or "").strip()
        if not path:
            return
        self._open_repo_file_in_vscode(path)

    def _apply_stage_from_selection(self) -> None:
        # Mantido por compatibilidade com fluxos antigos.
        return

    def _maybe_stage_entries_by_default(self, entries: list[dict[str, str | bool]]) -> list[dict[str, str | bool]]:
        if not entries:
            self.status_auto_stage_disabled = False
            return entries
        if self.status_auto_stage_disabled:
            return entries
        if all(self._entry_is_fully_staged(entry) for entry in entries):
            return entries
        try:
            run_git(self.repo_path, ["add", "-A"])
        except RuntimeError:
            return entries
        try:
            refreshed = self._get_status_entries()
        except RuntimeError:
            return entries
        self._set_status("Arquivos modificados foram selecionados automaticamente.")
        return refreshed

    def _stage_all_status_entries(self) -> None:
        if not self.repo_ready:
            return
        self.status_auto_stage_disabled = True
        perf_trigger = "stage:all_stage"
        start = self._perf_start("Stage todos", perf_trigger)
        try:
            run_git(self.repo_path, ["add", "-A"])
        except RuntimeError as exc:
            messagebox.showerror("Stage", str(exc))
            return
        finally:
            self._perf_end("Stage todos", start, perf_trigger)
        self.status_focus_path = ""
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._set_status("Todos os arquivos foram selecionados para commit.")
        self._refresh_status(trigger="post_stage_all")

    def _unstage_all_status_entries(self) -> None:
        if not self.repo_ready:
            return
        self.status_auto_stage_disabled = True
        try:
            staged = run_git(self.repo_path, ["diff", "--cached", "--name-only"]).strip()
        except RuntimeError as exc:
            messagebox.showerror("Unstage", str(exc))
            return
        if not staged:
            self._set_status("Nenhum arquivo selecionado para commit.")
            return
        perf_trigger = "stage:all_unstage"
        start = self._perf_start("Unstage todos", perf_trigger)
        try:
            run_git(self.repo_path, ["reset"])
        except RuntimeError as exc:
            messagebox.showerror("Unstage", str(exc))
            return
        finally:
            self._perf_end("Unstage todos", start, perf_trigger)
        self.status_focus_path = ""
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._set_status("Todos os arquivos foram desselecionados do commit.")
        self._refresh_status(trigger="post_unstage_all")

    def _update_worktree_diff_from_selection(self) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
        if not selected:
            self._set_text(self.worktree_diff_text, "Selecione um arquivo para ver o diff.")
            self.worktree_diff_data = None
            self.worktree_line_map.clear()
            self.worktree_hunk_marker_map.clear()
            self.worktree_hunk_patch_map.clear()
            self.worktree_line_scope_map.clear()
            self.worktree_line_patch_map.clear()
            self.worktree_diff_data_by_scope.clear()
            self._clear_worktree_selection_highlight()
            self._update_worktree_diff_actions()
            return
        entry = self.status_items[selected[0]]
        self._show_worktree_diff(entry)

    def _show_worktree_diff(self, entry: dict[str, str | bool]) -> None:
        status = str(entry.get("status", ""))
        path = str(entry.get("path_for_git", ""))
        if not path:
            self._set_text(self.worktree_diff_text, "Diff indisponível.")
            return
        sections: list[tuple[str, str, DiffData, list[str]]] = []
        raw_sections: list[tuple[str, str, DiffData]] = []
        try:
            for scope in self._diff_scopes_for_status(status):
                diff_raw = self._get_diff_for_scope(scope, path, word_diff=False)
                if not diff_raw.strip():
                    continue
                diff_view = diff_raw
                if self._word_diff_enabled():
                    rendered = self._get_diff_for_scope(scope, path, word_diff=True)
                    if rendered.strip():
                        diff_view = rendered
                raw_sections.append((scope, diff_view, parse_diff_data(diff_raw)))
        except RuntimeError as exc:
            messagebox.showerror("Diff", str(exc))
            return
        if not raw_sections:
            self._set_text(self.worktree_diff_text, "(sem diff)")
            self.worktree_diff_data = None
            self.worktree_line_map.clear()
            self.worktree_hunk_marker_map.clear()
            self.worktree_hunk_patch_map.clear()
            self.worktree_line_scope_map.clear()
            self.worktree_line_patch_map.clear()
            self.worktree_diff_data_by_scope.clear()
            self._clear_worktree_selection_highlight()
            self._update_worktree_diff_actions()
            return
        hunk_markers_by_scope = self._build_hunk_markers_by_scope(raw_sections)
        for scope, diff_view, diff_data in raw_sections:
            sections.append((scope, diff_view, diff_data, hunk_markers_by_scope.get(scope, [])))
        self.worktree_diff_data = sections[0][2]
        self.worktree_diff_scope = "mixed"
        self.worktree_line_map.clear()
        self.worktree_hunk_marker_map.clear()
        self.worktree_hunk_patch_map.clear()
        self.worktree_line_scope_map.clear()
        self.worktree_line_patch_map.clear()
        self.worktree_diff_data_by_scope.clear()
        self._render_worktree_diff_sections(sections, self._word_diff_enabled())
        self._clear_worktree_selection_highlight()
        self._update_worktree_diff_actions()

    @staticmethod
    def _diff_scopes_for_status(status: str) -> list[str]:
        if status.startswith("??"):
            return ["untracked"]
        scopes: list[str] = []
        if len(status) >= 2 and status[1] != " ":
            scopes.append("unstaged")
        if len(status) >= 1 and status[0] not in (" ", "?"):
            scopes.append("staged")
        if not scopes:
            scopes.append("unstaged")
        return scopes

    def _get_diff_for_scope(self, scope: str, path: str, word_diff: bool) -> str:
        if scope == "untracked":
            return self._get_untracked_diff(path, word_diff)
        cache = getattr(self, "worktree_diff_cache", None)
        token = getattr(self, "repo_state_token", 0)
        cache_key = (token, scope, path, word_diff)
        if cache is not None and cache_key in cache:
            return cache[cache_key]
        args = ["diff", "--unified=0"]
        if word_diff:
            args.append("--word-diff=plain")
        if scope == "staged":
            args.append("--cached")
        args.extend(["--", path])
        diff = run_git(self.repo_path, args)
        if cache is not None:
            cache[cache_key] = diff
        return diff

    @staticmethod
    def _scope_marker(scope: str) -> str:
        if scope == "staged":
            return "[x]"
        return "[ ]"

    @staticmethod
    def _hunk_signature(hunk: DiffHunk) -> tuple[int, int, int, int]:
        return (hunk.old_start, hunk.old_count, hunk.new_start, hunk.new_count)

    def _build_hunk_markers_by_scope(
        self, sections: list[tuple[str, str, DiffData]]
    ) -> dict[str, list[str]]:
        hunks_by_scope: dict[str, list[DiffHunk]] = {}
        for scope, _diff_view, diff_data in sections:
            hunks_by_scope[scope] = list(diff_data.hunks)

        unstaged_counter = Counter(self._hunk_signature(hunk) for hunk in hunks_by_scope.get("unstaged", []))
        staged_counter = Counter(self._hunk_signature(hunk) for hunk in hunks_by_scope.get("staged", []))
        shared_counter = Counter(
            {signature: min(unstaged_counter[signature], staged_counter[signature]) for signature in unstaged_counter}
        )
        shared_counter = Counter({signature: count for signature, count in shared_counter.items() if count > 0})
        shared_unstaged = Counter(shared_counter)
        shared_staged = Counter(shared_counter)

        markers_by_scope: dict[str, list[str]] = {}
        for scope, hunks in hunks_by_scope.items():
            scope_markers: list[str] = []
            for hunk in hunks:
                signature = self._hunk_signature(hunk)
                if scope == "unstaged":
                    marker = "[ ]"
                    if shared_unstaged.get(signature, 0) > 0:
                        marker = "[~]"
                        shared_unstaged[signature] -= 1
                elif scope == "staged":
                    marker = "[x]"
                    if shared_staged.get(signature, 0) > 0:
                        marker = "[~]"
                        shared_staged[signature] -= 1
                else:
                    marker = "[ ]"
                scope_markers.append(marker)
            markers_by_scope[scope] = scope_markers
        return markers_by_scope

    def _render_worktree_diff_sections(
        self, sections: list[tuple[str, str, DiffData, list[str]]], word_diff: bool
    ) -> None:
        self.worktree_diff_text.configure(state="normal")
        self.worktree_diff_text.delete("1.0", tk.END)
        self.worktree_line_map.clear()
        self.worktree_hunk_marker_map.clear()
        self.worktree_hunk_patch_map.clear()
        self.worktree_line_scope_map.clear()
        self.worktree_line_patch_map.clear()
        self.worktree_diff_data_by_scope.clear()

        for idx, (scope, diff_view, diff_data, hunk_markers) in enumerate(sections):
            before_end_line = int(self.worktree_diff_text.index("end-1c").split(".")[0])
            render_patch_to_widget(
                self.worktree_diff_text,
                diff_view,
                read_only=False,
                show_file_headers=False,
                word_diff=word_diff,
                line_marker=self._scope_marker(scope),
                show_hunk_headers=True,
                hunk_marker="[ ]",
                hunk_markers=hunk_markers,
                append=idx > 0,
            )
            self.worktree_diff_data_by_scope[scope] = diff_data
            after_end_line = int(self.worktree_diff_text.index("end-1c").split(".")[0])

            scan_start = 1 if idx == 0 else before_end_line + 1
            marker_lines = self._collect_hunk_marker_lines(scan_start, after_end_line)
            for hunk_idx, marker_line in enumerate(marker_lines):
                if hunk_idx >= len(diff_data.hunks):
                    break
                self.worktree_hunk_marker_map[marker_line] = (scope, hunk_idx)
                patch = build_patch_for_hunk(diff_data, hunk_idx)
                if patch:
                    self.worktree_hunk_patch_map[marker_line] = patch

            if word_diff or not diff_data.hunks:
                continue
            local_line_map = build_line_map(diff_data, include_hunk_headers=True)
            if marker_lines:
                line_offset = marker_lines[0] - 1
            else:
                line_offset = max(0, before_end_line)
            for local_line_no, line_info in local_line_map.items():
                global_line_no = line_offset + local_line_no
                self.worktree_line_map[global_line_no] = line_info
                self.worktree_line_scope_map[global_line_no] = scope
                patch = build_patch_for_line(diff_data, line_info)
                if patch:
                    self.worktree_line_patch_map[global_line_no] = patch

        self.worktree_diff_text.configure(state="disabled")

    def _collect_hunk_marker_lines(self, start_line: int, end_line: int) -> list[int]:
        if end_line < start_line:
            return []
        marker_lines: list[int] = []
        for line_no in range(max(1, start_line), end_line + 1):
            text = self.worktree_diff_text.get(f"{line_no}.0", f"{line_no}.end")
            if text.strip() in {"[ ]", "[x]", "[~]"}:
                marker_lines.append(line_no)
        return marker_lines

    def _worktree_line_marker_text(self, line_no: int) -> str:
        text = self.worktree_diff_text.get(f"{line_no}.0", f"{line_no}.end")
        if len(text) >= 3 and text[:3] in {"[ ]", "[x]", "[~]"}:
            return text[:3]
        return ""

    def _set_worktree_line_marker_text(self, line_no: int, marker: str) -> None:
        if marker not in {"[ ]", "[x]", "[~]"}:
            return
        self.worktree_diff_text.configure(state="normal")
        try:
            text = self.worktree_diff_text.get(f"{line_no}.0", f"{line_no}.end")
            if len(text) < 3 or text[:3] not in {"[ ]", "[x]", "[~]"}:
                return
            tags = list(self.worktree_diff_text.tag_names(f"{line_no}.4"))
            tags = [tag for tag in tags if tag not in {"selected_line", "selected_hunk"}]
            if line_no in self.worktree_hunk_marker_map:
                tags = ["meta"]
            self.worktree_diff_text.delete(f"{line_no}.0", f"{line_no}.3")
            if tags:
                self.worktree_diff_text.insert(f"{line_no}.0", marker, tuple(tags))
            else:
                self.worktree_diff_text.insert(f"{line_no}.0", marker)
        finally:
            self.worktree_diff_text.configure(state="disabled")

    def _find_hunk_marker_line_for_line(self, line_no: int) -> int | None:
        marker_lines = sorted(self.worktree_hunk_marker_map.keys())
        candidate: int | None = None
        for marker_line in marker_lines:
            if marker_line <= line_no:
                candidate = marker_line
            else:
                break
        return candidate

    def _refresh_hunk_marker_state(self, marker_line: int | None) -> None:
        if marker_line is None:
            return
        marker_lines = sorted(self.worktree_hunk_marker_map.keys())
        if marker_line not in marker_lines:
            return
        idx = marker_lines.index(marker_line)
        next_marker = marker_lines[idx + 1] if idx + 1 < len(marker_lines) else None
        start_line = marker_line + 1
        if next_marker is None:
            end_line = int(self.worktree_diff_text.index("end-1c").split(".")[0])
        else:
            end_line = next_marker - 1
        line_markers: list[str] = []
        for current_line in range(start_line, end_line + 1):
            marker = self._worktree_line_marker_text(current_line)
            if marker:
                line_markers.append(marker)
        if not line_markers:
            return
        if all(marker == "[x]" for marker in line_markers):
            hunk_marker = "[x]"
        elif all(marker == "[ ]" for marker in line_markers):
            hunk_marker = "[ ]"
        else:
            hunk_marker = "[~]"
        self._set_worktree_line_marker_text(marker_line, hunk_marker)

    def _operation_scope_from_marker(self, marker: str, default_scope: str) -> str:
        if marker == "[x]":
            return "staged"
        if marker in {"[ ]", "[~]"}:
            return "unstaged"
        return default_scope

    def _acquire_worktree_toggle_lock(self) -> bool:
        if self.worktree_toggle_busy:
            self._set_status("Aguarde concluir a operação anterior de stage/unstage.")
            return False
        self.worktree_toggle_busy = True
        return True

    def _release_worktree_toggle_lock(self) -> None:
        self.worktree_toggle_busy = False

    @staticmethod
    def _is_patch_outdated_error(exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return "patch does not apply" in message or "falha no patch" in message

    def _schedule_status_refresh(self, trigger: str, delay_ms: int = 220) -> None:
        normalized_trigger = self._normalize_perf_trigger(trigger) or "internal"
        self.status_refresh_debounce_trigger = normalized_trigger
        if self.status_refresh_debounce_job is not None:
            try:
                self.after_cancel(self.status_refresh_debounce_job)
            except tk.TclError:
                pass
            self.status_refresh_debounce_job = None
        self.status_refresh_debounce_job = self.after(delay_ms, self._flush_scheduled_status_refresh)

    def _flush_scheduled_status_refresh(self) -> None:
        self.status_refresh_debounce_job = None
        trigger = self.status_refresh_debounce_trigger.strip()
        self.status_refresh_debounce_trigger = ""
        self._refresh_status(trigger=trigger or "debounced")

    def _worktree_marker_clickable(self, event: tk.Event, line_no: int) -> bool:
        marker_width = 0
        if line_no in self.worktree_hunk_marker_map:
            marker_width = len("[~]") + 1
        elif line_no in self.worktree_line_scope_map:
            marker_width = len(self._scope_marker(self.worktree_line_scope_map[line_no])) + 1
        if marker_width <= 0:
            return False
        try:
            index = self.worktree_diff_text.index(f"@{event.x},{event.y}")
            col = int(index.split(".")[1])
        except (tk.TclError, ValueError):
            return False
        return col < marker_width

    def _worktree_line_no_from_event(self, event: tk.Event) -> int | None:
        try:
            index = self.worktree_diff_text.index(f"@{event.x},{event.y}")
            return int(index.split(".")[0])
        except (tk.TclError, ValueError):
            return None

    def _resolve_hunk_meta_for_line(self, line_no: int) -> tuple[str, int] | None:
        if line_no <= 0 or not self.worktree_hunk_marker_map:
            return None
        if line_no in self.worktree_hunk_marker_map:
            return self.worktree_hunk_marker_map[line_no]
        candidate_line: int | None = None
        for marker_line in self.worktree_hunk_marker_map:
            if marker_line <= line_no and (candidate_line is None or marker_line > candidate_line):
                candidate_line = marker_line
        if candidate_line is None:
            return None
        return self.worktree_hunk_marker_map.get(candidate_line)

    def _clear_worktree_selection_highlight(self) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        self.worktree_diff_text.tag_remove("selected_hunk", "1.0", tk.END)
        self.worktree_diff_text.tag_remove("selected_line", "1.0", tk.END)

    def _highlight_selected_diff_line(self, line_no: int, line_info: DiffLineInfo) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        self._clear_worktree_selection_highlight()
        for mapped_line_no, info in self.worktree_line_map.items():
            if info.hunk_index == line_info.hunk_index:
                self.worktree_diff_text.tag_add("selected_hunk", f"{mapped_line_no}.0", f"{mapped_line_no}.end")
        self.worktree_diff_text.tag_add("selected_line", f"{line_no}.0", f"{line_no}.end")

    def _get_diff_line_info_from_event(self, event: tk.Event) -> DiffLineInfo | None:
        if not self.worktree_line_map:
            return None
        line_no = self._worktree_line_no_from_event(event)
        if line_no is None:
            return None
        return self.worktree_line_map.get(line_no)

    def _remember_status_focus_from_selection(self) -> None:
        selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
        if not selected:
            return
        entry = self.status_items.get(selected[-1])
        if not entry:
            return
        self.status_focus_path = str(entry.get("path_for_git", "")).strip()

    def _on_worktree_diff_single_click(self, event: tk.Event) -> str:
        if self.worktree_toggle_busy:
            return "break"
        if self.diff_click_job is not None:
            try:
                self.after_cancel(self.diff_click_job)
            except tk.TclError:
                pass
            self.diff_click_job = None
        self.diff_click_line_no = 0
        line_no = self._worktree_line_no_from_event(event)
        if line_no is None:
            return "break"
        line_info = self.worktree_line_map.get(line_no)
        line_scope = self.worktree_line_scope_map.get(line_no, "")
        marker_text = self._worktree_line_marker_text(line_no)
        line_scope = self._operation_scope_from_marker(marker_text, line_scope)
        hunk_meta = self.worktree_hunk_marker_map.get(line_no)
        if line_info:
            self._highlight_selected_diff_line(line_no, line_info)
            self.worktree_diff_text.mark_set(tk.INSERT, f"{line_no}.0")
            if hunk_meta is None and line_scope:
                hunk_meta = (line_scope, line_info.hunk_index)
        else:
            self._clear_worktree_selection_highlight()
            if self._word_diff_enabled():
                hunk_meta = self._resolve_hunk_meta_for_line(line_no)
        if not self._worktree_marker_clickable(event, line_no):
            return "break"
        self._remember_status_focus_from_selection()
        if hunk_meta is None:
            return "break"
        if line_no in self.worktree_hunk_marker_map:
            hunk_marker = self._worktree_line_marker_text(line_no)
            operation_scope = self._operation_scope_from_marker(hunk_marker, hunk_meta[0])
            self._toggle_selected_hunk_by_index(hunk_meta[0], operation_scope, hunk_meta[1], marker_line=line_no)
            return "break"
        if self._word_diff_enabled():
            operation_scope = self._operation_scope_from_marker(marker_text, hunk_meta[0])
            marker_line = self._find_hunk_marker_line_for_line(line_no)
            self._toggle_selected_hunk_by_index(hunk_meta[0], operation_scope, hunk_meta[1], marker_line=marker_line)
            return "break"
        if line_info is None or not line_scope:
            return "break"
        operation_scope = self._operation_scope_from_marker(marker_text, line_scope)
        self._toggle_selected_line_by_info(line_scope, operation_scope, line_no, line_info)
        return "break"

    def _on_worktree_diff_double_click(self, event: tk.Event) -> str:
        return self._on_worktree_diff_single_click(event)

    def _toggle_selected_line_by_info(
        self,
        patch_scope: str,
        operation_scope: str,
        line_no: int,
        line_info: DiffLineInfo,
    ) -> None:
        if not self._acquire_worktree_toggle_lock():
            return
        try:
            if operation_scope == "untracked":
                selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
                if not selected:
                    return
                entry = self.status_items.get(selected[-1])
                if entry is None:
                    return
                self._toggle_status_entry_stage(entry)
                return
            patch = self.worktree_line_patch_map.get(line_no)
            if not patch:
                diff_data = self.worktree_diff_data_by_scope.get(patch_scope)
                if diff_data is None:
                    return
                patch = build_patch_for_line(diff_data, line_info)
            if not patch:
                return
            reverse = operation_scope == "staged"
            try:
                self._apply_patch(patch, reverse=reverse)
            except RuntimeError as exc:
                if self._is_patch_outdated_error(exc):
                    self._set_status("Diff desatualizado; atualizando após clique rápido.")
                    self._refresh_status(trigger="patch_mismatch_line")
                    return
                title = "Unstage" if reverse else "Stage"
                messagebox.showerror(title, str(exc))
                return
            self.preserve_worktree_diff_on_status_refresh = True
            new_marker = "[ ]" if reverse else "[x]"
            self._set_worktree_line_marker_text(line_no, new_marker)
            marker_line = self._find_hunk_marker_line_for_line(line_no)
            self._refresh_hunk_marker_state(marker_line)
            refresh_trigger = "post_stage_line_unstage" if reverse else "post_stage_line_stage"
            self._schedule_status_refresh(trigger=refresh_trigger)
        finally:
            self._release_worktree_toggle_lock()

    def _toggle_selected_hunk_by_index(
        self,
        patch_scope: str,
        operation_scope: str,
        hunk_index: int,
        marker_line: int | None = None,
    ) -> None:
        if not self._acquire_worktree_toggle_lock():
            return
        try:
            if hunk_index < 0:
                return
            if operation_scope == "untracked":
                selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
                if not selected:
                    return
                entry = self.status_items.get(selected[-1])
                if entry is None:
                    return
                self._toggle_status_entry_stage(entry)
                return
            if operation_scope not in ("unstaged", "staged"):
                return
            patch = self.worktree_hunk_patch_map.get(marker_line or -1, "")
            if not patch:
                diff_data = self.worktree_diff_data_by_scope.get(patch_scope)
                if diff_data is None:
                    return
                patch = build_patch_for_hunk(diff_data, hunk_index)
            if not patch:
                return
            reverse = operation_scope == "staged"
            try:
                self._apply_patch(patch, reverse=reverse)
            except RuntimeError as exc:
                if self._is_patch_outdated_error(exc):
                    self._set_status("Diff desatualizado; atualizando após clique rápido.")
                    self._refresh_status(trigger="patch_mismatch_hunk")
                    return
                title = "Unstage" if reverse else "Stage"
                messagebox.showerror(title, str(exc))
                return
            self.preserve_worktree_diff_on_status_refresh = True
            if marker_line is not None:
                target_marker = "[ ]" if reverse else "[x]"
                self._set_worktree_line_marker_text(marker_line, target_marker)
                marker_lines = sorted(self.worktree_hunk_marker_map.keys())
                idx = marker_lines.index(marker_line) if marker_line in marker_lines else -1
                next_marker = marker_lines[idx + 1] if idx >= 0 and idx + 1 < len(marker_lines) else None
                start_line = marker_line + 1
                if next_marker is None:
                    end_line = int(self.worktree_diff_text.index("end-1c").split(".")[0])
                else:
                    end_line = next_marker - 1
                for current_line in range(start_line, end_line + 1):
                    if self._worktree_line_marker_text(current_line):
                        self._set_worktree_line_marker_text(current_line, target_marker)
                        if target_marker in {"[x]", "[ ]"}:
                            self.worktree_line_scope_map[current_line] = (
                                "staged" if target_marker == "[x]" else "unstaged"
                            )
                self._refresh_hunk_marker_state(marker_line)
            refresh_trigger = "post_stage_hunk_unstage" if reverse else "post_stage_hunk_stage"
            self._schedule_status_refresh(trigger=refresh_trigger)
        finally:
            self._release_worktree_toggle_lock()

    def _get_selected_diff_line(self) -> DiffLineInfo | None:
        if not self.worktree_line_map:
            return None
        if self.worktree_diff_text.tag_ranges(tk.SEL):
            index = self.worktree_diff_text.index(tk.SEL_FIRST)
        else:
            index = self.worktree_diff_text.index(tk.INSERT)
        try:
            line_no = int(index.split(".")[0])
        except ValueError:
            return None
        return self.worktree_line_map.get(line_no)

    def _apply_patch(self, patch: str, reverse: bool) -> None:
        cmd = ["git", "-C", self.repo_path, "apply", "--recount", "--unidiff-zero", "--cached"]
        if reverse:
            cmd.append("-R")
        self.status_auto_stage_disabled = True
        perf_trigger = "stage:apply_reverse" if reverse else "stage:apply_forward"
        start = self._perf_start("Stage/Unstage patch", perf_trigger)
        try:
            result = subprocess.run(
                cmd,
                input=patch,
                text=True,
                capture_output=True,
            )
        finally:
            self._perf_end("Stage/Unstage patch", start, perf_trigger)
        if result.returncode != 0:
            stderr = result.stderr.strip() or "falha ao aplicar patch"
            raise RuntimeError(stderr)

    def _stage_selected_hunk(self) -> None:
        if not self.repo_ready or self.worktree_diff_scope != "unstaged":
            messagebox.showinfo("Stage", "Selecione um diff unstaged.")
            return
        line_info = self._get_selected_diff_line()
        if not line_info:
            messagebox.showinfo("Stage", "Selecione uma linha do diff.")
            return
        if not self.worktree_diff_data:
            return
        patch = build_patch_for_hunk(self.worktree_diff_data, line_info.hunk_index)
        if not patch:
            return
        try:
            self._apply_patch(patch, reverse=False)
        except RuntimeError as exc:
            messagebox.showerror("Stage", str(exc))
            return
        self._refresh_status(trigger="post_stage_hunk_stage")
        self._update_worktree_diff_from_selection()

    def _unstage_selected_hunk(self) -> None:
        if not self.repo_ready or self.worktree_diff_scope != "staged":
            messagebox.showinfo("Unstage", "Selecione um diff staged.")
            return
        line_info = self._get_selected_diff_line()
        if not line_info:
            messagebox.showinfo("Unstage", "Selecione uma linha do diff.")
            return
        if not self.worktree_diff_data:
            return
        patch = build_patch_for_hunk(self.worktree_diff_data, line_info.hunk_index)
        if not patch:
            return
        try:
            self._apply_patch(patch, reverse=True)
        except RuntimeError as exc:
            messagebox.showerror("Unstage", str(exc))
            return
        self._refresh_status(trigger="post_stage_hunk_unstage")
        self._update_worktree_diff_from_selection()

    def _stage_selected_line(self) -> None:
        if not self.repo_ready or self.worktree_diff_scope != "unstaged":
            messagebox.showinfo("Stage", "Selecione um diff unstaged.")
            return
        line_info = self._get_selected_diff_line()
        if not line_info:
            messagebox.showinfo("Stage", "Selecione uma linha do diff.")
            return
        if not self.worktree_diff_data:
            return
        patch = build_patch_for_line(self.worktree_diff_data, line_info)
        if not patch:
            messagebox.showinfo("Stage", "A linha selecionada nao e uma alteracao.")
            return
        try:
            self._apply_patch(patch, reverse=False)
        except RuntimeError as exc:
            messagebox.showerror("Stage", str(exc))
            return
        self._refresh_status(trigger="post_stage_line_stage")
        self._update_worktree_diff_from_selection()

    def _unstage_selected_line(self) -> None:
        if not self.repo_ready or self.worktree_diff_scope != "staged":
            messagebox.showinfo("Unstage", "Selecione um diff staged.")
            return
        line_info = self._get_selected_diff_line()
        if not line_info:
            messagebox.showinfo("Unstage", "Selecione uma linha do diff.")
            return
        if not self.worktree_diff_data:
            return
        patch = build_patch_for_line(self.worktree_diff_data, line_info)
        if not patch:
            messagebox.showinfo("Unstage", "A linha selecionada nao e uma alteracao.")
            return
        try:
            self._apply_patch(patch, reverse=True)
        except RuntimeError as exc:
            messagebox.showerror("Unstage", str(exc))
            return
        self._refresh_status(trigger="post_stage_line_unstage")
        self._update_worktree_diff_from_selection()

    def _update_worktree_diff_actions(self) -> None:
        if not hasattr(self, "diff_interaction_hint_var"):
            return
        if not self.worktree_diff_data:
            self.diff_interaction_hint_var.set("Selecione um arquivo para usar stage/unstage por clique.")
            return
        if self._word_diff_enabled():
            self.diff_interaction_hint_var.set("Clique no marcador cinza do bloco para stage/unstage do bloco.")
            return
        self.diff_interaction_hint_var.set(
            "Clique no marcador [ ]/[x] para alterar linha. Clique no marcador cinza para alterar bloco."
        )

    def _get_untracked_diff(self, path: str, word_diff: bool) -> str:
        cmd = ["git", "-C", self.repo_path, "diff", "--no-index", "--unified=0"]
        if word_diff:
            cmd.append("--word-diff=plain")
        cmd.extend(["/dev/null", path])
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def _get_status_entries(self) -> list[dict[str, str | bool]]:
        output = run_git(self.repo_path, ["status", "--porcelain", "-z"])
        entries: list[dict[str, str | bool]] = []
        chunks = [chunk for chunk in output.split("\0") if chunk]
        index = 0
        while index < len(chunks):
            raw = chunks[index]
            if len(raw) < 3:
                index += 1
                continue
            status = raw[:2]
            path = raw[3:]
            path_for_git = path
            if status[0] in ("R", "C") and index + 1 < len(chunks):
                new_path = chunks[index + 1]
                path = f"{path} -> {new_path}"
                path_for_git = new_path
                index += 1
            staged = status[0] not in (" ", "?")
            unstaged = status[1] != " "
            entries.append(
                {
                    "status": status,
                    "path": path,
                    "path_for_git": path_for_git,
                    "staged": staged,
                    "unstaged": unstaged,
                }
            )
            index += 1
        return entries

    def _commit_changes(self) -> bool:
        title = self.commit_title_var.get().strip()
        body = self.commit_body_text.get("1.0", tk.END).strip()
        if not title:
            messagebox.showwarning("Commit", "Informe o título do commit.")
            return False
        perf_trigger = "commit:create"
        start = self._perf_start("Commit", perf_trigger)
        try:
            try:
                staged = run_git(self.repo_path, ["diff", "--cached", "--name-only"]).strip()
            except RuntimeError as exc:
                messagebox.showerror("Erro", str(exc))
                return False
            if not staged:
                messagebox.showwarning("Commit", "Nenhum arquivo staged.")
                return False
            try:
                if body:
                    run_git(self.repo_path, ["commit", "-m", title, "-m", body])
                else:
                    run_git(self.repo_path, ["commit", "-m", title])
            except RuntimeError as exc:
                messagebox.showerror("Erro", str(exc))
                return False
            self.commit_title_var.set("")
            self.commit_body_text.delete("1.0", tk.END)
            if hasattr(self, "_bump_repo_state"):
                self._bump_repo_state()
            self._set_status("Commit criado.")
            self._refresh_status(trigger="post_commit")
            self._reload_commits(trigger="post_commit")
            if self._is_dirty():
                self._set_status("Commit criado, mas ainda há alterações locais.")
            return True
        finally:
            self._perf_end("Commit", start, perf_trigger)

    def _commit_and_push(self) -> None:
        if not self._fetch_repo_internal(show_errors=True, trigger="pre_commit_push"):
            return
        if not self._get_upstream():
            messagebox.showwarning(
                "Commit + Push",
                "Upstream não configurado para esta branch.",
            )
            return
        behind, _ahead = self._get_ahead_behind()
        if behind > 0:
            messagebox.showwarning(
                "Commit + Push",
                "Há commits para puxar (pull). Faça pull antes de enviar.",
            )
            return
        if self._commit_changes():
            self._push_repo()

    def _can_undo_last_commit(self) -> tuple[bool, str]:
        if not self.repo_ready:
            return False, "Selecione um repositório válido antes de desfazer commit."
        try:
            run_git(self.repo_path, ["rev-parse", "--verify", "HEAD"])
        except RuntimeError:
            return False, "Não há commits para desfazer."
        try:
            run_git(self.repo_path, ["rev-parse", "--verify", "HEAD~1"])
        except RuntimeError:
            return False, "Este fluxo não desfaz o commit inicial da branch."
        return True, ""

    def _on_undo_commit_button_hover(self, event: tk.Event) -> None:
        tooltip = self._get_undo_commit_tooltip_text()
        self._show_hover_tooltip("undo_commit_button", tooltip, event.x_root + 12, event.y_root + 12)

    def _get_undo_commit_tooltip_text(self) -> str:
        if not self.repo_ready:
            return "Selecione um repositório válido."
        try:
            head_commit = run_git(self.repo_path, ["show", "-s", "--pretty=format:%h %s", "HEAD"]).strip()
        except RuntimeError:
            return "Não há commit para desfazer."
        if not head_commit:
            return "Não há commit para desfazer."
        try:
            run_git(self.repo_path, ["rev-parse", "--verify", "HEAD~1"])
        except RuntimeError:
            return f"Commit inicial da branch:\n{head_commit}\nEste fluxo não desfaz o commit inicial."
        return f"Commit que será desfeito:\n{head_commit}"

    def _undo_last_commit(self, mode: str) -> bool:
        ok, message = self._can_undo_last_commit()
        if not ok:
            messagebox.showinfo("Undo commit", message)
            return False
        reset_mode_map = {
            "soft": "--soft",
            "mixed": "--mixed",
            "hard": "--hard",
        }
        reset_flag = reset_mode_map.get(mode)
        if not reset_flag:
            messagebox.showerror("Undo commit", "Modo de undo inválido.")
            return False
        mode_label_map = {
            "soft": "Soft: mantém mudanças staged.",
            "mixed": "Mixed: mantém mudanças sem stage.",
            "hard": "Hard: descarta as mudanças do commit e alterações locais.",
        }
        confirm = messagebox.askyesno(
            "Undo commit",
            f"Desfazer o último commit?\nModo: {mode_label_map[mode]}",
        )
        if not confirm:
            return False
        if mode == "hard":
            hard_confirm = messagebox.askyesno(
                "Undo commit",
                "Confirma modo HARD?\nEsta ação descarta alterações locais sem possibilidade de desfazer pela UI.",
            )
            if not hard_confirm:
                return False
        perf_trigger = f"undo_commit:{mode}"
        start = self._perf_start("Undo commit", perf_trigger)
        try:
            try:
                run_git(self.repo_path, ["reset", reset_flag, "HEAD~1"])
            except RuntimeError as exc:
                messagebox.showerror("Undo commit", str(exc))
                return False
            if hasattr(self, "_bump_repo_state"):
                self._bump_repo_state()
            self._refresh_status(trigger=f"post_undo_{mode}")
            self._reload_commits(trigger=f"post_undo_{mode}")
            self._refresh_branches(trigger=f"post_undo_{mode}")
            self._update_pull_push_labels()
            self._set_status(f"Último commit desfeito ({mode}).")
            return True
        finally:
            self._perf_end("Undo commit", start, perf_trigger)

    def _open_undo_commit_window(self) -> None:
        self._hide_hover_tooltip()
        ok, message = self._can_undo_last_commit()
        if not ok:
            messagebox.showinfo("Undo commit", message)
            return
        window = tk.Toplevel(self)
        window.title("Undo commit")
        window.geometry("560x250")
        window.transient(self)
        window.grab_set()

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.grid_columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text=(
                "Escolha como desfazer o último commit da branch atual.\n"
                "Use hard apenas quando tiver certeza."
            ),
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        mode_var = tk.StringVar(value="soft")
        ttk.Radiobutton(
            frame,
            text="Soft (reset --soft HEAD~1): mantém mudanças staged",
            variable=mode_var,
            value="soft",
        ).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Radiobutton(
            frame,
            text="Mixed (reset --mixed HEAD~1): mantém mudanças sem stage",
            variable=mode_var,
            value="mixed",
        ).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Radiobutton(
            frame,
            text="Hard (reset --hard HEAD~1): descarta alterações",
            variable=mode_var,
            value="hard",
        ).grid(row=3, column=0, sticky="w", pady=2)

        warning_var = tk.StringVar(value="")
        warning_label = ttk.Label(frame, textvariable=warning_var, foreground="#b42318")
        warning_label.grid(row=4, column=0, sticky="w", pady=(8, 0))

        def update_warning() -> None:
            if mode_var.get() == "hard":
                warning_var.set("Aviso: modo HARD descarta alterações locais.")
            else:
                warning_var.set("")

        update_warning()
        mode_var.trace_add("write", lambda *_: update_warning())

        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, sticky="e", pady=(12, 0))

        def execute() -> None:
            if self._undo_last_commit(mode_var.get().strip()):
                window.destroy()

        ttk.Button(actions, text="Cancelar", command=window.destroy).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Desfazer commit", command=execute).grid(row=0, column=1)

    def _open_commit_pr_in_github(self) -> None:
        if not self.repo_ready:
            messagebox.showinfo("PR", "Selecione um repositório válido antes de abrir PR.")
            return
        try:
            if self._is_dirty():
                messagebox.showinfo("PR", "Finalize o stage/commit antes de abrir a PR.")
                self._update_open_pr_button_visibility(len(self.status_items))
                return
        except RuntimeError as exc:
            messagebox.showerror("PR", str(exc))
            return
        selection = self._prompt_pr_branch_selection()
        if not selection:
            return
        base_branch, head_branch = selection
        opened = False
        if hasattr(self, "_open_pr_on_github"):
            opened = self._open_pr_on_github(self.repo_path, base_branch=base_branch, head_branch=head_branch)
        if opened:
            self._set_status("Página de PR aberta no GitHub.")

    def _prompt_pr_branch_selection(self) -> tuple[str, str] | None:
        branch_options = list(getattr(self, "branch_list", []))
        if not branch_options and hasattr(self, "_get_branches"):
            try:
                branch_options = self._get_branches()
            except RuntimeError:
                branch_options = []

        default_base = "main"
        base_getter = getattr(self, "_get_default_base_branch_for_pr", None)
        if callable(base_getter):
            resolved_base = str(base_getter(self.repo_path)).strip()
            if resolved_base:
                default_base = resolved_base
        default_head = ""
        head_getter = getattr(self, "_get_current_branch_for_pr", None)
        if callable(head_getter):
            default_head = str(head_getter(self.repo_path)).strip()
        if not default_head and hasattr(self, "branch_var"):
            default_head = self.branch_var.get().strip()

        for branch in (default_base, default_head):
            if branch and branch not in branch_options:
                branch_options.append(branch)

        if not branch_options:
            messagebox.showwarning("PR", "Não foi possível listar branches para abrir a PR.")
            return None

        if not default_base:
            default_base = branch_options[0]
        if not default_head:
            default_head = branch_options[0]
        if default_base == default_head and len(branch_options) > 1:
            for option in branch_options:
                if option != default_head:
                    default_base = option
                    break

        window = tk.Toplevel(self)
        window.title("Abrir PR no GitHub")
        window.transient(self)
        window.grab_set()
        window.resizable(False, False)

        frame = ttk.Frame(window)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.grid_columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Escolha as branches para abrir a página de Pull Request.",
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Destino (base):").grid(row=1, column=0, sticky="w")
        base_var = tk.StringVar(value=default_base)
        base_combo = ttk.Combobox(frame, textvariable=base_var, state="readonly", values=branch_options, width=36)
        base_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(frame, text="Origem (head):").grid(row=2, column=0, sticky="w", pady=(6, 0))
        head_var = tk.StringVar(value=default_head)
        head_combo = ttk.Combobox(frame, textvariable=head_var, state="readonly", values=branch_options, width=36)
        head_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        result: dict[str, tuple[str, str] | None] = {"value": None}

        def cancel() -> None:
            result["value"] = None
            window.destroy()

        def confirm() -> None:
            base = base_var.get().strip()
            head = head_var.get().strip()
            if not base or not head:
                messagebox.showwarning("PR", "Selecione as branches de destino e origem.")
                return
            if base == head:
                messagebox.showwarning("PR", "Origem e destino devem ser diferentes.")
                return
            result["value"] = (base, head)
            window.destroy()

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancelar", command=cancel).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Abrir PR", command=confirm).grid(row=0, column=1)

        window.bind("<Escape>", lambda _event: cancel())
        window.bind("<Return>", lambda _event: confirm())
        base_combo.focus_set()
        window.wait_window()
        return result["value"]
