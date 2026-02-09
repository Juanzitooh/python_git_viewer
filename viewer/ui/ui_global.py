#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..core.git_client import is_git_repo, run_git


class GlobalBarMixin:
    def _build_global_bar(self) -> None:
        self.global_bar = ttk.Frame(self)
        self.global_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self.global_bar.grid_columnconfigure(0, weight=1)
        self.global_bar.grid_columnconfigure(1, weight=0)

        self.repo_left_actions = ttk.Frame(self.global_bar)
        self.repo_left_actions.grid(row=0, column=0, sticky="ew")
        self.repo_left_actions.grid_columnconfigure(0, weight=1)

        self.repo_right_actions = ttk.Frame(self.global_bar)
        self.repo_right_actions.grid(row=0, column=1, sticky="e")

        self.repo_selector_frame = ttk.Frame(self.repo_left_actions)
        self.repo_selector_frame.grid(row=0, column=0, sticky="ew")
        self.repo_selector_frame.grid_columnconfigure(0, weight=1)
        self.repo_var = tk.StringVar(value="(nenhum)")
        self.repo_path_combo = ttk.Combobox(self.repo_selector_frame, textvariable=self.repo_var, state="readonly")
        self.repo_path_combo.grid(row=0, column=0, sticky="ew")
        self.repo_path_combo.bind("<<ComboboxSelected>>", self._on_repo_selected)
        self._repo_selector_lookup: dict[str, str] = {}
        self._repo_selector_visible = True

        ttk.Button(self.repo_left_actions, text="Copiar caminho", command=self._copy_repo_path).grid(
            row=0, column=1, padx=(6, 0)
        )

        ttk.Button(self.repo_left_actions, text="Abrir no VS Code", command=self._open_repo_in_vscode).grid(
            row=0, column=2, padx=(6, 0)
        )
        self.repo_favorite_button = ttk.Button(
            self.repo_left_actions,
            text="Adicionar favorito",
            command=self._toggle_current_repo_favorite,
        )
        self.repo_favorite_button.grid(row=0, column=3, padx=(6, 0))

        # Vars kept at global scope because they are shared across tabs.
        self.branch_var = tk.StringVar(value="")
        self.branch_origin_var = tk.StringVar(value="")
        self.branch_dest_var = tk.StringVar(value="")

        self.fetch_button = ttk.Button(self.repo_right_actions, text="Fetch", command=self._fetch_repo)
        self.fetch_button.grid(row=0, column=0, padx=(0, 0))
        self.pull_button = ttk.Button(self.repo_right_actions, text="Pull", command=self._pull_repo)
        self.pull_button.grid(row=0, column=1, padx=(6, 0))
        self.push_button = ttk.Button(self.repo_right_actions, text="Push", command=self._push_repo)
        self.push_button.grid(row=0, column=2, padx=(6, 0))
        self.push_button.bind("<Enter>", self._on_push_button_hover, add=True)
        self.push_button.bind("<Leave>", self._hide_hover_tooltip, add=True)

        self.upstream_var = tk.StringVar(value="")
        self.upstream_label = ttk.Label(self.repo_right_actions, textvariable=self.upstream_var)
        self.upstream_label.grid(row=0, column=3, sticky="w", padx=(12, 0))

        if not hasattr(self, "perf_var"):
            self.perf_var = tk.StringVar(value="")
        self.perf_title_label = ttk.Label(self.repo_right_actions, text="Perf:")
        self.perf_title_label.grid(row=0, column=4, sticky="w", padx=(12, 0))
        self.perf_label = ttk.Label(self.repo_right_actions, textvariable=self.perf_var)
        self.perf_label.grid(row=0, column=5, sticky="w")
        if not getattr(self, "perf_enabled", False):
            self.perf_title_label.grid_remove()
            self.perf_label.grid_remove()
        self._refresh_repo_selector()

    def _fetch_repo(self) -> None:
        if not self.repo_ready:
            return

        def task() -> None:
            run_git(self.repo_path, ["fetch", "--all", "--prune"])

        def success(_result: object) -> None:
            self._set_status("Fetch concluído.")
            self._update_pull_push_labels()

        def error(exc: Exception) -> None:
            messagebox.showerror("Erro", str(exc))

        self._run_async("fetch", "Fetch", task, success, error, perf_trigger="fetch:manual_button")

    def _pull_repo(self) -> None:
        if not self.repo_ready:
            return

        def task() -> None:
            run_git(self.repo_path, ["pull", "--ff-only"])

        def success(_result: object) -> None:
            if hasattr(self, "_bump_repo_state"):
                self._bump_repo_state()
            self._set_status("Pull concluído.")
            self._reload_commits(trigger="post_pull")
            self._refresh_status(trigger="post_pull")
            self._refresh_branches(trigger="post_pull")
            self._update_pull_push_labels()

        def error(exc: Exception) -> None:
            messagebox.showerror("Erro", str(exc))

        self._run_async("pull", "Pull", task, success, error, perf_trigger="pull:manual_button")

    def _push_repo(self) -> None:
        if not self.repo_ready:
            return
        self._hide_hover_tooltip()

        def task() -> None:
            run_git(self.repo_path, ["push"])

        def success(_result: object) -> None:
            self._set_status("Push concluído.")
            self._update_pull_push_labels()
            self._refresh_status(trigger="post_push")
            if self._is_dirty():
                self._set_status("Push concluído, mas ainda há alterações locais.")

        def error(exc: Exception) -> None:
            messagebox.showerror("Erro", str(exc))

        self._run_async("push", "Push", task, success, error, perf_trigger="push:manual_button")

    def _on_push_button_hover(self, event: tk.Event) -> None:
        tooltip = self._get_push_tooltip_text()
        self._show_hover_tooltip("push_button", tooltip, event.x_root + 12, event.y_root + 12)

    def _get_push_tooltip_text(self) -> str:
        if not self.repo_ready:
            return "Selecione um repositório válido."
        upstream = self._get_upstream()
        if not upstream:
            return "Sem upstream configurado para a branch atual."
        try:
            output = run_git(self.repo_path, ["log", "--pretty=format:%h %s", f"{upstream}..HEAD"])
        except RuntimeError as exc:
            return f"Falha ao listar commits para push:\n{exc}"
        commits = [line.strip() for line in output.splitlines() if line.strip()]
        if not commits:
            return "Nada para enviar."
        limit = 12
        visible = commits[:limit]
        suffix = ""
        if len(commits) > limit:
            suffix = f"\n... e mais {len(commits) - limit} commit(s)."
        return "Commits que serão enviados:\n" + "\n".join(visible) + suffix

    def _refresh_branches(self, trigger: str = "") -> None:
        if not self.repo_ready or self.branches_loading:
            return
        self.branches_loading = True
        normalized_trigger = self._normalize_perf_trigger(trigger) or "internal"
        perf_trigger = f"branches:{normalized_trigger}"

        def task() -> tuple[list[str], str]:
            return self._get_branches(), self._get_current_branch()

        def success(result: object) -> None:
            self.branches_loading = False
            branches, current = result  # type: ignore[misc]
            self._render_branches(branches, current)

        def error(exc: Exception) -> None:
            self.branches_loading = False
            messagebox.showerror("Erro", str(exc))

        self._run_async("branches", "Atualizar branches", task, success, error, perf_trigger=perf_trigger)

    def _render_branches(self, branches: list[str], current: str) -> None:
        self.branch_list = branches
        if current and current in branches:
            self.branch_var.set(current)
        elif branches:
            self.branch_var.set(branches[0])
        if hasattr(self, "_update_window_title"):
            self._update_window_title()
        if hasattr(self, "branch_dest_var"):
            if not self.branch_dest_var.get() or self.branch_dest_var.get() not in branches:
                self.branch_dest_var.set(current)
        self._set_status(f"Branch atual: {current}" if current else "Branch atual: (desconhecido)")
        self._update_pull_push_labels()
        self._update_branch_action_branches()
        self._update_operation_preview()
        self._refresh_filter_refs()
        if hasattr(self, "_sync_import_tab_with_current_repo"):
            self._sync_import_tab_with_current_repo()
        if hasattr(self, "_refresh_history_branch_quick_selector"):
            self._refresh_history_branch_quick_selector(branches, current)
        if hasattr(self, "_refresh_commit_branch_quick_selector"):
            self._refresh_commit_branch_quick_selector(branches, current)

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
        perf_trigger = "stash:quick"
        start = self._perf_start("Stash", perf_trigger)
        try:
            try:
                run_git(self.repo_path, ["stash", "push", "-u", "-m", "git_commits_viewer"])
            except RuntimeError as exc:
                messagebox.showerror("Stash", str(exc))
                return
            self._set_status("Stash criado.")
            self._refresh_status(trigger="post_stash")
        finally:
            self._perf_end("Stash", start, perf_trigger)

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
        choice = "checkout"
        if self._is_dirty():
            choice = self._prompt_dirty_checkout()
            if choice == "cancel":
                self.branch_var.set(current)
                return False
        perf_trigger = f"checkout:{target}"
        start = self._perf_start("Checkout branch", perf_trigger)
        try:
            try:
                if choice == "stash":
                    run_git(self.repo_path, ["stash", "push", "-u", "-m", "git_commits_viewer"])
                run_git(self.repo_path, ["checkout", target])
            except RuntimeError as exc:
                messagebox.showerror("Checkout", str(exc))
                return False
            self.branch_var.set(target)
            self._set_status(f"Checkout para {target}.")
            if hasattr(self, "_update_window_title"):
                self._update_window_title()
            if hasattr(self, "_bump_repo_state"):
                self._bump_repo_state()
            self._reload_commits(trigger="post_checkout")
            self._refresh_status(trigger="post_checkout")
            self._refresh_branches(trigger="post_checkout")
            self._update_pull_push_labels()
            return True
        finally:
            self._perf_end("Checkout branch", start, perf_trigger)

    def _prompt_create_branch(self, base_branch: str = "") -> bool:
        if not self.repo_ready:
            messagebox.showinfo("Nova branch", "Selecione um repositório válido antes de criar branch.")
            return False
        base = base_branch.strip() if base_branch else ""
        if not base:
            try:
                base = self._get_current_branch().strip()
            except RuntimeError as exc:
                messagebox.showerror("Nova branch", str(exc))
                return False
        if base:
            prompt = f"Nome da nova branch (base: {base}):"
        else:
            prompt = "Nome da nova branch:"
        branch_name = simpledialog.askstring("Nova branch", prompt, parent=self)
        if branch_name is None:
            return False
        branch_name = branch_name.strip()
        if not branch_name:
            messagebox.showwarning("Nova branch", "Informe o nome da branch.")
            return False
        if branch_name in self.branch_list:
            messagebox.showwarning("Nova branch", f"A branch '{branch_name}' já existe.")
            return False
        args = ["branch", branch_name]
        if base:
            args.append(base)
        perf_trigger = f"create_branch:{branch_name}"
        start = self._perf_start("Criar branch", perf_trigger)
        try:
            try:
                run_git(self.repo_path, args)
            except RuntimeError as exc:
                messagebox.showerror("Nova branch", str(exc))
                return False
            if base:
                self._set_status(f"Branch criada: {branch_name} (base: {base}).")
            else:
                self._set_status(f"Branch criada: {branch_name}.")
            self._refresh_branches(trigger="post_create_branch")
        finally:
            self._perf_end("Criar branch", start, perf_trigger)
        if messagebox.askyesno("Nova branch", f"Branch '{branch_name}' criada. Deseja fazer checkout agora?"):
            return self._checkout_to_branch(branch_name)
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

    @staticmethod
    def _normalize_repo_path_candidate(path: str) -> str:
        return os.path.normpath(os.path.abspath(os.path.expanduser(path.strip())))

    def _format_repo_display_path(self, repo_path: str) -> str:
        if not repo_path:
            return "(nenhum)"
        workspace_root = str(getattr(self, "repo_scan_root", "")).strip()
        normalized_repo = self._normalize_repo_path_candidate(repo_path)
        if workspace_root:
            normalized_root = self._normalize_repo_path_candidate(workspace_root)
            try:
                common = os.path.commonpath([normalized_repo, normalized_root])
            except ValueError:
                common = ""
            if common == normalized_root:
                relative = os.path.relpath(normalized_repo, normalized_root)
                if relative in (".", ""):
                    return "/"
                return "/" + relative.replace(os.sep, "/")
        return normalized_repo

    def _refresh_repo_selector(self) -> None:
        if not hasattr(self, "repo_path_combo"):
            return
        favorite_paths: list[str] = []
        for path in getattr(self, "favorite_repos", []):
            if not path:
                continue
            normalized = self._normalize_repo_path_candidate(path)
            if normalized not in favorite_paths:
                favorite_paths.append(normalized)
        other_paths: list[str] = []
        for path in getattr(self, "recent_repos", []):
            if not path:
                continue
            normalized = self._normalize_repo_path_candidate(path)
            if normalized in favorite_paths or normalized in other_paths:
                continue
            other_paths.append(normalized)
        current = ""
        if self.repo_path:
            current = self._normalize_repo_path_candidate(self.repo_path)
            if current not in favorite_paths and current not in other_paths:
                other_paths.insert(0, current)
        ordered_paths = favorite_paths + other_paths
        favorite_set = set(favorite_paths)
        labels: list[str] = []
        lookup: dict[str, str] = {}
        path_to_label: dict[str, str] = {}
        for path in ordered_paths:
            base = self._format_repo_display_path(path)
            if path in favorite_set:
                base = f"★ {base}"
            label = base
            suffix = 2
            while label in lookup:
                label = f"{base} [{suffix}]"
                suffix += 1
            labels.append(label)
            lookup[label] = path
            path_to_label[path] = label
        self._repo_selector_lookup = lookup
        self.repo_path_combo.configure(values=labels)
        if self.repo_ready and current:
            self.repo_var.set(path_to_label.get(current, self._format_repo_display_path(current)))
        else:
            self.repo_var.set("(nenhum)")
        self._update_repo_favorite_button()

    def _update_repo_display_path(self) -> None:
        self._refresh_repo_selector()

    def _on_repo_selected(self, _event: tk.Event) -> None:
        if not hasattr(self, "repo_var") or not hasattr(self, "_repo_selector_lookup"):
            return
        label = self.repo_var.get().strip()
        selected_path = self._repo_selector_lookup.get(label)
        if not selected_path:
            return
        if self.repo_ready and self.repo_path:
            current = self._normalize_repo_path_candidate(self.repo_path)
            if current == selected_path:
                return
        self._set_repo_path(selected_path, initial=False)

    def _refresh_repo_selector_visibility(self) -> None:
        if not hasattr(self, "repo_selector_frame"):
            return
        if not hasattr(self, "tabs") or not hasattr(self, "repos_tab"):
            self._set_repo_selector_visibility(True)
            return
        tab_id = self.tabs.select()
        is_repos_tab = bool(tab_id) and str(tab_id) == str(self.repos_tab)
        self._set_repo_selector_visibility(not is_repos_tab)

    def _set_repo_selector_visibility(self, visible: bool) -> None:
        if not hasattr(self, "repo_selector_frame"):
            return
        if visible:
            self.repo_selector_frame.grid()
            if hasattr(self, "repo_left_actions"):
                self.repo_left_actions.grid_columnconfigure(0, weight=1)
        else:
            self.repo_selector_frame.grid_remove()
            if hasattr(self, "repo_left_actions"):
                self.repo_left_actions.grid_columnconfigure(0, weight=0)
        self._repo_selector_visible = visible

    def _update_repo_favorite_button(self) -> None:
        if not hasattr(self, "repo_favorite_button"):
            return
        if not self.repo_ready or not self.repo_path:
            self.repo_favorite_button.configure(text="Adicionar favorito", state="disabled")
            return
        current = self._normalize_repo_path_candidate(self.repo_path)
        favorite_set = {self._normalize_repo_path_candidate(path) for path in getattr(self, "favorite_repos", [])}
        if current in favorite_set:
            self.repo_favorite_button.configure(text="Remover favorito", state="normal")
        else:
            self.repo_favorite_button.configure(text="Adicionar favorito", state="normal")

    def _toggle_current_repo_favorite(self) -> None:
        if not self.repo_ready or not self.repo_path:
            return
        current = self._normalize_repo_path_candidate(self.repo_path)
        favorite_set = {self._normalize_repo_path_candidate(path) for path in getattr(self, "favorite_repos", [])}
        if current in favorite_set:
            self._remove_favorite_repo(current)
        else:
            self._add_favorite_repo(current)
        self._refresh_repo_selector()

    def _copy_repo_path(self) -> None:
        if not self.repo_ready or not self.repo_path:
            messagebox.showinfo("Repo", "Selecione um repositório antes de copiar o caminho.")
            return
        self.clipboard_clear()
        self.clipboard_append(self.repo_path)
        self.update()

    def _apply_repo_from_entry(self) -> None:
        if not hasattr(self, "repo_var"):
            return
        path = self.repo_var.get().strip()
        if not path:
            self._set_repo_ui_no_repo()
            return
        self._set_repo_path(path, initial=False)

    def _open_repo_dialog(self) -> None:
        path = filedialog.askdirectory()
        if not path:
            return
        self._set_repo_path(path, initial=False)

    def _set_repo_path(self, path: str, initial: bool) -> bool:
        if hasattr(self, "_hide_hover_tooltip"):
            self._hide_hover_tooltip()
        repo_path = os.path.abspath(path)
        if not os.path.isdir(repo_path) or not is_git_repo(repo_path):
            if not initial:
                messagebox.showwarning("Repo", "Selecione um repositório git válido.")
            self._set_repo_ui_no_repo()
            return False
        self.repo_path = repo_path
        self.repo_ready = True
        if hasattr(self, "status_head_hash"):
            self.status_head_hash = ""
        self._update_repo_display_path()
        if hasattr(self, "_register_recent_repo"):
            self._register_recent_repo(repo_path, promote=False)
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        if hasattr(self, "_update_window_title"):
            self._update_window_title()

        self.patch_cache.clear()
        self.full_patch_cache.clear()
        self.selected_file_by_commit.clear()
        self._reload_commits(trigger="repo_switch")

        # Limpa seletores de branch da aba Comparar para evitar refs do repo anterior.
        self.branch_list = []
        self.branch_var.set("")
        if hasattr(self, "branch_origin_var"):
            self.branch_origin_var.set("")
        if hasattr(self, "branch_dest_var"):
            self.branch_dest_var.set("")
        if hasattr(self, "compare_origin_combo"):
            self.compare_origin_combo.configure(values=[], state="disabled")
        if hasattr(self, "compare_dest_combo"):
            self.compare_dest_combo.configure(values=[], state="disabled")
        if hasattr(self, "_clear_branch_comparison"):
            self._clear_branch_comparison("Atualizando branches do repositório...")

        self._set_action_visibility(self.fetch_button, True)
        self._refresh_branches(trigger="repo_switch")
        self._refresh_status(trigger="repo_switch")
        self._update_operation_preview()
        self._schedule_auto_fetch()
        self._schedule_auto_status()
        return True

    def _set_repo_ui_no_repo(self) -> None:
        self.repo_ready = False
        self.repo_path = ""
        if hasattr(self, "status_head_hash"):
            self.status_head_hash = ""
        self._update_repo_display_path()
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
        if hasattr(self, "local_only_commit_hashes"):
            self.local_only_commit_hashes = set()
        if hasattr(self, "history_has_upstream"):
            self.history_has_upstream = False
        self.commit_details_cache.clear()
        self.current_commit_hash = None
        if hasattr(self, "status_signature"):
            self.status_signature = ""
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
        if hasattr(self, "branch_dest_var"):
            self.branch_dest_var.set("")
        if hasattr(self, "diff_scope_combo"):
            self.diff_scope_combo.configure(state="disabled")
            self.diff_scope_var.set("Unstaged")
        if hasattr(self, "filter_branch_var"):
            self.filter_branch_var.set("(todas)")
        if hasattr(self, "filter_tag_var"):
            self.filter_tag_var.set("(todas)")
        if hasattr(self, "filter_repo_status_var"):
            self.filter_repo_status_var.set("Todos")
        if hasattr(self, "filter_branch_values"):
            self.filter_branch_values = ["(todas)"]
        if hasattr(self, "filter_tag_values"):
            self.filter_tag_values = ["(todas)"]
        filter_branch_combo = getattr(self, "filter_branch_combo", None)
        if filter_branch_combo is not None:
            filter_branch_combo.configure(values=["(todas)"], state="disabled")
        filter_tag_combo = getattr(self, "filter_tag_combo", None)
        if filter_tag_combo is not None:
            filter_tag_combo.configure(values=["(todas)"], state="disabled")
        filter_repo_status_combo = getattr(self, "filter_repo_status_combo", None)
        if filter_repo_status_combo is not None:
            filter_repo_status_combo.configure(state="disabled")
        if hasattr(self, "_sync_import_tab_with_current_repo"):
            self._sync_import_tab_with_current_repo()
        if hasattr(self, "_close_filter_modal"):
            self._close_filter_modal()
        if hasattr(self, "_hide_commit_tooltip"):
            self._hide_commit_tooltip()
        if hasattr(self, "_hide_hover_tooltip"):
            self._hide_hover_tooltip()
        if hasattr(self, "_refresh_history_branch_quick_selector"):
            self._refresh_history_branch_quick_selector([], "")
        if hasattr(self, "_refresh_commit_branch_quick_selector"):
            self._refresh_commit_branch_quick_selector([], "")
        self._update_filter_status()
        self._set_action_visibility(self.fetch_button, False)
        self._set_action_visibility(self.pull_button, False)
        self._set_action_visibility(self.push_button, False)
        if hasattr(self, "_clear_branch_comparison"):
            self._clear_branch_comparison("Selecione um repositório.")
        if hasattr(self, "_update_branch_action_branches"):
            self._update_branch_action_branches()
        if hasattr(self, "_refresh_repo_status_panel"):
            self._refresh_repo_status_panel()
        if hasattr(self, "_bump_repo_state"):
            self._bump_repo_state()
        if hasattr(self, "_update_window_title"):
            self._update_window_title()
        self.upstream_var.set("")
        self._set_status("Selecione um repositório.")
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

    def _fetch_repo_internal(self, show_errors: bool, trigger: str = "") -> bool:
        if not self.repo_ready:
            return False
        normalized_trigger = self._normalize_perf_trigger(trigger) or "internal"
        perf_trigger = f"fetch:{normalized_trigger}"
        start = self._perf_start("Fetch", perf_trigger)
        try:
            run_git(self.repo_path, ["fetch", "--all", "--prune"])
        except RuntimeError as exc:
            if show_errors:
                messagebox.showerror("Erro", str(exc))
            self._perf_end("Fetch", start, perf_trigger)
            return False
        self._perf_end("Fetch", start, perf_trigger)
        self._set_status("Fetch concluído.")
        self._update_pull_push_labels()
        return True

    def _auto_fetch(self) -> None:
        self._fetch_repo_internal(show_errors=False, trigger="auto_timer")
        self._schedule_auto_fetch()

    def _auto_status(self) -> None:
        self._refresh_status(trigger="auto_timer")
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
