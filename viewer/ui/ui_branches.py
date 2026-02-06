#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..core.diff_utils import render_patch_to_widget
from ..core.git_client import run_git


class BranchesTabMixin:
    def _build_branches_tab(self) -> None:
        self.branches_tab.grid_columnconfigure(0, weight=1)
        self.branches_tab.grid_rowconfigure(4, weight=1)

        selection_frame = ttk.Frame(self.branches_tab)
        selection_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        selection_frame.grid_columnconfigure(1, weight=1)
        selection_frame.grid_columnconfigure(3, weight=1)

        ttk.Label(selection_frame, text="Origem:").grid(row=0, column=0, sticky="w")
        origin_var = getattr(self, "branch_origin_var", None)
        if origin_var is None:
            origin_var = tk.StringVar()
            self.branch_origin_var = origin_var
        self.compare_origin_combo = ttk.Combobox(
            selection_frame,
            textvariable=origin_var,
            state="readonly",
            width=24,
        )
        self.compare_origin_combo.grid(row=0, column=1, sticky="w", padx=(6, 12))
        self.compare_origin_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_branch_comparison())

        ttk.Label(selection_frame, text="Destino:").grid(row=0, column=2, sticky="w")
        dest_var = getattr(self, "branch_dest_var", None)
        if dest_var is None:
            dest_var = tk.StringVar()
            self.branch_dest_var = dest_var
        self.compare_dest_combo = ttk.Combobox(
            selection_frame,
            textvariable=dest_var,
            state="readonly",
            width=24,
        )
        self.compare_dest_combo.grid(row=0, column=3, sticky="w", padx=(6, 12))
        self.compare_dest_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_branch_comparison())

        ttk.Button(selection_frame, text="Comparar", command=self._refresh_branch_comparison).grid(
            row=0,
            column=4,
            sticky="e",
        )

        action_frame = ttk.Frame(self.branches_tab)
        action_frame.grid(row=1, column=0, sticky="ew", padx=8)
        action_frame.grid_columnconfigure(5, weight=1)

        ttk.Label(action_frame, text="Ação:").grid(row=0, column=0, sticky="w")
        self.branch_action_var = tk.StringVar(value="Merge")
        self.branch_action_combo = ttk.Combobox(
            action_frame,
            textvariable=self.branch_action_var,
            state="readonly",
            width=12,
            values=["Merge", "Rebase", "Squash merge"],
        )
        self.branch_action_combo.grid(row=0, column=1, sticky="w", padx=(6, 12))
        self.branch_action_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_operation_preview())

        ttk.Label(action_frame, text="Mensagem (squash):").grid(row=0, column=2, sticky="w")
        self.branch_message_var = tk.StringVar()
        self.branch_message_entry = ttk.Entry(action_frame, textvariable=self.branch_message_var, width=28)
        self.branch_message_entry.grid(row=0, column=3, sticky="w", padx=(6, 12))
        self.branch_message_entry.bind("<KeyRelease>", lambda _e: self._update_operation_preview())

        self.branch_action_button = ttk.Button(action_frame, text="Executar", command=self._run_branch_action)
        self.branch_action_button.grid(row=0, column=4, sticky="w")
        self.branch_action_button.bind("<Enter>", self._show_action_hint)
        self.branch_action_button.bind("<Leave>", self._hide_action_hint)

        self.branch_action_status = ttk.Label(self.branches_tab, text="")
        self.branch_action_status.grid(row=2, column=0, sticky="w", padx=8, pady=(6, 0))
        self.branch_action_status.bind("<Enter>", self._show_action_hint)
        self.branch_action_status.bind("<Leave>", self._hide_action_hint)

        self.compare_status_var = tk.StringVar(value="Selecione as branches para comparar.")
        self.compare_status_label = ttk.Label(self.branches_tab, textvariable=self.compare_status_var)
        self.compare_status_label.grid(row=3, column=0, sticky="w", padx=8, pady=(2, 6))

        paned = ttk.PanedWindow(self.branches_tab, orient="horizontal")
        paned.grid(row=4, column=0, sticky="nsew", padx=8, pady=(0, 8))

        commits_frame = ttk.Frame(paned)
        commits_frame.grid_columnconfigure(0, weight=1)
        commits_frame.grid_rowconfigure(1, weight=1)
        ttk.Label(commits_frame, text="Commits a aplicar (origem → destino)").grid(
            row=0, column=0, sticky="w"
        )
        self.compare_commits_listbox = tk.Listbox(commits_frame, height=10, activestyle="dotbox")
        self.compare_commits_listbox.grid(row=1, column=0, sticky="nsew")
        commits_scroll = ttk.Scrollbar(commits_frame, orient="vertical", command=self.compare_commits_listbox.yview)
        commits_scroll.grid(row=1, column=1, sticky="ns")
        self.compare_commits_listbox.configure(yscrollcommand=commits_scroll.set)
        paned.add(commits_frame, weight=1)

        diff_frame = ttk.Frame(paned)
        diff_frame.grid_columnconfigure(0, weight=1)
        diff_frame.grid_rowconfigure(2, weight=1)

        files_header = ttk.Frame(diff_frame)
        files_header.grid(row=0, column=0, sticky="ew")
        files_header.grid_columnconfigure(0, weight=1)
        ttk.Label(files_header, text="Arquivos alterados").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            files_header,
            text="Diff por palavra",
            variable=self.word_diff_var,
            command=self._toggle_word_diff,
        ).grid(row=0, column=1, sticky="e")
        ttk.Checkbutton(
            files_header,
            text="Modo leitura",
            variable=self.read_mode_var,
            command=self._toggle_read_mode,
        ).grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.compare_read_mode_var = tk.StringVar(value="")
        ttk.Label(files_header, textvariable=self.compare_read_mode_var).grid(
            row=0, column=3, sticky="e", padx=(8, 0)
        )

        self.compare_files_listbox = tk.Listbox(diff_frame, height=8, activestyle="dotbox")
        self.compare_files_listbox.grid(row=1, column=0, sticky="nsew")
        self.compare_files_listbox.bind("<<ListboxSelect>>", self._on_compare_file_select)
        self.compare_files_listbox.bind("<Double-Button-1>", self._open_compare_file_in_vscode)
        files_scroll = ttk.Scrollbar(diff_frame, orient="vertical", command=self.compare_files_listbox.yview)
        files_scroll.grid(row=1, column=1, sticky="ns")
        self.compare_files_listbox.configure(yscrollcommand=files_scroll.set)

        self.compare_diff_text = tk.Text(diff_frame, wrap="none")
        self.compare_diff_text.grid(row=2, column=0, sticky="nsew")
        diff_scroll = ttk.Scrollbar(diff_frame, orient="vertical", command=self.compare_diff_text.yview)
        diff_scroll.grid(row=2, column=1, sticky="ns")
        self.compare_diff_text.configure(yscrollcommand=diff_scroll.set)
        self.compare_diff_text.configure(font="TkFixedFont")
        self.compare_diff_text.configure(state="disabled")
        palette = getattr(self, "theme_palette", None)
        if palette and hasattr(self, "_apply_text_widget_theme"):
            self._apply_text_widget_theme(self.compare_diff_text, palette)
            self._apply_diff_tags(self.compare_diff_text, palette)
        if palette and hasattr(self, "_apply_listbox_theme"):
            self._apply_listbox_theme(self.compare_files_listbox, palette)
        paned.add(diff_frame, weight=2)

        self.compare_file_stats_by_index: dict[int, dict[str, object]] = {}

    def _update_branch_action_branches(self) -> None:
        if not hasattr(self, "compare_origin_combo"):
            return
        if not self.repo_ready:
            self.compare_origin_combo.configure(values=[], state="disabled")
            self.compare_dest_combo.configure(values=[], state="disabled")
            return
        values = list(self.branch_list)
        self.compare_origin_combo.configure(values=values, state="readonly")
        self.compare_dest_combo.configure(values=values, state="readonly")

        current = self._get_current_branch()
        if not self.branch_dest_var.get() or self.branch_dest_var.get() not in values:
            if current in values:
                self.branch_dest_var.set(current)
            elif values:
                self.branch_dest_var.set(values[0])
            else:
                self.branch_dest_var.set("")

        origin = self.branch_origin_var.get()
        if not origin or origin not in values or origin == self.branch_dest_var.get():
            fallback = next((item for item in values if item != self.branch_dest_var.get()), "")
            self.branch_origin_var.set(fallback)

        self._refresh_branch_comparison()

    def _refresh_branch_comparison(self) -> None:
        if not hasattr(self, "compare_commits_listbox"):
            return
        start = self._perf_start("Comparar branches")
        if not self.repo_ready:
            self._clear_branch_comparison("Selecione um repositório.")
            self._perf_end("Comparar branches", start)
            return
        origin = self.branch_origin_var.get().strip()
        dest = self.branch_dest_var.get().strip()
        if not origin or not dest:
            self._clear_branch_comparison("Selecione origem e destino.")
            self._perf_end("Comparar branches", start)
            return
        if origin == dest:
            self._clear_branch_comparison("Origem e destino devem ser diferentes.")
            self._perf_end("Comparar branches", start)
            return

        commits = self._load_compare_commits(origin, dest)
        stats, totals = self._load_compare_file_stats(origin, dest)
        self._render_compare_commits(commits)
        self._render_compare_files(stats)
        self._update_compare_status(origin, dest, commits, totals)
        self._update_operation_preview()
        self._perf_end("Comparar branches", start)

    def _clear_branch_comparison(self, message: str) -> None:
        if hasattr(self, "compare_commits_listbox"):
            self.compare_commits_listbox.delete(0, tk.END)
        if hasattr(self, "compare_files_listbox"):
            self.compare_files_listbox.delete(0, tk.END)
        if hasattr(self, "compare_diff_text"):
            self._set_text(self.compare_diff_text, "")
        if hasattr(self, "compare_status_var"):
            self.compare_status_var.set(message)
        self.compare_file_stats_by_index.clear()

    def _load_compare_commits(self, origin: str, dest: str) -> list[str]:
        try:
            output = run_git(self.repo_path, ["log", "--oneline", f"{dest}..{origin}"])
        except RuntimeError as exc:
            messagebox.showerror("Comparar", str(exc))
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _load_compare_file_stats(self, origin: str, dest: str) -> tuple[list[dict[str, object]], dict[str, int]]:
        try:
            output = run_git(self.repo_path, ["diff", "--numstat", f"{dest}...{origin}"])
        except RuntimeError as exc:
            messagebox.showerror("Comparar", str(exc))
            return [], {"files": 0, "added": 0, "deleted": 0, "binary": 0}
        stats: list[dict[str, object]] = []
        totals = {"files": 0, "added": 0, "deleted": 0, "binary": 0}
        for raw in output.splitlines():
            if not raw.strip():
                continue
            parts = raw.split("\t", 2)
            if len(parts) < 3:
                continue
            added_raw, deleted_raw, path = parts
            is_binary = added_raw == "-" or deleted_raw == "-"
            added = 0 if is_binary else int(added_raw)
            deleted = 0 if is_binary else int(deleted_raw)
            stats.append(
                {
                    "path": path,
                    "added": added,
                    "deleted": deleted,
                    "binary": is_binary,
                }
            )
            totals["files"] += 1
            totals["added"] += added
            totals["deleted"] += deleted
            if is_binary:
                totals["binary"] += 1
        return stats, totals

    def _render_compare_commits(self, commits: list[str]) -> None:
        self.compare_commits_listbox.delete(0, tk.END)
        for line in commits:
            self.compare_commits_listbox.insert(tk.END, line)

    def _render_compare_files(self, stats: list[dict[str, object]]) -> None:
        self.compare_files_listbox.delete(0, tk.END)
        self.compare_file_stats_by_index.clear()
        for idx, entry in enumerate(stats):
            path = str(entry["path"])
            if entry["binary"]:
                label = f"{path} (bin)"
            else:
                label = f"{path} (+{entry['added']}/-{entry['deleted']})"
            self.compare_files_listbox.insert(tk.END, label)
            self.compare_file_stats_by_index[idx] = entry
        if stats:
            self.compare_files_listbox.selection_set(0)
            self._show_compare_diff_for_index(0)
        else:
            self._set_text(self.compare_diff_text, "(nenhuma diferença)")

    def _update_compare_status(
        self,
        origin: str,
        dest: str,
        commits: list[str],
        totals: dict[str, int],
    ) -> None:
        if not hasattr(self, "compare_status_var"):
            return
        summary = (
            f"{origin} → {dest} | Commits: {len(commits)} | Arquivos: {totals['files']} | "
            f"+{totals['added']}/-{totals['deleted']}"
        )
        if totals["binary"]:
            summary = f"{summary} | Binários: {totals['binary']}"
        self.compare_status_var.set(summary)

    def _on_compare_file_select(self, _event: tk.Event) -> None:
        selection = self.compare_files_listbox.curselection()
        if not selection:
            return
        self._show_compare_diff_for_index(selection[0])

    def _open_compare_file_in_vscode(self, event: tk.Event) -> None:
        if self.compare_files_listbox.size() == 0:
            return
        index = self.compare_files_listbox.nearest(event.y)
        if index >= self.compare_files_listbox.size():
            return
        entry = self.compare_file_stats_by_index.get(index)
        if not entry:
            return
        path = str(entry.get("path", "")).strip()
        if not path:
            return
        self._open_repo_file_in_vscode(path)

    def _show_compare_diff_for_index(self, index: int) -> None:
        entry = self.compare_file_stats_by_index.get(index)
        if not entry:
            return
        if entry.get("binary"):
            self._set_text(self.compare_diff_text, "Arquivo binário: sem diff disponível.")
            if hasattr(self, "compare_read_mode_var"):
                self.compare_read_mode_var.set("")
            return
        origin = self.branch_origin_var.get().strip()
        dest = self.branch_dest_var.get().strip()
        if not origin or not dest:
            self._set_text(self.compare_diff_text, "Selecione origem e destino.")
            if hasattr(self, "compare_read_mode_var"):
                self.compare_read_mode_var.set("")
            return
        path = str(entry.get("path", "")).strip()
        if not path:
            return
        args = ["diff", "--unified=0"]
        if self._word_diff_enabled():
            args.append("--word-diff=plain")
        args.append(f"{dest}...{origin}")
        args.extend(["--", path])
        cache = getattr(self, "compare_diff_cache", None)
        token = getattr(self, "repo_state_token", 0)
        cache_key = (token, origin, dest, path, self._word_diff_enabled())
        if cache is not None and cache_key in cache:
            diff_output = cache[cache_key]
        else:
            try:
                diff_output = run_git(self.repo_path, args)
            except RuntimeError as exc:
                messagebox.showerror("Comparar", str(exc))
                return
            if cache is not None:
                cache[cache_key] = diff_output
        display_diff, truncated, shown, total = self._apply_read_mode_to_diff(diff_output)
        render_patch_to_widget(
            self.compare_diff_text,
            display_diff,
            read_only=True,
            show_file_headers=False,
            word_diff=self._word_diff_enabled(),
        )
        if hasattr(self, "compare_read_mode_var"):
            if truncated:
                self.compare_read_mode_var.set(f"Modo leitura: {shown}/{total} linhas")
            else:
                self.compare_read_mode_var.set("")

    def _refresh_compare_diff(self) -> None:
        if not hasattr(self, "compare_files_listbox"):
            return
        selection = self.compare_files_listbox.curselection()
        if not selection:
            return
        self._show_compare_diff_for_index(selection[0])

    def _update_operation_preview(self) -> None:
        if not hasattr(self, "branch_action_status"):
            return
        if not self.repo_ready:
            self.branch_action_status.configure(text="Selecione um repositório.")
            self.branch_action_button.configure(state="disabled")
            return
        dest = self.branch_dest_var.get().strip()
        origin = self.branch_origin_var.get().strip()
        if not origin or not dest:
            self.branch_action_status.configure(text="Selecione origem e destino.")
            self.branch_action_button.configure(state="disabled")
            return
        if origin == dest:
            self.branch_action_status.configure(text="Origem e destino devem ser diferentes.")
            self.branch_action_button.configure(state="disabled")
            return
        if self._is_dirty():
            self.branch_action_status.configure(text="Working tree sujo. Veja a aba Commit.")
            self.branch_action_button.configure(state="disabled")
            return
        behind, ahead = self._get_ahead_behind_between(origin, dest)
        conflict = self._has_potential_conflict(origin, dest)
        conflict_label = "Conflito: sim" if conflict else "Conflito: não"
        status_text = f"{origin} → {dest} | Ahead: {ahead} | Behind: {behind} | {conflict_label}"
        self.branch_action_status.configure(text=status_text)
        action = self.branch_action_var.get()
        if action == "Squash merge" and not self.branch_message_var.get().strip():
            self.branch_action_button.configure(state="disabled")
        else:
            self.branch_action_button.configure(state="normal")

    def _get_ahead_behind_between(self, origin: str, dest: str) -> tuple[int, int]:
        try:
            output = run_git(self.repo_path, ["rev-list", "--left-right", "--count", f"{origin}...{dest}"])
        except RuntimeError:
            return 0, 0
        parts = output.strip().split()
        if len(parts) != 2:
            return 0, 0
        behind = int(parts[0])
        ahead = int(parts[1])
        return behind, ahead

    def _has_potential_conflict(self, origin: str, dest: str) -> bool:
        try:
            base = run_git(self.repo_path, ["merge-base", dest, origin]).strip()
            output = run_git(self.repo_path, ["merge-tree", base, dest, origin])
        except RuntimeError:
            return False
        return "<<<<<<<" in output

    def _run_branch_action(self) -> None:
        if not self.repo_ready:
            return
        origin = self.branch_origin_var.get().strip()
        dest = self.branch_dest_var.get().strip()
        if not origin or not dest:
            messagebox.showwarning("Ação", "Selecione a branch de origem e destino.")
            return
        if origin == dest:
            messagebox.showwarning("Ação", "Origem e destino devem ser diferentes.")
            return
        if self._is_dirty():
            messagebox.showwarning("Ação", "Working tree sujo. Faça stash/commit antes.")
            return
        action = self.branch_action_var.get()
        if action == "Squash merge":
            message = self.branch_message_var.get().strip()
            if not message:
                messagebox.showwarning("Squash", "Mensagem obrigatória para squash.")
                return
        if not self._confirm_branch_action(origin, dest, action):
            return
        if not self._checkout_to_branch(dest):
            return
        try:
            if action == "Merge":
                run_git(self.repo_path, ["merge", origin])
            elif action == "Rebase":
                run_git(self.repo_path, ["rebase", origin])
            else:
                run_git(self.repo_path, ["merge", "--squash", origin])
                run_git(self.repo_path, ["commit", "-m", message])
        except RuntimeError as exc:
            messagebox.showerror("Ação", str(exc))
            self._show_conflicts_window()
            return
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        self._reload_commits()
        self._refresh_status()
        self._refresh_branches()
        self._update_pull_push_labels()
        self._refresh_branch_comparison()

    def _confirm_branch_action(self, origin: str, dest: str, action: str) -> bool:
        commits = self._load_compare_commits(origin, dest)
        stats, totals = self._load_compare_file_stats(origin, dest)
        behind, ahead = self._get_ahead_behind_between(origin, dest)
        conflict = self._has_potential_conflict(origin, dest)

        dialog = tk.Toplevel(self)
        dialog.title("Confirmar ação")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(3, weight=1)

        header = ttk.Frame(dialog)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(header, text=f"Ação: {action}").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=f"Origem: {origin}").grid(row=1, column=0, sticky="w")
        ttk.Label(header, text=f"Destino: {dest}").grid(row=2, column=0, sticky="w")

        summary_lines = [
            f"Commits da origem: {behind}",
            f"Commits locais: {ahead}",
            f"Arquivos: {totals['files']} | +{totals['added']}/-{totals['deleted']}",
        ]
        if totals["binary"]:
            summary_lines.append(f"Binários: {totals['binary']}")
        summary_text = " | ".join(summary_lines)
        ttk.Label(dialog, text=summary_text).grid(row=1, column=0, sticky="w", padx=12)

        warnings: list[str] = []
        if behind == 0 and not commits:
            warnings.append("Nenhuma mudança da origem para aplicar.")
        if conflict:
            warnings.append("Conflito potencial detectado.")
        if action == "Rebase" and ahead > 0:
            warnings.append(f"Rebase vai reescrever {ahead} commit(s) locais.")
        if action == "Merge" and ahead > 0:
            warnings.append("Merge criará commit de merge (há commits locais).")
        if action == "Squash merge" and behind > 0:
            warnings.append("Squash irá agrupar commits em um único commit.")

        if warnings:
            warn_text = "\n".join(f"- {item}" for item in warnings)
            warn_label = ttk.Label(dialog, text=warn_text, foreground="#b42318", justify="left")
            warn_label.grid(row=2, column=0, sticky="w", padx=12, pady=(6, 0))

        list_frame = ttk.Frame(dialog)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(8, 0))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(list_frame, text="Commits a incorporar:").grid(row=0, column=0, sticky="w")
        commit_text = tk.Text(list_frame, height=10, wrap="none")
        commit_text.grid(row=1, column=0, sticky="nsew")
        commit_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=commit_text.yview)
        commit_scroll.grid(row=1, column=1, sticky="ns")
        commit_text.configure(yscrollcommand=commit_scroll.set)
        if commits:
            commit_text.insert(tk.END, "\n".join(commits))
        else:
            commit_text.insert(tk.END, "(nenhum)")
        commit_text.configure(state="disabled")

        result = {"confirmed": False}

        def confirm() -> None:
            result["confirmed"] = True
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        actions = ttk.Frame(dialog)
        actions.grid(row=4, column=0, sticky="e", padx=12, pady=12)
        ttk.Button(actions, text="Cancelar", command=cancel).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Continuar", command=confirm).grid(row=0, column=1)

        dialog.wait_window()
        return bool(result["confirmed"])

    def _show_action_hint(self, event: tk.Event) -> None:
        if not self.repo_ready:
            return
        try:
            is_dirty = self._is_dirty()
        except RuntimeError:
            return
        if not is_dirty:
            return
        if getattr(self, "action_hint_window", None) is not None:
            return
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.attributes("-topmost", True)
        label = tk.Label(
            tooltip,
            text="Working tree sujo. Veja a aba Commit.",
            background="#fff8dc",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=4,
        )
        label.pack()

        x = event.x_root + 12
        y = event.y_root + 12
        tooltip.wm_geometry(f"+{x}+{y}")
        self.action_hint_window = tooltip

    def _hide_action_hint(self, _event: tk.Event) -> None:
        tooltip = getattr(self, "action_hint_window", None)
        if tooltip is not None:
            tooltip.destroy()
            self.action_hint_window = None
