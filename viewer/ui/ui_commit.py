#!/usr/bin/env python3
from __future__ import annotations

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
        status_frame.grid_columnconfigure(2, weight=0)
        status_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(status_frame, text="Arquivos em aberto:").grid(row=0, column=0, sticky="w")
        self.stage_count_var = tk.StringVar(value="Selecionados: 0/0")
        ttk.Label(status_frame, textvariable=self.stage_count_var).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(status_frame, text="Atualizar status", command=self._refresh_status).grid(
            row=0,
            column=2,
            sticky="e",
            padx=(8, 0),
        )

        self.status_listbox = tk.Listbox(
            status_frame,
            selectmode="extended",
            exportselection=False,
            font="TkFixedFont",
        )
        self.status_listbox.grid(row=1, column=0, sticky="nsew")

        status_scroll = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_listbox.yview)
        status_scroll.grid(row=1, column=1, sticky="ns")
        self.status_listbox.configure(yscrollcommand=status_scroll.set)
        self.status_listbox.bind("<<ListboxSelect>>", self._on_status_select)
        self.status_listbox.bind("<Double-Button-1>", self._open_status_file_in_vscode)

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
        self.worktree_diff_text.configure(font="TkFixedFont")
        self.worktree_diff_text.configure(state="disabled")

        hunk_actions = ttk.Frame(diff_frame)
        hunk_actions.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.stage_hunk_button = ttk.Button(hunk_actions, text="Stage hunk", command=self._stage_selected_hunk)
        self.stage_hunk_button.grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        self.unstage_hunk_button = ttk.Button(hunk_actions, text="Unstage hunk", command=self._unstage_selected_hunk)
        self.unstage_hunk_button.grid(
            row=0,
            column=1,
            padx=(0, 6),
        )
        self.stage_line_button = ttk.Button(hunk_actions, text="Stage linha", command=self._stage_selected_line)
        self.stage_line_button.grid(
            row=0,
            column=2,
            padx=(0, 6),
        )
        self.unstage_line_button = ttk.Button(hunk_actions, text="Unstage linha", command=self._unstage_selected_line)
        self.unstage_line_button.grid(
            row=0,
            column=3,
        )

        paned.add(left_column, weight=1)
        paned.add(diff_frame, weight=2)

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self.branch_tab, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, sticky="w", padx=8, pady=(6, 8))

        self.status_items: dict[str, dict[str, str | bool]] = {}
        self._refresh_branches()
        self._refresh_status()

    def _refresh_status(self) -> None:
        if not self.repo_ready:
            return
        start = self._perf_start("Atualizar status")
        self.status_listbox.delete(0, tk.END)
        self.status_items.clear()
        self.status_headers: set[int] = set()

        try:
            entries = self._get_status_entries()
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            self._perf_end("Atualizar status", start)
            return

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
            self.stage_count_var.set(f"Selecionados: {staged_count}/{total}")
        self._sync_selection_to_staged()
        self._update_worktree_diff_from_selection()
        self._update_operation_preview()
        if hasattr(self, "_refresh_repo_status_panel"):
            self._refresh_repo_status_panel()
        self._perf_end("Atualizar status", start)

    def _sync_selection_to_staged(self) -> None:
        if self.suspend_stage_sync:
            return
        self.suspend_stage_sync = True
        self.status_listbox.selection_clear(0, tk.END)
        for index, entry in self.status_items.items():
            if entry.get("staged"):
                self.status_listbox.selection_set(index)
        self.suspend_stage_sync = False

    def _on_status_select(self, _event: tk.Event) -> None:
        if self.suspend_stage_sync:
            return
        selected = set(self.status_listbox.curselection())
        file_selected = [index for index in selected if index in self.status_items]
        if len(file_selected) != len(selected):
            self.suspend_stage_sync = True
            self.status_listbox.selection_clear(0, tk.END)
            for index in file_selected:
                self.status_listbox.selection_set(index)
            self.suspend_stage_sync = False
            if not file_selected:
                self._sync_selection_to_staged()
                return
        self._update_worktree_diff_from_selection()
        if self.stage_sync_job is not None:
            try:
                self.after_cancel(self.stage_sync_job)
            except tk.TclError:
                pass
        self.stage_sync_job = self.after(50, self._apply_stage_from_selection)

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
        if self.status_listbox.size() == 0:
            return
        index = self.status_listbox.nearest(event.y)
        if index >= self.status_listbox.size():
            return
        entry = self.status_items.get(index)
        if not entry:
            return
        path = str(entry.get("path_for_git") or entry.get("path") or "").strip()
        if not path:
            return
        self._open_repo_file_in_vscode(path)

    def _apply_stage_from_selection(self) -> None:
        self.stage_sync_job = None
        selected = set(self.status_listbox.curselection())
        add_paths: list[str] = []
        reset_paths: list[str] = []
        for index, entry in self.status_items.items():
            staged = bool(entry["staged"])
            selected_now = index in selected
            path_for_git = str(entry["path_for_git"])
            if selected_now and not staged:
                add_paths.append(path_for_git)
            elif not selected_now and staged:
                reset_paths.append(path_for_git)
        try:
            for path in add_paths:
                run_git(self.repo_path, ["add", "--", path])
            for path in reset_paths:
                run_git(self.repo_path, ["reset", "--", path])
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self._refresh_status()

    def _update_worktree_diff_from_selection(self) -> None:
        if not hasattr(self, "worktree_diff_text"):
            return
        selected = [index for index in self.status_listbox.curselection() if index in self.status_items]
        if not selected:
            self._set_text(self.worktree_diff_text, "Selecione um arquivo para ver o diff.")
            self.worktree_diff_data = None
            self.worktree_line_map.clear()
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
            self._update_worktree_diff_actions()
            return
        self.worktree_diff_data = parse_diff_data(diff_raw)
        self.worktree_diff_scope = scope
        self.worktree_line_map.clear()
        self._render_worktree_diff(diff_view, self._word_diff_enabled())
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
        args = ["diff", "--unified=0"]
        if word_diff:
            args.append("--word-diff=plain")
        if scope == "staged":
            args.append("--cached")
        args.extend(["--", path])
        return run_git(self.repo_path, args)

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
        if not hasattr(self, "stage_hunk_button"):
            return
        disabled = "disabled"
        enabled = "normal"
        if not self.worktree_diff_data:
            self.stage_hunk_button.configure(state=disabled)
            self.unstage_hunk_button.configure(state=disabled)
            self.stage_line_button.configure(state=disabled)
            self.unstage_line_button.configure(state=disabled)
            return
        if self._word_diff_enabled():
            self.stage_hunk_button.configure(state=disabled)
            self.unstage_hunk_button.configure(state=disabled)
            self.stage_line_button.configure(state=disabled)
            self.unstage_line_button.configure(state=disabled)
            return
        if self.worktree_diff_scope == "unstaged":
            self.stage_hunk_button.configure(state=enabled)
            self.stage_line_button.configure(state=enabled)
            self.unstage_hunk_button.configure(state=disabled)
            self.unstage_line_button.configure(state=disabled)
        elif self.worktree_diff_scope == "staged":
            self.stage_hunk_button.configure(state=disabled)
            self.stage_line_button.configure(state=disabled)
            self.unstage_hunk_button.configure(state=enabled)
            self.unstage_line_button.configure(state=enabled)
        else:
            self.stage_hunk_button.configure(state=disabled)
            self.unstage_hunk_button.configure(state=disabled)
            self.stage_line_button.configure(state=disabled)
            self.unstage_line_button.configure(state=disabled)

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
        if self.stage_sync_job is not None:
            try:
                self.after_cancel(self.stage_sync_job)
            except tk.TclError:
                pass
            self.stage_sync_job = None
        self._apply_stage_from_selection()
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
