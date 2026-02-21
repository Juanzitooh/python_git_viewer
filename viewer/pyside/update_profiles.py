from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateProfile:
    key: str
    label: str
    status_interval_sec: int
    fetch_interval_sec: int
    history_interval_sec: int
    workspace_interval_sec: int
    description: str


UPDATE_PROFILES: tuple[UpdateProfile, ...] = (
    UpdateProfile(
        key="realtime",
        label="Tempo real",
        status_interval_sec=5,
        fetch_interval_sec=60,
        history_interval_sec=20,
        workspace_interval_sec=45,
        description="Atualiza mais rapido (maior uso de CPU/disco/rede).",
    ),
    UpdateProfile(
        key="balanced",
        label="Balanceado",
        status_interval_sec=15,
        fetch_interval_sec=180,
        history_interval_sec=45,
        workspace_interval_sec=120,
        description="Bom equilibrio entre fluidez e uso de recursos.",
    ),
    UpdateProfile(
        key="economic",
        label="Economico",
        status_interval_sec=30,
        fetch_interval_sec=600,
        history_interval_sec=120,
        workspace_interval_sec=300,
        description="Menos consultas automaticas; melhor para repos grandes.",
    ),
)

UPDATE_PROFILE_BY_KEY = {profile.key: profile for profile in UPDATE_PROFILES}


def resolve_update_profile(settings_data: dict[str, object]) -> UpdateProfile:
    raw_key = str(settings_data.get("update_profile", "balanced")).strip().lower()
    if raw_key == "custom":
        status_interval = _as_int(
            settings_data.get("status_interval_sec"),
            fallback=15,
            minimum=5,
        )
        fetch_interval = _as_int(
            settings_data.get("fetch_interval_sec"),
            fallback=180,
            minimum=10,
        )
        history_interval = _as_int(
            settings_data.get("history_refresh_interval_sec"),
            fallback=45,
            minimum=10,
        )
        workspace_interval = _as_int(
            settings_data.get("workspace_refresh_interval_sec"),
            fallback=120,
            minimum=20,
        )
        return UpdateProfile(
            key="custom",
            label="Personalizado",
            status_interval_sec=status_interval,
            fetch_interval_sec=fetch_interval,
            history_interval_sec=history_interval,
            workspace_interval_sec=workspace_interval,
            description="Usa os intervalos customizados salvos no settings.json.",
        )
    profile = UPDATE_PROFILE_BY_KEY.get(raw_key)
    if profile is not None:
        return profile
    return UPDATE_PROFILE_BY_KEY["balanced"]


def _as_int(value: object, *, fallback: int, minimum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if parsed < minimum:
        return fallback
    return parsed
