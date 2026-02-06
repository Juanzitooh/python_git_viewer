#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..core.diff_utils import render_patch_to_widget
from ..core.git_client import run_git


class StashMixin:
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

        stash_read_mode_var = tk.StringVar(value="")
        ttk.Label(top_bar, textvariable=stash_read_mode_var).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(4, 0)
        )

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
        stash_diff_text.configure(font="TkFixedFont")
        stash_diff_text.configure(state="disabled")

        palette = getattr(self, "theme_palette", None)
        if palette and hasattr(self, "_apply_text_widget_theme"):
            self._apply_text_widget_theme(stash_diff_text, palette)
            self._apply_diff_tags(stash_diff_text, palette)
        if palette and hasattr(self, "_apply_listbox_theme"):
            self._apply_listbox_theme(stash_listbox, palette)

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
                stash_read_mode_var.set("")
                return
            try:
                diff = run_git(self.repo_path, ["stash", "show", "-p", ref])
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            display_diff, truncated, shown, total = self._apply_read_mode_to_diff(diff)
            render_patch_to_widget(
                stash_diff_text,
                display_diff,
                read_only=True,
                show_file_headers=True,
                word_diff=self._word_diff_enabled(),
            )
            if truncated:
                stash_read_mode_var.set(f"Modo leitura: {shown}/{total} linhas")
            else:
                stash_read_mode_var.set("")

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
