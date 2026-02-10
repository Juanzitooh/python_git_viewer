#!/usr/bin/env python3
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from ..core.cherry_pick_ops import (
    cherry_pick_commit as core_cherry_pick_commit,
    has_unmerged_conflicts as core_has_unmerged_conflicts,
)
from ..core.commit_content import get_commit_patch as core_get_commit_patch, list_commit_files as core_list_commit_files
from ..core.git_client import is_git_repo, load_commit_summaries, run_git
from ..core.models import CommitFilters, CommitSummary
from ..core.settings_store import normalize_repo_path


class ImportTabMixin:
    def _build_import_tab(self) -> None:
        self.import_tab.grid_columnconfigure(0, weight=1)
        self.import_tab.grid_rowconfigure(2, weight=1)

        source_frame = ttk.LabelFrame(self.import_tab, text="Origem")
        source_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        source_frame.grid_columnconfigure(1, weight=1)
        source_frame.grid_columnconfigure(4, weight=1)

        ttk.Label(source_frame, text="Repositório origem:").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)
        self.import_source_repo_var = tk.StringVar(value="")
        self.import_source_repo_combo = ttk.Combobox(
            source_frame,
            textvariable=self.import_source_repo_var,
            state="disabled",
            values=[],
        )
        self.import_source_repo_combo.grid(row=0, column=1, sticky="ew", pady=6)
        self.import_source_repo_combo.bind("<<ComboboxSelected>>", self._on_import_source_repo_selected)
        self.import_source_repo_refresh_button = ttk.Button(
            source_frame,
            text="Atualizar repos",
            command=self._refresh_import_source_repo_options,
        )
        self.import_source_repo_refresh_button.grid(row=0, column=2, sticky="w", padx=(6, 0), pady=6)
        self.import_source_current_button = ttk.Button(
            source_frame,
            text="Usar atual",
            command=self._use_current_repo_as_import_source,
        )
        self.import_source_current_button.grid(row=0, column=3, sticky="w", padx=(6, 8), pady=6)

        ttk.Label(source_frame, text="Branch origem:").grid(row=1, column=0, sticky="w", padx=(8, 4), pady=(0, 6))
        self.import_source_branch_var = tk.StringVar(value="")
        self.import_source_branch_combo = ttk.Combobox(
            source_frame,
            textvariable=self.import_source_branch_var,
            state="disabled",
            values=[],
        )
        self.import_source_branch_combo.grid(row=1, column=1, sticky="ew", pady=(0, 6))
        self.import_source_branch_combo.bind("<<ComboboxSelected>>", self._on_import_source_branch_selected)
        self.import_source_refresh_button = ttk.Button(
            source_frame,
            text="Atualizar lista",
            command=self._load_import_source_commits,
            state="disabled",
        )
        self.import_source_refresh_button.grid(row=1, column=2, sticky="w", padx=(6, 0), pady=(0, 6))

        target_frame = ttk.LabelFrame(self.import_tab, text="Destino")
        target_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        self.import_target_var = tk.StringVar(value="Destino: (nenhum)")
        ttk.Label(target_frame, textvariable=self.import_target_var).grid(row=0, column=0, sticky="w", padx=8, pady=6)

        commits_frame = ttk.LabelFrame(self.import_tab, text="Commits da origem")
        commits_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        commits_frame.grid_columnconfigure(0, weight=1)
        commits_frame.grid_rowconfigure(0, weight=1)

        self.import_commits_listbox = tk.Listbox(
            commits_frame,
            selectmode="extended",
            exportselection=False,
            activestyle="dotbox",
            font="TkFixedFont",
        )
        self.import_commits_listbox.grid(row=0, column=0, sticky="nsew")
        self.import_commits_listbox.bind("<<ListboxSelect>>", self._on_import_commits_selection)
        self.import_commits_listbox.bind("<Button-3>", self._on_import_commit_context_menu_request, add=True)
        import_scroll = ttk.Scrollbar(commits_frame, orient="vertical", command=self.import_commits_listbox.yview)
        import_scroll.grid(row=0, column=1, sticky="ns")
        self.import_commits_listbox.configure(yscrollcommand=import_scroll.set)

        actions = ttk.Frame(self.import_tab)
        actions.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 4))
        self.import_copy_button = ttk.Button(
            actions,
            text="Copiar hashes",
            command=self._copy_selected_import_hashes,
            state="disabled",
        )
        self.import_copy_button.grid(row=0, column=0, padx=(0, 6))
        self.import_run_button = ttk.Button(
            actions,
            text="Importar selecionados",
            command=self._import_selected_commits,
            state="disabled",
        )
        self.import_run_button.grid(row=0, column=1)

        self.import_status_var = tk.StringVar(value="Selecione o repositório de origem para carregar commits.")
        ttk.Label(self.import_tab, textvariable=self.import_status_var).grid(
            row=4,
            column=0,
            sticky="w",
            padx=8,
            pady=(0, 8),
        )

        self.import_source_repo_path = ""
        self.import_source_repo_lookup: dict[str, str] = {}
        self.import_commit_summaries: list[CommitSummary] = []
        self.import_commit_context_menu: tk.Menu | None = None
        self._refresh_import_source_repo_options()
        self._sync_import_tab_with_current_repo()

    def _open_import_tab(self) -> None:
        if not hasattr(self, "tabs") or not hasattr(self, "import_tab"):
            return
        self.tabs.select(self.import_tab)
        if hasattr(self, "_on_notebook_tab_changed"):
            self._on_notebook_tab_changed()

    def _sync_import_tab_with_current_repo(self) -> None:
        if not hasattr(self, "import_target_var"):
            return
        if hasattr(self, "_refresh_import_source_repo_options"):
            needs_refresh = not bool(getattr(self, "import_source_repo_lookup", {}))
            if self.repo_ready and self.repo_path:
                current_repo = normalize_repo_path(self.repo_path)
                if current_repo not in self.import_source_repo_lookup.values():
                    needs_refresh = True
            if needs_refresh:
                self._refresh_import_source_repo_options()
        if not self.repo_ready or not self.repo_path:
            self.import_target_var.set("Destino: (nenhum repositório selecionado)")
            self._update_import_controls_state()
            return
        if hasattr(self, "_format_repo_display_path"):
            display_repo = self._format_repo_display_path(self.repo_path)
        else:
            display_repo = self.repo_path
        current_branch = ""
        if hasattr(self, "branch_var"):
            current_branch = self.branch_var.get().strip()
        if not current_branch:
            current_branch = "(desconhecida)"
        self.import_target_var.set(f"Destino: {display_repo} | Branch atual: {current_branch}")
        self._update_import_controls_state()

    def _collect_import_source_repos(self) -> list[str]:
        ordered: list[str] = []
        candidates: list[str] = []
        if hasattr(self, "_get_workspace_card_repos"):
            candidates.extend(self._get_workspace_card_repos())
        else:
            for source in (self.favorite_repos, self.recent_repos):
                candidates.extend(source)
        if self.repo_ready and self.repo_path:
            candidates.append(self.repo_path)
        for path in candidates:
            normalized = normalize_repo_path(path)
            if normalized in ordered:
                continue
            if not os.path.isdir(normalized):
                continue
            if not is_git_repo(normalized):
                continue
            ordered.append(normalized)
        return ordered

    def _refresh_import_source_repo_options(self) -> None:
        if not hasattr(self, "import_source_repo_combo"):
            return
        repos = self._collect_import_source_repos()
        favorite_set = {normalize_repo_path(path) for path in self.favorite_repos}
        labels: list[str] = []
        lookup: dict[str, str] = {}
        path_to_label: dict[str, str] = {}
        for repo_path in repos:
            if hasattr(self, "_format_repo_display_path"):
                label_base = self._format_repo_display_path(repo_path)
            else:
                label_base = repo_path
            if repo_path in favorite_set:
                label_base = f"★ {label_base}"
            label = label_base
            suffix = 2
            while label in lookup:
                label = f"{label_base} [{suffix}]"
                suffix += 1
            labels.append(label)
            lookup[label] = repo_path
            path_to_label[repo_path] = label
        self.import_source_repo_lookup = lookup

        source_path = normalize_repo_path(self.import_source_repo_path) if self.import_source_repo_path else ""
        if source_path and source_path not in path_to_label:
            self.import_source_repo_path = ""
            self.import_source_branch_var.set("")
            self.import_source_branch_combo.configure(values=[], state="disabled")
            self.import_commit_summaries = []
            self.import_commits_listbox.delete(0, tk.END)
            source_path = ""

        if labels:
            self.import_source_repo_combo.configure(values=labels, state="readonly")
        else:
            self.import_source_repo_combo.configure(values=[], state="disabled")

        if source_path and source_path in path_to_label:
            self.import_source_repo_var.set(path_to_label[source_path])
        elif self.import_source_repo_var.get().strip() not in lookup:
            self.import_source_repo_var.set("")

        if not labels and not self.import_source_repo_path:
            self.import_status_var.set("Nenhum repositório do scan disponível. Reescanear na aba Repositórios.")
        self._update_import_controls_state()

    def _on_import_source_repo_selected(self, _event: tk.Event) -> None:
        self._apply_import_source_repo_from_entry()

    def _use_current_repo_as_import_source(self) -> None:
        if not self.repo_ready or not self.repo_path:
            messagebox.showinfo("Importar", "Selecione um repositório destino antes de usar o atual como origem.")
            return
        self._set_import_source_repo(self.repo_path, show_errors=True)

    def _apply_import_source_repo_from_entry(self) -> None:
        raw = self.import_source_repo_var.get().strip() if hasattr(self, "import_source_repo_var") else ""
        selected = self.import_source_repo_lookup.get(raw, raw)
        self._set_import_source_repo(selected, show_errors=True)

    def _set_import_source_repo(self, path: str, *, show_errors: bool) -> bool:
        if not path.strip():
            self._dismiss_import_commit_context_menu()
            self.import_source_repo_path = ""
            self.import_commit_summaries = []
            self.import_source_repo_var.set("")
            if hasattr(self, "import_source_branch_combo"):
                self.import_source_branch_combo.configure(values=[], state="disabled")
            if hasattr(self, "import_source_branch_var"):
                self.import_source_branch_var.set("")
            if hasattr(self, "import_commits_listbox"):
                self.import_commits_listbox.delete(0, tk.END)
            self.import_status_var.set("Selecione o repositório de origem para carregar commits.")
            self._update_import_controls_state()
            return False
        normalized = normalize_repo_path(path)
        if not os.path.isdir(normalized) or not is_git_repo(normalized):
            if show_errors:
                messagebox.showwarning("Importar", "Selecione um repositório Git válido como origem.")
            self._update_import_controls_state()
            return False
        self.import_source_repo_path = normalized
        selected_label = ""
        for label, repo_path in self.import_source_repo_lookup.items():
            if repo_path == normalized:
                selected_label = label
                break
        self.import_source_repo_var.set(selected_label or normalized)
        self.import_status_var.set("Carregando branches da origem...")
        self._load_import_source_branches()
        return True

    def _load_import_source_branches(self) -> None:
        source_repo = self.import_source_repo_path
        if not source_repo:
            self._update_import_controls_state()
            return

        def task() -> tuple[list[str], str]:
            branches_output = run_git(source_repo, ["branch", "--format=%(refname:short)"])
            branches = [line.strip() for line in branches_output.splitlines() if line.strip()]
            current = run_git(source_repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
            return branches, current

        def success(result: object) -> None:
            branches, current = result  # type: ignore[misc]
            if not branches:
                self.import_source_branch_combo.configure(values=[], state="disabled")
                self.import_source_branch_var.set("")
                self.import_commit_summaries = []
                self.import_commits_listbox.delete(0, tk.END)
                self.import_status_var.set("Nenhuma branch encontrada no repositório de origem.")
                self._update_import_controls_state()
                return
            selected = self.import_source_branch_var.get().strip()
            if selected not in branches:
                if current and current in branches:
                    selected = current
                else:
                    selected = branches[0]
            self.import_source_branch_combo.configure(values=branches, state="readonly")
            self.import_source_branch_var.set(selected)
            self._update_import_controls_state()
            self._load_import_source_commits()

        def error(exc: Exception) -> None:
            self.import_source_branch_combo.configure(values=[], state="disabled")
            self.import_source_branch_var.set("")
            self.import_commits_listbox.delete(0, tk.END)
            self.import_commit_summaries = []
            self.import_status_var.set("Falha ao carregar branches da origem.")
            messagebox.showerror("Importar", str(exc))
            self._update_import_controls_state()

        self._run_async("import_source_branches", "Branches origem", task, success, error)

    def _on_import_source_branch_selected(self, _event: tk.Event) -> None:
        self._load_import_source_commits()

    def _load_import_source_commits(self) -> None:
        self._dismiss_import_commit_context_menu()
        source_repo = self.import_source_repo_path
        branch = self.import_source_branch_var.get().strip() if hasattr(self, "import_source_branch_var") else ""
        if not source_repo or not branch:
            self._update_import_controls_state()
            return
        self.import_status_var.set(f"Carregando commits de {branch}...")
        self.import_source_refresh_button.configure(state="disabled")

        def task() -> list[CommitSummary]:
            filters = CommitFilters(ref=branch)
            return load_commit_summaries(source_repo, self.commit_limit, filters=filters)

        def success(result: object) -> None:
            self._dismiss_import_commit_context_menu()
            summaries = list(result)  # type: ignore[list-item]
            self.import_commit_summaries = summaries
            self.import_commits_listbox.delete(0, tk.END)
            for summary in summaries:
                self.import_commits_listbox.insert(tk.END, f"{summary.commit_hash[:7]} | {summary.subject}")
            if summaries:
                self.import_status_var.set(f"{len(summaries)} commits carregados da branch {branch}.")
            else:
                self.import_status_var.set(f"Nenhum commit encontrado na branch {branch}.")
            self._update_import_controls_state()

        def error(exc: Exception) -> None:
            self._dismiss_import_commit_context_menu()
            self.import_commit_summaries = []
            self.import_commits_listbox.delete(0, tk.END)
            self.import_status_var.set("Falha ao carregar commits da origem.")
            messagebox.showerror("Importar", str(exc))
            self._update_import_controls_state()

        self._run_async("import_source_commits", "Commits origem", task, success, error)

    def _on_import_commits_selection(self, _event: tk.Event) -> None:
        self._dismiss_import_commit_context_menu()
        self._update_import_controls_state()

    def _dismiss_import_commit_context_menu(self, event: tk.Event | None = None) -> None:
        if event is not None and self._is_event_inside_import_commit_context_menu(event):
            return
        menu = getattr(self, "import_commit_context_menu", None)
        self.import_commit_context_menu = None
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

    def _is_event_inside_import_commit_context_menu(self, event: tk.Event) -> bool:
        menu = getattr(self, "import_commit_context_menu", None)
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

    def _on_import_commit_context_menu_unmap(self, _event: tk.Event | None = None) -> None:
        self.import_commit_context_menu = None

    def _import_commit_index_from_y(self, y: int) -> int | None:
        size = self.import_commits_listbox.size()
        if size <= 0:
            return None
        index = self.import_commits_listbox.nearest(y)
        if index < 0 or index >= size:
            return None
        bbox = self.import_commits_listbox.bbox(index)
        if bbox:
            top = bbox[1]
            bottom = bbox[1] + bbox[3]
            if y < top or y > bottom:
                return None
        if index < 0 or index >= len(self.import_commit_summaries):
            return None
        return index

    def _copy_import_commit_hash(self, commit_hash: str) -> None:
        if not commit_hash:
            return
        if hasattr(self, "_copy_to_clipboard"):
            copied = self._copy_to_clipboard(commit_hash)
            if copied and hasattr(self, "_set_status"):
                self._set_status("Hash do commit copiado.")
            return
        self.clipboard_clear()
        self.clipboard_append(commit_hash)
        self.update()

    def _copy_import_commit_files_list(self, commit_hash: str) -> None:
        source_repo = self.import_source_repo_path.strip()
        if not source_repo:
            messagebox.showwarning("Importar", "Selecione repositório e branch de origem.")
            return
        try:
            paths = core_list_commit_files(source_repo, commit_hash)
        except RuntimeError as exc:
            messagebox.showerror("Importar", str(exc))
            return
        payload = ", ".join(paths)
        if hasattr(self, "_copy_to_clipboard"):
            copied = self._copy_to_clipboard(payload)
            if copied and hasattr(self, "_set_status"):
                self._set_status("Lista de arquivos do commit copiada.")
            return
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update()

    def _copy_import_commit_patch(self, commit_hash: str) -> None:
        source_repo = self.import_source_repo_path.strip()
        if not source_repo:
            messagebox.showwarning("Importar", "Selecione repositório e branch de origem.")
            return
        try:
            patch = core_get_commit_patch(source_repo, commit_hash)
        except RuntimeError as exc:
            messagebox.showerror("Importar", str(exc))
            return
        payload = patch.strip()
        if not payload:
            messagebox.showinfo("Importar", "Sem patch para copiar neste commit.")
            return
        if hasattr(self, "_copy_to_clipboard"):
            copied = self._copy_to_clipboard(payload)
            if copied and hasattr(self, "_set_status"):
                self._set_status("Patch completo do commit copiado.")
            return
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update()

    def _show_import_commit_context_menu(self, event: tk.Event, summary: CommitSummary) -> None:
        self._dismiss_import_commit_context_menu()
        commit_hash = summary.commit_hash.strip()
        if not commit_hash:
            return
        source_repo = self.import_source_repo_path.strip()
        if not source_repo:
            messagebox.showwarning("Importar", "Selecione repositório e branch de origem.")
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Abrir commit no GitHub",
            command=lambda selected_hash=commit_hash: self._open_commit_in_github(selected_hash, source_repo),
        )
        menu.add_command(
            label="Copiar URL do commit no GitHub",
            command=lambda selected_hash=commit_hash: self._copy_commit_github_url(selected_hash, source_repo),
        )
        menu.add_separator()
        menu.add_command(
            label="Copiar hash completo",
            command=lambda selected_hash=commit_hash: self._copy_import_commit_hash(selected_hash),
        )
        menu.add_command(
            label="Copiar lista de arquivos",
            command=lambda selected_hash=commit_hash: self._copy_import_commit_files_list(selected_hash),
        )
        menu.add_command(
            label="Copiar patch completo",
            command=lambda selected_hash=commit_hash: self._copy_import_commit_patch(selected_hash),
        )
        self.import_commit_context_menu = menu
        menu.bind("<Unmap>", self._on_import_commit_context_menu_unmap, add=True)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _on_import_commit_context_menu_request(self, event: tk.Event) -> str:
        index = self._import_commit_index_from_y(int(event.y))
        if index is None:
            selected_indices = self.import_commits_listbox.curselection()
            if selected_indices:
                index = selected_indices[-1]
        if index is None or index < 0 or index >= len(self.import_commit_summaries):
            return "break"
        summary = self.import_commit_summaries[index]
        self._show_import_commit_context_menu(event, summary)
        return "break"

    def _get_selected_import_summaries(self) -> list[CommitSummary]:
        if not hasattr(self, "import_commits_listbox"):
            return []
        selected_indices = sorted(self.import_commits_listbox.curselection())
        selected: list[CommitSummary] = []
        for index in selected_indices:
            if index < 0 or index >= len(self.import_commit_summaries):
                continue
            selected.append(self.import_commit_summaries[index])
        return selected

    def _copy_selected_import_hashes(self) -> None:
        selected = self._get_selected_import_summaries()
        if not selected:
            messagebox.showinfo("Importar", "Selecione commits para copiar os hashes.")
            return
        payload = "\n".join(item.commit_hash for item in selected)
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update()

    def _has_unmerged_conflicts(self) -> bool:
        try:
            return core_has_unmerged_conflicts(self.repo_path)
        except RuntimeError:
            return False

    def _import_selected_commits(self) -> None:
        if not self.repo_ready or not self.repo_path:
            messagebox.showinfo("Importar", "Selecione um repositório destino válido antes de importar.")
            return
        source_repo = self.import_source_repo_path
        if not source_repo:
            messagebox.showwarning("Importar", "Selecione o repositório de origem.")
            return
        selected = self._get_selected_import_summaries()
        if not selected:
            messagebox.showwarning("Importar", "Selecione ao menos um commit para importar.")
            return
        target_branch = ""
        if hasattr(self, "branch_var"):
            target_branch = self.branch_var.get().strip()
        if not target_branch:
            target_branch = self._get_current_branch().strip()
        if not target_branch:
            messagebox.showwarning("Importar", "Não foi possível identificar a branch de destino.")
            return
        source_branch = self.import_source_branch_var.get().strip()
        confirm = messagebox.askyesno(
            "Importar commits",
            (
                f"Importar {len(selected)} commit(s)\n"
                f"Origem: {source_repo} ({source_branch or '(sem branch)'})\n"
                f"Destino: {self.repo_path} ({target_branch})"
            ),
        )
        if not confirm:
            return

        source_is_target = normalize_repo_path(source_repo) == normalize_repo_path(self.repo_path)
        ordered = list(reversed(selected))
        applied = 0
        failing_hash = ""
        self.import_status_var.set("Importando commits...")
        perf_trigger = "import:selected_commits"
        start = self._perf_start("Importar commits", perf_trigger)
        try:
            for summary in ordered:
                commit_hash = summary.commit_hash
                failing_hash = commit_hash
                try:
                    core_cherry_pick_commit(
                        self.repo_path,
                        commit_hash,
                        source_repo=source_repo,
                        fetch_source=not source_is_target,
                    )
                except RuntimeError as exc:
                    if applied > 0:
                        if hasattr(self, "_bump_repo_state"):
                            self._bump_repo_state()
                        self._reload_commits(trigger="post_import_partial")
                        self._refresh_status(trigger="post_import_partial")
                        self._refresh_branches(trigger="post_import_partial")
                        self._update_pull_push_labels()
                    messagebox.showerror(
                        "Importar",
                        (
                            f"Falha ao importar {failing_hash[:7]}.\n{exc}\n"
                            "Resolva conflitos e finalize ou aborte o cherry-pick antes de continuar."
                        ),
                    )
                    if self._has_unmerged_conflicts() and hasattr(self, "_show_conflicts_window"):
                        self._show_conflicts_window(operation="cherry-pick", source_label="Importar")
                    self.import_status_var.set(f"Importação interrompida após {applied} commit(s).")
                    self._update_import_controls_state()
                    return
                applied += 1

            if applied > 0:
                if hasattr(self, "_bump_repo_state"):
                    self._bump_repo_state()
                self._reload_commits(trigger="post_import_success")
                self._refresh_status(trigger="post_import_success")
                self._refresh_branches(trigger="post_import_success")
                self._update_pull_push_labels()
                self._set_status(f"Importado em {target_branch}: {applied} commit(s).")
                self.import_status_var.set(f"Importação concluída: {applied} commit(s) em {target_branch}.")
            else:
                self.import_status_var.set("Nenhum commit foi importado.")
            self._update_import_controls_state()
        finally:
            self._perf_end("Importar commits", start, perf_trigger)

    def _update_import_controls_state(self) -> None:
        if not hasattr(self, "import_run_button"):
            return
        selected = bool(self._get_selected_import_summaries())
        source_ready = bool(self.import_source_repo_path and self.import_source_branch_var.get().strip())
        has_source_options = bool(getattr(self, "import_source_repo_lookup", {}))
        can_import = bool(self.repo_ready and source_ready and selected)
        self.import_run_button.configure(state="normal" if can_import else "disabled")
        self.import_copy_button.configure(state="normal" if selected else "disabled")
        if source_ready:
            self.import_source_refresh_button.configure(state="normal")
        else:
            self.import_source_refresh_button.configure(state="disabled")
        if hasattr(self, "import_source_repo_refresh_button"):
            self.import_source_repo_refresh_button.configure(state="normal")
        if hasattr(self, "import_source_repo_combo") and not has_source_options and not self.import_source_repo_path:
            self.import_source_repo_combo.configure(state="disabled")
