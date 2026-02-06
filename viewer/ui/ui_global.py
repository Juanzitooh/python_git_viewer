#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..core.git_client import is_git_repo, run_git


class GlobalBarMixin:
    def _build_global_bar(self) -> None:
        self.global_bar = ttk.Frame(self)
        self.global_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self.global_bar.grid_columnconfigure(1, weight=1)
        self.global_bar.grid_columnconfigure(6, weight=1)

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

        ttk.Button(self.global_bar, text="VS Code", command=self._open_repo_in_vscode).grid(
            row=0, column=4, padx=(6, 0)
        )

        ttk.Label(self.global_bar, text="Branch:").grid(row=0, column=5, sticky="w", padx=(12, 0))

        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(
            self.global_bar,
            textvariable=self.branch_var,
            state="readonly",
            width=24,
        )
        self.branch_combo.grid(row=0, column=6, sticky="w")
        self.branch_combo.bind("<<ComboboxSelected>>", self._on_branch_selected)

        ttk.Label(self.global_bar, text="Origem:").grid(row=0, column=7, sticky="w", padx=(12, 0))
        self.branch_origin_var = tk.StringVar()
        self.branch_origin_combo = ttk.Combobox(
            self.global_bar,
            textvariable=self.branch_origin_var,
            state="readonly",
            width=18,
        )
        self.branch_origin_combo.grid(row=0, column=8, sticky="w")
        self.branch_origin_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_operation_preview())

        ttk.Label(self.global_bar, text="Destino:").grid(row=0, column=9, sticky="w", padx=(12, 0))
        self.branch_dest_var = tk.StringVar(value="")
        self.branch_dest_label = ttk.Label(self.global_bar, textvariable=self.branch_dest_var)
        self.branch_dest_label.grid(row=0, column=10, sticky="w")

        self.fetch_button = ttk.Button(self.global_bar, text="Fetch", command=self._fetch_repo)
        self.fetch_button.grid(row=0, column=11, padx=(12, 0))
        self.pull_button = ttk.Button(self.global_bar, text="Pull", command=self._pull_repo)
        self.pull_button.grid(row=0, column=12, padx=(6, 0))
        self.push_button = ttk.Button(self.global_bar, text="Push", command=self._push_repo)
        self.push_button.grid(row=0, column=13, padx=(6, 0))

        self.upstream_var = tk.StringVar(value="")
        self.upstream_label = ttk.Label(self.global_bar, textvariable=self.upstream_var)
        self.upstream_label.grid(row=0, column=14, sticky="w", padx=(12, 0))

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

    def _get_vscode_command(self) -> list[str] | None:
        for candidate in ("code", "code-insiders", "codium"):
            resolved = shutil.which(candidate)
            if resolved:
                return [resolved]
        return None

    def _open_path_in_vscode(self, path: str, *, use_goto: bool) -> bool:
        command = self._get_vscode_command()
        if not command:
            messagebox.showwarning(
                "VS Code",
                "Comando `code` não encontrado. Verifique se o VS Code está instalado e no PATH.",
            )
            return False
        if use_goto:
            command += ["-g", path]
        else:
            command.append(path)
        try:
            subprocess.Popen(command)
        except OSError as exc:
            messagebox.showerror("VS Code", f"Falha ao abrir no VS Code: {exc}")
            return False
        return True

    def _open_repo_in_vscode(self) -> None:
        if not self.repo_ready or not self.repo_path:
            messagebox.showinfo("VS Code", "Selecione um repositório válido antes de abrir.")
            return
        if not os.path.isdir(self.repo_path):
            messagebox.showwarning("VS Code", "Caminho do repositório inválido.")
            return
        self._open_path_in_vscode(self.repo_path, use_goto=False)

    def _open_repo_file_in_vscode(self, repo_relative_path: str) -> bool:
        if not self.repo_ready or not self.repo_path:
            messagebox.showinfo("VS Code", "Selecione um repositório válido antes de abrir arquivos.")
            return False
        if not repo_relative_path:
            messagebox.showwarning("VS Code", "Caminho do arquivo não informado.")
            return False
        if os.path.isabs(repo_relative_path):
            abs_path = repo_relative_path
        else:
            abs_path = os.path.join(self.repo_path, repo_relative_path)
        abs_path = os.path.normpath(abs_path)
        if not os.path.exists(abs_path):
            messagebox.showwarning("VS Code", f"Arquivo não encontrado: {repo_relative_path}")
            return False
        return self._open_path_in_vscode(abs_path, use_goto=True)

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

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

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
