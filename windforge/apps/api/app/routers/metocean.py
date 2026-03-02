"""Metocean site CRUD endpoints — org-level resource."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.iec.sea_conditions import (
    ess_wave_height_1yr,
    ess_wave_height_50yr,
    nss_wave_height,
    nss_wave_period,
    sss_wave_height,
)
from app.models.metocean import MetoceanSite
from app.models.user import User
from app.schemas.metocean import (
    MetoceanAutoGenerate,
    MetoceanSiteCreate,
    MetoceanSiteResponse,
    MetoceanSiteUpdate,
)

router = APIRouter(prefix="/metocean-sites", tags=["metocean"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _get_site_or_404(site_id: str, org_id: str, db: AsyncSession) -> MetoceanSite:
    result = await db.execute(
        select(MetoceanSite).where(
            MetoceanSite.id == site_id, MetoceanSite.org_id == org_id
        )
    )
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Metocean site not found"
        )
    return site


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=list[MetoceanSiteResponse])
async def list_metocean_sites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all metocean sites for the user's organisation."""
    result = await db.execute(
        select(MetoceanSite)
        .where(MetoceanSite.org_id == current_user.org_id)
        .order_by(MetoceanSite.created_at.desc())
    )
    return [MetoceanSiteResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=MetoceanSiteResponse, status_code=status.HTTP_201_CREATED)
async def create_metocean_site(
    body: MetoceanSiteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new metocean site."""
    site = MetoceanSite(org_id=current_user.org_id, **body.model_dump(exclude_unset=True))
    db.add(site)
    await db.flush()
    await db.refresh(site)
    return MetoceanSiteResponse.model_validate(site)


@router.get("/{site_id}", response_model=MetoceanSiteResponse)
async def get_metocean_site(
    site_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single metocean site."""
    site = await _get_site_or_404(site_id, current_user.org_id, db)
    return MetoceanSiteResponse.model_validate(site)


@router.put("/{site_id}", response_model=MetoceanSiteResponse)
async def update_metocean_site(
    site_id: str,
    body: MetoceanSiteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing metocean site."""
    site = await _get_site_or_404(site_id, current_user.org_id, db)
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(site, field, value)
    site.version += 1
    await db.flush()
    await db.refresh(site)
    return MetoceanSiteResponse.model_validate(site)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metocean_site(
    site_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a metocean site."""
    site = await _get_site_or_404(site_id, current_user.org_id, db)
    await db.delete(site)
    await db.flush()


@router.post("/auto-generate", response_model=MetoceanSiteResponse, status_code=status.HTTP_201_CREATED)
async def auto_generate_metocean(
    body: MetoceanAutoGenerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate a metocean site from IEC 61400-3-1 empirical formulas.

    Uses the built-in IEC sea condition models to compute NSS/SSS/ESS
    wave heights and periods for each wind speed bin.
    """
    ws = body.wind_speeds
    depth = body.water_depth

    # Compute NSS
    hs_nss = [round(nss_wave_height(v, depth), 3) for v in ws]
    tp_nss = [round(nss_wave_period(hs), 3) for hs in hs_nss]

    # Compute SSS
    hs_sss = [round(sss_wave_height(v, depth), 3) for v in ws]
    tp_sss = [round(nss_wave_period(hs), 3) for hs in hs_sss]

    # ESS — constant across wind speeds (return-period based)
    hs_ess_50 = ess_wave_height_50yr(depth)
    hs_ess_1 = ess_wave_height_1yr(depth)
    hs_ess = [round(hs_ess_50, 3)] * len(ws)
    tp_ess = [round(nss_wave_period(hs_ess_50), 3)] * len(ws)

    # JONSWAP gamma — default 3.3 (typical North Sea)
    gamma = [3.3] * len(ws)

    site = MetoceanSite(
        org_id=current_user.org_id,
        name=body.name,
        description=f"Auto-generated from IEC 61400-3-1 for depth={depth}m, "
                    f"Hs1={hs_ess_1:.1f}m, Hs50={hs_ess_50:.1f}m",
        water_depth=depth,
        current_speed=0.0,
        wind_speeds=ws,
        wave_hs_nss=hs_nss,
        wave_tp_nss=tp_nss,
        wave_hs_sss=hs_sss,
        wave_tp_sss=tp_sss,
        wave_hs_ess=hs_ess,
        wave_tp_ess=tp_ess,
        wave_gamma=gamma,
    )
    db.add(site)
    await db.flush()
    await db.refresh(site)
    return MetoceanSiteResponse.model_validate(site)
