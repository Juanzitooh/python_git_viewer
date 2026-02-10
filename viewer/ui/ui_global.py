#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import quote

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
        self.repo_left_actions.grid_columnconfigure(1, weight=0)

        self.repo_right_actions = ttk.Frame(self.global_bar)
        self.repo_right_actions.grid(row=0, column=1, sticky="e")

        self.repo_selector_frame = ttk.Frame(self.repo_left_actions)
        self.repo_selector_frame.grid(row=0, column=0, sticky="ew")
        self.repo_selector_frame.grid_columnconfigure(0, weight=1)
        self.repo_var = tk.StringVar(value="(nenhum)")
        self.repo_path_combo = ttk.Combobox(self.repo_selector_frame, textvariable=self.repo_var, state="readonly")
        self.repo_path_combo.grid(row=0, column=0, sticky="ew")
        self.repo_path_combo.bind("<<ComboboxSelected>>", self._on_repo_selected)
        self.repo_path_combo.bind("<Button-3>", self._on_repo_selector_context_menu, add=True)
        self.repo_path_combo_dropdown = None
        self.repo_path_combo_dropdown_path = ""
        self._bind_repo_selector_dropdown_context_menu()
        self._repo_selector_lookup: dict[str, str] = {}
        self._repo_selector_visible = True
        self.repo_context_menu: tk.Menu | None = None
        self._repo_context_selection_lock = False
        self._repo_focus_out_job: str | None = None
        self.bind_all("<ButtonPress-1>", self._on_global_pointer_click, add=True)
        self.bind_all("<ButtonPress-2>", self._on_global_pointer_click, add=True)
        self.bind_all("<ButtonPress-3>", self._on_global_right_click, add=True)
        self.bind_all("<Escape>", self._dismiss_repo_context_menu, add=True)
        self.bind_all("<FocusOut>", self._on_app_focus_out, add=True)
        self.bind("<Unmap>", self._dismiss_repo_context_menu, add=True)

        self.global_branch_quick_frame = ttk.Frame(self.repo_left_actions)
        self.global_branch_quick_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Label(self.global_branch_quick_frame, text="Branch:").grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.global_branch_quick_var = tk.StringVar(value="")
        self.global_branch_quick_combo = ttk.Combobox(
            self.global_branch_quick_frame,
            textvariable=self.global_branch_quick_var,
            state="disabled",
            width=18,
            values=[],
        )
        self.global_branch_quick_combo.grid(row=0, column=1, sticky="e")
        self.global_branch_quick_combo.bind("<<ComboboxSelected>>", self._on_global_quick_branch_selected)
        self.global_new_branch_button = ttk.Button(
            self.global_branch_quick_frame,
            text="Nova branch",
            command=self._create_global_quick_branch,
            state="disabled",
        )
        self.global_new_branch_button.grid(row=0, column=2, sticky="e", padx=(6, 0))

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
        self._refresh_global_branch_quick_selector([], "")
        self._refresh_global_branch_quick_visibility()

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
            self._reload_commits(trigger="post_push")
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
        self._refresh_global_branch_quick_selector(branches, current)

    def _get_branches(self) -> list[str]:
        output = run_git(self.repo_path, ["branch", "--format=%(refname:short)"])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _refresh_global_branch_quick_selector(self, branches: list[str], current: str) -> None:
        combo = getattr(self, "global_branch_quick_combo", None)
        var = getattr(self, "global_branch_quick_var", None)
        new_branch_button = getattr(self, "global_new_branch_button", None)
        if combo is None or var is None:
            return
        if not self.repo_ready or not branches:
            combo.configure(values=[], state="disabled")
            var.set("")
            if new_branch_button is not None:
                new_branch_button.configure(state="disabled")
            return
        combo.configure(values=branches, state="readonly")
        if new_branch_button is not None:
            new_branch_button.configure(state="normal")
        if current and current in branches:
            var.set(current)
            return
        selected = var.get().strip()
        if selected in branches:
            return
        var.set(branches[0])

    def _on_global_quick_branch_selected(self, _event: tk.Event) -> None:
        if not self.repo_ready:
            return
        target = self.global_branch_quick_var.get().strip()
        if not target:
            return
        current = self.branch_var.get().strip() if hasattr(self, "branch_var") else ""
        if target == current:
            return
        if not self._checkout_to_branch(target):
            self._refresh_global_branch_quick_selector(self.branch_list, current)

    def _create_global_quick_branch(self) -> None:
        base = self.global_branch_quick_var.get().strip() if hasattr(self, "global_branch_quick_var") else ""
        self._prompt_create_branch(base)

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

    def _open_repo_in_vscode(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("VS Code", "Selecione um repositório válido antes de abrir.")
            return False
        if not os.path.isdir(resolved_repo):
            messagebox.showwarning("VS Code", "Caminho do repositório inválido.")
            return False
        return self._open_path_in_vscode(resolved_repo, use_goto=False)

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
        self._bind_repo_selector_dropdown_context_menu()

    def _update_repo_display_path(self) -> None:
        self._refresh_repo_selector()

    def _on_repo_selected(self, _event: tk.Event) -> None:
        if not hasattr(self, "repo_var") or not hasattr(self, "_repo_selector_lookup"):
            return
        if getattr(self, "_repo_context_selection_lock", False):
            self._repo_context_selection_lock = False
            self._update_repo_display_path()
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
            self._refresh_global_branch_quick_visibility()
            return
        tab_id = self.tabs.select()
        is_repos_tab = bool(tab_id) and str(tab_id) == str(self.repos_tab)
        self._set_repo_selector_visibility(not is_repos_tab)
        self._refresh_global_branch_quick_visibility()

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

    def _refresh_global_branch_quick_visibility(self) -> None:
        frame = getattr(self, "global_branch_quick_frame", None)
        if frame is None:
            return
        should_show = bool(getattr(self, "_repo_selector_visible", False)) and self._is_global_branch_quick_tab_selected()
        if should_show:
            frame.grid()
            return
        frame.grid_remove()

    def _is_global_branch_quick_tab_selected(self) -> bool:
        if not hasattr(self, "tabs"):
            return False
        try:
            selected = self.tabs.select()
        except tk.TclError:
            return False
        if not selected:
            return False
        selected_path = str(selected)
        targets: list[str] = []
        for name in ("branch_tab", "history_tab", "import_tab"):
            tab_widget = getattr(self, name, None)
            if tab_widget is None:
                continue
            targets.append(str(tab_widget))
        return selected_path in targets

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

    def _resolve_repo_action_path(self, repo_path: str = "") -> str:
        candidate = repo_path.strip()
        if candidate:
            normalized = self._normalize_repo_path_candidate(candidate)
            if os.path.isdir(normalized) and is_git_repo(normalized):
                return normalized
            return ""
        if hasattr(self, "repo_var") and hasattr(self, "_repo_selector_lookup"):
            label = self.repo_var.get().strip()
            selected = str(self._repo_selector_lookup.get(label, "")).strip()
            if selected:
                normalized = self._normalize_repo_path_candidate(selected)
                if os.path.isdir(normalized) and is_git_repo(normalized):
                    return normalized
        if self.repo_ready and self.repo_path:
            normalized = self._normalize_repo_path_candidate(self.repo_path)
            if os.path.isdir(normalized) and is_git_repo(normalized):
                return normalized
        return ""

    def _on_repo_selector_context_menu(self, event: tk.Event) -> str:
        self._repo_context_selection_lock = True
        selected = self._resolve_repo_action_path("")
        self._show_repo_context_menu(event, selected)
        return "break"

    def _resolve_repo_selector_dropdown_path(self) -> str:
        if not hasattr(self, "repo_path_combo"):
            return ""
        try:
            popdown_path = str(self.tk.call("ttk::combobox::PopdownWindow", str(self.repo_path_combo)))
        except tk.TclError:
            self.repo_path_combo_dropdown_path = ""
            return ""
        listbox_path = f"{popdown_path}.f.l"
        self.repo_path_combo_dropdown_path = listbox_path
        return listbox_path

    def _bind_repo_selector_dropdown_context_menu(self) -> None:
        if not hasattr(self, "repo_path_combo"):
            return
        listbox_path = self._resolve_repo_selector_dropdown_path()
        if not listbox_path:
            self.repo_path_combo_dropdown = None
            return
        try:
            listbox_widget = self.nametowidget(listbox_path)
        except (tk.TclError, KeyError):
            self.repo_path_combo_dropdown = None
            return
        self.repo_path_combo_dropdown = listbox_widget
        listbox_widget.bind("<Button-3>", self._on_repo_selector_dropdown_context_menu, add=True)
        listbox_widget.bind("<ButtonPress-3>", self._on_repo_selector_dropdown_context_menu, add=True)

    def _on_global_right_click(self, event: tk.Event) -> None:
        if hasattr(self, "_dismiss_commit_context_menu"):
            self._dismiss_commit_context_menu(event)
        if self._is_pointer_inside_widget(getattr(self, "repo_path_combo", None), event.x_root, event.y_root):
            self._on_repo_selector_context_menu(event)
            return
        dropdown_label = self._get_repo_dropdown_label_at_pointer(event.x_root, event.y_root)
        if not dropdown_label:
            return
        self._repo_context_selection_lock = True
        selected_path = str(self._repo_selector_lookup.get(dropdown_label, "")).strip()
        self._show_repo_context_menu(event, selected_path, close_dropdown=False)

    def _on_global_pointer_click(self, event: tk.Event) -> None:
        if hasattr(self, "_dismiss_commit_context_menu"):
            self._dismiss_commit_context_menu(event)
        close_dropdown = False
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if isinstance(x_root, int) and isinstance(y_root, int):
            inside_combo = self._is_pointer_inside_widget(getattr(self, "repo_path_combo", None), x_root, y_root)
            inside_dropdown = self._is_point_inside_repo_dropdown(x_root, y_root)
            close_dropdown = not inside_combo and not inside_dropdown
        self._dismiss_repo_context_menu(event, close_dropdown=close_dropdown)

    def _is_pointer_inside_widget(self, widget: object | None, x_root: int, y_root: int) -> bool:
        if widget is None:
            return False
        try:
            if int(widget.winfo_ismapped()) != 1:
                return False
            root_x = int(widget.winfo_rootx())
            root_y = int(widget.winfo_rooty())
            width = int(widget.winfo_width())
            height = int(widget.winfo_height())
        except (tk.TclError, ValueError, TypeError, AttributeError):
            return False
        if width <= 0 or height <= 0:
            return False
        return root_x <= x_root < (root_x + width) and root_y <= y_root < (root_y + height)

    def _is_point_inside_repo_dropdown(self, x_root: int, y_root: int) -> bool:
        dropdown_path = self._resolve_repo_selector_dropdown_path()
        if not dropdown_path:
            return False
        try:
            if int(self.tk.call("winfo", "ismapped", dropdown_path)) != 1:
                return False
            root_x = int(self.tk.call("winfo", "rootx", dropdown_path))
            root_y = int(self.tk.call("winfo", "rooty", dropdown_path))
            width = int(self.tk.call("winfo", "width", dropdown_path))
            height = int(self.tk.call("winfo", "height", dropdown_path))
        except (tk.TclError, ValueError, TypeError):
            return False
        if width <= 0 or height <= 0:
            return False
        return root_x <= x_root < (root_x + width) and root_y <= y_root < (root_y + height)

    def _get_repo_dropdown_label_at_pointer(self, x_root: int, y_root: int) -> str:
        if not self._is_point_inside_repo_dropdown(x_root, y_root):
            return ""
        dropdown_path = self._resolve_repo_selector_dropdown_path()
        if not dropdown_path:
            return ""
        try:
            root_y = int(self.tk.call("winfo", "rooty", dropdown_path))
        except (tk.TclError, ValueError, TypeError):
            return ""
        local_y = y_root - root_y
        try:
            index = int(self.tk.call(dropdown_path, "nearest", local_y))
            return str(self.tk.call(dropdown_path, "get", index)).strip()
        except (tk.TclError, ValueError, TypeError):
            return ""

    def _resolve_repo_selector_dropdown_widget(self, widget: object | None) -> object | None:
        if widget is not None and hasattr(widget, "nearest") and hasattr(widget, "get"):
            return widget
        if isinstance(widget, str):
            try:
                resolved = self.nametowidget(widget)
            except (tk.TclError, KeyError):
                resolved = None
            if resolved is not None and hasattr(resolved, "nearest") and hasattr(resolved, "get"):
                self.repo_path_combo_dropdown = resolved
                return resolved
        cached = getattr(self, "repo_path_combo_dropdown", None)
        if cached is not None and hasattr(cached, "nearest") and hasattr(cached, "get"):
            return cached
        dropdown_path = str(getattr(self, "repo_path_combo_dropdown_path", "")).strip()
        if not dropdown_path:
            return None
        try:
            resolved = self.nametowidget(dropdown_path)
        except (tk.TclError, KeyError):
            return None
        if resolved is None or not hasattr(resolved, "nearest") or not hasattr(resolved, "get"):
            return None
        self.repo_path_combo_dropdown = resolved
        return resolved

    def _on_repo_selector_dropdown_context_menu(self, event: tk.Event) -> str:
        self._repo_context_selection_lock = True
        label = self._get_repo_dropdown_label_at_pointer(event.x_root, event.y_root)
        if not label:
            dropdown = self._resolve_repo_selector_dropdown_widget(getattr(event, "widget", None))
            if dropdown is None:
                return "break"
            if isinstance(dropdown, str):
                try:
                    index = int(self.tk.call(dropdown, "nearest", event.y))
                    label = str(self.tk.call(dropdown, "get", index)).strip()
                except (tk.TclError, ValueError, TypeError):
                    return "break"
            else:
                try:
                    index = int(dropdown.nearest(event.y))
                    label = str(dropdown.get(index)).strip()
                except (tk.TclError, ValueError, TypeError):
                    return "break"
        selected_path = str(self._repo_selector_lookup.get(label, "")).strip()
        self._show_repo_context_menu(event, selected_path, close_dropdown=False)
        return "break"

    def _on_repo_context_menu_request(self, event: tk.Event, repo_path: str = "", *, source: str = "") -> str:
        self._show_repo_context_menu(event, repo_path, source=source)
        return "break"

    def _dismiss_repo_selector_dropdown(self) -> None:
        if not hasattr(self, "repo_path_combo"):
            return
        try:
            self.tk.call("ttk::combobox::Unpost", str(self.repo_path_combo))
        except tk.TclError:
            return

    def _on_app_focus_out(self, _event: tk.Event | None = None) -> None:
        if self._repo_focus_out_job is not None:
            try:
                self.after_cancel(self._repo_focus_out_job)
            except tk.TclError:
                pass
        self._repo_focus_out_job = self.after(160, self._dismiss_repo_overlays_if_unfocused)

    def _focus_path_for_display(self) -> str:
        try:
            value = self.tk.call("focus", "-displayof", str(self))
        except tk.TclError:
            return ""
        if value is None:
            return ""
        return str(value).strip()

    def _has_local_focus(self) -> bool:
        focus_path = self._focus_path_for_display()
        if not focus_path:
            return False
        root_path = str(self).strip()
        if not root_path:
            return False
        return focus_path.startswith(root_path)

    def _is_pointer_over_local_widget(self) -> bool:
        try:
            x_root = int(self.winfo_pointerx())
            y_root = int(self.winfo_pointery())
        except (tk.TclError, ValueError, TypeError):
            return False
        try:
            widget = self.winfo_containing(x_root, y_root)
        except tk.TclError:
            return False
        if widget is None:
            return False
        path = str(widget).strip()
        if not path:
            return False
        root_path = str(self).strip()
        if root_path and path.startswith(root_path):
            return True
        dropdown_path = str(getattr(self, "repo_path_combo_dropdown_path", "")).strip()
        if dropdown_path and (path == dropdown_path or path.startswith(f"{dropdown_path}.")):
            return True
        return ".popdown." in path

    def _dismiss_repo_overlays_if_unfocused(self) -> None:
        self._repo_focus_out_job = None
        if self._has_local_focus():
            return
        if self._is_pointer_over_local_widget():
            return
        if hasattr(self, "_dismiss_commit_context_menu"):
            self._dismiss_commit_context_menu()
        self._dismiss_repo_context_menu(close_dropdown=True)

    def _dismiss_repo_context_menu(
        self,
        _event: tk.Event | None = None,
        *,
        clear_lock: bool = True,
        close_dropdown: bool = False,
    ) -> None:
        if _event is not None and self._is_event_inside_repo_context_menu(_event):
            return
        if close_dropdown:
            self._dismiss_repo_selector_dropdown()
        if clear_lock:
            self._repo_context_selection_lock = False
        menu = getattr(self, "repo_context_menu", None)
        self.repo_context_menu = None
        if menu is None:
            return
        try:
            menu.unpost()
        except tk.TclError:
            pass
        try:
            menu.destroy()
        except tk.TclError:
            pass

    def _is_event_inside_repo_context_menu(self, event: tk.Event) -> bool:
        menu = getattr(self, "repo_context_menu", None)
        if menu is None:
            return False
        menu_path = str(menu).strip()
        if not menu_path:
            return False
        candidate_paths: list[str] = []
        widget = getattr(event, "widget", None)
        if widget is not None:
            widget_path = str(widget).strip()
            if widget_path:
                candidate_paths.append(widget_path)
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if isinstance(x_root, int) and isinstance(y_root, int):
            try:
                contained = self.tk.call("winfo", "containing", x_root, y_root)
            except tk.TclError:
                contained = ""
            contained_path = str(contained).strip()
            if contained_path:
                candidate_paths.append(contained_path)
        for path in candidate_paths:
            if path == menu_path or path.startswith(f"{menu_path}."):
                return True
        return False

    def _on_repo_context_menu_unmap(self, _event: tk.Event | None = None) -> None:
        self._repo_context_selection_lock = False
        self.repo_context_menu = None

    def _show_repo_context_menu(
        self,
        event: tk.Event,
        repo_path: str = "",
        *,
        close_dropdown: bool = True,
        source: str = "",
    ) -> None:
        if self._repo_focus_out_job is not None:
            try:
                self.after_cancel(self._repo_focus_out_job)
            except tk.TclError:
                pass
            self._repo_focus_out_job = None
        self._dismiss_repo_context_menu(clear_lock=False)
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            self._repo_context_selection_lock = False
            return
        if close_dropdown:
            self._dismiss_repo_selector_dropdown()
        normalized_repo = self._normalize_repo_path_candidate(resolved_repo)
        current_repo = self._normalize_repo_path_candidate(self.repo_path) if self.repo_ready and self.repo_path else ""
        is_current = normalized_repo == current_repo
        favorite_set = {self._normalize_repo_path_candidate(path) for path in getattr(self, "favorite_repos", [])}
        is_favorite = normalized_repo in favorite_set
        menu = tk.Menu(self, tearoff=0)

        def run_repo_menu_action(action: object) -> None:
            self._dismiss_repo_context_menu(close_dropdown=True)
            action()

        if is_current:
            menu.add_command(label="Repositório atual", state="disabled")
        else:
            menu.add_command(
                label="Abrir no Git Viewer",
                command=lambda path=normalized_repo: run_repo_menu_action(
                    lambda: self._set_repo_path(path, initial=False)
                ),
            )
        menu.add_command(
            label="Abrir no VS Code",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_in_vscode(path)),
        )
        menu.add_command(
            label="Abrir na Pasta",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_in_file_manager(path)),
        )
        github_menu = tk.Menu(menu, tearoff=0)
        github_menu.add_command(
            label="Abrir repositorio",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_in_github(path)),
        )
        github_menu.add_command(
            label="Abrir branch atual",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_branch_in_github(path)),
        )
        github_menu.add_command(
            label="Abrir commits da branch",
            command=lambda path=normalized_repo: run_repo_menu_action(
                lambda: self._open_repo_branch_commits_in_github(path)
            ),
        )
        github_menu.add_command(
            label="Abrir issues",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_issues_in_github(path)),
        )
        github_menu.add_command(
            label="Abrir actions",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_actions_in_github(path)),
        )
        github_menu.add_command(
            label="Abrir releases",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._open_repo_releases_in_github(path)),
        )
        github_menu.add_separator()
        github_menu.add_command(
            label="Copiar URL do repositorio",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._copy_repo_github_url(path)),
        )
        github_menu.add_command(
            label="Copiar URL da branch atual",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._copy_repo_branch_github_url(path)),
        )
        menu.add_cascade(label="GitHub", menu=github_menu)
        menu.add_separator()
        menu.add_command(
            label="Copiar caminho",
            command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._copy_repo_path(path)),
        )
        menu.add_separator()
        if is_favorite:
            menu.add_command(
                label="Remover dos favoritos",
                command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._remove_favorite_repo(path)),
            )
        else:
            menu.add_command(
                label="Adicionar aos favoritos",
                command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._add_favorite_repo(path)),
            )
        if source == "card":
            menu.add_separator()
            menu.add_command(
                label="Excluir repositório...",
                command=lambda path=normalized_repo: run_repo_menu_action(lambda: self._delete_repo_directory(path)),
            )
        self.repo_context_menu = menu
        menu.bind("<Unmap>", self._on_repo_context_menu_unmap, add=True)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _copy_to_clipboard(self, content: str) -> bool:
        payload = content.strip()
        if not payload:
            return False
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update()
        return True

    def _copy_repo_path(self, repo_path: str = "") -> None:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("Repo", "Selecione um repositório antes de copiar o caminho.")
            return
        self._copy_to_clipboard(resolved_repo)
        self._set_status("Caminho do repositorio copiado.")

    def _copy_repo_github_url(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositorio valido antes de copiar URL.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        copied = self._copy_to_clipboard(repo_base_url)
        if copied:
            self._set_status("URL do repositorio copiada.")
        return copied

    def _copy_repo_branch_github_url(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositorio valido antes de copiar URL da branch.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        branch = self._get_current_branch_for_pr(resolved_repo).strip()
        if not branch:
            messagebox.showwarning("GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        branch_enc = quote(branch, safe="")
        branch_url = f"{repo_base_url}/tree/{branch_enc}"
        copied = self._copy_to_clipboard(branch_url)
        if copied:
            self._set_status("URL da branch copiada.")
        return copied

    def _delete_repo_directory(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("Excluir repositório", "Selecione um repositório válido antes de excluir.")
            return False
        normalized_repo = self._normalize_repo_path_candidate(resolved_repo)
        repo_name = os.path.basename(normalized_repo.rstrip(os.sep)) or normalized_repo
        confirmed = messagebox.askyesno(
            "Excluir repositório",
            (
                f"Excluir permanentemente '{repo_name}'?\n\n"
                f"Caminho: {normalized_repo}\n\n"
                "Esta ação remove a pasta local inteira e não pode ser desfeita."
            ),
            icon="warning",
            default="no",
        )
        if not confirmed:
            return False
        current_repo = self._normalize_repo_path_candidate(self.repo_path) if self.repo_ready and self.repo_path else ""
        is_current = normalized_repo == current_repo

        def task() -> str:
            if os.path.islink(normalized_repo):
                os.unlink(normalized_repo)
            else:
                shutil.rmtree(normalized_repo)
            return normalized_repo

        def success(_result: object) -> None:
            normalized = self._normalize_repo_path_candidate(normalized_repo)
            self.favorite_repos = [
                item for item in self.favorite_repos if self._normalize_repo_path_candidate(item) != normalized
            ]
            self.recent_repos = [
                item for item in self.recent_repos if self._normalize_repo_path_candidate(item) != normalized
            ]
            if self._normalize_repo_path_candidate(getattr(self, "last_repo_path", "")) == normalized:
                self.last_repo_path = ""
            if hasattr(self, "workspace_card_detail_cache"):
                self.workspace_card_detail_cache.pop(normalized, None)
            if hasattr(self, "workspace_card_detail_ts"):
                self.workspace_card_detail_ts.pop(normalized, None)
            if is_current:
                self._set_repo_ui_no_repo()
            self._persist_settings()
            if hasattr(self, "_refresh_repo_lists"):
                self._refresh_repo_lists()
            if hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set(f"Repositório excluído: {normalized}")
            self._set_status(f"Repositório excluído: {repo_name}")

        def error(exc: Exception) -> None:
            messagebox.showerror("Excluir repositório", f"Falha ao excluir:\n{exc}")
            self._set_status("Falha ao excluir repositório.")

        self._set_status(f"Excluindo repositório: {repo_name}...")
        if hasattr(self, "_run_async"):
            self._run_async("delete_repo", "Excluir repo", task, success, error, perf_trigger="repo_delete:context_menu")
        else:
            try:
                success(task())
            except Exception as exc:
                error(exc)
        return True

    def _open_repo_in_file_manager(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("Pasta", "Selecione um repositório válido antes de abrir a pasta.")
            return False
        try:
            if os.name == "nt":
                os.startfile(resolved_repo)  # type: ignore[attr-defined]
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", resolved_repo])
            elif shutil.which("open"):
                subprocess.Popen(["open", resolved_repo])
            else:
                messagebox.showwarning("Pasta", "Não foi encontrado um comando para abrir a pasta.")
                return False
        except OSError as exc:
            messagebox.showerror("Pasta", f"Falha ao abrir a pasta: {exc}")
            return False
        return True

    @staticmethod
    def _normalize_remote_url_for_browser(remote_url: str) -> str:
        value = remote_url.strip()
        if not value:
            return ""
        if value.startswith("git@"):
            prefix, sep, path = value.partition(":")
            if not sep or "@" not in prefix:
                return ""
            host = prefix.split("@", 1)[1]
            clean_path = path.removesuffix(".git").strip("/")
            if not host or not clean_path:
                return ""
            return f"https://{host}/{clean_path}"
        if value.startswith("ssh://"):
            payload = value[len("ssh://") :]
            if "@" in payload:
                payload = payload.split("@", 1)[1]
            host, sep, path = payload.partition("/")
            clean_path = path.removesuffix(".git").strip("/")
            if not sep or not host or not clean_path:
                return ""
            return f"https://{host}/{clean_path}"
        if value.startswith("http://") or value.startswith("https://"):
            return value.removesuffix(".git")
        return ""

    def _get_repo_origin_url(self, resolved_repo: str) -> str:
        return run_git(resolved_repo, ["remote", "get-url", "origin"]).strip()

    def _get_repo_github_base_url(self, resolved_repo: str) -> str:
        remote_url_raw = self._get_repo_origin_url(resolved_repo)
        remote_url = self._normalize_remote_url_for_browser(remote_url_raw)
        if not remote_url or "github.com/" not in remote_url:
            raise RuntimeError(f"Remote origin nao aponta para GitHub:\n{remote_url_raw}")
        return remote_url.rstrip("/")

    def _open_browser_url(self, title: str, url: str) -> bool:
        try:
            opened = webbrowser.open(url, new=2)
        except webbrowser.Error as exc:
            messagebox.showerror(title, f"Falha ao abrir navegador: {exc}")
            return False
        if not opened:
            messagebox.showwarning(title, f"Nao foi possivel abrir automaticamente:\n{url}")
            return False
        return True

    @staticmethod
    def _get_default_base_branch_for_pr(repo_path: str) -> str:
        try:
            ref = run_git(repo_path, ["symbolic-ref", "refs/remotes/origin/HEAD"]).strip()
        except RuntimeError:
            return "main"
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            branch = ref[len(prefix) :].strip()
            if branch:
                return branch
        return "main"

    @staticmethod
    def _get_current_branch_for_pr(repo_path: str) -> str:
        try:
            current = run_git(repo_path, ["branch", "--show-current"]).strip()
            if current:
                return current
        except RuntimeError:
            pass
        try:
            current = run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        except RuntimeError:
            return ""
        if current == "HEAD":
            return ""
        return current

    def _open_repo_in_github(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir no GitHub.")
            return False
        try:
            remote_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        return self._open_browser_url("GitHub", remote_url)

    def _open_repo_branch_in_github(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir a branch no GitHub.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        branch = self._get_current_branch_for_pr(resolved_repo).strip()
        if not branch:
            messagebox.showwarning("GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        branch_enc = quote(branch, safe="")
        return self._open_browser_url("GitHub", f"{repo_base_url}/tree/{branch_enc}")

    def _open_repo_branch_commits_in_github(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir commits no GitHub.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        branch = self._get_current_branch_for_pr(resolved_repo).strip()
        if not branch:
            messagebox.showwarning("GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        branch_enc = quote(branch, safe="")
        return self._open_browser_url("GitHub", f"{repo_base_url}/commits/{branch_enc}")

    def _open_repo_issues_in_github(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir issues.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        return self._open_browser_url("GitHub", f"{repo_base_url}/issues")

    def _open_repo_actions_in_github(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir actions.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        return self._open_browser_url("GitHub", f"{repo_base_url}/actions")

    def _open_repo_releases_in_github(self, repo_path: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir releases.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        return self._open_browser_url("GitHub", f"{repo_base_url}/releases")

    def _open_pr_on_github(self, repo_path: str = "", base_branch: str = "", head_branch: str = "") -> bool:
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("PR", "Selecione um repositório válido antes de abrir PR.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("PR", str(exc))
            return False
        resolved_head = head_branch.strip() or self._get_current_branch_for_pr(resolved_repo)
        if not resolved_head:
            messagebox.showwarning("PR", "Nao foi possivel identificar a branch atual para montar a URL de PR.")
            return False
        resolved_base = base_branch.strip() or self._get_default_base_branch_for_pr(resolved_repo)
        base_enc = quote(resolved_base, safe="")
        head_enc = quote(resolved_head, safe="")
        pr_url = f"{repo_base_url}/compare/{base_enc}...{head_enc}"
        return self._open_browser_url("PR", pr_url)

    def _open_commit_in_github(self, commit_hash: str, repo_path: str = "") -> bool:
        sha = commit_hash.strip()
        if not sha:
            messagebox.showwarning("GitHub", "Informe um hash de commit valido.")
            return False
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositório válido antes de abrir commit no GitHub.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        commit_url = f"{repo_base_url}/commit/{sha}"
        return self._open_browser_url("GitHub", commit_url)

    def _copy_commit_github_url(self, commit_hash: str, repo_path: str = "") -> bool:
        sha = commit_hash.strip()
        if not sha:
            messagebox.showwarning("GitHub", "Informe um hash de commit valido.")
            return False
        resolved_repo = self._resolve_repo_action_path(repo_path)
        if not resolved_repo:
            messagebox.showinfo("GitHub", "Selecione um repositorio valido antes de copiar URL de commit.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            messagebox.showerror("GitHub", str(exc))
            return False
        commit_url = f"{repo_base_url}/commit/{sha}"
        copied = self._copy_to_clipboard(commit_url)
        if copied:
            self._set_status("URL do commit copiada.")
        return copied

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
        if hasattr(self, "_hide_conflicts_tab"):
            self._hide_conflicts_tab(select_history=False)
        repo_path = os.path.abspath(path)
        if not os.path.isdir(repo_path) or not is_git_repo(repo_path):
            if not initial:
                messagebox.showwarning("Repo", "Selecione um repositório git válido.")
            self._set_repo_ui_no_repo()
            return False
        self.repo_path = repo_path
        self.last_repo_path = self._normalize_repo_path_candidate(repo_path)
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
        if hasattr(self, "_hide_conflicts_tab"):
            self._hide_conflicts_tab(select_history=False)
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
        if hasattr(self, "_update_reorder_local_button_visibility"):
            self._update_reorder_local_button_visibility()
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
        if hasattr(self, "worktree_hunk_marker_map"):
            self.worktree_hunk_marker_map.clear()
        if hasattr(self, "worktree_line_scope_map"):
            self.worktree_line_scope_map.clear()
        if hasattr(self, "worktree_diff_data_by_scope"):
            self.worktree_diff_data_by_scope.clear()
        if hasattr(self, "status_refresh_debounce_job") and self.status_refresh_debounce_job is not None:
            try:
                self.after_cancel(self.status_refresh_debounce_job)
            except tk.TclError:
                pass
            self.status_refresh_debounce_job = None
        if hasattr(self, "status_refresh_debounce_trigger"):
            self.status_refresh_debounce_trigger = ""
        self.worktree_diff_scope = ""
        self._update_worktree_diff_actions()
        if hasattr(self, "stage_count_var"):
            self.stage_count_var.set("Selecionados: 0/0")
        if hasattr(self, "_update_open_pr_button_visibility"):
            self._update_open_pr_button_visibility(1)
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
        self._refresh_global_branch_quick_selector([], "")
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
