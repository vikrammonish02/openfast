"""
AeroDyn input file generator for OpenFAST v4.1.2.

Generates two files:
  1. AeroDyn primary input file (.dat)
  2. AeroDyn blade definition input file (.dat)

Format verified against:
  r-test/v4.1.2/glue-codes/openfast/5MW_Land_DLL_WTurb/NRELOffshrBsline5MW_Onshore_AeroDyn.dat
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes for blade aerodynamic stations
# ---------------------------------------------------------------------------

@dataclass
class AeroBladeStation:
    """A single AeroDyn blade station entry (v4.1.2 with buoyancy columns)."""
    bl_spn: float       # Blade span position (m)
    bl_crv_ac: float    # Out-of-plane offset of aerodynamic center (m)
    bl_swp_ac: float    # In-plane offset of aerodynamic center (m)
    bl_crv_ang: float   # Angle of curvature (deg)
    bl_twist: float     # Blade twist (deg)
    bl_chord: float     # Blade chord length (m)
    bl_af_id: int       # Airfoil ID number (1-based index into AFNames)
    bl_cb: float = 0.0       # Buoyancy coefficient (-)
    bl_cen_bn: float = 0.0   # Center offset in blade normal direction (m)
    bl_cen_bt: float = 0.0   # Center offset in blade tangent direction (m)


@dataclass
class TowerAeroStation:
    """A single AeroDyn tower node entry."""
    twr_elev: float     # Tower elevation (m)
    twr_diam: float     # Tower diameter (m)
    twr_cd: float       # Tower drag coefficient (-)
    twr_ti: float       # Tower turbulence intensity used with TwrShadow=2 (-)
    twr_cb: float       # Tower buoyancy coefficient used with Buoyancy=True (-)


# ---------------------------------------------------------------------------
# Configuration data classes
# ---------------------------------------------------------------------------

def _nrel5mw_aero_blade_stations() -> list[AeroBladeStation]:
    """Return default NREL 5MW aerodynamic blade stations (19 stations)."""
    # Data from r-test/v4.1.2: NRELOffshrBsline5MW_AeroDyn_blade.dat
    # (BlSpn, BlCrvAC, BlSwpAC, BlCrvAng, BlTwist, BlChord, BlAFID)
    data = [
        ( 0.0000,  0.0000000e+00,  0.0000000e+00, 0.0, 13.308, 3.542, 1),
        ( 1.3667, -8.1531745e-04, -3.4468858e-03, 0.0, 13.308, 3.542, 1),
        ( 4.1000, -2.4839790e-02, -1.0501421e-01, 0.0, 13.308, 3.854, 1),
        ( 6.8333, -5.9469375e-02, -2.5141635e-01, 0.0, 13.308, 4.167, 2),
        (10.2500, -1.0909141e-01, -4.6120149e-01, 0.0, 13.308, 4.557, 3),
        (14.3500, -1.1573354e-01, -5.6986665e-01, 0.0, 11.480, 4.652, 4),
        (18.4500, -9.8316709e-02, -5.4850833e-01, 0.0, 10.162, 4.458, 4),
        (22.5500, -8.3186967e-02, -5.2457001e-01, 0.0,  9.011, 4.249, 5),
        (26.6500, -6.7933232e-02, -4.9624675e-01, 0.0,  7.795, 4.007, 6),
        (30.7500, -5.3393159e-02, -4.6544755e-01, 0.0,  6.544, 3.748, 6),
        (34.8500, -4.0899260e-02, -4.3583519e-01, 0.0,  5.361, 3.502, 7),
        (38.9500, -2.9722933e-02, -4.0591323e-01, 0.0,  4.188, 3.256, 7),
        (43.0500, -2.0511081e-02, -3.7569051e-01, 0.0,  3.125, 3.010, 8),
        (47.1500, -1.3980013e-02, -3.4521705e-01, 0.0,  2.319, 2.764, 8),
        (51.2500, -8.3819737e-03, -3.1463837e-01, 0.0,  1.526, 2.518, 8),
        (54.6667, -4.3546914e-03, -2.8909220e-01, 0.0,  0.863, 2.313, 8),
        (57.4000, -1.6838383e-03, -2.6074456e-01, 0.0,  0.370, 2.086, 8),
        (60.1333, -3.2815226e-04, -1.7737470e-01, 0.0,  0.106, 1.419, 8),
        (61.4999, -3.2815226e-04, -1.7737470e-01, 0.0,  0.106, 1.419, 8),
    ]
    return [AeroBladeStation(*d) for d in data]


@dataclass
class AeroDynBladeConfig:
    """Configuration for an AeroDyn blade definition file."""
    num_bl_nds: int = 19
    stations: list[AeroBladeStation] = field(default_factory=_nrel5mw_aero_blade_stations)


def _nrel5mw_tower_aero_stations() -> list[TowerAeroStation]:
    """Return default NREL 5MW tower aero stations (20 stations).

    Note: These elevations must lie within the ElastoDyn tower range
    [TowerBsHt, TowerBsHt + TowerHt] = [10.0, 87.6] for the NREL 5MW.
    The r-test reference uses elevations 0.0-87.6 but the 5MW_Land_DLL_WTurb
    test case has TowerBsHt=10.0, so we must start at 10.0 to avoid mesh
    mapping errors.
    """
    # Start at 15m (above TurbSim grid bottom at ~14.4m) to avoid
    # "Grid too small in Z direction" error
    data = [
        (15.000,  5.787, 1.0, 0.1, 0.0),
        (22.260,  5.574, 1.0, 0.1, 0.0),
        (29.520,  5.361, 1.0, 0.1, 0.0),
        (36.780,  5.148, 1.0, 0.1, 0.0),
        (44.040,  4.935, 1.0, 0.1, 0.0),
        (51.300,  4.722, 1.0, 0.1, 0.0),
        (58.560,  4.509, 1.0, 0.1, 0.0),
        (65.820,  4.296, 1.0, 0.1, 0.0),
        (73.080,  4.083, 1.0, 0.1, 0.0),
        (80.340,  3.870, 1.0, 0.1, 0.0),
        (87.600,  3.870, 1.0, 0.1, 0.0),
    ]
    return [TowerAeroStation(*d) for d in data]


@dataclass
class AeroDynConfig:
    """Configuration for the AeroDyn primary input file (v4.1.2 format)."""

    # --- General Options ---
    echo: bool = False
    dt_aero: str = "default"
    wake_mod: int = 1          # 0=none, 1=BEMT, 3=OLAF
    twr_potent: int = 1        # 0=none, 1=baseline potential flow, 2=with Bak correction
    twr_shadow: int = 0        # 0=none, 1=Powles, 2=Eames
    twr_aero: bool = True
    cavit_check: bool = False
    buoyancy: bool = False
    nacelle_drag: bool = False
    comp_aa: bool = False
    aa_input_file: str = "unused"

    # --- Environmental Conditions ---
    air_dens: str = "default"
    kin_visc: str = "default"
    spd_sound: str = "default"
    patm: str = "default"
    pvap: str = "default"

    # --- BEMT Options ---
    bem_mod: int = 1           # 1=legacy NoSweepPitchTwist, 2=polar
    # Skew correction
    skew_mod: int = 1          # 0=No skew, -1=remove non-normal for linearization, 1=active
    skew_mom_corr: bool = False
    skew_redistr_mod: str = "default"  # 0=no redistribution, 1=Glauert/Pitt/Peters
    skew_redistr_factor: str = "default"
    # BEM algorithm
    tip_loss: bool = True
    hub_loss: bool = True
    tan_ind: bool = True
    ai_drag: bool = False
    ti_drag: bool = False
    ind_toler: str = "Default"
    max_iter: int = 100
    # Shear correction
    sect_avg: bool = False
    sect_avg_weighting: int = 1
    sect_avg_n_points: str = "default"
    sect_avg_psi_bwd: str = "default"
    sect_avg_psi_fwd: str = "default"
    # Dynamic wake/inflow
    dbemt_mod: int = 0         # 0=No Dynamic Wake, -1=Frozen, 1=const tau1, 2=time-dep, 3=const+continuous
    tau1_const: float = 4.0

    # --- OLAF Options ---
    olaf_input_file: str = "unused"

    # --- Unsteady Aero Options ---
    aoa34: bool = True
    ua_mod: int = 3            # 0=Quasi-steady, 2=B-L Gonzalez, 3=B-L Minnema/Pierce, 4=B-L HGM, 5=HGM+vortex, 6=Oye, 7=Boeing-Vertol
    f_lookup: bool = True
    integration_method: int = 3  # 1=RK4, 2=AB4, 3=ABM4, 4=BDF2
    ua_start_rad: float = 0.0
    ua_end_rad: float = 1.0

    # --- Airfoil Information ---
    af_tab_mod: int = 1
    in_col_alfa: int = 1
    in_col_cl: int = 2
    in_col_cd: int = 3
    in_col_cm: int = 4
    in_col_cpmin: int = 0
    num_af_files: int = 8
    af_names: list[str] = field(default_factory=lambda: [
        "Airfoils/Cylinder1.dat",
        "Airfoils/Cylinder2.dat",
        "Airfoils/DU40_A17.dat",
        "Airfoils/DU35_A17.dat",
        "Airfoils/DU30_A17.dat",
        "Airfoils/DU25_A17.dat",
        "Airfoils/DU21_A17.dat",
        "Airfoils/NACA64_A17.dat",
    ])

    # --- Blade Properties ---
    use_bl_cm: bool = True
    num_bl: int = 3
    ad_bl_file: str = "AeroDyn_blade.dat"

    # --- Hub Properties (Buoyancy) ---
    vol_hub: float = 0.0
    hub_cen_bx: float = 0.0

    # --- Nacelle Properties (Buoyancy/NacelleDrag) ---
    vol_nac: float = 0.0
    nac_cen_b: tuple[float, float, float] = (0.0, 0.0, 0.0)
    nac_area: tuple[float, float, float] = (0.0, 0.0, 0.0)
    nac_cd: tuple[float, float, float] = (0.0, 0.0, 0.0)
    nac_drag_ac: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # --- Tail Fin ---
    t_fin_aero: bool = False
    t_fin_file: str = "unused"

    # --- Tower Influence ---
    num_twr_nds: int = 11
    tower_stations: list[TowerAeroStation] = field(default_factory=_nrel5mw_tower_aero_stations)

    # --- Outputs ---
    sum_print: bool = True
    n_bl_outs: int = 0
    bl_out_nd: list[int] = field(default_factory=lambda: [1, 9, 19])
    n_tw_outs: int = 0
    tw_out_nd: list[int] = field(default_factory=lambda: [1, 2, 6])
    out_list: list[str] = field(default_factory=list)

    # --- Node Outputs ---
    bld_nd_blades_out: int = 1
    bld_nd_bl_out_nd: str = "ALL"
    out_list_nodal: list[str] = field(default_factory=list)


class AeroDynGenerator:
    """Generates AeroDyn primary and blade definition input files (v4.1.2)."""

    def generate_main_file(self, config: AeroDynConfig) -> str:
        """Generate the AeroDyn primary input file in v4.1.2 format.

        Parameters
        ----------
        config : AeroDynConfig
            Complete AeroDyn configuration parameters.

        Returns
        -------
        str
            Complete AeroDyn primary input file content.
        """
        lines: list[str] = []
        _a = lines.append
        _f = _flag

        _a("------- AERODYN INPUT FILE --------------------------------------------------------------------------")
        _a("Generated by WindForge - AeroDyn primary input file")

        # ====== General Options ======
        _a("======  General Options  ============================================================================")
        _a(f"{_f(config.echo):<22s}Echo        - Echo the input to \"<rootname>.AD.ech\"? (flag)")
        _a(f'{"\"" + config.dt_aero + "\"":<22s}DTAero      - Time interval for aerodynamic calculations {{or \"default\"}} (s)')
        _a(f"{config.wake_mod:<22d}Wake_Mod    - Wake/induction model (switch) {{0=none, 1=BEMT, 3=OLAF}} [Wake_Mod cannot be 2 or 3 when linearizing]")
        _a(f"{config.twr_potent:<22d}TwrPotent   - Type tower influence on wind based on potential flow around the tower (switch) {{0=none, 1=baseline potential flow, 2=potential flow with Bak correction}}")
        _a(f"{config.twr_shadow:<22d}TwrShadow   - Calculate tower influence on wind based on downstream tower shadow (switch) {{0=none, 1=Powles model, 2=Eames model}}")
        _a(f"{_f(config.twr_aero):<22s}TwrAero     - Calculate tower aerodynamic loads? (flag)")
        _a(f"{_f(config.cavit_check):<22s}CavitCheck  - Perform cavitation check? (flag) [UA_Mod must be 0 when CavitCheck=true]")
        _a(f"{_f(config.buoyancy):<22s}Buoyancy    - Include buoyancy effects? (flag)")
        _a(f"{_f(config.nacelle_drag):<22s}NacelleDrag - Include Nacelle Drag effects? (flag)")
        _a(f"{_f(config.comp_aa):<22s}CompAA      - Flag to compute AeroAcoustics calculation [used only when Wake_Mod = 1 or 2]")
        _a(f'{"\"" + config.aa_input_file + "\"":<22s}AA_InputFile - AeroAcoustics input file [used only when CompAA=true]')

        # ====== Environmental Conditions ======
        _a("======  Environmental Conditions  ===================================================================")
        _a(f'{"\"" + config.air_dens + "\"":<22s}AirDens     - Air density (kg/m^3)')
        _a(f'{"\"" + config.kin_visc + "\"":<22s}KinVisc     - Kinematic viscosity of working fluid (m^2/s)')
        _a(f'{"\"" + config.spd_sound + "\"":<22s}SpdSound    - Speed of sound in working fluid (m/s)')
        _a(f'{"\"" + config.patm + "\"":<22s}Patm        - Atmospheric pressure (Pa) [used only when CavitCheck=True]')
        _a(f'{"\"" + config.pvap + "\"":<22s}Pvap        - Vapour pressure of working fluid (Pa) [used only when CavitCheck=True]')

        # ====== BEMT Options ======
        _a("======  Blade-Element/Momentum Theory Options  ====================================================== [unused when Wake_Mod=0 or 3, except for BEM_Mod]")
        _a(f"{config.bem_mod:<22d}BEM_Mod     - BEM model {{1=legacy NoSweepPitchTwist, 2=polar}} (switch) [used for all Wake_Mod to determine output coordinate system]")
        # --- Skew correction
        _a("--- Skew correction")
        _a(f"{config.skew_mod:<22d}Skew_Mod    - Skew model {{0=No skew model, -1=Remove non-normal component for linearization, 1=skew model active}}")
        _a(f"{_f(config.skew_mom_corr):<22s}SkewMomCorr - Turn the skew momentum correction on or off [used only when Skew_Mod=1]")
        _a(f"{config.skew_redistr_mod:<22s}SkewRedistr_Mod - Type of skewed-wake correction model (switch) {{0=no redistribution, 1=Glauert/Pitt/Peters, default=1}} [used only when Skew_Mod=1]")
        _a(f'{"\"" + config.skew_redistr_factor + "\"":<22s}SkewRedistrFactor - Constant used in Pitt/Peters skewed wake model {{or \"default\" is 15/32*pi}} (-) [used only when Skew_Mod=1 and SkewRedistr_Mod=1]')
        # --- BEM algorithm
        _a("--- BEM algorithm ")
        _a(f"{_f(config.tip_loss):<22s}TipLoss     - Use the Prandtl tip-loss model? (flag) [unused when Wake_Mod=0 or 3]")
        _a(f"{_f(config.hub_loss):<22s}HubLoss     - Use the Prandtl hub-loss model? (flag) [unused when Wake_Mod=0 or 3]")
        _a(f"{_f(config.tan_ind):<22s}TanInd      - Include tangential induction in BEMT calculations? (flag) [unused when Wake_Mod=0 or 3]")
        _a(f"{_f(config.ai_drag):<22s}AIDrag      - Include the drag term in the axial-induction calculation? (flag) [unused when Wake_Mod=0 or 3]")
        _a(f"{_f(config.ti_drag):<22s}TIDrag      - Include the drag term in the tangential-induction calculation? (flag) [unused when Wake_Mod=0,3 or TanInd=FALSE]")
        _a(f'{"\"" + config.ind_toler + "\"":<22s}IndToler    - Convergence tolerance for BEMT nonlinear solve residual equation {{or \"default\"}} (-) [unused when Wake_Mod=0 or 3]')
        _a(f"{config.max_iter:<22d}MaxIter     - Maximum number of iteration steps (-) [unused when Wake_Mod=0]")
        # --- Shear correction
        _a("--- Shear correction")
        _a(f"{_f(config.sect_avg):<22s}SectAvg     - Use sector averaging (flag)")
        _a(f"{config.sect_avg_weighting:<22d}SectAvgWeighting - Weighting function for sector average {{1=Uniform, default=1}} within a sector centered on the blade (switch) [used only when SectAvg=True]")
        _a(f"{config.sect_avg_n_points:<22s}SectAvgNPoints - Number of points per sectors (-) {{default=5}} [used only when SectAvg=True]")
        _a(f"{config.sect_avg_psi_bwd:<22s}SectAvgPsiBwd - Backward azimuth relative to blade where the sector starts (<=0) {{default=-60}} (deg) [used only when SectAvg=True]")
        _a(f"{config.sect_avg_psi_fwd:<22s}SectAvgPsiFwd - Forward azimuth relative to blade where the sector ends (>=0) {{default=60}} (deg) [used only when SectAvg=True]")
        # --- Dynamic wake/inflow
        _a("--- Dynamic wake/inflow")
        _a(f"{config.dbemt_mod:<22d}DBEMT_Mod   - Type of dynamic BEMT (DBEMT) model {{0=No Dynamic Wake, -1=Frozen Wake for linearization, 1:constant tau1, 2=time-dependent tau1, 3=constant tau1 with continuous formulation}} (-)")
        _a(f"{config.tau1_const:<22d}tau1_const  - Time constant for DBEMT (s) [used only when DBEMT_Mod=1 or 3]" if isinstance(config.tau1_const, int) else f"{config.tau1_const:<22.0f}tau1_const  - Time constant for DBEMT (s) [used only when DBEMT_Mod=1 or 3]")

        # ====== OLAF ======
        _a("======  OLAF -- cOnvecting LAgrangian Filaments (Free Vortex Wake) Theory Options  ================== [used only when Wake_Mod=3]")
        _a(f'{"\"" + config.olaf_input_file + "\"":<22s}OLAFInputFileName - Input file for OLAF [used only when Wake_Mod=3]')

        # ====== Unsteady Aero Options ======
        _a("======  Unsteady Airfoil Aerodynamics Options  ====================================================")
        _a(f"{_f(config.aoa34):<22s}AoA34       - Sample the angle of attack (AoA) at the 3/4 chord or the AC point {{default=True}} [always used]")
        _a(f"{config.ua_mod:<22d}UA_Mod      - Unsteady Aero Model Switch (switch) {{0=Quasi-steady (no UA), 2=B-L Gonzalez, 3=B-L Minnema/Pierce, 4=B-L HGM 4-states, 5=B-L HGM+vortex 5 states, 6=Oye, 7=Boeing-Vertol}}")
        _a(f"{_f(config.f_lookup):<22s}FLookup     - Flag to indicate whether a lookup for f' will be calculated (TRUE) or whether best-fit exponential equations will be used (FALSE); if FALSE S1-S4 must be provided in airfoil input files (flag) [used only when UA_Mod>0]")
        _a(f"{config.integration_method:<15d}  IntegrationMethod  - Switch to indicate which integration method UA uses (1=RK4, 2=AB4, 3=ABM4, 4=BDF2)")
        _a(f"{config.ua_start_rad:<22.1f}UAStartRad  - Starting radius for dynamic stall (fraction of rotor radius [0.0,1.0]) [used only when UA_Mod>0; if line is missing UAStartRad=0]")
        _a(f"{config.ua_end_rad:<22.1f}UAEndRad    - Ending radius for dynamic stall (fraction of rotor radius [0.0,1.0]) [used only when UA_Mod>0; if line is missing UAEndRad=1]")

        # ====== Airfoil Information ======
        _a("======  Airfoil Information =========================================================================")
        _a(f"{config.af_tab_mod:<22d}AFTabMod    - Interpolation method for multiple airfoil tables {{1=1D interpolation on AoA (first table only); 2=2D interpolation on AoA and Re; 3=2D interpolation on AoA and UserProp}} (-)")
        _a(f"{config.in_col_alfa:<22d}InCol_Alfa  - The column in the airfoil tables that contains the angle of attack (-)")
        _a(f"{config.in_col_cl:<22d}InCol_Cl    - The column in the airfoil tables that contains the lift coefficient (-)")
        _a(f"{config.in_col_cd:<22d}InCol_Cd    - The column in the airfoil tables that contains the drag coefficient (-)")
        _a(f"{config.in_col_cm:<22d}InCol_Cm    - The column in the airfoil tables that contains the pitching-moment coefficient; use zero if there is no Cm column (-)")
        _a(f"{config.in_col_cpmin:<22d}InCol_Cpmin - The column in the airfoil tables that contains the Cpmin coefficient; use zero if there is no Cpmin column (-)")
        _a(f"{config.num_af_files:<22d}NumAFfiles  - Number of airfoil files used (-)")
        for i, af_name in enumerate(config.af_names):
            if i == 0:
                _a(f'"{af_name}"    AFNames - Airfoil file names (NumAFfiles lines) (quoted strings)')
            else:
                _a(f'"{af_name}"')

        # ====== Rotor/Blade Properties ======
        _a("======  Rotor/Blade Properties  =====================================================================")
        _a(f"{_f(config.use_bl_cm):<22s}UseBlCm     - Include aerodynamic pitching moment in calculations? (flag)")
        for i in range(config.num_bl):
            _a(f'{"\"" + config.ad_bl_file + "\"":<40s}   ADBlFile({i+1}) - Name of file containing distributed aerodynamic properties for Blade #{i+1} (-)')

        # ====== Hub Properties ======
        _a("======  Hub Properties ============================================================================== [used only when Buoyancy=True]")
        _a(f"{config.vol_hub:<22.0f}VolHub      - Hub volume (m^3)")
        _a(f"{config.hub_cen_bx:<22.0f}HubCenBx    - Hub center of buoyancy x direction offset (m)")

        # ====== Nacelle Properties ======
        _a("======  Nacelle Properties ========================================================================== [used only when Buoyancy=True or NacelleDrag=True]")
        _a(f"{config.vol_nac:<22.0f}VolNac      - Nacelle volume (m^3)")
        nac_b_str = ", ".join(f"{v:.1f}" for v in config.nac_cen_b)
        _a(f"{nac_b_str:<22s}NacCenB            - Position of nacelle center of buoyancy from yaw bearing in nacelle coordinates (m)")
        nac_area_str = ", ".join(f"{v:.0f}" for v in config.nac_area)
        _a(f"{nac_area_str:<22s}NacArea        - Projected area of the nacelle in X, Y, Z in the nacelle coordinate system (m^2)")
        nac_cd_str = ", ".join(f"{v:.0f}" for v in config.nac_cd)
        _a(f"{nac_cd_str:<22s}NacCd          - Drag coefficient for the nacelle areas defined above (-)")
        nac_drag_str = ", ".join(f"{v:.0f}" for v in config.nac_drag_ac)
        _a(f"{nac_drag_str:<22s}NacDragAC          - Position of aerodynamic center of nacelle drag in nacelle coordinates (m)")

        # ====== Tail Fin ======
        _a("======  Tail Fin Aerodynamics =======================================================================")
        _a(f"{_f(config.t_fin_aero):<22s}TFinAero    - Calculate tail fin aerodynamics model (flag)")
        _a(f'{"\"" + config.t_fin_file + "\"":<22s}TFinFile    - Input file for tail fin aerodynamics [used only when TFinAero=True]')

        # ====== Tower Influence ======
        _a("======  Tower Influence and Aerodynamics ============================================================ [used only when TwrPotent/=0, TwrShadow/=0, TwrAero=True, or Buoyancy=True]")
        _a(f"{config.num_twr_nds:<22d}NumTwrNds   - Number of tower nodes used in the analysis (-) [used only when TwrPotent/=0, TwrShadow/=0, TwrAero=True, or Buoyancy=True]")
        if config.num_twr_nds > 0:
            _a("TwrElev        TwrDiam        TwrCd          TwrTI          TwrCb         ! TwrTI used only when TwrShadow=2; TwrCb used only when Buoyancy=True")
            _a("(m)            (m)            (-)            (-)            (-)           ")
            for ts in config.tower_stations:
                _a(f"{ts.twr_elev:14.7E}  {ts.twr_diam:14.7E}  {ts.twr_cd:14.7E}  {ts.twr_ti:14.7E}  {ts.twr_cb:14.7E}")

        # ====== Outputs ======
        _a("======  Outputs  ====================================================================================")
        _a(f"{_f(config.sum_print):<22s}SumPrint    - Generate a summary file listing input options and interpolated properties to \"<rootname>.AD.sum\"? (flag)")
        _a(f"{config.n_bl_outs:<22d}NBlOuts     - Number of blade node outputs [0 - 9] (-)")
        bl_out_str = ", ".join(str(n) for n in config.bl_out_nd) if config.bl_out_nd else "1, 9, 19"
        _a(f"{bl_out_str:<22s}BlOutNd     - Blade nodes whose values will be output (-)")
        _a(f"{config.n_tw_outs:<22d}NTwOuts     - Number of tower node outputs [0 - 9] (-)")
        tw_out_str = ", ".join(str(n) for n in config.tw_out_nd) if config.tw_out_nd else "1, 2, 6"
        _a(f"{tw_out_str:<22s}TwOutNd     - Tower nodes whose values will be output (-)")
        _a("                       OutList     - The next line(s) contains a list of output parameters.  See OutListParameters.xlsx for a listing of available output channels, (-)")
        for out in config.out_list:
            _a(out)
        _a("")
        _a("END of OutList section (the word \"END\" must appear in the first 3 columns of the last OutList line)")

        # ====== Node Outputs ======
        _a("---------------------- NODE OUTPUTS --------------------------------------------")
        _a(f"{config.bld_nd_blades_out:<22d}BldNd_BladesOut  - Number of blades to output all node information at.  Up to number of blades on turbine. (-)")
        _a(f"{config.bld_nd_bl_out_nd:<22s}BldNd_BlOutNd   - Specify a portion of the nodes to output. {{\"ALL\", \"Tip\", \"Root\", or a list of node numbers}} (-)")
        _a("                       OutList_Nodal - The next line(s) contains a list of output parameters.  See OutListParameters.xlsx for a listing of available output channels, (-)")
        for out in config.out_list_nodal:
            _a(out)
        _a("")
        _a("END (the word \"END\" must appear in the first 3 columns of this last OutList line in the optional nodal output section)")
        _a("====================================================================================================")

        return "\n".join(lines) + "\n"

    def generate_blade_file(self, config: AeroDynBladeConfig) -> str:
        """Generate the AeroDyn blade definition input file.

        Parameters
        ----------
        config : AeroDynBladeConfig
            Blade aerodynamic station data.

        Returns
        -------
        str
            Complete AeroDyn blade definition file content.
        """
        lines: list[str] = []
        _a = lines.append

        _a("------- AERODYN BLADE DEFINITION INPUT FILE -------------------------------------")
        _a("Generated by WindForge - AeroDyn blade definition file")

        _a("======  Blade Properties =================================================================")
        _a(f"   {config.num_bl_nds:<15d}   NumBlNds           - Number of blade nodes used in the analysis (-)")
        _a("    BlSpn        BlCrvAC        BlSwpAC      BlCrvAng       BlTwist       BlChord       BlAFID     BlCb     BlCenBn   BlCenBt")
        _a("     (m)           (m)            (m)          (deg)         (deg)          (m)           (-)       (-)       (m)        (m)")
        for s in config.stations:
            _a(
                f" {s.bl_spn:11.4f}"
                f"  {s.bl_crv_ac:14.7E}"
                f"  {s.bl_swp_ac:14.7E}"
                f"  {s.bl_crv_ang:10.4f}"
                f"  {s.bl_twist:10.3f}"
                f"  {s.bl_chord:12.5f}"
                f"  {s.bl_af_id:5d}"
                f"  {s.bl_cb:8.3f}"
                f"  {s.bl_cen_bn:8.4f}"
                f"  {s.bl_cen_bt:8.4f}"
            )

        return "\n".join(lines) + "\n"


def _flag(value: bool) -> str:
    """Convert a boolean to OpenFAST flag format."""
    return "True" if value else "False"
