#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from git_client import is_git_repo, load_commit_details, load_commit_summaries, run_git
from models import CommitFilters, CommitInfo, CommitSummary, DiffData, DiffHunk, DiffLineInfo, FileStat


LARGE_PATCH_THRESHOLD = 1000


class CommitsViewer(tk.Tk):
    def __init__(self, repo_path: str, summaries: list[CommitSummary], patch_limit: int, commit_limit: int) -> None:
        super().__init__()
        self.repo_path = repo_path
        self.commit_summaries = summaries
        self.patch_limit = patch_limit
        self.commit_limit = commit_limit
        self.fetch_interval_sec = 60
        self.status_interval_sec = 15
        self.commit_filters = CommitFilters()
        self.tag_list: list[str] = []
        self.word_diff_var = tk.BooleanVar(value=False)
        self.diff_scope_var = tk.StringVar(value="Unstaged")
        self.worktree_diff_data: DiffData | None = None
        self.worktree_line_map: dict[int, DiffLineInfo] = {}
        self.worktree_diff_scope: str = ""
        self.title("Git Commits Viewer")
        self.geometry("1200x700")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.patch_cache: dict[tuple[str, str], str] = {}
        self.full_patch_cache: dict[str, str] = {}
        self.selected_file_by_commit: dict[str, int] = {}
        self.current_commit_hash: str | None = None
        self.branch_list: list[str] = []
        self.auto_fetch_job: str | None = None
        self.auto_status_job: str | None = None
        self.stage_sync_job: str | None = None
        self.suspend_stage_sync = False
        self.commit_details_cache: dict[str, CommitInfo] = {}
        self.commit_offset = len(summaries)
        self.loading_more = False
        self.no_more_commits = False
        self.repo_ready = False

        self._build_global_bar()
        self._build_tabs()
        self._populate_commit_list()
        if self.repo_path and is_git_repo(self.repo_path):
            self._set_repo_path(self.repo_path, initial=True)
        else:
            self._set_repo_ui_no_repo()

    def _build_tabs(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.history_tab = ttk.Frame(self.tabs)
        self.branch_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.history_tab, text="Histórico")
        self.tabs.add(self.branch_tab, text="Commit")
        self.tabs.add(self.settings_tab, text="Configurações")

        self._build_history_tab()
        self._build_branch_tab()
        self._build_settings_tab()

    def _build_global_bar(self) -> None:
        self.global_bar = ttk.Frame(self)
        self.global_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self.global_bar.grid_columnconfigure(1, weight=1)
        self.global_bar.grid_columnconfigure(5, weight=1)

        ttk.Label(self.global_bar, text="Repo:").grid(row=0, column=0, sticky="w")
        self.repo_var = tk.StringVar(value=self.repo_path)
        self.repo_entry = ttk.Entry(self.global_bar, textvariable=self.repo_var, width=50)
        self.repo_entry.grid(row=0, column=1, sticky="w")
        self.repo_entry.bind("<Return>", lambda _e: self._apply_repo_from_entry())

        ttk.Button(self.global_bar, text="Abrir repo", command=self._open_repo_dialog).grid(
            row=0, column=2, padx=(6, 0)
        )
        ttk.Button(self.global_bar, text="Usar caminho", command=self._apply_repo_from_entry).grid(
            row=0, column=3, padx=(6, 0)
        )

        ttk.Label(self.global_bar, text="Branch:").grid(row=0, column=4, sticky="w", padx=(12, 0))

        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(
            self.global_bar,
            textvariable=self.branch_var,
            state="readonly",
            width=24,
        )
        self.branch_combo.grid(row=0, column=5, sticky="w")
        self.branch_combo.bind("<<ComboboxSelected>>", self._on_branch_selected)

        ttk.Label(self.global_bar, text="Origem:").grid(row=0, column=6, sticky="w", padx=(12, 0))
        self.branch_origin_var = tk.StringVar()
        self.branch_origin_combo = ttk.Combobox(
            self.global_bar,
            textvariable=self.branch_origin_var,
            state="readonly",
            width=18,
        )
        self.branch_origin_combo.grid(row=0, column=7, sticky="w")
        self.branch_origin_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_operation_preview())

        ttk.Label(self.global_bar, text="Destino:").grid(row=0, column=8, sticky="w", padx=(12, 0))
        self.branch_dest_var = tk.StringVar(value="")
        self.branch_dest_label = ttk.Label(self.global_bar, textvariable=self.branch_dest_var)
        self.branch_dest_label.grid(row=0, column=9, sticky="w")

        self.fetch_button = ttk.Button(self.global_bar, text="Fetch", command=self._fetch_repo)
        self.fetch_button.grid(row=0, column=10, padx=(12, 0))
        self.pull_button = ttk.Button(self.global_bar, text="Pull", command=self._pull_repo)
        self.pull_button.grid(row=0, column=11, padx=(6, 0))
        self.push_button = ttk.Button(self.global_bar, text="Push", command=self._push_repo)
        self.push_button.grid(row=0, column=12, padx=(6, 0))

        self.upstream_var = tk.StringVar(value="")
        self.upstream_label = ttk.Label(self.global_bar, textvariable=self.upstream_var)
        self.upstream_label.grid(row=0, column=13, sticky="w", padx=(12, 0))

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

    def _build_branch_tab(self) -> None:
        self.branch_tab.grid_columnconfigure(0, weight=1)
        self.branch_tab.grid_rowconfigure(0, weight=1)

        content_frame = ttk.Frame(self.branch_tab)
        content_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
        content_frame.grid_columnconfigure(0, weight=2)
        content_frame.grid_columnconfigure(1, weight=4)
        content_frame.grid_rowconfigure(0, weight=1)

        left_column = ttk.Frame(content_frame)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
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
            font=("Courier New", 10),
        )
        self.status_listbox.grid(row=1, column=0, sticky="nsew")

        status_scroll = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_listbox.yview)
        status_scroll.grid(row=1, column=1, sticky="ns")
        self.status_listbox.configure(yscrollcommand=status_scroll.set)
        self.status_listbox.bind("<<ListboxSelect>>", self._on_status_select)

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

        diff_frame = ttk.Frame(content_frame)
        diff_frame.grid(row=0, column=1, sticky="nsew")
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
        self.worktree_diff_text.configure(font=("Courier New", 10))
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

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self.branch_tab, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, sticky="w", padx=8, pady=(6, 8))

        self.status_items: dict[str, dict[str, str | bool]] = {}
        self._refresh_branches()
        self._refresh_status()

    def _build_settings_tab(self) -> None:
        self.settings_tab.grid_columnconfigure(1, weight=1)

        ttk.Label(self.settings_tab, text="Limite do histórico (commits):").grid(
            row=0,
            column=0,
            sticky="w",
            padx=8,
            pady=(8, 4),
        )
        self.commit_limit_var = tk.StringVar(value=str(self.commit_limit))
        self.commit_limit_entry = ttk.Entry(self.settings_tab, textvariable=self.commit_limit_var, width=12)
        self.commit_limit_entry.grid(row=0, column=1, sticky="w", padx=8, pady=(8, 4))

        ttk.Label(self.settings_tab, text="Intervalo de fetch automático (segundos):").grid(
            row=1,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.fetch_interval_var = tk.StringVar(value=str(self.fetch_interval_sec))
        self.fetch_interval_entry = ttk.Entry(self.settings_tab, textvariable=self.fetch_interval_var, width=12)
        self.fetch_interval_entry.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(self.settings_tab, text="Intervalo de status automático (segundos):").grid(
            row=2,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.status_interval_var = tk.StringVar(value=str(self.status_interval_sec))
        self.status_interval_entry = ttk.Entry(self.settings_tab, textvariable=self.status_interval_var, width=12)
        self.status_interval_entry.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        actions = ttk.Frame(self.settings_tab)
        actions.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(actions, text="Aplicar", command=self._apply_settings).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Restaurar padrão", command=self._reset_settings).grid(row=0, column=1)

        self.settings_status_var = tk.StringVar(value="")
        ttk.Label(self.settings_tab, textvariable=self.settings_status_var).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=(6, 0),
        )

    def _apply_settings(self) -> None:
        try:
            commit_limit = int(self.commit_limit_var.get().strip())
            fetch_interval = int(self.fetch_interval_var.get().strip())
            status_interval = int(self.status_interval_var.get().strip())
        except ValueError:
            self.settings_status_var.set("Valores inválidos. Use números inteiros.")
            return
        if commit_limit <= 0 or fetch_interval < 10 or status_interval < 5:
            self.settings_status_var.set("Valores inválidos. Use números positivos.")
            return
        self.commit_limit = commit_limit
        self.fetch_interval_sec = fetch_interval
        self.status_interval_sec = status_interval
        self.settings_status_var.set("Configurações aplicadas.")
        if self.repo_ready:
            self._reload_commits()
            self._schedule_auto_fetch()
            self._schedule_auto_status()

    def _reset_settings(self) -> None:
        self.commit_limit = 100
        self.fetch_interval_sec = 60
        self.status_interval_sec = 15
        self.commit_limit_var.set(str(self.commit_limit))
        self.fetch_interval_var.set(str(self.fetch_interval_sec))
        self.status_interval_var.set(str(self.status_interval_sec))
        self.settings_status_var.set("Padrões restaurados.")
        if self.repo_ready:
            self._reload_commits()
            self._schedule_auto_fetch()
            self._schedule_auto_status()

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

    def _toggle_word_diff(self) -> None:
        self.patch_cache.clear()
        self.full_patch_cache.clear()
        self.worktree_diff_data = None
        self.worktree_line_map.clear()
        selection = self.commit_listbox.curselection()
        if selection:
            self._show_commit(selection[-1])
        self._update_worktree_diff_from_selection()

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

    def _open_stash_window(self) -> None:
        if not self.repo_ready:
            messagebox.showinfo("Stash", "Selecione um repositório primeiro.")
            return

        window = tk.Toplevel(self)
        window.title("Stashes")
        window.geometry("900x600")

        container = ttk.Frame(window)
        container.pack(fill="both", expand=True, padx=8, pady=8)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=2)
        container.grid_rowconfigure(1, weight=1)

        top_bar = ttk.Frame(container)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        top_bar.grid_columnconfigure(1, weight=1)

        ttk.Label(top_bar, text="Mensagem:").grid(row=0, column=0, sticky="w")
        stash_message_var = tk.StringVar()
        stash_entry = ttk.Entry(top_bar, textvariable=stash_message_var)
        stash_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))

        def create_stash() -> None:
            message = stash_message_var.get().strip()
            args = ["stash", "push", "-u"]
            if message:
                args.extend(["-m", message])
            try:
                run_git(self.repo_path, args)
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            stash_message_var.set("")
            self._refresh_status()
            refresh_list()

        ttk.Button(top_bar, text="Criar stash", command=create_stash).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(top_bar, text="Atualizar", command=lambda: refresh_list()).grid(row=0, column=3)

        list_frame = ttk.Frame(container)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        stash_listbox = tk.Listbox(list_frame, activestyle="dotbox", exportselection=False)
        stash_listbox.grid(row=0, column=0, sticky="nsew")
        stash_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=stash_listbox.yview)
        stash_scroll.grid(row=0, column=1, sticky="ns")
        stash_listbox.configure(yscrollcommand=stash_scroll.set)

        diff_frame = ttk.Frame(container)
        diff_frame.grid(row=1, column=1, sticky="nsew")
        diff_frame.grid_rowconfigure(0, weight=1)
        diff_frame.grid_columnconfigure(0, weight=1)

        stash_diff_text = tk.Text(diff_frame, wrap="none")
        stash_diff_text.grid(row=0, column=0, sticky="nsew")
        stash_diff_scroll = ttk.Scrollbar(diff_frame, orient="vertical", command=stash_diff_text.yview)
        stash_diff_scroll.grid(row=0, column=1, sticky="ns")
        stash_diff_text.configure(yscrollcommand=stash_diff_scroll.set)
        stash_diff_text.tag_configure("added", foreground="#1a7f37")
        stash_diff_text.tag_configure("removed", foreground="#d1242f")
        stash_diff_text.tag_configure("meta", foreground="#57606a")
        stash_diff_text.tag_configure("added_word", foreground="#1a7f37", background="#dafbe1")
        stash_diff_text.tag_configure("removed_word", foreground="#d1242f", background="#ffebe9")
        stash_diff_text.configure(font=("Courier New", 10))
        stash_diff_text.configure(state="disabled")

        actions = ttk.Frame(container)
        actions.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        stash_refs: list[str] = []

        def selected_ref() -> str | None:
            selection = stash_listbox.curselection()
            if not selection:
                return None
            return stash_refs[selection[0]]

        def show_selected_stash() -> None:
            ref = selected_ref()
            if not ref:
                self._set_text(stash_diff_text, "(sem stash selecionado)")
                return
            try:
                diff = run_git(self.repo_path, ["stash", "show", "-p", ref])
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            self._render_patch_to_widget(
                stash_diff_text,
                diff,
                read_only=True,
                show_file_headers=True,
                word_diff=self._word_diff_enabled(),
            )

        def refresh_list() -> None:
            stash_listbox.delete(0, tk.END)
            stash_refs.clear()
            try:
                entries = run_git(self.repo_path, ["stash", "list"]).splitlines()
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            for line in entries:
                ref, _, desc = line.partition(":")
                stash_refs.append(ref.strip())
                stash_listbox.insert(tk.END, f"{ref.strip()}:{desc}")
            if stash_refs:
                stash_listbox.selection_set(0)
                show_selected_stash()
            else:
                self._set_text(stash_diff_text, "(sem stashes)")

        def apply_stash(pop: bool) -> None:
            ref = selected_ref()
            if not ref:
                messagebox.showinfo("Stash", "Selecione um stash.")
                return
            cmd = ["stash", "pop" if pop else "apply", ref]
            try:
                run_git(self.repo_path, cmd)
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            self._refresh_status()
            self._reload_commits()
            refresh_list()

        def drop_stash() -> None:
            ref = selected_ref()
            if not ref:
                messagebox.showinfo("Stash", "Selecione um stash.")
                return
            try:
                run_git(self.repo_path, ["stash", "drop", ref])
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            refresh_list()

        ttk.Button(actions, text="Aplicar", command=lambda: apply_stash(pop=False)).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Aplicar e remover", command=lambda: apply_stash(pop=True)).grid(
            row=0,
            column=1,
            padx=(0, 6),
        )
        ttk.Button(actions, text="Descartar", command=drop_stash).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(actions, text="Fechar", command=window.destroy).grid(row=0, column=3)

        stash_listbox.bind("<<ListboxSelect>>", lambda _e: show_selected_stash())
        refresh_list()

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
            self._render_patch_to_widget(
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

    def _refresh_status(self) -> None:
        if not self.repo_ready:
            return
        self.status_listbox.delete(0, tk.END)
        self.status_items.clear()
        self.status_headers: set[int] = set()

        try:
            entries = self._get_status_entries()
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
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
        self.worktree_diff_data = self._parse_diff_data(diff_raw)
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

    def _parse_diff_data(self, diff_text: str) -> DiffData:
        header_lines: list[str] = []
        hunks: list[DiffHunk] = []
        current: DiffHunk | None = None
        old_line = 0
        new_line = 0

        for line in diff_text.splitlines():
            if line.startswith("diff --git") or line.startswith("index ") or line.startswith("---") or line.startswith("+++"):
                header_lines.append(line)
                continue
            if line.startswith("@@"):
                old_start, old_count, new_start, new_count = self._parse_hunk_header_full(line)
                current = DiffHunk(
                    header=line,
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=[],
                    raw_lines=[line],
                )
                hunks.append(current)
                old_line = old_start
                new_line = new_start
                continue
            if not current:
                continue
            if line.startswith("\\ No newline at end of file"):
                continue
            if line.startswith("-"):
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="removed",
                    old_line=old_line,
                    new_line=new_line,
                    content=line[1:],
                    raw=line,
                )
                old_line += 1
            elif line.startswith("+"):
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="added",
                    old_line=old_line,
                    new_line=new_line,
                    content=line[1:],
                    raw=line,
                )
                new_line += 1
            elif line.startswith(" "):
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="context",
                    old_line=old_line,
                    new_line=new_line,
                    content=line[1:],
                    raw=line,
                )
                old_line += 1
                new_line += 1
            else:
                continue
            current.lines.append(info)
            current.raw_lines.append(line)

        return DiffData(header_lines=header_lines, hunks=hunks)

    def _render_worktree_diff(self, diff_text: str, word_diff: bool) -> None:
        self._render_patch_to_widget(
            self.worktree_diff_text,
            diff_text,
            read_only=True,
            show_file_headers=False,
            word_diff=word_diff,
        )
        if word_diff or not self.worktree_diff_data:
            self.worktree_line_map.clear()
            return
        self.worktree_line_map = self._build_line_map(self.worktree_diff_data)

    @staticmethod
    def _build_line_map(diff_data: DiffData) -> dict[int, DiffLineInfo]:
        line_map: dict[int, DiffLineInfo] = {}
        line_index = 1
        for hunk in diff_data.hunks:
            for info in hunk.lines:
                line_map[line_index] = info
                line_index += 1
        return line_map

    @staticmethod
    def _parse_hunk_header_full(header: str) -> tuple[int, int, int, int]:
        parts = header.split()
        if len(parts) < 3:
            return 0, 0, 0, 0

        def parse_range(value: str) -> tuple[int, int]:
            if "," in value:
                start, count = value.split(",", 1)
                return int(start), int(count)
            return int(value), 1

        try:
            old_start, old_count = parse_range(parts[1].lstrip("-"))
            new_start, new_count = parse_range(parts[2].lstrip("+"))
        except ValueError:
            return 0, 0, 0, 0
        return old_start, old_count, new_start, new_count

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

    def _build_patch_for_hunk(self, hunk_index: int) -> str | None:
        if not self.worktree_diff_data:
            return None
        if hunk_index < 0 or hunk_index >= len(self.worktree_diff_data.hunks):
            return None
        hunk = self.worktree_diff_data.hunks[hunk_index]
        lines = [*self.worktree_diff_data.header_lines, *hunk.raw_lines]
        return "\n".join(lines) + "\n"

    def _build_patch_for_line(self, line_info: DiffLineInfo) -> str | None:
        if not self.worktree_diff_data:
            return None
        if line_info.line_type not in ("added", "removed"):
            return None
        if line_info.line_type == "added":
            old_start = line_info.old_line
            new_start = line_info.new_line
            old_count = 0
            new_count = 1
            line = f"+{line_info.content}"
        else:
            old_start = line_info.old_line
            new_start = line_info.new_line
            old_count = 1
            new_count = 0
            line = f"-{line_info.content}"
        header = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
        lines = [*self.worktree_diff_data.header_lines, header, line]
        return "\n".join(lines) + "\n"

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
        patch = self._build_patch_for_hunk(line_info.hunk_index)
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
        patch = self._build_patch_for_hunk(line_info.hunk_index)
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
        patch = self._build_patch_for_line(line_info)
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
        patch = self._build_patch_for_line(line_info)
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

    def _fetch_repo(self) -> None:
        self._fetch_repo_internal(show_errors=True)

    def _pull_repo(self) -> None:
        if not self.repo_ready:
            return
        try:
            run_git(self.repo_path, ["pull", "--ff-only"])
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self._set_status("Pull concluído.")
        self._reload_commits()
        self._refresh_status()
        self._refresh_branches()
        self._update_pull_push_labels()

    def _push_repo(self) -> None:
        if not self.repo_ready:
            return
        try:
            run_git(self.repo_path, ["push"])
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self._set_status("Push concluído.")
        self._update_pull_push_labels()
        self._refresh_status()
        if self._is_dirty():
            self._set_status("Push concluído, mas ainda há alterações locais.")

    def _refresh_branches(self) -> None:
        if not self.repo_ready:
            return
        branches = self._get_branches()
        current = self._get_current_branch()
        self.branch_list = branches
        self.branch_combo["values"] = branches
        if current and current in branches:
            self.branch_var.set(current)
        elif branches:
            self.branch_var.set(branches[0])
        if hasattr(self, "branch_dest_var"):
            self.branch_dest_var.set(current)
        self._set_status(f"Branch atual: {current}" if current else "Branch atual: (desconhecido)")
        self._update_pull_push_labels()
        self._update_branch_action_branches()
        self._update_operation_preview()
        self._refresh_filter_refs()

    def _get_branches(self) -> list[str]:
        output = run_git(self.repo_path, ["branch", "--format=%(refname:short)"])
        return [line.strip() for line in output.splitlines() if line.strip()]

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

    def _get_current_branch(self) -> str:
        if not self.repo_ready:
            return ""
        output = run_git(self.repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        return output.strip()

    def _is_dirty(self) -> bool:
        output = run_git(self.repo_path, ["status", "--porcelain"])
        return bool(output.strip())

    def _stash_changes(self) -> None:
        if not self._is_dirty():
            self._set_status("Nada para stash.")
            return
        run_git(self.repo_path, ["stash", "push", "-u", "-m", "git_commits_viewer"])
        self._set_status("Stash criado.")
        self._refresh_status()

    def _checkout_branch(self) -> bool:
        target = self.branch_var.get().strip()
        return self._checkout_to_branch(target)

    def _checkout_to_branch(self, target: str) -> bool:
        if not target:
            return False
        current = self._get_current_branch()
        if target == current:
            return True
        if self._is_dirty():
            choice = self._prompt_dirty_checkout()
            if choice == "cancel":
                self.branch_var.set(current)
                return False
            if choice == "stash":
                run_git(self.repo_path, ["stash", "push", "-u", "-m", "git_commits_viewer"])
        try:
            run_git(self.repo_path, ["checkout", target])
        except RuntimeError as exc:
            messagebox.showerror("Checkout", str(exc))
            return False
        self.branch_var.set(target)
        self._set_status(f"Checkout para {target}.")
        self._reload_commits()
        self._refresh_status()
        self._refresh_branches()
        self._update_pull_push_labels()
        return True

    def _prompt_dirty_checkout(self) -> str:
        dialog = tk.Toplevel(self)
        dialog.title("Alterações locais")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="Há alterações locais. Como deseja proceder?",
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(12, 8))

        result = {"choice": "cancel"}

        def set_choice(choice: str) -> None:
            result["choice"] = choice
            dialog.destroy()

        ttk.Button(dialog, text="Stash + Checkout", command=lambda: set_choice("stash")).grid(
            row=1,
            column=0,
            padx=6,
            pady=12,
        )
        ttk.Button(dialog, text="Checkout mesmo assim", command=lambda: set_choice("checkout")).grid(
            row=1,
            column=1,
            padx=6,
            pady=12,
        )
        ttk.Button(dialog, text="Cancelar", command=lambda: set_choice("cancel")).grid(
            row=1,
            column=2,
            padx=6,
            pady=12,
        )

        dialog.wait_window()
        return result["choice"]

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

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

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

    def _apply_repo_from_entry(self) -> None:
        path = self.repo_var.get().strip()
        if not path:
            self._set_repo_ui_no_repo()
            return
        self._set_repo_path(path, initial=False)

    def _open_repo_dialog(self) -> None:
        path = filedialog.askdirectory()
        if not path:
            return
        self.repo_var.set(path)
        self._set_repo_path(path, initial=False)

    def _set_repo_path(self, path: str, initial: bool) -> bool:
        repo_path = os.path.abspath(path)
        if not os.path.isdir(repo_path) or not is_git_repo(repo_path):
            if not initial:
                messagebox.showwarning("Repo", "Selecione um repositório git válido.")
            self._set_repo_ui_no_repo()
            return False
        self.repo_path = repo_path
        self.repo_ready = True
        self.repo_var.set(repo_path)

        self.patch_cache.clear()
        self.full_patch_cache.clear()
        self.selected_file_by_commit.clear()
        self._reload_commits()

        self.branch_combo.configure(state="readonly")
        self._set_action_visibility(self.fetch_button, True)
        self._refresh_branches()
        self._refresh_status()
        self._update_branch_action_branches()
        self._update_operation_preview()
        self._schedule_auto_fetch()
        self._schedule_auto_status()
        return True

    def _set_repo_ui_no_repo(self) -> None:
        self.repo_ready = False
        if self.auto_fetch_job is not None:
            try:
                self.after_cancel(self.auto_fetch_job)
            except tk.TclError:
                pass
            self.auto_fetch_job = None
        if self.auto_status_job is not None:
            try:
                self.after_cancel(self.auto_status_job)
            except tk.TclError:
                pass
            self.auto_status_job = None
        self.commit_summaries = []
        self.commit_details_cache.clear()
        self.current_commit_hash = None
        self.commit_listbox.delete(0, tk.END)
        self._set_text(self.commit_info, "(nenhum repositório selecionado)")
        self._set_text(self.patch_text, "")
        self.files_listbox.delete(0, tk.END)
        self.load_patch_button.configure(state="disabled")
        self.load_patch_button.grid_remove()
        self.worktree_diff_data = None
        self.worktree_line_map.clear()
        self.worktree_diff_scope = ""
        self._update_worktree_diff_actions()
        if hasattr(self, "stage_count_var"):
            self.stage_count_var.set("Selecionados: 0/0")
        self.branch_list = []
        self.branch_var.set("")
        self.branch_combo.configure(values=[], state="disabled")
        if hasattr(self, "branch_dest_var"):
            self.branch_dest_var.set("")
        if hasattr(self, "diff_scope_combo"):
            self.diff_scope_combo.configure(state="disabled")
            self.diff_scope_var.set("Unstaged")
        if hasattr(self, "filter_branch_combo"):
            self.filter_branch_combo.configure(values=["(todas)"], state="disabled")
            self.filter_branch_var.set("(todas)")
        if hasattr(self, "filter_tag_combo"):
            self.filter_tag_combo.configure(values=["(todas)"], state="disabled")
            self.filter_tag_var.set("(todas)")
        if hasattr(self, "filter_repo_status_combo"):
            self.filter_repo_status_combo.configure(state="disabled")
            self.filter_repo_status_var.set("Todos")
        self._update_filter_status()
        self._set_action_visibility(self.fetch_button, False)
        self._set_action_visibility(self.pull_button, False)
        self._set_action_visibility(self.push_button, False)
        self.upstream_var.set("")
        self._set_status("Selecione um repositório.")
        if hasattr(self, "branch_origin_combo"):
            self.branch_origin_combo.configure(values=[], state="disabled")
        if hasattr(self, "branch_action_button"):
            self.branch_action_button.configure(state="disabled")
        if hasattr(self, "branch_action_status"):
            self.branch_action_status.configure(text="")

    def _on_branch_selected(self, _event: tk.Event) -> None:
        self._checkout_branch()
        self._update_operation_preview()

    def _get_upstream(self) -> str | None:
        if not self.repo_ready:
            return None
        try:
            output = run_git(self.repo_path, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        except RuntimeError:
            return None
        upstream = output.strip()
        return upstream if upstream else None

    def _get_ahead_behind(self) -> tuple[int, int]:
        upstream = self._get_upstream()
        if not upstream:
            return 0, 0
        output = run_git(self.repo_path, ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        parts = output.strip().split()
        if len(parts) != 2:
            return 0, 0
        behind = int(parts[0])
        ahead = int(parts[1])
        return behind, ahead

    def _update_pull_push_labels(self) -> None:
        if not hasattr(self, "pull_button"):
            return
        upstream = self._get_upstream()
        if not upstream:
            self._set_action_visibility(self.pull_button, False)
            self._set_action_visibility(self.push_button, False)
            if hasattr(self, "fetch_button"):
                self.fetch_button.configure(text="Fetch")
            if hasattr(self, "upstream_var"):
                self.upstream_var.set("Upstream: (não configurado)")
            return
        behind, ahead = self._get_ahead_behind()
        if behind > 0:
            self.pull_button.configure(text=f"Pull ({behind})", state="normal")
            self._set_action_visibility(self.pull_button, True)
        else:
            self.pull_button.configure(text="Pull", state="disabled")
            self._set_action_visibility(self.pull_button, False)
        if ahead > 0:
            self.push_button.configure(text=f"Push ({ahead})", state="normal")
            self._set_action_visibility(self.push_button, True)
        else:
            self.push_button.configure(text="Push", state="disabled")
            self._set_action_visibility(self.push_button, False)
        if hasattr(self, "fetch_button"):
            if behind > 0:
                self.fetch_button.configure(text=f"Fetch ({behind})")
            else:
                self.fetch_button.configure(text="Fetch")
        if hasattr(self, "upstream_var"):
            self.upstream_var.set(f"Ahead: {ahead} | Behind: {behind}")
        self._update_operation_preview()

    @staticmethod
    def _set_action_visibility(button: ttk.Button, visible: bool) -> None:
        if visible:
            button.grid()
        else:
            button.grid_remove()

    def _fetch_repo_internal(self, show_errors: bool) -> bool:
        if not self.repo_ready:
            return False
        try:
            run_git(self.repo_path, ["fetch", "--all", "--prune"])
        except RuntimeError as exc:
            if show_errors:
                messagebox.showerror("Erro", str(exc))
            return False
        self._set_status("Fetch concluído.")
        self._update_pull_push_labels()
        return True

    def _auto_fetch(self) -> None:
        self._fetch_repo_internal(show_errors=False)
        self._schedule_auto_fetch()

    def _auto_status(self) -> None:
        self._refresh_status()
        self._schedule_auto_status()

    def _schedule_auto_fetch(self) -> None:
        if not self.repo_ready:
            return
        if self.auto_fetch_job is not None:
            try:
                self.after_cancel(self.auto_fetch_job)
            except tk.TclError:
                pass
        self.auto_fetch_job = self.after(self.fetch_interval_sec * 1000, self._auto_fetch)

    def _schedule_auto_status(self) -> None:
        if not self.repo_ready:
            return
        if self.auto_status_job is not None:
            try:
                self.after_cancel(self.auto_status_job)
            except tk.TclError:
                pass
        self.auto_status_job = self.after(self.status_interval_sec * 1000, self._auto_status)

    @staticmethod
    def _set_text(widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.configure(state="disabled")

    def _word_diff_enabled(self) -> bool:
        if not hasattr(self, "word_diff_var"):
            return False
        return bool(self.word_diff_var.get())

    def _render_patch(self, patch: str) -> None:
        self._render_patch_to_widget(
            self.patch_text,
            patch,
            read_only=True,
            show_file_headers=False,
            word_diff=self._word_diff_enabled(),
        )

    def _render_patch_to_widget(
        self,
        widget: tk.Text,
        patch: str,
        read_only: bool,
        show_file_headers: bool,
        word_diff: bool,
    ) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)

        if not patch.strip():
            widget.insert(tk.END, "(sem diff)")
            if read_only:
                widget.configure(state="disabled")
            return

        old_line = 0
        new_line = 0
        in_hunk = False

        for raw_line in patch.splitlines():
            if raw_line.startswith("diff --git"):
                in_hunk = False
                if show_file_headers:
                    try:
                        parts = raw_line.split()
                        path = parts[2][2:]
                    except IndexError:
                        path = raw_line
                    widget.insert(tk.END, f"\n=== {path} ===\n", "meta")
                continue
            if raw_line.startswith("index ") or raw_line.startswith("---") or raw_line.startswith("+++"):
                continue
            if raw_line.startswith("@@"):
                old_line, new_line = self._parse_hunk_header(raw_line)
                in_hunk = True
                continue
            if raw_line.startswith("\\ No newline at end of file"):
                continue

            if raw_line.startswith("-"):
                content = raw_line[1:]
                self._insert_line_with_word_diff(
                    widget,
                    f"{old_line:>6} - ",
                    content,
                    base_tag="removed",
                    word_diff=word_diff,
                )
                old_line += 1
                continue
            if raw_line.startswith("+"):
                content = raw_line[1:]
                self._insert_line_with_word_diff(
                    widget,
                    f"{new_line:>6} + ",
                    content,
                    base_tag="added",
                    word_diff=word_diff,
                )
                new_line += 1
                continue
            if raw_line.startswith(" "):
                content = raw_line[1:]
                self._insert_line_with_word_diff(
                    widget,
                    f"{old_line:>6}   ",
                    content,
                    base_tag="",
                    word_diff=word_diff,
                )
                old_line += 1
                new_line += 1
                continue

            if word_diff and in_hunk and self._line_has_word_markers(raw_line):
                self._insert_line_with_word_diff(
                    widget,
                    f"{old_line:>6}   ",
                    raw_line,
                    base_tag="",
                    word_diff=True,
                )
                old_line += 1
                new_line += 1
                continue

            widget.insert(tk.END, raw_line + "\n")

        if read_only:
            widget.configure(state="disabled")

    @staticmethod
    def _line_has_word_markers(line: str) -> bool:
        return "{+" in line or "+}" in line or "[-" in line or "-]" in line or "{-" in line or "-}" in line

    def _insert_line_with_word_diff(
        self,
        widget: tk.Text,
        prefix: str,
        content: str,
        base_tag: str,
        word_diff: bool,
    ) -> None:
        if not word_diff:
            if base_tag:
                widget.insert(tk.END, f"{prefix}{content}\n", base_tag)
            else:
                widget.insert(tk.END, f"{prefix}{content}\n")
            return
        if base_tag:
            widget.insert(tk.END, prefix, base_tag)
        else:
            widget.insert(tk.END, prefix)
        self._insert_word_diff_content(widget, content, base_tag)
        widget.insert(tk.END, "\n")

    def _insert_word_diff_content(self, widget: tk.Text, content: str, base_tag: str) -> None:
        markers = [
            ("{+", "+}", "added_word"),
            ("[-", "-]", "removed_word"),
            ("{-", "-}", "removed_word"),
        ]
        index = 0
        while index < len(content):
            next_marker = None
            for opener, closer, tag in markers:
                pos = content.find(opener, index)
                if pos == -1:
                    continue
                if next_marker is None or pos < next_marker[0]:
                    next_marker = (pos, opener, closer, tag)
            if next_marker is None:
                text = content[index:]
                if text:
                    if base_tag:
                        widget.insert(tk.END, text, base_tag)
                    else:
                        widget.insert(tk.END, text)
                break
            pos, opener, closer, tag = next_marker
            if pos > index:
                if base_tag:
                    widget.insert(tk.END, content[index:pos], base_tag)
                else:
                    widget.insert(tk.END, content[index:pos])
            end = content.find(closer, pos + len(opener))
            if end == -1:
                if base_tag:
                    widget.insert(tk.END, content[pos:], base_tag)
                else:
                    widget.insert(tk.END, content[pos:])
                break
            word = content[pos + len(opener) : end]
            tags = (tag, base_tag) if base_tag else (tag,)
            widget.insert(tk.END, word, tags)
            index = end + len(closer)

    @staticmethod
    def _parse_hunk_header(header: str) -> tuple[int, int]:
        # Example: @@ -77,4 +77,4 @@
        try:
            parts = header.split()
            old_part = parts[1]
            new_part = parts[2]
            old_line = int(old_part.split(",")[0].lstrip("-"))
            new_line = int(new_part.split(",")[0].lstrip("+"))
            return old_line, new_line
        except (IndexError, ValueError):
            return 0, 0


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
