#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import tkinter as tk
import time
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from ..core.branch_ops import checkout_branch as core_checkout_branch
from ..core.git_client import is_git_repo
from ..core.repo_state import (
    get_ahead_behind as core_get_ahead_behind,
    get_current_branch as core_get_current_branch,
    get_upstream as core_get_upstream,
    is_dirty as core_is_dirty,
    list_branches as core_list_branches,
    list_worktree_changed_files as core_list_worktree_changed_files,
)
from ..core.repo_workspace import (
    check_github_ssh_auth,
    clone_repository,
    discover_git_repositories,
    ensure_github_ssh_key,
    github_ssh_key_exists,
)
from ..core.settings_store import normalize_repo_path


WORKSPACE_CARD_CACHE_TTL_SEC = 45.0


class ReposTabMixin:
    def _build_repos_tab(self) -> None:
        self.repos_tab.grid_columnconfigure(0, weight=1)
        self.repos_tab.grid_columnconfigure(1, weight=1)
        self.repos_tab.grid_rowconfigure(1, weight=1)

        workspace_frame = ttk.LabelFrame(self.repos_tab, text="Workspace GitHub")
        workspace_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        workspace_frame.grid_columnconfigure(1, weight=1)
        workspace_frame.grid_columnconfigure(4, weight=1)
        workspace_frame.grid_columnconfigure(5, weight=1)

        ttk.Label(workspace_frame, text="Raiz local do Workspace GitHub:").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=(6, 4)
        )
        self.repo_scan_root_var = tk.StringVar(value=self.repo_scan_root)
        self.repo_scan_root_entry = ttk.Entry(workspace_frame, textvariable=self.repo_scan_root_var)
        self.repo_scan_root_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=(6, 4))
        self.repo_scan_root_entry.bind("<Return>", lambda _e: self._save_repo_scan_root())

        ttk.Button(workspace_frame, text="Pasta...", command=self._choose_repo_scan_root).grid(
            row=0,
            column=4,
            sticky="w",
            padx=(6, 0),
            pady=(6, 4),
        )
        ttk.Button(workspace_frame, text="Reescanear", command=self._scan_repo_workspace).grid(
            row=0,
            column=5,
            sticky="w",
            padx=(6, 8),
            pady=(6, 4),
        )

        self.repo_scan_status_var = tk.StringVar(value="")
        ttk.Label(workspace_frame, textvariable=self.repo_scan_status_var).grid(
            row=1, column=0, columnspan=6, sticky="w", padx=8, pady=(0, 6)
        )

        self._build_workspace_cards_panel()
        self._refresh_repo_lists()
        self._refresh_github_ssh_state(startup=True)
        self._bootstrap_repo_workspace()

    def _build_workspace_cards_panel(self) -> None:
        cards_frame = ttk.LabelFrame(self.repos_tab, text="Visao Geral do Workspace")
        cards_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=(4, 8))
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_rowconfigure(0, weight=1)
        self.workspace_cards_frame = cards_frame
        self.workspace_card_paths: list[str] = []
        self.workspace_card_frames: list[ttk.LabelFrame] = []
        self.workspace_card_detail_cache: dict[str, dict[str, object]] = {}
        self.workspace_card_detail_ts: dict[str, float] = {}
        self.workspace_card_refresh_job: str | None = None

        self.workspace_cards_canvas = tk.Canvas(cards_frame, highlightthickness=0, borderwidth=0)
        self.workspace_cards_canvas.grid(row=0, column=0, sticky="nsew")
        self.workspace_cards_scrollbar = ttk.Scrollbar(
            cards_frame, orient="vertical", command=self.workspace_cards_canvas.yview
        )
        self.workspace_cards_scrollbar.grid(row=0, column=1, sticky="ns")
        self.workspace_cards_canvas.configure(yscrollcommand=self.workspace_cards_scrollbar.set)

        self.workspace_cards_inner = ttk.Frame(self.workspace_cards_canvas)
        self.workspace_cards_window = self.workspace_cards_canvas.create_window(
            (0, 0), window=self.workspace_cards_inner, anchor="nw"
        )
        self.workspace_cards_inner.bind("<Configure>", self._on_workspace_cards_inner_configure)
        self.workspace_cards_canvas.bind("<Configure>", self._on_workspace_cards_canvas_configure)
        self._bind_workspace_scroll_events(self.workspace_cards_canvas)
        self._bind_workspace_scroll_events(self.workspace_cards_inner)

    def _bind_workspace_scroll_events(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_workspace_cards_mousewheel, add=True)
        widget.bind("<Button-4>", self._on_workspace_cards_mousewheel, add=True)
        widget.bind("<Button-5>", self._on_workspace_cards_mousewheel, add=True)

    def _on_workspace_cards_inner_configure(self, _event: tk.Event) -> None:
        if not hasattr(self, "workspace_cards_canvas"):
            return
        self.workspace_cards_canvas.configure(scrollregion=self.workspace_cards_canvas.bbox("all"))

    def _on_workspace_cards_canvas_configure(self, event: tk.Event) -> None:
        if not hasattr(self, "workspace_cards_canvas") or not hasattr(self, "workspace_cards_window"):
            return
        self.workspace_cards_canvas.itemconfigure(self.workspace_cards_window, width=event.width)

    def _on_workspace_cards_mousewheel(self, event: tk.Event) -> None:
        if not hasattr(self, "workspace_cards_canvas"):
            return
        if hasattr(event, "num") and event.num == 4:
            self.workspace_cards_canvas.yview_scroll(-1, "units")
            return
        if hasattr(event, "num") and event.num == 5:
            self.workspace_cards_canvas.yview_scroll(1, "units")
            return
        delta = int(getattr(event, "delta", 0))
        if delta == 0:
            return
        direction = -1 if delta > 0 else 1
        self.workspace_cards_canvas.yview_scroll(direction, "units")

    def _get_file_mtime_ns(self, path: str) -> int:
        try:
            return Path(path).stat().st_mtime_ns
        except OSError:
            return 0

    def _save_github_ssh_cache(self, *, has_key: bool, key_path: str, authenticated: bool) -> None:
        normalized_path = normalize_repo_path(key_path) if key_path.strip() else ""
        key_mtime_ns = self._get_file_mtime_ns(normalized_path) if has_key and normalized_path else 0
        cache: dict[str, object] = {
            "has_key": bool(has_key),
            "authenticated": bool(authenticated),
            "key_path": normalized_path if has_key else "",
            "checked_at": int(time.time()),
            "key_mtime_ns": int(key_mtime_ns) if has_key else 0,
        }
        current = getattr(self, "github_ssh_cache", {})
        if isinstance(current, dict) and has_key and not authenticated:
            current_has_key = bool(current.get("has_key", False))
            current_authenticated = bool(current.get("authenticated", False))
            current_path_raw = current.get("key_path", "")
            current_path = normalize_repo_path(current_path_raw) if isinstance(current_path_raw, str) else ""
            try:
                current_mtime_ns = int(current.get("key_mtime_ns", 0))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                current_mtime_ns = 0
            if (
                current_has_key
                and current_authenticated
                and current_path == normalized_path
                and current_mtime_ns > 0
                and current_mtime_ns == key_mtime_ns
            ):
                return
        if isinstance(current, dict) and current == cache:
            return
        self.github_ssh_cache = cache
        if hasattr(self, "_persist_settings"):
            self._persist_settings()

    def _use_cached_github_ssh_state(self) -> bool:
        cache_raw = getattr(self, "github_ssh_cache", {})
        if not isinstance(cache_raw, dict):
            return False
        has_key = bool(cache_raw.get("has_key", False))
        authenticated = bool(cache_raw.get("authenticated", False))
        key_path_raw = cache_raw.get("key_path", "")
        if not has_key or not authenticated:
            return False
        if not isinstance(key_path_raw, str) or not key_path_raw.strip():
            return False
        normalized_path = normalize_repo_path(key_path_raw)
        exists, resolved_key_path = github_ssh_key_exists(normalized_path)
        if not exists:
            return False
        try:
            cached_mtime_ns = int(cache_raw.get("key_mtime_ns", 0))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        if cached_mtime_ns <= 0:
            return False
        current_mtime_ns = self._get_file_mtime_ns(resolved_key_path)
        if current_mtime_ns <= 0 or current_mtime_ns != cached_mtime_ns:
            return False
        if hasattr(self, "prepare_ssh_button"):
            self.prepare_ssh_button.grid_remove()
        return True

    def _refresh_github_ssh_state(self, *, startup: bool = False) -> None:
        if startup and self._use_cached_github_ssh_state():
            return

        def task() -> tuple[bool, str, bool, str]:
            has_key, key_path = github_ssh_key_exists()
            if not has_key:
                return False, key_path, False, ""
            try:
                authenticated, _output = check_github_ssh_auth(key_path)
            except Exception as exc:
                return True, key_path, False, str(exc)
            return True, key_path, authenticated, ""

        def success(result: object) -> None:
            has_key, key_path, authenticated, warning = result  # type: ignore[misc]
            self._save_github_ssh_cache(has_key=has_key, key_path=key_path, authenticated=authenticated)
            if not has_key:
                if hasattr(self, "prepare_ssh_button"):
                    self.prepare_ssh_button.grid()
                if not startup and hasattr(self, "repo_scan_status_var"):
                    self.repo_scan_status_var.set(f"Chave SSH ausente: {key_path}")
                return
            if hasattr(self, "prepare_ssh_button"):
                self.prepare_ssh_button.grid_remove()
            if not startup and hasattr(self, "repo_scan_status_var"):
                if warning:
                    self.repo_scan_status_var.set(f"Chave SSH encontrada, teste pendente: {key_path}")
                    return
                if authenticated:
                    self.repo_scan_status_var.set(f"Chave SSH pronta: {key_path}")
                else:
                    self.repo_scan_status_var.set(f"Chave SSH encontrada, mas autenticacao pendente: {key_path}")

        def error(_exc: Exception) -> None:
            if hasattr(self, "prepare_ssh_button"):
                self.prepare_ssh_button.grid()
            if not startup and hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set("Nao foi possivel validar a chave SSH.")

        if hasattr(self, "_run_async"):
            self._run_async("github_ssh_status", "SSH", task, success, error)
        else:
            try:
                success(task())
            except Exception as exc:
                error(exc)

    def _bootstrap_repo_workspace(self) -> None:
        if not self.repo_scan_root and hasattr(self, "repo_scan_root_var"):
            candidate = self.repo_scan_root_var.get().strip()
            if candidate:
                self.repo_scan_root = normalize_repo_path(candidate)
        self.after(200, lambda: self._scan_repo_workspace(startup=True))

    def _save_repo_scan_root(self, *, show_status: bool = True, quiet: bool = False) -> bool:
        candidate = self.repo_scan_root_var.get().strip() if hasattr(self, "repo_scan_root_var") else ""
        if not candidate:
            if not quiet:
                messagebox.showwarning("Workspace", "Informe a pasta base para rastrear repositórios.")
            return False
        normalized = normalize_repo_path(candidate)
        self.repo_scan_root = normalized
        if hasattr(self, "repo_scan_root_var"):
            self.repo_scan_root_var.set(normalized)
        if hasattr(self, "_update_repo_display_path"):
            self._update_repo_display_path()
        self._schedule_workspace_cards_refresh()
        self._persist_settings()
        if show_status and hasattr(self, "repo_scan_status_var"):
            self.repo_scan_status_var.set(f"Pasta base salva: {normalized}")
        return True

    def _choose_repo_scan_root(self) -> None:
        initial = self.repo_scan_root or str(Path.home())
        path = filedialog.askdirectory(initialdir=initial)
        if not path:
            return
        if hasattr(self, "repo_scan_root_var"):
            self.repo_scan_root_var.set(path)
        self._save_repo_scan_root()

    def _scan_repo_workspace(self, *, startup: bool = False) -> None:
        if not self._save_repo_scan_root(show_status=False, quiet=startup):
            return
        root = self.repo_scan_root
        if hasattr(self, "repo_scan_status_var"):
            prefix = "Scan inicial" if startup else "Escaneando"
            self.repo_scan_status_var.set(f"{prefix}: {root}")

        def task() -> list[str]:
            return discover_git_repositories(root)

        def success(result: object) -> None:
            repos = list(result)  # type: ignore[list-item]
            if not repos:
                if hasattr(self, "repo_scan_status_var"):
                    if startup:
                        self.repo_scan_status_var.set("Scan inicial concluido: nenhum repositorio Git encontrado.")
                    else:
                        self.repo_scan_status_var.set("Nenhum repositório Git encontrado na pasta base.")
                return
            added = 0
            for repo in repos:
                normalized = normalize_repo_path(repo)
                if normalized not in self.recent_repos:
                    added += 1
                self._register_recent_repo(normalized)
            if hasattr(self, "repo_scan_status_var"):
                if startup:
                    self.repo_scan_status_var.set(
                        f"Scan inicial: {len(repos)} encontrados, {added} adicionados em Recentes."
                    )
                else:
                    self.repo_scan_status_var.set(
                        f"Escaneado: {len(repos)} encontrados, {added} adicionados em Recentes."
                    )

        def error(exc: Exception) -> None:
            if not startup:
                messagebox.showerror("Workspace", str(exc))
            if hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set("Falha ao escanear repositórios.")

        if hasattr(self, "_run_async"):
            self._run_async("scan_workspace", "Escanear repos", task, success, error)
        else:
            try:
                success(task())
            except Exception as exc:
                error(exc)

    def _prepare_github_ssh_key(self) -> None:
        if hasattr(self, "repo_scan_status_var"):
            self.repo_scan_status_var.set("Preparando chave SSH para GitHub...")

        def task() -> tuple[bool, str, str, bool, str]:
            created, key_path, pub_key = ensure_github_ssh_key()
            authenticated, ssh_output = check_github_ssh_auth(key_path)
            return created, key_path, pub_key, authenticated, ssh_output

        def success(result: object) -> None:
            created, key_path, pub_key, authenticated, ssh_output = result  # type: ignore[misc]
            if created:
                status = f"Chave SSH criada: {key_path}"
            else:
                status = f"Chave SSH existente: {key_path}"
            if authenticated:
                status += " | GitHub SSH OK"
            else:
                status += " | GitHub SSH pendente"
            if hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set(status)
            message = (
                "Cole esta chave publica em https://github.com/settings/keys:\n\n"
                f"{pub_key}\n\n"
                "Teste SSH:\n"
                f"{ssh_output or '(sem saida)'}\n"
            )
            if hasattr(self, "_open_text_window"):
                self._open_text_window("Chave publica GitHub", message, render_patch=False)
            else:
                messagebox.showinfo("GitHub SSH", message)
            self._refresh_github_ssh_state()

        def error(exc: Exception) -> None:
            messagebox.showerror("GitHub SSH", str(exc))
            if hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set("Falha ao preparar chave SSH.")
            self._refresh_github_ssh_state()

        if hasattr(self, "_run_async"):
            self._run_async("github_ssh_key", "Chave SSH", task, success, error)
        else:
            try:
                success(task())
            except Exception as exc:
                error(exc)

    def _clone_repo_from_url(
        self,
        *,
        repo_url: str = "",
        target_name: str = "",
        on_finished: Callable[[bool, str], None] | None = None,
        on_progress: Callable[[str], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        repo_url = repo_url.strip()
        if not repo_url:
            messagebox.showwarning("Clone", "Informe a URL SSH/HTTPS do repositório.")
            if on_finished:
                on_finished(False, "URL não informada.")
            return
        if not self._save_repo_scan_root(show_status=False):
            if on_finished:
                on_finished(False, "Raiz do workspace inválida.")
            return
        target_name = target_name.strip()
        root = self.repo_scan_root
        if hasattr(self, "repo_scan_status_var"):
            self.repo_scan_status_var.set(f"Clonando em: {root}")
        if on_progress:
            on_progress(f"Clonando em: {root}")

        def task() -> str:
            return clone_repository(repo_url, root, target_name, on_progress=on_progress, is_cancelled=is_cancelled)

        def success(cloned_path: object) -> None:
            path = str(cloned_path)
            self._register_recent_repo(path)
            if hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set(f"Clone concluido: {path}")
            self._open_repo_from_path(path)
            if on_finished:
                on_finished(True, path)

        def error(exc: Exception) -> None:
            message = str(exc)
            cancelled = "cancelado pelo usuario" in message.lower()
            if not cancelled:
                messagebox.showerror("Clone", message)
            if hasattr(self, "repo_scan_status_var"):
                self.repo_scan_status_var.set("Clone cancelado." if cancelled else "Falha no clone.")
            if on_finished:
                on_finished(False, message)

        if hasattr(self, "_run_async"):
            self._run_async("clone_repo", "Clone", task, success, error)
        else:
            try:
                success(task())
            except Exception as exc:
                error(exc)

    def _set_clone_ui_locked(self, locked: bool) -> None:
        if locked:
            if getattr(self, "clone_ui_lock_active", False):
                return
            self.clone_ui_lock_active = True
            self.clone_ui_saved_states: list[tuple[tk.Widget, str]] = []
            self.clone_tabs_state: list[tuple[int, str]] = []
            targets: list[tk.Widget] = []
            for name in (
                "repo_path_combo",
                "fetch_button",
                "pull_button",
                "push_button",
                "repo_scan_root_entry",
            ):
                widget = getattr(self, name, None)
                if widget is not None:
                    targets.append(widget)
            for widget in targets:
                try:
                    previous = str(widget.cget("state"))
                except (tk.TclError, AttributeError):
                    continue
                self.clone_ui_saved_states.append((widget, previous))
                try:
                    widget.configure(state="disabled")
                except tk.TclError:
                    continue
            tabs_widget = getattr(self, "tabs", None)
            if tabs_widget is not None:
                try:
                    tab_count = tabs_widget.index("end")
                    for index in range(tab_count):
                        tab_state = str(tabs_widget.tab(index, "state"))
                        self.clone_tabs_state.append((index, tab_state))
                        if tab_state != "disabled":
                            tabs_widget.tab(index, state="disabled")
                except tk.TclError:
                    self.clone_tabs_state = []
            return
        if not getattr(self, "clone_ui_lock_active", False):
            return
        self.clone_ui_lock_active = False
        for widget, previous in getattr(self, "clone_ui_saved_states", []):
            try:
                widget.configure(state=previous)
            except tk.TclError:
                continue
        self.clone_ui_saved_states = []
        tabs_widget = getattr(self, "tabs", None)
        if tabs_widget is not None:
            for index, state in getattr(self, "clone_tabs_state", []):
                try:
                    tabs_widget.tab(index, state=state)
                except tk.TclError:
                    continue
        self.clone_tabs_state = []

    def _refresh_repo_lists(self) -> None:
        if hasattr(self, "_refresh_repo_selector"):
            self._refresh_repo_selector()
        if hasattr(self, "_refresh_import_source_repo_options"):
            self._refresh_import_source_repo_options()
        self._schedule_workspace_cards_refresh()

    def _schedule_workspace_cards_refresh(self, delay_ms: int = 120) -> None:
        if not hasattr(self, "workspace_cards_inner"):
            return
        if self.workspace_card_refresh_job is not None:
            try:
                self.after_cancel(self.workspace_card_refresh_job)
            except tk.TclError:
                pass
        self.workspace_card_refresh_job = self.after(delay_ms, self._refresh_workspace_cards)

    def _refresh_workspace_cards(self) -> None:
        if not hasattr(self, "workspace_cards_inner"):
            return
        self.workspace_card_refresh_job = None
        repos = self._get_workspace_card_repos()
        if not repos:
            self._render_workspace_cards([])
            return
        current_repo = normalize_repo_path(self.repo_path) if self.repo_ready and self.repo_path else ""
        favorite_set = {normalize_repo_path(path) for path in self.favorite_repos}
        stale = self._get_stale_workspace_card_repos(repos)

        if not stale:
            if repos == self.workspace_card_paths and self._update_workspace_card_titles_only(
                repos,
                favorite_set,
                current_repo,
            ):
                return
            rows = self._build_workspace_rows_from_cache(repos, favorite_set, current_repo)
            self._render_workspace_cards(rows)
            return

        rows = self._build_workspace_rows_from_cache(repos, favorite_set, current_repo)
        if rows:
            self._render_workspace_cards(rows)
        else:
            self._render_workspace_cards_loading(repos)

        def task() -> dict[str, dict[str, object]]:
            details: dict[str, dict[str, object]] = {}
            for repo_path in stale:
                details[repo_path] = self._collect_workspace_card_details(repo_path)
            return details

        def success(result: object) -> None:
            details = dict(result)  # type: ignore[arg-type]
            now = time.time()
            for repo_path, info in details.items():
                self.workspace_card_detail_cache[repo_path] = info
                self.workspace_card_detail_ts[repo_path] = now
            rows = self._build_workspace_rows_from_cache(repos, favorite_set, current_repo)
            self._render_workspace_cards(rows)

        def error(_exc: Exception) -> None:
            rows = self._build_workspace_rows_from_cache(repos, favorite_set, current_repo)
            self._render_workspace_cards(rows)

        if hasattr(self, "_run_async"):
            self._run_async("workspace_cards", "Workspace cards", task, success, error)
        else:
            try:
                success(task())
            except Exception as exc:
                error(exc)

    def _get_workspace_card_repos(self) -> list[str]:
        ordered: list[str] = []
        for source in (self.favorite_repos, self.recent_repos):
            for item in source:
                normalized = normalize_repo_path(item)
                if normalized not in ordered and os.path.isdir(normalized):
                    ordered.append(normalized)
        if self.repo_ready and self.repo_path:
            current = normalize_repo_path(self.repo_path)
            if current not in ordered and os.path.isdir(current):
                ordered.append(current)
        return ordered

    def _get_stale_workspace_card_repos(self, repos: list[str]) -> list[str]:
        now = time.time()
        stale: list[str] = []
        for repo_path in repos:
            ts = self.workspace_card_detail_ts.get(repo_path)
            info = self.workspace_card_detail_cache.get(repo_path)
            if info is None or ts is None:
                stale.append(repo_path)
                continue
            if now - ts > WORKSPACE_CARD_CACHE_TTL_SEC:
                stale.append(repo_path)
        return stale

    def _build_workspace_rows_from_cache(
        self,
        repos: list[str],
        favorite_set: set[str],
        current_repo: str,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for repo_path in repos:
            info = self.workspace_card_detail_cache.get(repo_path)
            if info is None:
                continue
            rows.append(
                self._compose_workspace_card_row(
                    repo_path,
                    info,
                    is_favorite=repo_path in favorite_set,
                    is_current=repo_path == current_repo,
                )
            )
        return rows

    def _collect_workspace_card_details(
        self,
        repo_path: str,
    ) -> dict[str, object]:
        basename = os.path.basename(repo_path.rstrip(os.sep)) or repo_path

        if hasattr(self, "_format_repo_display_path"):
            display_path = self._format_repo_display_path(repo_path)
        else:
            display_path = repo_path

        if not is_git_repo(repo_path):
            return {
                "repo_path": repo_path,
                "base_name": basename,
                "path": display_path,
                "branch_name": "(invalido)",
                "branches": [],
                "branch": "Branch: (invalido)",
                "sync": "Ahead/Behind: (indisponivel)",
                "status": "Status: (indisponivel)",
            }

        try:
            branch = core_get_current_branch(repo_path).strip() or "(desconhecida)"
        except RuntimeError:
            branch = "(desconhecida)"
        try:
            branches = core_list_branches(repo_path)
        except RuntimeError:
            branches = []
        if branch and branch not in branches and branch != "(desconhecida)":
            branches.insert(0, branch)

        sync = "Ahead 0 | Behind 0"
        upstream = core_get_upstream(repo_path) or ""
        if upstream:
            try:
                behind, ahead = core_get_ahead_behind(repo_path, upstream)
                sync = f"Ahead {ahead} | Behind {behind}"
            except RuntimeError:
                sync = "Ahead/Behind: (erro)"
        else:
            sync = "Ahead/Behind: sem upstream"
        worktree_status = self._build_repo_worktree_status_summary(repo_path)

        return {
            "repo_path": repo_path,
            "base_name": basename,
            "path": display_path,
            "branch_name": branch,
            "branches": branches,
            "branch": f"Branch: {branch}",
            "sync": sync,
            "status": worktree_status,
        }

    def _compose_workspace_card_row(
        self,
        repo_path: str,
        info: dict[str, object],
        *,
        is_favorite: bool,
        is_current: bool,
    ) -> dict[str, object]:
        base_name = str(info.get("base_name", os.path.basename(repo_path.rstrip(os.sep)) or repo_path))
        name = base_name
        if is_favorite:
            name = f"★ {name}"
        if is_current:
            name = f"▶ {name}"
        row = dict(info)
        row["name"] = name
        row["repo_path"] = repo_path
        return row

    def _render_workspace_cards_loading(self, repos: list[str]) -> None:
        rows: list[dict[str, object]] = []
        for repo_path in repos:
            basename = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
            rows.append(
                {
                    "repo_path": repo_path,
                    "name": basename,
                    "path": "Carregando...",
                    "branch_name": "...",
                    "branches": [],
                    "branch": "Branch: ...",
                    "sync": "Ahead/Behind: ...",
                    "status": "Status: ...",
                }
            )
        self._render_workspace_cards(rows)

    def _render_workspace_cards(self, rows: list[dict[str, object]]) -> None:
        if not hasattr(self, "workspace_cards_inner"):
            return
        for child in self.workspace_cards_inner.winfo_children():
            child.destroy()
        self.workspace_card_paths = []
        self.workspace_card_frames = []

        for column in range(4):
            self.workspace_cards_inner.grid_columnconfigure(column, weight=1)

        for index, row in enumerate(rows):
            repo_path = str(row.get("repo_path", "")).strip()
            self.workspace_card_paths.append(repo_path)
            self._render_workspace_repo_card(index, row)
        self._render_workspace_add_card(len(rows))
        self.workspace_cards_canvas.configure(scrollregion=self.workspace_cards_canvas.bbox("all"))

    def _render_workspace_repo_card(self, index: int, row: dict[str, object]) -> None:
        card_row = index // 4
        card_column = index % 4
        repo_path = str(row.get("repo_path", "")).strip()
        card = ttk.LabelFrame(self.workspace_cards_inner, text=str(row.get("name", f"Repo {index + 1}")))
        card.grid(row=card_row, column=card_column, sticky="nsew", padx=4, pady=4)
        card.grid_columnconfigure(0, weight=1)
        self.workspace_card_frames.append(card)

        path = str(row.get("path", ""))
        branch_name = str(row.get("branch_name", "")).strip()
        branch_values_raw = row.get("branches", [])
        branch_values: list[str] = []
        if isinstance(branch_values_raw, list):
            for value in branch_values_raw:
                if not isinstance(value, str):
                    continue
                candidate = value.strip()
                if candidate and candidate not in branch_values:
                    branch_values.append(candidate)
        if branch_name and branch_name not in branch_values and branch_name != "...":
            branch_values.insert(0, branch_name)
        if not branch_name and branch_values:
            branch_name = branch_values[0]
        if not branch_name:
            branch_name = "(indisponivel)"
        sync = str(row.get("sync", ""))
        status = str(row.get("status", ""))
        path_label = ttk.Label(card, text=path, justify="left", wraplength=220)
        path_label.grid(row=0, column=0, sticky="w", padx=6, pady=(4, 2))
        branch_row = ttk.Frame(card)
        branch_row.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))
        branch_row.grid_columnconfigure(1, weight=1)
        branch_row.grid_columnconfigure(0, weight=0)
        ttk.Label(branch_row, text="Branch:", justify="left").grid(row=0, column=0, sticky="w", padx=(0, 4))
        branch_var = tk.StringVar(value=branch_name)
        branch_combo_state = "readonly" if branch_values else "disabled"
        branch_combo = ttk.Combobox(
            branch_row,
            textvariable=branch_var,
            values=branch_values,
            state=branch_combo_state,
        )
        branch_combo.grid(row=0, column=1, sticky="ew")
        if branch_values:
            branch_combo.bind(
                "<<ComboboxSelected>>",
                lambda _e, path=repo_path, var=branch_var: self._on_workspace_card_branch_selected(path, var),
            )
        sync_label = ttk.Label(card, text=sync, justify="left")
        sync_label.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 6))
        status_label = ttk.Label(card, text=status, justify="left", wraplength=220)
        status_label.grid(row=3, column=0, sticky="w", padx=6, pady=(0, 6))

        for widget in (card, path_label, branch_row, sync_label, status_label):
            widget.bind("<Button-1>", lambda _e, idx=index: self._open_workspace_card_repo(idx), add=True)
            widget.bind("<Double-Button-1>", lambda _e, idx=index: self._open_workspace_card_repo_vscode(idx), add=True)
            widget.bind(
                "<Button-3>",
                lambda event, path=repo_path: self._on_repo_context_menu_request(event, path, source="card"),
                add=True,
            )
            self._bind_workspace_scroll_events(widget)
        branch_combo.bind(
            "<Button-3>",
            lambda event, path=repo_path: self._on_repo_context_menu_request(event, path, source="card"),
            add=True,
        )
        self._bind_workspace_scroll_events(branch_combo)

    def _get_workspace_card_repo_path(self, index: int) -> str:
        if not hasattr(self, "workspace_card_paths"):
            return ""
        if index < 0 or index >= len(self.workspace_card_paths):
            return ""
        return self.workspace_card_paths[index]

    def _update_workspace_card_titles_only(
        self,
        repos: list[str],
        favorite_set: set[str],
        current_repo: str,
    ) -> bool:
        if len(repos) != len(self.workspace_card_frames):
            return False
        for idx, repo_path in enumerate(repos):
            info = self.workspace_card_detail_cache.get(repo_path)
            if info is None:
                return False
            row = self._compose_workspace_card_row(
                repo_path,
                info,
                is_favorite=repo_path in favorite_set,
                is_current=repo_path == current_repo,
            )
            self.workspace_card_frames[idx].configure(text=str(row.get("name", f"Repo {idx + 1}")))
        return True

    def _build_repo_worktree_status_summary(self, repo_path: str) -> str:
        try:
            changed_files = core_list_worktree_changed_files(repo_path)
        except RuntimeError:
            return "Status: (indisponivel)"
        if not changed_files:
            return "Status: limpo"
        total = len(changed_files)
        if total == 0:
            return "Status: alteracoes locais"
        if total <= 2:
            joined = ", ".join(changed_files)
            suffix = "arquivo" if total == 1 else "arquivos"
            return f"Status: {total} {suffix}: {joined}"
        preview = ", ".join(changed_files[:2])
        return f"Status: {total} arquivos: {preview}, +{total - 2}"

    def _render_workspace_add_card(self, index: int) -> None:
        card_row = index // 4
        card_column = index % 4
        add_card = ttk.LabelFrame(self.workspace_cards_inner, text="+1")
        add_card.grid(row=card_row, column=card_column, sticky="nsew", padx=4, pady=4)
        add_card.grid_columnconfigure(0, weight=1)

        title = ttk.Label(add_card, text="Adicionar repositório", justify="left")
        title.grid(row=0, column=0, sticky="w", padx=6, pady=(4, 2))
        description = ttk.Label(
            add_card,
            text="Abrir janela de clonagem\n(URL HTTPS/SSH)",
            justify="left",
        )
        description.grid(row=1, column=0, sticky="w", padx=6)
        add_button = ttk.Button(add_card, text="Adicionar", command=self._open_add_repo_dialog)
        add_button.grid(
            row=2, column=0, sticky="w", padx=6, pady=(6, 6)
        )
        for widget in (add_card, title, description, add_button):
            self._bind_workspace_scroll_events(widget)

    def _open_add_repo_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Adicionar repositório")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(1, weight=1)

        root_var = tk.StringVar(value=self.repo_scan_root)
        clone_url_var = tk.StringVar(value="")
        clone_name_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="Informe a URL para clonar (pasta aceita grupo/repositorio).")
        progress_hint_var = tk.StringVar(value="Progresso reportado: 0%")
        clone_running = False
        clone_cancel_requested = False
        clone_success_flash_job: str | None = None

        def choose_root() -> None:
            self._choose_repo_scan_root()
            root_var.set(self.repo_scan_root)

        ttk.Label(dialog, text="Raiz do workspace:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        root_entry = ttk.Entry(dialog, textvariable=root_var)
        root_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(10, 4))
        root_entry.configure(state="readonly")
        choose_root_button = ttk.Button(dialog, text="Pasta...", command=choose_root)
        choose_root_button.grid(row=0, column=2, sticky="w", padx=(0, 10), pady=(10, 4))

        ttk.Label(dialog, text="Clone URL/SSH:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        clone_url_entry = ttk.Entry(dialog, textvariable=clone_url_var)
        clone_url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)

        ttk.Label(dialog, text="Pasta (opcional):").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        clone_name_entry = ttk.Entry(dialog, textvariable=clone_name_var)
        clone_name_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)

        has_key, _key_path = github_ssh_key_exists()
        prepare_ssh_button: ttk.Button | None = None
        if not has_key:
            prepare_ssh_button = ttk.Button(dialog, text="Preparar chave SSH", command=self._prepare_github_ssh_key)
            prepare_ssh_button.grid(
                row=3, column=0, sticky="w", padx=10, pady=(2, 4)
            )

        progress_frame = ttk.LabelFrame(dialog, text="Progresso da clonagem")
        progress_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=10, pady=(4, 2))
        progress_frame.grid_columnconfigure(0, weight=1)
        progress_frame.grid_rowconfigure(0, weight=1)
        progress_text = tk.Text(progress_frame, height=8, wrap="word", state="disabled")
        progress_text.grid(row=0, column=0, sticky="nsew")
        progress_scroll = ttk.Scrollbar(progress_frame, orient="vertical", command=progress_text.yview)
        progress_scroll.grid(row=0, column=1, sticky="ns")
        progress_text.configure(yscrollcommand=progress_scroll.set)
        progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="indeterminate")
        progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Label(dialog, textvariable=progress_hint_var).grid(
            row=5, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 2)
        )
        ttk.Label(dialog, textvariable=status_var).grid(row=6, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 0))
        actions = ttk.Frame(dialog)
        actions.grid(row=7, column=0, columnspan=3, sticky="e", padx=10, pady=10)

        def append_progress_line(raw_line: str) -> None:
            if not dialog.winfo_exists():
                return
            line = raw_line.strip()
            if not line:
                return
            status_var.set(line)
            percent_match = re.search(r"(\d{1,3})%", line)
            if percent_match:
                progress_hint_var.set(f"Progresso reportado: {percent_match.group(1)}%")
            progress_text.configure(state="normal")
            progress_text.insert(tk.END, f"{line}\n")
            progress_text.see(tk.END)
            progress_text.configure(state="disabled")

        def set_dialog_running(running: bool) -> None:
            nonlocal clone_running
            clone_running = running
            if running:
                root_entry.configure(state="disabled")
                clone_url_entry.configure(state="disabled")
                clone_name_entry.configure(state="disabled")
                choose_root_button.configure(state="disabled")
                if prepare_ssh_button is not None:
                    prepare_ssh_button.configure(state="disabled")
                clone_button.configure(state="disabled")
                cancel_button.configure(text="Cancelar clone")
                progress_bar.start(10)
                if hasattr(self, "_set_clone_ui_locked"):
                    self._set_clone_ui_locked(True)
                return
            root_entry.configure(state="readonly")
            clone_url_entry.configure(state="normal")
            clone_name_entry.configure(state="normal")
            choose_root_button.configure(state="normal")
            if prepare_ssh_button is not None:
                prepare_ssh_button.configure(state="normal")
            clone_button.configure(state="normal")
            cancel_button.configure(text="Fechar")
            progress_bar.stop()
            if hasattr(self, "_set_clone_ui_locked"):
                self._set_clone_ui_locked(False)

        def animate_clone_success_flash(steps: int = 8, on_done: Callable[[], None] | None = None) -> None:
            nonlocal clone_success_flash_job
            if not dialog.winfo_exists():
                return
            if steps <= 0:
                progress_bar.configure(mode="determinate", maximum=100, value=100)
                clone_success_flash_job = None
                if on_done is not None:
                    dialog.after(120, on_done)
                return
            value = 100 if steps % 2 == 0 else 0
            progress_bar.configure(mode="determinate", maximum=100, value=value)
            clone_success_flash_job = dialog.after(
                120,
                lambda: animate_clone_success_flash(steps - 1, on_done),
            )

        def on_clone_finished(ok: bool, detail: str) -> None:
            nonlocal clone_cancel_requested, clone_success_flash_job
            clone_cancel_requested = False
            if not dialog.winfo_exists():
                if hasattr(self, "_set_clone_ui_locked"):
                    self._set_clone_ui_locked(False)
                return
            if clone_success_flash_job is not None:
                try:
                    dialog.after_cancel(clone_success_flash_job)
                except tk.TclError:
                    pass
                clone_success_flash_job = None
            set_dialog_running(False)
            if ok:
                status_var.set("Clone concluido.")
                progress_hint_var.set("Progresso reportado: 100%")
                if hasattr(self, "_open_repositories_tab"):
                    self._open_repositories_tab()
                self.after(50, self._scan_repo_workspace)
                clone_button.configure(state="disabled")
                cancel_button.configure(state="disabled")
                animate_clone_success_flash(on_done=lambda: dialog.winfo_exists() and dialog.destroy())
            else:
                cancelled = "cancelado pelo usuario" in detail.lower()
                if cancelled:
                    status_var.set("Clone cancelado pelo usuario.")
                else:
                    status_var.set(detail.strip() or "Falha no clone.")

        def clone_action() -> None:
            nonlocal clone_cancel_requested
            repo_url = clone_url_var.get().strip()
            target_name = clone_name_var.get().strip()
            if not repo_url:
                messagebox.showwarning("Clone", "Informe a URL SSH/HTTPS do repositório.")
                return
            clone_cancel_requested = False
            progress_text.configure(state="normal")
            progress_text.delete("1.0", tk.END)
            progress_text.configure(state="disabled")
            progress_hint_var.set("Progresso reportado: 0%")
            status_var.set("Iniciando clone...")
            set_dialog_running(True)
            self._clone_repo_from_url(
                repo_url=repo_url,
                target_name=target_name,
                on_finished=on_clone_finished,
                on_progress=lambda line: self.after(0, lambda value=line: append_progress_line(value)),
                is_cancelled=lambda: clone_cancel_requested,
            )

        def cancel_action() -> None:
            nonlocal clone_cancel_requested
            if clone_running:
                clone_cancel_requested = True
                status_var.set("Cancelando clone...")
                return
            if hasattr(self, "_set_clone_ui_locked"):
                self._set_clone_ui_locked(False)
            dialog.destroy()

        cancel_button = ttk.Button(actions, text="Cancelar", command=cancel_action)
        cancel_button.grid(row=0, column=0, padx=(0, 6))
        clone_button = ttk.Button(actions, text="Clonar", command=clone_action)
        clone_button.grid(row=0, column=1)
        dialog.protocol("WM_DELETE_WINDOW", cancel_action)
        clone_url_entry.focus_set()

    def _open_workspace_card_repo(self, index: int) -> None:
        repo_path = self._get_workspace_card_repo_path(index)
        if not repo_path:
            return
        if self.repo_ready and self.repo_path:
            current = normalize_repo_path(self.repo_path)
            if current == normalize_repo_path(repo_path):
                return
        if not self._open_repo_from_path(repo_path):
            return
        if self._is_repositories_tab_selected():
            self._open_repo_post_select_tab()

    def _open_workspace_card_repo_vscode(self, index: int) -> None:
        repo_path = self._get_workspace_card_repo_path(index)
        if not repo_path:
            return
        self._open_workspace_card_repo(index)
        if hasattr(self, "_open_path_in_vscode"):
            self._open_path_in_vscode(repo_path, use_goto=False)

    def _on_workspace_card_branch_selected(self, repo_path: str, branch_var: tk.StringVar) -> None:
        target = branch_var.get().strip()
        if not target:
            return
        normalized_repo = normalize_repo_path(repo_path)
        info = self.workspace_card_detail_cache.get(normalized_repo, {})
        previous_branch = str(info.get("branch_name", "")).strip()
        if previous_branch == target:
            return
        if self.repo_ready and self.repo_path and normalize_repo_path(self.repo_path) == normalized_repo:
            if not self._checkout_to_branch(target):
                if previous_branch:
                    branch_var.set(previous_branch)
                return
            self.workspace_card_detail_ts.pop(normalized_repo, None)
            self._schedule_workspace_cards_refresh(0)
            return
        perf_trigger = "workspace_card:checkout_other_repo"
        start = self._perf_start("Checkout branch", perf_trigger)
        try:
            try:
                repo_is_dirty = core_is_dirty(normalized_repo)
            except RuntimeError as exc:
                messagebox.showerror("Checkout", str(exc))
                if previous_branch:
                    branch_var.set(previous_branch)
                return
            if repo_is_dirty:
                repo_name = os.path.basename(normalized_repo.rstrip(os.sep)) or normalized_repo
                proceed = messagebox.askyesno(
                    "Checkout",
                    f"O repositório '{repo_name}' possui alterações locais.\nContinuar checkout para '{target}'?",
                )
                if not proceed:
                    if previous_branch:
                        branch_var.set(previous_branch)
                    return
            try:
                core_checkout_branch(normalized_repo, target)
            except RuntimeError as exc:
                messagebox.showerror("Checkout", str(exc))
                if previous_branch:
                    branch_var.set(previous_branch)
                return
            refreshed = self._collect_workspace_card_details(normalized_repo)
            self.workspace_card_detail_cache[normalized_repo] = refreshed
            self.workspace_card_detail_ts[normalized_repo] = time.time()
            if hasattr(self, "_set_status"):
                self._set_status(f"Checkout em {os.path.basename(normalized_repo)}: {target}")
            self._schedule_workspace_cards_refresh(0)
        finally:
            self._perf_end("Checkout branch", start, perf_trigger)

    def _open_repo_from_dialog(self) -> None:
        path = filedialog.askdirectory()
        if not path:
            return
        self._open_repo_from_path(path)

    def _open_repo_from_path(self, path: str) -> bool:
        return self._open_repo_from_path_with_options(path, refresh_remote=False, switch_to_history=False)

    def _open_repo_from_path_with_options(
        self,
        path: str,
        *,
        refresh_remote: bool,
        switch_to_history: bool,
    ) -> bool:
        if not path:
            return False
        if not self._set_repo_path(path, initial=False):
            return False
        if refresh_remote and hasattr(self, "_fetch_repo"):
            self._fetch_repo()
        if switch_to_history:
            self._open_history_tab()
        return True

    def _is_repositories_tab_selected(self) -> bool:
        if not hasattr(self, "tabs") or not hasattr(self, "repos_tab"):
            return False
        try:
            selected = self.tabs.select()
        except tk.TclError:
            return False
        return bool(selected) and str(selected) == str(self.repos_tab)

    def _open_repo_post_select_tab(self) -> None:
        if not self.repo_ready:
            return
        try:
            has_pending_changes = self._is_dirty()
        except RuntimeError:
            has_pending_changes = False
        if has_pending_changes:
            self._open_commit_tab()
        else:
            self._open_history_tab()

    def _open_commit_tab(self) -> None:
        if not hasattr(self, "tabs"):
            return
        tab_count = self.tabs.index("end")
        for index in range(tab_count):
            if self.tabs.tab(index, "text") != "Commit":
                continue
            if hasattr(self, "_select_tab"):
                self._select_tab(index)
            else:
                self.tabs.select(index)
            return

    def _open_history_tab(self) -> None:
        if not hasattr(self, "tabs"):
            return
        tab_count = self.tabs.index("end")
        for index in range(tab_count):
            if self.tabs.tab(index, "text") != "Histórico":
                continue
            if hasattr(self, "_select_tab"):
                self._select_tab(index)
            else:
                self.tabs.select(index)
            return

    def _open_repositories_tab(self) -> None:
        if not hasattr(self, "tabs") or not hasattr(self, "repos_tab"):
            return
        try:
            index = int(self.tabs.index(self.repos_tab))
        except tk.TclError:
            return
        if hasattr(self, "_select_tab"):
            self._select_tab(index)
        else:
            self.tabs.select(index)

    def _open_selected_favorite(self) -> None:
        path = self._get_selected_repo(self.favorite_listbox, self.favorite_repos)
        if path:
            self._open_repo_from_path(path)

    def _open_selected_recent(self) -> None:
        path = self._get_selected_repo(self.recent_listbox, self.recent_repos)
        if path:
            self._open_repo_from_path_with_options(path, refresh_remote=True, switch_to_history=True)

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

    def _refresh_repo_status_panel(self) -> None:
        if not hasattr(self, "repo_status_path_var"):
            return
        if not self.repo_ready:
            self.repo_status_path_var.set("(nenhum)")
            self.repo_status_branch_var.set("(nenhum)")
            self.repo_status_upstream_var.set("(não configurado)")
            self.repo_status_ahead_behind_var.set("0/0")
            self.repo_status_dirty_var.set("Limpo")
            return
        self.repo_status_path_var.set(self.repo_path)
        try:
            branch = self._get_current_branch()
        except RuntimeError:
            branch = ""
        self.repo_status_branch_var.set(branch or "(desconhecido)")

        upstream = self._get_upstream()
        self.repo_status_upstream_var.set(upstream or "(não configurado)")

        try:
            behind, ahead = self._get_ahead_behind()
        except RuntimeError:
            behind, ahead = 0, 0
        self.repo_status_ahead_behind_var.set(f"{ahead}/{behind}")

        try:
            dirty = self._is_dirty()
        except RuntimeError:
            dirty = False
        self.repo_status_dirty_var.set("Sujo" if dirty else "Limpo")

    @staticmethod
    def _get_selected_repo(listbox: tk.Listbox, data: list[str]) -> str | None:
        selection = listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if index < 0 or index >= len(data):
            return None
        return data[index]
