#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SettingsTabMixin:
    def _build_settings_tab(self) -> None:
        self.settings_tab.grid_columnconfigure(1, weight=1)

        ttk.Label(self.settings_tab, text="Tema:").grid(
            row=0,
            column=0,
            sticky="w",
            padx=8,
            pady=(8, 4),
        )
        theme_label = "Claro" if getattr(self, "theme_name", "light") == "light" else "Escuro"
        self.theme_var = tk.StringVar(value=theme_label)
        self.theme_combo = ttk.Combobox(
            self.settings_tab,
            textvariable=self.theme_var,
            state="readonly",
            width=12,
            values=["Claro", "Escuro"],
        )
        self.theme_combo.grid(row=0, column=1, sticky="w", padx=8, pady=(8, 4))

        ttk.Label(self.settings_tab, text="Limite do histórico (commits):").grid(
            row=1,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.commit_limit_var = tk.StringVar(value=str(self.commit_limit))
        self.commit_limit_entry = ttk.Entry(self.settings_tab, textvariable=self.commit_limit_var, width=12)
        self.commit_limit_entry.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(self.settings_tab, text="Intervalo de fetch automático (segundos):").grid(
            row=2,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.fetch_interval_var = tk.StringVar(value=str(self.fetch_interval_sec))
        self.fetch_interval_entry = ttk.Entry(self.settings_tab, textvariable=self.fetch_interval_var, width=12)
        self.fetch_interval_entry.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(self.settings_tab, text="Intervalo de status automático (segundos):").grid(
            row=3,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.status_interval_var = tk.StringVar(value=str(self.status_interval_sec))
        self.status_interval_entry = ttk.Entry(self.settings_tab, textvariable=self.status_interval_var, width=12)
        self.status_interval_entry.grid(row=3, column=1, sticky="w", padx=8, pady=4)

        ttk.Separator(self.settings_tab, orient="horizontal").grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(8, 4),
        )

        ttk.Label(self.settings_tab, text="Fonte da interface:").grid(
            row=5,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.ui_font_family_var = tk.StringVar(value=getattr(self, "ui_font_family", ""))
        self.ui_font_family_entry = ttk.Entry(self.settings_tab, textvariable=self.ui_font_family_var, width=24)
        self.ui_font_family_entry.grid(row=5, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(self.settings_tab, text="Tamanho da fonte (UI):").grid(
            row=6,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.ui_font_size_var = tk.StringVar(value=str(getattr(self, "ui_font_size", 10)))
        self.ui_font_size_entry = ttk.Entry(self.settings_tab, textvariable=self.ui_font_size_var, width=12)
        self.ui_font_size_entry.grid(row=6, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(self.settings_tab, text="Fonte monoespaçada:").grid(
            row=7,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.mono_font_family_var = tk.StringVar(value=getattr(self, "mono_font_family", ""))
        self.mono_font_family_entry = ttk.Entry(self.settings_tab, textvariable=self.mono_font_family_var, width=24)
        self.mono_font_family_entry.grid(row=7, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(self.settings_tab, text="Tamanho da fonte (mono):").grid(
            row=8,
            column=0,
            sticky="w",
            padx=8,
            pady=4,
        )
        self.mono_font_size_var = tk.StringVar(value=str(getattr(self, "mono_font_size", 10)))
        self.mono_font_size_entry = ttk.Entry(self.settings_tab, textvariable=self.mono_font_size_var, width=12)
        self.mono_font_size_entry.grid(row=8, column=1, sticky="w", padx=8, pady=4)

        actions = ttk.Frame(self.settings_tab)
        actions.grid(row=9, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(actions, text="Aplicar", command=self._apply_settings).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Restaurar padrão", command=self._reset_settings).grid(row=0, column=1)

        self.settings_status_var = tk.StringVar(value="")
        ttk.Label(self.settings_tab, textvariable=self.settings_status_var).grid(
            row=10,
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
            ui_font_size = int(self.ui_font_size_var.get().strip())
            mono_font_size = int(self.mono_font_size_var.get().strip())
        except ValueError:
            self.settings_status_var.set("Valores inválidos. Use números inteiros.")
            return
        if commit_limit <= 0 or fetch_interval < 10 or status_interval < 5:
            self.settings_status_var.set("Valores inválidos. Use números positivos.")
            return
        if ui_font_size <= 0 or mono_font_size <= 0:
            self.settings_status_var.set("Tamanho de fonte inválido.")
            return
        self.commit_limit = commit_limit
        self.fetch_interval_sec = fetch_interval
        self.status_interval_sec = status_interval
        self.theme_name = "light" if self.theme_var.get() == "Claro" else "dark"
        self.ui_font_family = self.ui_font_family_var.get().strip()
        self.ui_font_size = ui_font_size
        self.mono_font_family = self.mono_font_family_var.get().strip()
        self.mono_font_size = mono_font_size
        if not self.ui_font_family or not self.mono_font_family:
            if hasattr(self, "_get_default_font_settings"):
                default_ui_family, _, default_mono_family, _ = self._get_default_font_settings()
                if not self.ui_font_family:
                    self.ui_font_family = default_ui_family
                    self.ui_font_family_var.set(self.ui_font_family)
                if not self.mono_font_family:
                    self.mono_font_family = default_mono_family
                    self.mono_font_family_var.set(self.mono_font_family)
        self.settings_status_var.set("Configurações aplicadas.")
        if hasattr(self, "_apply_theme_settings"):
            self._apply_theme_settings()
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
        if hasattr(self, "_reset_theme_settings"):
            self._reset_theme_settings()
        self.settings_status_var.set("Padrões restaurados.")
        if hasattr(self, "_persist_settings"):
            self._persist_settings()
        if self.repo_ready:
            self._reload_commits()
            self._schedule_auto_fetch()
            self._schedule_auto_status()
