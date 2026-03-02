"""Reference turbine template registry."""

from .nrel_5mw import NREL_5MW
from .dtu_10mw import DTU_10MW
from .iea_15mw import IEA_15MW

REFERENCE_TURBINES: dict[str, dict] = {
    "nrel_5mw": NREL_5MW,
    "dtu_10mw": DTU_10MW,
    "iea_15mw": IEA_15MW,
}


def get_template(template_id: str) -> dict | None:
    return REFERENCE_TURBINES.get(template_id)


def list_templates() -> list[dict]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "rated_power_kw": t["project"]["rated_power"],
            "rotor_diameter": t["project"]["rotor_diameter"],
            "hub_height": t["project"]["hub_height"],
            "platform_type": t["project"].get("platform_type", "onshore"),
            "wind_class": t["project"]["wind_class"],
            "turbulence_class": t["project"]["turbulence_class"],
            "is_offshore": t.get("is_offshore", False),
        }
        for t in REFERENCE_TURBINES.values()
    ]
