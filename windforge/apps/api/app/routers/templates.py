"""Reference turbine template endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.components import Blade, Controller, Tower, TurbineModel
from app.models.project import Project
from app.models.user import User
from app.reference_turbines import get_template, list_templates
from app.schemas.project import ProjectResponse
from app.schemas.templates import CreateFromTemplateRequest, TemplateInfo

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateInfo])
async def list_all_templates():
    """List all available reference turbine templates."""
    return [TemplateInfo(**t) for t in list_templates()]


@router.get("/{template_id}", response_model=TemplateInfo)
async def get_template_info(template_id: str):
    """Get metadata for a single reference turbine template."""
    templates = list_templates()
    for t in templates:
        if t["id"] == template_id:
            return TemplateInfo(**t)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Template '{template_id}' not found",
    )


@router.post("/create-project", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_from_template(
    body: CreateFromTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a full project from a reference turbine template in a single transaction."""
    template = get_template(body.template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{body.template_id}' not found",
        )

    tpl_project = template["project"]
    tpl_tower = template["tower"]
    tpl_blade = template["blade"]
    tpl_controller = template["controller"]
    tpl_turbine_model = template["turbine_model"]

    # --- Project ---
    project = Project(
        org_id=current_user.org_id,
        created_by=current_user.id,
        name=body.name,
        description=body.description,
        rated_power=tpl_project["rated_power"],
        rotor_diameter=tpl_project["rotor_diameter"],
        hub_height=tpl_project["hub_height"],
        num_blades=tpl_project.get("num_blades", 3),
        wind_class=tpl_project["wind_class"],
        turbulence_class=tpl_project["turbulence_class"],
        cut_in_speed=tpl_project["cut_in_speed"],
        rated_speed=tpl_project["rated_wind_speed"],
        cut_out_speed=tpl_project["cut_out_speed"],
        dt=tpl_project["dt"],
        t_max=tpl_project["t_max"],
        platform_type=body.platform_type or tpl_project.get("platform_type", "onshore"),
        water_depth=tpl_project.get("water_depth"),
    )
    db.add(project)
    await db.flush()

    # --- Tower ---
    tower = Tower(
        project_id=project.id,
        name=tpl_tower["name"],
        tower_height=tpl_tower["height"],
        tower_base_height=tpl_tower["base_elevation"],
        stations=tpl_tower["stations"],
        fa_mode_1_coeffs=tpl_tower["mode_shapes"]["FA_mode_1"],
        fa_mode_2_coeffs=tpl_tower["mode_shapes"]["FA_mode_2"],
        ss_mode_1_coeffs=tpl_tower["mode_shapes"]["SS_mode_1"],
        ss_mode_2_coeffs=tpl_tower["mode_shapes"]["SS_mode_2"],
        tower_fa_damping_1=tpl_tower["damping"]["FA_1"],
        tower_fa_damping_2=tpl_tower["damping"]["FA_2"],
        tower_ss_damping_1=tpl_tower["damping"]["SS_1"],
        tower_ss_damping_2=tpl_tower["damping"]["SS_2"],
    )
    db.add(tower)
    await db.flush()

    # --- Blade ---
    blade = Blade(
        project_id=project.id,
        name=tpl_blade["name"],
        blade_length=tpl_blade["length"],
        structural_stations=tpl_blade["structural_stations"],
        aero_stations=tpl_blade["aero_stations"],
        flap_mode_1_coeffs=tpl_blade["mode_shapes"]["flap_mode_1"],
        flap_mode_2_coeffs=tpl_blade["mode_shapes"]["flap_mode_2"],
        edge_mode_1_coeffs=tpl_blade["mode_shapes"]["edge_mode_1"],
        blade_flap_damping=tpl_blade["damping"]["flap"],
        blade_edge_damping=tpl_blade["damping"]["edge"],
    )
    db.add(blade)
    await db.flush()

    # --- Controller ---
    controller = Controller(
        project_id=project.id,
        name=tpl_controller["name"],
        controller_type=tpl_controller["type"],
        pcmode=tpl_controller["pcmode"],
        vscontrl=tpl_controller["vscontrl"],
        parameters=tpl_controller["parameters"],
    )
    db.add(controller)
    await db.flush()

    # --- TurbineModel ---
    turbine_model = TurbineModel(
        project_id=project.id,
        name=tpl_turbine_model["name"],
        tower_id=tower.id,
        blade_id=blade.id,
        controller_id=controller.id,
        gearbox_ratio=tpl_turbine_model.get("gearbox_ratio"),
        generator_inertia=tpl_turbine_model.get("generator_inertia"),
        drivetrain_stiffness=tpl_turbine_model.get("drivetrain_stiffness"),
        drivetrain_damping=tpl_turbine_model.get("drivetrain_damping"),
        hub_mass=tpl_turbine_model.get("hub_mass"),
        hub_inertia=tpl_turbine_model.get("hub_inertia"),
        nacelle_mass=tpl_turbine_model.get("nacelle_mass"),
        nacelle_inertia=tpl_turbine_model.get("nacelle_inertia"),
        overhang=tpl_turbine_model.get("overhang"),
        shaft_tilt=tpl_turbine_model.get("shaft_tilt"),
        precone=tpl_turbine_model.get("precone"),
        rotor_speed_rated=tpl_turbine_model.get("rotor_speed_rated"),
        substructure_config=template.get("substructure_config"),
        hydrodyn_config=template.get("hydrodyn_config"),
        moordyn_config=template.get("moordyn_config"),
    )
    db.add(turbine_model)
    await db.flush()

    await db.refresh(project)
    return ProjectResponse.model_validate(project)
