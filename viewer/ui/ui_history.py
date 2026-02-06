#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..core.diff_utils import render_patch_to_widget
from ..core.git_client import is_git_repo, load_commit_details, load_commit_summaries, run_git
from ..core.models import CommitFilters, CommitInfo, CommitSummary, FileStat


LARGE_PATCH_THRESHOLD = 1000


class HistoryTabMixin:
    def _build_history_tab(self) -> None:
        self.history_tab.grid_columnconfigure(0, weight=1)
        self.history_tab.grid_columnconfigure(1, weight=3)
        self.history_tab.grid_rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self.history_tab)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        top_bar.grid_columnconfigure(0, weight=1)
        top_bar.grid_columnconfigure(1, weight=1)

        history_actions = ttk.Frame(top_bar)
        history_actions.grid(row=0, column=0, sticky="w")
        ttk.Button(history_actions, text="Cherry-pick", command=self._open_cherry_pick_window).grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        ttk.Button(history_actions, text="Importar commits", command=self._open_import_commits_window).grid(
            row=0,
            column=1,
        )

        action_frame = ttk.Frame(top_bar)
        action_frame.grid(row=0, column=1, sticky="e")

        ttk.Label(action_frame, text="Ação:").grid(row=0, column=0, sticky="w")
        self.branch_action_var = tk.StringVar(value="Merge")
        self.branch_action_combo = ttk.Combobox(
            action_frame,
            textvariable=self.branch_action_var,
            state="readonly",
            width=12,
            values=["Merge", "Rebase", "Squash merge"],
        )
        self.branch_action_combo.grid(row=0, column=1, sticky="w", padx=(4, 8))
        self.branch_action_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_operation_preview())

        ttk.Label(action_frame, text="Mensagem (squash):").grid(row=0, column=2, sticky="w")
        self.branch_message_var = tk.StringVar()
        self.branch_message_entry = ttk.Entry(action_frame, textvariable=self.branch_message_var, width=18)
        self.branch_message_entry.grid(row=0, column=3, sticky="w", padx=(4, 8))
        self.branch_message_entry.bind("<KeyRelease>", lambda _e: self._update_operation_preview())

        self.branch_action_button = ttk.Button(action_frame, text="Executar", command=self._run_branch_action)
        self.branch_action_button.grid(row=0, column=4, sticky="w")
        self.branch_action_button.bind("<Enter>", self._show_action_hint)
        self.branch_action_button.bind("<Leave>", self._hide_action_hint)

        self.branch_action_status = ttk.Label(top_bar, text="")
        self.branch_action_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.branch_action_status.bind("<Enter>", self._show_action_hint)
        self.branch_action_status.bind("<Leave>", self._hide_action_hint)

        filter_frame = ttk.LabelFrame(top_bar, text="Filtro de commits")
        filter_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        filter_frame.grid_columnconfigure(1, weight=1)
        filter_frame.grid_columnconfigure(3, weight=1)
        filter_frame.grid_columnconfigure(5, weight=1)
        filter_frame.grid_columnconfigure(7, weight=0)
        filter_frame.grid_columnconfigure(9, weight=0)

        ttk.Label(filter_frame, text="Texto:").grid(row=0, column=0, sticky="w", padx=(6, 2), pady=4)
        self.filter_text_var = tk.StringVar()
        filter_text_entry = ttk.Entry(filter_frame, textvariable=self.filter_text_var, width=22)
        filter_text_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        ttk.Label(filter_frame, text="Autor:").grid(row=0, column=2, sticky="w", padx=(0, 2), pady=4)
        self.filter_author_var = tk.StringVar()
        filter_author_entry = ttk.Entry(filter_frame, textvariable=self.filter_author_var, width=18)
        filter_author_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=4)

        ttk.Label(filter_frame, text="Arquivo:").grid(row=0, column=4, sticky="w", padx=(0, 2), pady=4)
        self.filter_path_var = tk.StringVar()
        filter_path_entry = ttk.Entry(filter_frame, textvariable=self.filter_path_var, width=24)
        filter_path_entry.grid(row=0, column=5, sticky="ew", padx=(0, 8), pady=4)

        ttk.Label(filter_frame, text="Desde:").grid(row=0, column=6, sticky="w", padx=(0, 2), pady=4)
        self.filter_since_var = tk.StringVar()
        filter_since_entry = ttk.Entry(filter_frame, textvariable=self.filter_since_var, width=12)
        filter_since_entry.grid(row=0, column=7, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(filter_frame, text="Ate:").grid(row=0, column=8, sticky="w", padx=(0, 2), pady=4)
        self.filter_until_var = tk.StringVar()
        filter_until_entry = ttk.Entry(filter_frame, textvariable=self.filter_until_var, width=12)
        filter_until_entry.grid(row=0, column=9, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(filter_frame, text="Branch:").grid(row=1, column=0, sticky="w", padx=(6, 2), pady=4)
        self.filter_branch_var = tk.StringVar(value="(todas)")
        self.filter_branch_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_branch_var,
            state="readonly",
            width=16,
            values=["(todas)"],
        )
        self.filter_branch_combo.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)
        self.filter_branch_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_commit_filters())

        ttk.Label(filter_frame, text="Tag:").grid(row=1, column=2, sticky="w", padx=(0, 2), pady=4)
        self.filter_tag_var = tk.StringVar(value="(todas)")
        self.filter_tag_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_tag_var,
            state="readonly",
            width=16,
            values=["(todas)"],
        )
        self.filter_tag_combo.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=4)
        self.filter_tag_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_commit_filters())

        ttk.Label(filter_frame, text="Status repo:").grid(row=1, column=4, sticky="w", padx=(0, 2), pady=4)
        self.filter_repo_status_var = tk.StringVar(value="Todos")
        self.filter_repo_status_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_repo_status_var,
            state="readonly",
            width=22,
            values=["Todos", "Somente limpo", "Somente com alteracoes"],
        )
        self.filter_repo_status_combo.grid(row=1, column=5, sticky="w", padx=(0, 8), pady=4)
        self.filter_repo_status_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_commit_filters())

        filter_actions = ttk.Frame(filter_frame)
        filter_actions.grid(row=1, column=8, columnspan=2, sticky="e", padx=(0, 8), pady=4)
        ttk.Button(filter_actions, text="Aplicar", command=self._apply_commit_filters).grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        ttk.Button(filter_actions, text="Limpar", command=self._clear_commit_filters).grid(
            row=0,
            column=1,
        )

        self.filter_status_var = tk.StringVar(value="Sem filtro ativo.")
        self.filter_status_label = ttk.Label(filter_frame, textvariable=self.filter_status_var)
        self.filter_status_label.grid(row=2, column=0, columnspan=10, sticky="w", padx=6, pady=(0, 6))

        for entry in (
            filter_text_entry,
            filter_author_entry,
            filter_path_entry,
            filter_since_entry,
            filter_until_entry,
        ):
            entry.bind("<Return>", lambda _e: self._apply_commit_filters())

        self.left_frame = ttk.Frame(self.history_tab)
        self.left_frame.grid(row=1, column=0, sticky="nsew")
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

        self.commit_scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=self._on_history_scrollbar)
        self.commit_scrollbar.grid(row=0, column=1, sticky="ns")
        self.commit_listbox.configure(yscrollcommand=self._on_history_yscroll)

        self._build_right_panel()

    def _build_right_panel(self) -> None:
        self.right_frame = ttk.Frame(self.history_tab)
        self.right_frame.grid(row=1, column=1, sticky="nsew")
        self.right_frame.grid_rowconfigure(3, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        top_actions = ttk.Frame(self.right_frame)
        top_actions.grid(row=0, column=0, sticky="ne", padx=8, pady=(8, 4))

        self.copy_files_button = ttk.Button(
            top_actions,
            text="Copiar lista",
            command=self._copy_files_list,
        )
        self.copy_files_button.grid(row=0, column=0, padx=(0, 6))

        self.copy_patch_button = ttk.Button(
            top_actions,
            text="Copiar patch completo",
            command=self._copy_full_patch,
        )
        self.copy_patch_button.grid(row=0, column=1, padx=(0, 6))

        self.load_patch_button = ttk.Button(
            top_actions,
            text="Carregar patch grande",
            command=self._load_full_patch_for_selected_file,
            state="disabled",
        )
        self.load_patch_button.grid(row=0, column=2)
        self.load_patch_button.grid_remove()

        self.commit_info = tk.Text(self.right_frame, height=8, wrap="word")
        self.commit_info.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        self.commit_info.configure(state="disabled")

        files_frame = ttk.Frame(self.right_frame)
        files_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        files_frame.grid_rowconfigure(1, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)
        files_frame.grid_columnconfigure(1, weight=0)

        self.files_listbox = tk.Listbox(files_frame, height=6, activestyle="dotbox")
        self.files_listbox.grid(row=1, column=0, sticky="nsew")
        self.files_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        files_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_listbox.yview)
        files_scroll.grid(row=1, column=1, sticky="ns")
        self.files_listbox.configure(yscrollcommand=files_scroll.set)

        self.file_stats_by_index: dict[int, FileStat] = {}

        patch_frame = ttk.Frame(self.right_frame)
        patch_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=(4, 8))
        patch_frame.grid_rowconfigure(1, weight=1)
        patch_frame.grid_columnconfigure(0, weight=1)

        patch_header = ttk.Frame(patch_frame)
        patch_header.grid(row=0, column=0, sticky="ew")
        patch_header.grid_columnconfigure(0, weight=1)
        ttk.Label(patch_header, text="Patch do arquivo").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            patch_header,
            text="Diff por palavra",
            variable=self.word_diff_var,
            command=self._toggle_word_diff,
        ).grid(row=0, column=1, sticky="e")

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
        self.patch_text.configure(font=("Courier New", 10))
        self.patch_text.configure(state="disabled")

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
            return
        if not self.commit_filters.is_active():
            self.filter_status_var.set("Sem filtro ativo.")
            return
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

    def _populate_commit_list(self) -> None:
        self.commit_listbox.delete(0, tk.END)
        for summary in self.commit_summaries:
            short_hash = summary.commit_hash[:7]
            self.commit_listbox.insert(tk.END, f"{short_hash} | {summary.subject}")
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
            short_hash = summary.commit_hash[:7]
            self.commit_listbox.insert(tk.END, f"{short_hash} | {summary.subject}")
        self.commit_summaries.extend(summaries)
        self.commit_offset = len(self.commit_summaries)
        if len(summaries) < self.commit_limit:
            self.no_more_commits = True

    def _load_more_commits(self) -> None:
        if not self.repo_ready or self.loading_more or self.no_more_commits:
            return
        self.loading_more = True
        more = self._load_commit_summaries(skip=self.commit_offset)
        self._append_commit_summaries(more)
        self.loading_more = False

    def _maybe_load_more(self) -> None:
        if self.loading_more or self.no_more_commits:
            return
        first, last = self.commit_listbox.yview()
        if float(last) >= 0.98:
            self._load_more_commits()

    def _on_history_scrollbar(self, *args: str) -> None:
        self.commit_listbox.yview(*args)
        self._maybe_load_more()

    def _on_history_yscroll(self, first: str, last: str) -> None:
        if hasattr(self, "commit_scrollbar"):
            self.commit_scrollbar.set(first, last)
        if float(last) >= 0.98:
            self._maybe_load_more()

    def _on_history_mousewheel(self, event: tk.Event) -> None:
        self.after(0, self._maybe_load_more)

    def _on_commit_select(self, _event: tk.Event) -> None:
        selection = self.commit_listbox.curselection()
        if not selection:
            return
        self._show_commit(selection[-1])

    def _show_commit(self, index: int) -> None:
        summary = self.commit_summaries[index]
        self.current_commit_hash = summary.commit_hash
        commit = self._get_commit_details(summary.commit_hash)
        self._set_text(self.commit_info, self._format_commit_info(commit))
        self._populate_files_list(commit)
        self.load_patch_button.configure(state="normal")
        self.load_patch_button.grid_remove()

    def _format_commit_info(self, commit: CommitInfo) -> str:
        return (
            f"Hash: {commit.commit_hash}\n"
            f"Autor: {commit.author}\n"
            f"Data: {commit.date}\n"
            f"Título: {commit.subject}\n"
            f"Descrição:\n{commit.body or '(sem descrição)'}\n"
            f"Total linhas: +{commit.total_added} -{commit.total_deleted}"
        )

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

    def _get_patch(self, commit_hash: str, path: str | None = None, word_diff: bool | None = None) -> str:
        if word_diff is None:
            word_diff = self._word_diff_enabled()
        args = ["show", "--unified=0", "--format="]
        if word_diff:
            args.append("--word-diff=plain")
        args.append(commit_hash)
        if path:
            args.extend(["--", path])
        return run_git(self.repo_path, args)

    def _on_file_select(self, _event: tk.Event) -> None:
        selection = self.files_listbox.curselection()
        if not selection:
            return
        self._show_file_patch(selection[0])

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

    def _get_commit_details(self, commit_hash: str) -> CommitInfo:
        cached = self.commit_details_cache.get(commit_hash)
        if cached is not None:
            return cached
        details = load_commit_details(self.repo_path, commit_hash)
        self.commit_details_cache[commit_hash] = details
        return details

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

    def _copy_files_list(self) -> None:
        commit = self._get_selected_commit()
        if not commit:
            return
        paths = [stat.path for stat in commit.file_stats]
        content = ", ".join(paths)
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()

    def _copy_full_patch(self) -> None:
        commit = self._get_selected_commit()
        if not commit:
            return
        try:
            patch = self.full_patch_cache.get(commit.commit_hash)
            if patch is None:
                patch = self._get_patch(commit.commit_hash)
                self.full_patch_cache[commit.commit_hash] = patch
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self.clipboard_clear()
        self.clipboard_append(patch)
        self.update()

    def _copy_patch(self) -> None:
        content = self.patch_text.get("1.0", tk.END).strip()
        if not content:
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()

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
            messagebox.showinfo("Cherry-pick", "Selecione um repositório primeiro.")
            return
        commits = self._get_selected_commits()
        if not commits:
            messagebox.showinfo("Cherry-pick", "Selecione commits na aba Histórico.")
            return
        current = self._get_current_branch()
        branch_options = [branch for branch in self.branch_list if branch != current]
        if not branch_options and current:
            branch_options = [current]

        window = tk.Toplevel(self)
        window.title("Cherry-pick")
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
            if current and target == current:
                badge_var.set("Aviso: destino = origem")
                badge_label.configure(fg="#b42318")
            else:
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

        def run_cherry_pick() -> None:
            target = target_var.get().strip()
            if not target:
                messagebox.showwarning("Cherry-pick", "Selecione a branch de destino.")
                return
            if not self._checkout_to_branch(target):
                return
            applied: list[str] = []
            for commit in commits:
                try:
                    run_git(self.repo_path, ["cherry-pick", commit.commit_hash])
                except RuntimeError as exc:
                    messagebox.showerror(
                        "Cherry-pick",
                        f"Falha ao aplicar {commit.commit_hash[:7]}.\n{exc}\n"
                        "Resolva conflitos e finalize ou aborte o cherry-pick.",
                    )
                    self._show_conflicts_window()
                    break
                applied.append(commit.commit_hash)
            if applied:
                self._reload_commits()
                self._refresh_status()
                self._update_pull_push_labels()
                self._set_status(f"Cherry-pick aplicado em {target}.")
            window.destroy()

        def abort_cherry_pick() -> None:
            try:
                run_git(self.repo_path, ["cherry-pick", "--abort"])
            except RuntimeError as exc:
                messagebox.showerror("Cherry-pick", str(exc))
                return
            self._set_status("Cherry-pick abortado.")
            self._refresh_status()
            self._update_pull_push_labels()

        def continue_cherry_pick() -> None:
            try:
                run_git(self.repo_path, ["cherry-pick", "--continue"])
            except RuntimeError as exc:
                messagebox.showerror("Cherry-pick", str(exc))
                return
            self._set_status("Cherry-pick continuado.")
            self._reload_commits()
            self._refresh_status()
            self._update_pull_push_labels()

        ttk.Button(actions, text="Copiar hashes", command=copy_hashes).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Cherry-pick", command=run_cherry_pick).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(actions, text="Abortar", command=abort_cherry_pick).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(actions, text="Continuar", command=continue_cherry_pick).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(actions, text="Fechar", command=window.destroy).grid(row=0, column=4)

    def _open_import_commits_window(self) -> None:
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
                    run_git(self.repo_path, ["fetch", source_path, commit_hash])
                except RuntimeError as exc:
                    messagebox.showerror("Importar", f"Falha ao buscar {commit_hash[:7]}.\n{exc}")
                    break
                try:
                    run_git(self.repo_path, ["cherry-pick", commit_hash])
                except RuntimeError as exc:
                    messagebox.showerror(
                        "Importar",
                        f"Falha ao aplicar {commit_hash[:7]}.\n{exc}\n"
                        "Resolva conflitos e finalize ou aborte o cherry-pick.",
                    )
                    self._show_conflicts_window()
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

    def _show_conflicts_window(self) -> None:
        try:
            output = run_git(self.repo_path, ["diff", "--name-only", "--diff-filter=U"])
        except RuntimeError as exc:
            messagebox.showerror("Conflitos", str(exc))
            return
        files = [line.strip() for line in output.splitlines() if line.strip()]
        if not files:
            messagebox.showinfo("Conflitos", "Nenhum conflito detectado.")
            return

        window = tk.Toplevel(self)
        window.title("Conflitos")
        window.geometry("600x400")

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ttk.Label(frame, text=f"Conflitos: {len(files)}").grid(row=0, column=0, sticky="w")

        listbox = tk.Listbox(frame, selectmode="extended")
        listbox.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        listbox.configure(yscrollcommand=scroll.set)

        for item in files:
            listbox.insert(tk.END, item)

        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="w", pady=(8, 0))

        def open_in_vscode() -> None:
            selection = listbox.curselection()
            if not selection:
                messagebox.showinfo("Conflitos", "Selecione arquivos para abrir.")
                return
            for index in selection:
                path = listbox.get(index)
                abs_path = os.path.join(self.repo_path, path)
                subprocess.run(["code", "-g", abs_path], check=False)

        def abort_cherry_pick() -> None:
            try:
                run_git(self.repo_path, ["cherry-pick", "--abort"])
            except RuntimeError as exc:
                messagebox.showerror("Cherry-pick", str(exc))
                return
            self._set_status("Cherry-pick abortado.")
            self._refresh_status()
            self._update_pull_push_labels()

        def continue_cherry_pick() -> None:
            try:
                run_git(self.repo_path, ["cherry-pick", "--continue"])
            except RuntimeError as exc:
                messagebox.showerror("Cherry-pick", str(exc))
                return
            self._set_status("Cherry-pick continuado.")
            self._reload_commits()
            self._refresh_status()
            self._update_pull_push_labels()
            window.destroy()

        ttk.Button(actions, text="Abrir no VS Code", command=open_in_vscode).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Abortar", command=abort_cherry_pick).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(actions, text="Continuar", command=continue_cherry_pick).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(actions, text="Fechar", command=window.destroy).grid(row=0, column=3)

    def _get_tags(self) -> list[str]:
        output = run_git(self.repo_path, ["tag", "--list"])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _refresh_filter_refs(self) -> None:
        if not hasattr(self, "filter_branch_combo"):
            return
        if not self.repo_ready:
            self.filter_branch_combo.configure(values=["(todas)"], state="disabled")
            self.filter_tag_combo.configure(values=["(todas)"], state="disabled")
            return
        branch_values = ["(todas)"] + self.branch_list
        self.filter_branch_combo.configure(values=branch_values, state="readonly")
        if self.filter_branch_var.get() not in branch_values:
            self.filter_branch_var.set("(todas)")

        self.tag_list = self._get_tags()
        tag_values = ["(todas)"] + self.tag_list
        self.filter_tag_combo.configure(values=tag_values, state="readonly")
        if self.filter_tag_var.get() not in tag_values:
            self.filter_tag_var.set("(todas)")
        if hasattr(self, "filter_repo_status_combo"):
            self.filter_repo_status_combo.configure(state="readonly")

    def _reload_commits(self) -> None:
        try:
            self.commit_summaries = self._load_commit_summaries()
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            self._update_filter_status()
            return
        self.commit_details_cache.clear()
        self.current_commit_hash = None
        self.no_more_commits = False
        self.loading_more = False
        self._populate_commit_list()
        self._update_filter_status()

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
        text_widget.configure(font=("Courier New", 10))

        text_widget.tag_configure("added", foreground="#1a7f37")
        text_widget.tag_configure("removed", foreground="#d1242f")
        text_widget.tag_configure("meta", foreground="#57606a")
        text_widget.tag_configure("added_word", foreground="#1a7f37", background="#dafbe1")
        text_widget.tag_configure("removed_word", foreground="#d1242f", background="#ffebe9")

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

    def _update_branch_action_branches(self) -> None:
        if not hasattr(self, "branch_origin_combo"):
            return
        if not self.repo_ready:
            self.branch_origin_combo.configure(values=[], state="disabled")
            return
        current = self._get_current_branch()
        options = [branch for branch in self.branch_list if branch != current]
        self.branch_origin_combo.configure(values=options, state="readonly")
        if not options:
            self.branch_origin_var.set("")
            return
        if not self.branch_origin_var.get() and options:
            self.branch_origin_var.set(options[0])
        elif self.branch_origin_var.get() not in options and options:
            self.branch_origin_var.set(options[0])

    def _update_operation_preview(self) -> None:
        if not hasattr(self, "branch_action_status"):
            return
        if not self.repo_ready:
            self.branch_action_status.configure(text="Selecione um repositório.")
            self.branch_action_button.configure(state="disabled")
            return
        dest = self._get_current_branch()
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
        dest = self._get_current_branch()
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
        self._reload_commits()
        self._refresh_status()
        self._refresh_branches()
        self._update_pull_push_labels()

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
            font=("TkDefaultFont", 9),
        )
        label.pack(ipadx=6, ipady=2)
        x = event.widget.winfo_rootx() + 8
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 6
        tooltip.wm_geometry(f"+{x}+{y}")
        self.action_hint_window = tooltip

    def _hide_action_hint(self, _event: tk.Event) -> None:
        tooltip = getattr(self, "action_hint_window", None)
        if tooltip is not None:
            tooltip.destroy()
            self.action_hint_window = None

    def _render_patch(self, patch: str) -> None:
        render_patch_to_widget(
            self.patch_text,
            patch,
            read_only=True,
            show_file_headers=False,
            word_diff=self._word_diff_enabled(),
        )


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
