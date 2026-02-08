#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

from ..core.diff_utils import build_line_map, build_patch_for_hunk, build_patch_for_line, parse_diff_data, render_patch_to_widget
from ..core.git_client import run_git
from ..core.models import DiffData, DiffLineInfo


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
        self.stage_count_var = tk.StringVar(value="Staged: 0/0")
        ttk.Label(header_row, textvariable=self.stage_count_var).grid(row=0, column=1, sticky="e", padx=(8, 0))

        controls_row = ttk.Frame(status_frame)
        controls_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Button(controls_row, text="Atualizar status", command=self._refresh_status).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        commit_branch_controls = ttk.Frame(controls_row)
        commit_branch_controls.grid(row=0, column=1, sticky="w")
        ttk.Label(commit_branch_controls, text="Branch:").grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.commit_branch_quick_var = tk.StringVar(value="")
        self.commit_branch_quick_combo = ttk.Combobox(
            commit_branch_controls,
            textvariable=self.commit_branch_quick_var,
            state="disabled",
            width=20,
            values=[],
        )
        self.commit_branch_quick_combo.grid(row=0, column=1, sticky="e")
        self.commit_branch_quick_combo.bind("<<ComboboxSelected>>", self._on_commit_quick_branch_selected)
        ttk.Button(
            commit_branch_controls,
            text="Nova branch",
            command=self._create_commit_quick_branch,
        ).grid(row=0, column=2, sticky="e", padx=(6, 0))

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

        diff_frame = ttk.Frame(paned)
        diff_frame.grid_columnconfigure(0, weight=1)
        diff_frame.grid_rowconfigure(1, weight=1)

        diff_header = ttk.Frame(diff_frame)
        diff_header.grid(row=0, column=0, sticky="ew")
        diff_header.grid_columnconfigure(0, weight=1)
        ttk.Label(diff_header, text="Diff do arquivo selecionado:").grid(row=0, column=0, sticky="w")
        self.diff_scope_combo = ttk.Combobox(
            diff_header,
            textvariable=self.diff_scope_var,
            state="readonly",
            width=10,
            values=["Unstaged", "Staged"],
        )
        self.diff_scope_combo.grid(row=0, column=1, padx=(8, 0))
        self.diff_scope_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_worktree_diff_from_selection())
        ttk.Checkbutton(
            diff_header,
            text="Diff por palavra",
            variable=self.word_diff_var,
            command=self._toggle_word_diff,
        ).grid(row=0, column=2, padx=(8, 0))
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
        self.status_focus_path = ""
        self.status_click_job: str | None = None
        self.status_click_path = ""
        self.diff_click_job: str | None = None
        self.diff_click_line_no = 0
        self._refresh_branches()
        self._refresh_status()

    def _refresh_status(self) -> None:
        if not self.repo_ready or self.status_loading:
            return
        self.status_loading = True

        def task() -> list[dict[str, str | bool]]:
            return self._get_status_entries()

        def success(entries: object) -> None:
            self.status_loading = False
            self._render_status_entries(list(entries))  # type: ignore[list-item]

        def error(exc: Exception) -> None:
            self.status_loading = False
            messagebox.showerror("Erro", str(exc))

        self._run_async("status", "Atualizar status", task, success, error)

    def _render_status_entries(self, entries: list[dict[str, str | bool]]) -> None:
        self.status_listbox.delete(0, tk.END)
        self.status_items.clear()
        self.status_headers = set()
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

        for folder in sorted_folders:
            header_text = f"{folder}/" if folder else "(root)"
            header_index = self.status_listbox.size()
            self.status_listbox.insert(tk.END, header_text)
            self.status_headers.add(header_index)

            folder_entries = grouped[folder]
            folder_entries.sort(key=lambda item: str(item["path_for_git"]))
            for entry in folder_entries:
                staged_label = "[x]" if entry["staged"] else "[ ]"
                if entry["staged"]:
                    staged_count += 1
                display_path = str(entry["path"])
                leaf = display_path.split("/")[-1]
                if " -> " in display_path:
                    leaf = display_path
                line = f"  {entry['status']:>2} {staged_label} {leaf}"
                item_index = self.status_listbox.size()
                self.status_listbox.insert(tk.END, line)
                self.status_items[item_index] = entry
        if hasattr(self, "stage_count_var"):
            self.stage_count_var.set(f"Staged: {staged_count}/{total}")
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
        self._update_worktree_diff_from_selection()
        self._update_operation_preview()
        if hasattr(self, "_refresh_repo_status_panel"):
            self._refresh_repo_status_panel()

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
        if index not in self.status_items:
            return None
        return index

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
        self._select_status_index(index)
        self._on_status_select(None)
        entry = self.status_items.get(index)
        if not entry:
            return "break"
        self.status_click_path = str(entry.get("path_for_git", "")).strip()
        if self.status_click_job is not None:
            try:
                self.after_cancel(self.status_click_job)
            except tk.TclError:
                pass
            self.status_click_job = None
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
        staged = bool(entry.get("staged", False))
        try:
            if staged:
                run_git(self.repo_path, ["reset", "--", path_for_git])
                self._set_status(f"Arquivo removido do stage: {path_for_git}")
            else:
                run_git(self.repo_path, ["add", "--", path_for_git])
                self._set_status(f"Arquivo adicionado ao stage: {path_for_git}")
        except RuntimeError as exc:
            messagebox.showerror("Stage", str(exc))
            return
        self.status_focus_path = path_for_git
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._refresh_status()

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

    def _update_worktree_diff_from_selection(self) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
        if not selected:
            self._set_text(self.worktree_diff_text, "Selecione um arquivo para ver o diff.")
            self.worktree_diff_data = None
            self.worktree_line_map.clear()
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
        try:
            scope = self._resolve_diff_scope(status)
            diff_raw = self._get_diff_for_scope(scope, path, word_diff=False)
            diff_view = diff_raw
            if self._word_diff_enabled():
                diff_view = self._get_diff_for_scope(scope, path, word_diff=True)
        except RuntimeError as exc:
            messagebox.showerror("Diff", str(exc))
            return
        if not diff_view.strip():
            self._set_text(self.worktree_diff_text, "(sem diff)")
            self.worktree_diff_data = None
            self.worktree_line_map.clear()
            self._clear_worktree_selection_highlight()
            self._update_worktree_diff_actions()
            return
        self.worktree_diff_data = parse_diff_data(diff_raw)
        self.worktree_diff_scope = scope
        self.worktree_line_map.clear()
        self._render_worktree_diff(diff_view, self._word_diff_enabled())
        self._clear_worktree_selection_highlight()
        self._update_worktree_diff_actions()

    def _resolve_diff_scope(self, status: str) -> str:
        if status.startswith("??"):
            if hasattr(self, "diff_scope_combo"):
                self.diff_scope_combo.configure(state="disabled")
            self.diff_scope_var.set("Unstaged")
            return "untracked"
        has_staged = status[0] not in (" ", "?")
        has_unstaged = status[1] not in (" ", "?")
        requested = self.diff_scope_var.get()
        if requested == "Staged" and has_staged:
            scope = "staged"
        elif requested == "Unstaged" and has_unstaged:
            scope = "unstaged"
        elif has_unstaged:
            scope = "unstaged"
        elif has_staged:
            scope = "staged"
        else:
            scope = "unstaged"
        if hasattr(self, "diff_scope_combo"):
            if has_staged and has_unstaged:
                self.diff_scope_combo.configure(state="readonly")
            else:
                self.diff_scope_combo.configure(state="disabled")
        self.diff_scope_var.set("Staged" if scope == "staged" else "Unstaged")
        return scope

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

    def _render_worktree_diff(self, diff_text: str, word_diff: bool) -> None:
        render_patch_to_widget(
            self.worktree_diff_text,
            diff_text,
            read_only=True,
            show_file_headers=False,
            word_diff=word_diff,
        )
        if word_diff or not self.worktree_diff_data:
            self.worktree_line_map.clear()
            return
        self.worktree_line_map = build_line_map(self.worktree_diff_data)

    def _clear_worktree_selection_highlight(self) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        self.worktree_diff_text.tag_remove("selected_hunk", "1.0", tk.END)
        self.worktree_diff_text.tag_remove("selected_line", "1.0", tk.END)

    def _highlight_selected_diff_line(self, line_info: DiffLineInfo) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        self._clear_worktree_selection_highlight()
        for line_no, info in self.worktree_line_map.items():
            if info.hunk_index == line_info.hunk_index:
                self.worktree_diff_text.tag_add("selected_hunk", f"{line_no}.0", f"{line_no}.end")
        self.worktree_diff_text.tag_add("selected_line", f"{line_info.line_no}.0", f"{line_info.line_no}.end")

    def _get_diff_line_info_from_event(self, event: tk.Event) -> DiffLineInfo | None:
        if not self.worktree_line_map:
            return None
        try:
            index = self.worktree_diff_text.index(f"@{event.x},{event.y}")
            line_no = int(index.split(".")[0])
        except (tk.TclError, ValueError):
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
        if self.diff_click_job is not None:
            try:
                self.after_cancel(self.diff_click_job)
            except tk.TclError:
                pass
            self.diff_click_job = None
        line_info = self._get_diff_line_info_from_event(event)
        if not line_info:
            return "break"
        self._highlight_selected_diff_line(line_info)
        self.diff_click_line_no = line_info.line_no
        self.diff_click_job = self.after(220, self._execute_worktree_line_click)
        return "break"

    def _on_worktree_diff_double_click(self, event: tk.Event) -> str:
        if self.diff_click_job is not None:
            try:
                self.after_cancel(self.diff_click_job)
            except tk.TclError:
                pass
            self.diff_click_job = None
        line_info = self._get_diff_line_info_from_event(event)
        if not line_info:
            return "break"
        self._highlight_selected_diff_line(line_info)
        self.worktree_diff_text.mark_set(tk.INSERT, f"{line_info.line_no}.0")
        self._remember_status_focus_from_selection()
        if self._word_diff_enabled():
            self._set_status("Desative Diff por palavra para stage/unstage por hunk.")
            return "break"
        if self.worktree_diff_scope == "unstaged":
            self._stage_selected_hunk()
        elif self.worktree_diff_scope == "staged":
            self._unstage_selected_hunk()
        elif self.worktree_diff_scope == "untracked":
            selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
            if selected:
                entry = self.status_items.get(selected[-1])
                if entry is not None:
                    self._toggle_status_entry_stage(entry)
        return "break"

    def _execute_worktree_line_click(self) -> None:
        self.diff_click_job = None
        line_no = self.diff_click_line_no
        self.diff_click_line_no = 0
        if line_no <= 0:
            return
        line_info = self.worktree_line_map.get(line_no)
        if not line_info:
            return
        self.worktree_diff_text.mark_set(tk.INSERT, f"{line_info.line_no}.0")
        self._remember_status_focus_from_selection()
        if self._word_diff_enabled():
            self._set_status("Desative Diff por palavra para stage/unstage por linha.")
            return
        if self.worktree_diff_scope == "unstaged":
            self._stage_selected_line()
            return
        if self.worktree_diff_scope == "staged":
            self._unstage_selected_line()
            return
        if self.worktree_diff_scope == "untracked":
            selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
            if not selected:
                return
            entry = self.status_items.get(selected[-1])
            if entry is None:
                return
            self._toggle_status_entry_stage(entry)
            return

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
        result = subprocess.run(
            cmd,
            input=patch,
            text=True,
            capture_output=True,
        )
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
        self._refresh_status()
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
        self._refresh_status()
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
        self._refresh_status()
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
        self._refresh_status()
        self._update_worktree_diff_from_selection()

    def _update_worktree_diff_actions(self) -> None:
        if not hasattr(self, "diff_interaction_hint_var"):
            return
        if not self.worktree_diff_data:
            self.diff_interaction_hint_var.set("Selecione um arquivo para usar stage/unstage por clique.")
            return
        if self._word_diff_enabled():
            self.diff_interaction_hint_var.set("Desative Diff por palavra para stage/unstage por linha e hunk.")
            return
        if self.worktree_diff_scope == "unstaged":
            self.diff_interaction_hint_var.set("Clique: stage linha | duplo clique: stage hunk.")
            return
        if self.worktree_diff_scope == "staged":
            self.diff_interaction_hint_var.set("Clique: unstage linha | duplo clique: unstage hunk.")
            return
        if self.worktree_diff_scope == "untracked":
            self.diff_interaction_hint_var.set("Clique no diff para stagear o arquivo inteiro.")
            return
        self.diff_interaction_hint_var.set("")

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
            staged = status[0] != " " and status[0] != "?"
            entries.append(
                {
                    "status": status,
                    "path": path,
                    "path_for_git": path_for_git,
                    "staged": staged,
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
        self._refresh_status()
        self._reload_commits()
        if self._is_dirty():
            self._set_status("Commit criado, mas ainda há alterações locais.")
        return True

    def _commit_and_push(self) -> None:
        if not self._fetch_repo_internal(show_errors=True):
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
        try:
            run_git(self.repo_path, ["reset", reset_flag, "HEAD~1"])
        except RuntimeError as exc:
            messagebox.showerror("Undo commit", str(exc))
            return False
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._refresh_status()
        self._reload_commits()
        self._refresh_branches()
        self._update_pull_push_labels()
        self._set_status(f"Último commit desfeito ({mode}).")
        return True

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

    def _refresh_commit_branch_quick_selector(self, branches: list[str], current: str) -> None:
        if not hasattr(self, "commit_branch_quick_combo"):
            return
        if not self.repo_ready or not branches:
            self.commit_branch_quick_combo.configure(values=[], state="disabled")
            if hasattr(self, "commit_branch_quick_var"):
                self.commit_branch_quick_var.set("")
            return
        self.commit_branch_quick_combo.configure(values=branches, state="readonly")
        if current and current in branches:
            self.commit_branch_quick_var.set(current)
            return
        selected = self.commit_branch_quick_var.get().strip()
        if selected in branches:
            return
        self.commit_branch_quick_var.set(branches[0])

    def _on_commit_quick_branch_selected(self, _event: tk.Event) -> None:
        if not self.repo_ready:
            return
        target = self.commit_branch_quick_var.get().strip()
        if not target:
            return
        current = self.branch_var.get().strip() if hasattr(self, "branch_var") else ""
        if target == current:
            return
        if not self._checkout_to_branch(target):
            self._refresh_commit_branch_quick_selector(self.branch_list, current)

    def _create_commit_quick_branch(self) -> None:
        base = self.commit_branch_quick_var.get().strip() if hasattr(self, "commit_branch_quick_var") else ""
        self._prompt_create_branch(base)
