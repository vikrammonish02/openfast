"""API endpoints for reference turbine data — airfoils, blade, tower, Cp-Ct-Cq, costs.

These endpoints parse the validated NREL reference input files bundled
in ``reference_inputs/`` and return structured JSON for the frontend
visualisation components.
"""

from fastapi import APIRouter, HTTPException, status

from app.openfast.reference_parser import (
    list_airfoils,
    list_available_turbines,
    parse_blade_properties,
    parse_cp_ct_cq,
    parse_tower_properties,
    get_cost_breakdown,
)

router = APIRouter(prefix="/reference", tags=["reference-data"])


@router.get("/turbines")
async def get_available_turbines():
    """List available reference turbine decks."""
    return {"turbines": list_available_turbines()}


@router.get("/{turbine}/airfoils")
async def get_airfoils(turbine: str):
    """Return all parsed airfoil data (polars + coordinates) for a reference turbine."""
    try:
        airfoils = list_airfoils(turbine)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"turbine": turbine, "airfoils": airfoils}


@router.get("/{turbine}/blade")
async def get_blade_properties(turbine: str):
    """Return distributed blade properties (BlFract, twist, mass, stiffness)."""
    try:
        props = parse_blade_properties(turbine)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"turbine": turbine, **props}


@router.get("/{turbine}/tower")
async def get_tower_properties(turbine: str):
    """Return distributed tower properties (HtFract, mass, FA/SS stiffness)."""
    try:
        props = parse_tower_properties(turbine)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"turbine": turbine, **props}


@router.get("/{turbine}/performance")
async def get_performance_surfaces(turbine: str):
    """Return Cp-Ct-Cq performance surfaces (pitch x TSR matrices)."""
    try:
        data = parse_cp_ct_cq(turbine)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"turbine": turbine, **data}


@router.get("/{turbine}/costs")
async def get_cost_breakdown_endpoint(turbine: str):
    """Return reference cost breakdown based on NREL Cost & Scaling Model."""
    try:
        costs = get_cost_breakdown(turbine)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"turbine": turbine, **costs}
