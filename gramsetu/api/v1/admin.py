from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from gramsetu.core import DevActor, Role, Environment, require_roles
from gramsetu.store import TransactionCoordinator
from gramsetu.units import DatasetContractError
from gramsetu.release import validate_release_zip, import_staged_release_to_store
from gramsetu.api.deps import get_coordinator, get_app_settings
from gramsetu.core import Settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/import/sandbox-release")
async def post_import_sandbox_release(
    release_path: Optional[str] = None,
    release_pin: Optional[str] = None,
    actor: DevActor = Depends(require_roles(Role.FPO_ADMIN, Role.SYSTEM)),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
    cfg: Settings = Depends(get_app_settings),
):
    target_path = release_path or cfg.RELEASE_ARCHIVE_PATH
    target_pin = release_pin or cfg.RELEASE_PIN
    env_str = str(cfg.ENVIRONMENT).lower()

    if "prod" in env_str or cfg.ENVIRONMENT == Environment.PRODUCTION or not cfg.ALLOW_SYNTHETIC_SEED:
        return JSONResponse(
            status_code=403,
            content={
                "error": "FORBIDDEN",
                "message": "Synthetic fixture release cannot be seeded into production environment or without explicit ALLOW_SYNTHETIC_SEED=true",
                "status_code": 403,
            },
        )

    try:
        staged = validate_release_zip(target_path)
        res = import_staged_release_to_store(
            staged,
            coordinator,
            environment=env_str,
            allow_synthetic_seed=cfg.ALLOW_SYNTHETIC_SEED,
            release_pin=target_pin,
        )
        return res
    except DatasetContractError as e:
        return JSONResponse(
            status_code=422,
            content={
                "error": "UNPROCESSABLE_ENTITY",
                "message": str(e),
                "status_code": 422,
            },
        )
