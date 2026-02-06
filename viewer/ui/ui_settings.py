#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SettingsTabMixin:
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
        if hasattr(self, "_persist_settings"):
            self._persist_settings()
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
        if hasattr(self, "_persist_settings"):
            self._persist_settings()
        if self.repo_ready:
            self._reload_commits()
            self._schedule_auto_fetch()
            self._schedule_auto_status()
