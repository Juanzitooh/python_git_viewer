#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class ReposTabMixin:
    def _build_repos_tab(self) -> None:
        self.repos_tab.grid_columnconfigure(0, weight=1)
        self.repos_tab.grid_columnconfigure(1, weight=1)
        self.repos_tab.grid_rowconfigure(1, weight=1)

        ttk.Label(self.repos_tab, text="Favoritos").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Label(self.repos_tab, text="Recentes").grid(row=0, column=1, sticky="w", padx=8, pady=(8, 4))

        favorites_frame = ttk.Frame(self.repos_tab)
        favorites_frame.grid(row=1, column=0, sticky="nsew", padx=8)
        favorites_frame.grid_rowconfigure(0, weight=1)
        favorites_frame.grid_columnconfigure(0, weight=1)

        self.favorite_listbox = tk.Listbox(favorites_frame, activestyle="dotbox", exportselection=False)
        self.favorite_listbox.grid(row=0, column=0, sticky="nsew")
        self.favorite_listbox.bind("<Double-Button-1>", lambda _e: self._open_selected_favorite())
        fav_scroll = ttk.Scrollbar(favorites_frame, orient="vertical", command=self.favorite_listbox.yview)
        fav_scroll.grid(row=0, column=1, sticky="ns")
        self.favorite_listbox.configure(yscrollcommand=fav_scroll.set)

        recent_frame = ttk.Frame(self.repos_tab)
        recent_frame.grid(row=1, column=1, sticky="nsew", padx=8)
        recent_frame.grid_rowconfigure(0, weight=1)
        recent_frame.grid_columnconfigure(0, weight=1)

        self.recent_listbox = tk.Listbox(recent_frame, activestyle="dotbox", exportselection=False)
        self.recent_listbox.grid(row=0, column=0, sticky="nsew")
        self.recent_listbox.bind("<Double-Button-1>", lambda _e: self._open_selected_recent())
        recent_scroll = ttk.Scrollbar(recent_frame, orient="vertical", command=self.recent_listbox.yview)
        recent_scroll.grid(row=0, column=1, sticky="ns")
        self.recent_listbox.configure(yscrollcommand=recent_scroll.set)

        fav_actions = ttk.Frame(self.repos_tab)
        fav_actions.grid(row=2, column=0, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(fav_actions, text="Abrir favorito", command=self._open_selected_favorite).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(fav_actions, text="Remover favorito", command=self._remove_selected_favorite).grid(
            row=0, column=1
        )

        recent_actions = ttk.Frame(self.repos_tab)
        recent_actions.grid(row=2, column=1, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(recent_actions, text="Abrir recente", command=self._open_selected_recent).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(recent_actions, text="Favoritar", command=self._favorite_selected_recent).grid(
            row=0, column=1, padx=(0, 6)
        )
        ttk.Button(recent_actions, text="Remover recente", command=self._remove_selected_recent).grid(
            row=0, column=2
        )

        global_actions = ttk.Frame(self.repos_tab)
        global_actions.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 8))
        ttk.Button(global_actions, text="Favoritar atual", command=self._favorite_current_repo).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(global_actions, text="Abrir pasta...", command=self._open_repo_from_dialog).grid(
            row=0, column=1
        )

        self._refresh_repo_lists()

    def _refresh_repo_lists(self) -> None:
        if not hasattr(self, "favorite_listbox"):
            return
        self.favorite_listbox.delete(0, tk.END)
        self.recent_listbox.delete(0, tk.END)
        for path in self.favorite_repos:
            self.favorite_listbox.insert(tk.END, path)
        for path in self.recent_repos:
            self.recent_listbox.insert(tk.END, path)

    def _open_repo_from_dialog(self) -> None:
        path = filedialog.askdirectory()
        if not path:
            return
        self._open_repo_from_path(path)

    def _open_repo_from_path(self, path: str) -> None:
        if not path:
            return
        if not self._set_repo_path(path, initial=False):
            return

    def _open_selected_favorite(self) -> None:
        path = self._get_selected_repo(self.favorite_listbox, self.favorite_repos)
        if path:
            self._open_repo_from_path(path)

    def _open_selected_recent(self) -> None:
        path = self._get_selected_repo(self.recent_listbox, self.recent_repos)
        if path:
            self._open_repo_from_path(path)

    def _favorite_selected_recent(self) -> None:
        path = self._get_selected_repo(self.recent_listbox, self.recent_repos)
        if not path:
            messagebox.showinfo("Favoritos", "Selecione um repositório recente.")
            return
        self._add_favorite_repo(path)

    def _favorite_current_repo(self) -> None:
        if not self.repo_ready or not self.repo_path:
            messagebox.showinfo("Favoritos", "Selecione um repositório válido.")
            return
        self._add_favorite_repo(self.repo_path)

    def _remove_selected_favorite(self) -> None:
        path = self._get_selected_repo(self.favorite_listbox, self.favorite_repos)
        if not path:
            messagebox.showinfo("Favoritos", "Selecione um favorito para remover.")
            return
        self._remove_favorite_repo(path)

    def _remove_selected_recent(self) -> None:
        path = self._get_selected_repo(self.recent_listbox, self.recent_repos)
        if not path:
            messagebox.showinfo("Recentes", "Selecione um recente para remover.")
            return
        self._remove_recent_repo(path)

    @staticmethod
    def _get_selected_repo(listbox: tk.Listbox, data: list[str]) -> str | None:
        selection = listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if index < 0 or index >= len(data):
            return None
        return data[index]
