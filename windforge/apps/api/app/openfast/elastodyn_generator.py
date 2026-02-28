"""
ElastoDyn input file generator for OpenFAST.

Generates three files:
  1. ElastoDyn primary input (.dat)
  2. ElastoDyn blade input (.dat)
  3. ElastoDyn tower input (.dat)

The primary file covers simulation control, DOFs, initial conditions,
turbine configuration, mass & inertia, drivetrain, and output lists.
Blade and tower files contain structural property tables and mode shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes for blade / tower structural station tables
# ---------------------------------------------------------------------------

@dataclass
class BladeStation:
    """A single ElastoDyn blade station entry."""
    bl_fract: float       # Blade fractional radius (0..1)
    pitch_ax: float       # Pitch axis location (fraction of chord)
    strc_twist: float     # Structural twist (deg)
    b_mass_den: float     # Blade mass density (kg/m)
    flp_stff: float       # Flapwise stiffness EI_flap (N-m^2)
    edg_stff: float       # Edgewise stiffness EI_edge (N-m^2)


@dataclass
class TowerStation:
    """A single ElastoDyn tower station entry."""
    ht_fract: float       # Fractional height along tower (0..1)
    t_mass_den: float     # Tower mass density (kg/m)
    tw_fa_stif: float     # Tower fore-aft stiffness EI (N-m^2)
    tw_ss_stif: float     # Tower side-side stiffness EI (N-m^2)


# ---------------------------------------------------------------------------
# Configuration data classes
# ---------------------------------------------------------------------------

def _nrel5mw_blade_stations() -> list[BladeStation]:
    """Return the NREL 5MW reference blade structural stations (49 stations)."""
    # Data from r-test/v4.1.2: NRELOffshrBsline5MW_Blade.dat
    data = [
        (0.0000000, 0.25000, 13.308, 678.935, 1.8110e10, 1.8114e10),
        (0.0032500, 0.25000, 13.308, 678.935, 1.8110e10, 1.8114e10),
        (0.0195100, 0.25049, 13.308, 773.363, 1.9425e10, 1.9559e10),
        (0.0357700, 0.25490, 13.308, 740.550, 1.7456e10, 1.9498e10),
        (0.0520300, 0.26716, 13.308, 740.042, 1.5287e10, 1.9789e10),
        (0.0682900, 0.27941, 13.308, 592.496, 1.0782e10, 1.4859e10),
        (0.0845500, 0.29167, 13.308, 450.275, 7.2297e9,  1.0221e10),
        (0.1008100, 0.30392, 13.308, 424.054, 6.3095e9,  9.1447e9),
        (0.1170700, 0.31618, 13.308, 400.638, 5.5284e9,  8.0632e9),
        (0.1333500, 0.32844, 13.308, 382.062, 4.9801e9,  6.8844e9),
        (0.1495900, 0.34069, 13.308, 399.655, 4.9368e9,  7.0092e9),
        (0.1658500, 0.35294, 13.308, 426.321, 4.6917e9,  7.1677e9),
        (0.1821100, 0.36519, 13.181, 416.820, 3.9495e9,  7.2717e9),
        (0.1983700, 0.37500, 12.848, 406.186, 3.3865e9,  7.0817e9),
        (0.2146500, 0.37500, 12.192, 381.420, 2.9337e9,  6.2445e9),
        (0.2308900, 0.37500, 11.561, 352.822, 2.5690e9,  5.0490e9),
        (0.2471500, 0.37500, 11.072, 349.477, 2.3887e9,  4.9485e9),
        (0.2634100, 0.37500, 10.792, 346.538, 2.2720e9,  4.8080e9),
        (0.2959500, 0.37500, 10.232, 339.333, 2.0501e9,  4.5014e9),
        (0.3284600, 0.37500,  9.672, 330.004, 1.8283e9,  4.2441e9),
        (0.3609800, 0.37500,  9.110, 321.990, 1.5887e9,  3.9953e9),
        (0.3935000, 0.37500,  8.534, 313.820, 1.3619e9,  3.7508e9),
        (0.4260200, 0.37500,  7.932, 294.734, 1.1024e9,  3.4471e9),
        (0.4585500, 0.37500,  7.321, 287.120, 8.7580e8,  3.1391e9),
        (0.4910600, 0.37500,  6.711, 263.343, 6.8130e8,  2.7342e9),
        (0.5235800, 0.37500,  6.122, 253.207, 5.3472e8,  2.5549e9),
        (0.5561000, 0.37500,  5.546, 241.666, 4.0890e8,  2.3340e9),
        (0.5886200, 0.37500,  4.971, 220.638, 3.1454e8,  1.8287e9),
        (0.6211500, 0.37500,  4.401, 200.293, 2.3863e8,  1.5841e9),
        (0.6536600, 0.37500,  3.834, 179.404, 1.7588e8,  1.3234e9),
        (0.6861800, 0.37500,  3.332, 165.094, 1.2601e8,  1.1837e9),
        (0.7187000, 0.37500,  2.890, 154.411, 1.0726e8,  1.0202e9),
        (0.7512200, 0.37500,  2.503, 138.935, 9.0880e7,  7.9781e8),
        (0.7837600, 0.37500,  2.116, 129.555, 7.6310e7,  7.0961e8),
        (0.8162600, 0.37500,  1.730, 107.264, 6.1050e7,  5.1819e8),
        (0.8487800, 0.37500,  1.342,  98.776, 4.9480e7,  4.5487e8),
        (0.8813000, 0.37500,  0.954,  90.248, 3.9360e7,  3.9512e8),
        (0.8975600, 0.37500,  0.760,  83.001, 3.4670e7,  3.5372e8),
        (0.9138200, 0.37500,  0.574,  72.906, 3.0410e7,  3.0473e8),
        (0.9300800, 0.37500,  0.404,  68.772, 2.6520e7,  2.8142e8),
        (0.9382100, 0.37500,  0.319,  66.264, 2.3840e7,  2.6171e8),
        (0.9463600, 0.37500,  0.253,  59.340, 1.9630e7,  1.5881e8),
        (0.9544700, 0.37500,  0.216,  55.914, 1.6000e7,  1.3788e8),
        (0.9626000, 0.37500,  0.178,  52.484, 1.2830e7,  1.1879e8),
        (0.9707300, 0.37500,  0.140,  49.114, 1.0080e7,  1.0163e8),
        (0.9788600, 0.37500,  0.101,  45.818, 7.5500e6,  8.5070e7),
        (0.9869900, 0.37500,  0.062,  41.669, 4.6000e6,  6.4260e7),
        (0.9951200, 0.37500,  0.023,  11.453, 2.5000e5,  6.6100e6),
        (1.0000000, 0.37500,  0.000,  10.319, 1.7000e5,  5.0100e6),
    ]
    return [BladeStation(d[0], d[1], d[2], d[3], d[4], d[5]) for d in data]


def _nrel5mw_tower_stations() -> list[TowerStation]:
    """Return the NREL 5MW reference tower structural stations (11 stations)."""
    # Data from r-test/v4.1.2: NRELOffshrBsline5MW_Onshore_ElastoDyn_Tower.dat
    data = [
        (0.0, 5590.87, 6.14343e11, 6.14343e11),
        (0.1, 5232.43, 5.34821e11, 5.34821e11),
        (0.2, 4885.76, 4.63267e11, 4.63267e11),
        (0.3, 4550.87, 3.99131e11, 3.99131e11),
        (0.4, 4227.75, 3.41883e11, 3.41883e11),
        (0.5, 3916.41, 2.91011e11, 2.91011e11),
        (0.6, 3616.83, 2.46027e11, 2.46027e11),
        (0.7, 3329.03, 2.06457e11, 2.06457e11),
        (0.8, 3053.01, 1.71851e11, 1.71851e11),
        (0.9, 2788.75, 1.41776e11, 1.41776e11),
        (1.0, 2536.27, 1.15820e11, 1.15820e11),
    ]
    return [TowerStation(d[0], d[1], d[2], d[3]) for d in data]


@dataclass
class ElastoDynBladeConfig:
    """Blade structural configuration for ElastoDyn blade file."""
    n_bl_inp_st: int = 49
    bld_flex_l: float = 61.5       # Blade flexible length (m) — carried for main ElastoDyn
    bld_fl_dmp_1: float = 0.477465  # Blade flap mode #1 damping (%)
    bld_fl_dmp_2: float = 0.477465  # Blade flap mode #2 damping (%)
    bld_ed_dmp_1: float = 0.477465  # Blade edge mode #1 damping (%)

    # Blade station table (BlFract, PitchAx, StrcTwst, BMassDen, FlpStff, EdgStff)
    stations: list[BladeStation] = field(default_factory=_nrel5mw_blade_stations)

    # Blade mode shape polynomial coefficients (5 terms: x^2..x^6)
    flp_mode_1: list[float] = field(
        default_factory=lambda: [0.0622, 1.7254, -3.2452, 4.7131, -2.2555]
    )
    flp_mode_2: list[float] = field(
        default_factory=lambda: [-0.5809, 1.2067, -15.5349, 29.7347, -13.8255]
    )
    edg_mode_1: list[float] = field(
        default_factory=lambda: [0.3627, 2.5337, -3.5772, 2.3760, -0.6952]
    )


@dataclass
class ElastoDynTowerConfig:
    """Tower structural configuration for ElastoDyn tower file."""
    n_tw_inp_st: int = 11
    twr_fa_dmp1: float = 1.0    # Tower 1st FA mode structural damping (%)
    twr_ss_dmp1: float = 1.0    # Tower 1st SS mode structural damping (%)
    twr_fa_dmp2: float = 1.0    # Tower 2nd FA mode structural damping (%)
    twr_ss_dmp2: float = 1.0    # Tower 2nd SS mode structural damping (%)

    # Tower station table (HtFract, TMassDen, TwFAStif, TwSSStif)
    stations: list[TowerStation] = field(default_factory=_nrel5mw_tower_stations)

    # Tower mode shape polynomial coefficients (5 terms: x^2..x^6)
    fa_mode_1: list[float] = field(
        default_factory=lambda: [0.7004, 2.1963, -5.6202, 6.2275, -2.5040]
    )
    fa_mode_2: list[float] = field(
        default_factory=lambda: [-70.5319, -63.7623, 289.737, -176.513, 22.0706]
    )
    ss_mode_1: list[float] = field(
        default_factory=lambda: [1.385, -1.7684, 3.0871, -2.2395, 0.5357]
    )
    ss_mode_2: list[float] = field(
        default_factory=lambda: [-121.21, 184.415, -224.904, 298.536, -135.838]
    )


@dataclass
class ElastoDynConfig:
    """Full ElastoDyn primary file configuration.

    Field order matches OpenFAST v4.1.2 parse order (FAST_ReadPrimaryFile
    in FAST_Subs.f90 and ED_ReadInput in ElastoDyn_IO.f90).
    """

    # --- Simulation Control ---
    echo: bool = False
    method: int = 3       # Integration method: 1=RK4, 2=AB4, 3=ABM4
    dt: str = "default"   # Integration time step (s) or "default"

    # --- Degrees of Freedom ---
    flap_dof1: bool = True
    flap_dof2: bool = True
    edge_dof: bool = True
    teet_dof: bool = False    # Rotor-teeter DOF (unused for 3 blades)
    drtr_dof: bool = True
    gen_dof: bool = True
    yaw_dof: bool = False
    tw_fa_dof1: bool = True
    tw_fa_dof2: bool = True
    tw_ss_dof1: bool = True
    tw_ss_dof2: bool = True
    ptfm_sg_dof: bool = False
    ptfm_sw_dof: bool = False
    ptfm_hv_dof: bool = False
    ptfm_r_dof: bool = False
    ptfm_p_dof: bool = False
    ptfm_y_dof: bool = False

    # --- Initial Conditions ---
    oopo_a: float = 0.0      # Out of plane blade 1 deflection (m)
    ipo_a: float = 0.0       # In plane blade 1 deflection (m)
    bl_pitch1: float = 0.0   # Blade 1 initial pitch (deg)
    bl_pitch2: float = 0.0   # Blade 2 initial pitch (deg)
    bl_pitch3: float = 0.0   # Blade 3 initial pitch (deg)
    teeter: float = 0.0      # Initial teeter angle (deg)
    azimuth: float = 0.0     # Initial azimuth (deg)
    rot_speed: float = 12.1  # Initial rotor speed (rpm)
    nac_yaw: float = 0.0     # Initial nacelle yaw (deg)
    ttdspfa: float = 0.0     # Initial fore-aft tower-top displacement (m)
    ttdspss: float = 0.0     # Initial side-side tower-top displacement (m)
    ptfm_surge: float = 0.0
    ptfm_sway: float = 0.0
    ptfm_heave: float = 0.0
    ptfm_roll: float = 0.0
    ptfm_pitch: float = 0.0
    ptfm_yaw: float = 0.0

    # --- Turbine Configuration ---
    num_bl: int = 3
    tip_rad: float = 63.0    # Tip radius (m)
    hub_rad: float = 1.5     # Hub radius (m)
    pre_cone_1: float = -2.5  # Blade 1 cone angle (deg)
    pre_cone_2: float = -2.5  # Blade 2 cone angle (deg)
    pre_cone_3: float = -2.5  # Blade 3 cone angle (deg)
    hub_cm: float = 0.0       # Hub CM location (m)
    undslng: float = 0.0      # Undersling (m)
    delta_3: float = 0.0      # Delta-3 angle for teetering (deg)
    azim_b1_up: float = 0.0   # Azimuth when blade 1 is Up (deg)
    overhang: float = -5.0191 # Rotor overhang (m) (negative downwind)
    shft_gag_l: float = 1.912 # Distance from hub to shaft strain gages (m)
    shft_tilt: float = -5.0   # Rotor shaft tilt angle (deg)
    nacelle_cm_xn: float = 1.9   # Nacelle CM fore-aft location (m)
    nacelle_cm_yn: float = 0.0   # Nacelle CM lateral location (m)
    nacelle_cm_zn: float = 1.75  # Nacelle CM vertical location (m)
    nc_imu_xn: float = -3.09528  # Nacelle IMU downwind location (m)
    nc_imu_yn: float = 0.0       # Nacelle IMU lateral location (m)
    nc_imu_zn: float = 2.23336   # Nacelle IMU vertical location (m)
    twr2shft: float = 1.96256  # Vertical distance from tower-top to rotor shaft (m)
    tower_ht: float = 87.6     # Tower height from ground/MSL (m)
    tower_bsht: float = 0.0    # Tower base height above ground/MSL (m) (v4.x default=0)
    ptfm_cm_xt: float = 0.0
    ptfm_cm_yt: float = 0.0
    ptfm_cm_zt: float = 0.0
    ptfm_ref_zt: float = 0.0

    # --- Mass and Inertia ---
    tip_mass_1: float = 0.0   # Tip brake mass 1 (kg)
    tip_mass_2: float = 0.0
    tip_mass_3: float = 0.0
    hub_mass: float = 56780.0  # Hub mass (kg)
    hub_iner: float = 115926.0 # Hub inertia about rotor axis (kg-m^2)
    gen_iner: float = 534.116  # Generator inertia about HSS (kg-m^2)
    nac_mass: float = 240000.0 # Nacelle mass (kg)
    nac_yiner: float = 2607890.0  # Nacelle yaw inertia (kg-m^2)
    yaw_br_mass: float = 0.0  # Yaw bearing mass (kg)
    ptfm_mass: float = 0.0    # Platform mass (kg)
    ptfm_r_iner: float = 0.0  # Platform roll inertia (kg-m^2)
    ptfm_p_iner: float = 0.0  # Platform pitch inertia (kg-m^2)
    ptfm_y_iner: float = 0.0  # Platform yaw inertia (kg-m^2)
    ptfm_xy_iner: float = 0.0 # Platform xy moment of inertia (kg-m^2) (v4.x)
    ptfm_yz_iner: float = 0.0 # Platform yz moment of inertia (kg-m^2) (v4.x)
    ptfm_xz_iner: float = 0.0 # Platform xz moment of inertia (kg-m^2) (v4.x)

    # --- Blade ---
    bld_nodes: int = 17       # Number of blade nodes per blade for analysis
    blade_file: str = "NRELOffs662hrBl_ElastoDyn_Blade.dat"

    # --- Yaw-Friction (v4.x) ---
    yaw_frct_mod: int = 0     # 0=none, 1=simple, 2=Coulomb, 3=user
    m_cs_max: float = 300.0   # Max static Coulomb friction torque (N-m)
    m_fcs_max: float = 0.0
    m_mcs_max: float = 0.0
    m_cd: float = 40.0        # Dynamic Coulomb friction moment (N-m)
    m_fcd: float = 0.0
    m_mcd: float = 0.0
    sig_v: float = 0.0        # Linear viscous friction coefficient
    sig_v2: float = 0.0       # Quadratic viscous friction coefficient
    omg_cut: float = 0.0      # Yaw angular velocity cutoff (rad/s)

    # --- Drivetrain ---
    gb_ratio: float = 97.0    # Gearbox ratio
    gb_eff: float = 100.0     # Gearbox efficiency (%) -- NOT USED when using ServoDyn
    dt_tor_spr: float = 867637000.0  # Drivetrain torsional spring (N-m/rad)
    dt_tor_dmp: float = 6215000.0    # Drivetrain torsional damper (N-m/(rad/s))

    # --- Furling ---
    furling: bool = False

    # --- Tower File ---
    tower_file: str = "NRELOffs662hrBl_ElastoDyn_Tower.dat"
    twr_nodes: int = 20       # Number of tower nodes

    # --- Output ---
    sum_print: bool = False
    out_file: int = 1
    tab_delim: bool = True
    out_fmt: str = "ES10.3E2"
    t_start: float = 0.0     # Time to begin tabular output (s)
    dec_fact: int = 1
    n_tw_gages: int = 0
    tw_gage_nds: list[int] = field(default_factory=list)
    n_bl_gages: int = 0
    bl_gage_nds: list[int] = field(default_factory=list)
    out_list: list[str] = field(default_factory=lambda: [
        '"BldPitch1"', '"BldPitch2"', '"BldPitch3"',
        '"Azimuth"', '"RotSpeed"', '"GenSpeed"',
        '"NacYaw"', '"OoPDefl1"', '"IPDefl1"', '"TTDspFA"', '"TTDspSS"',
        '"RootMxc1"', '"RootMyc1"', '"RootMzc1"',
        '"RootMxc2"', '"RootMyc2"', '"RootMzc2"',
        '"RootMxc3"', '"RootMyc3"', '"RootMzc3"',
        '"RotTorq"', '"LSSGagMya"', '"LSSGagMza"',
        '"YawBrFxp"', '"YawBrFyp"', '"YawBrFzp"',
        '"YawBrMxp"', '"YawBrMyp"', '"YawBrMzp"',
        '"TwrBsFxt"', '"TwrBsFyt"', '"TwrBsFzt"',
        '"TwrBsMxt"', '"TwrBsMyt"', '"TwrBsMzt"',
    ])

    # --- ElastoDyn Nodal Outputs (v4.x) ---
    ed_bld_nd_blades_out: int = 1
    ed_bld_nd_bl_out_nd: str = "All"
    out_list_nodal: list[str] = field(default_factory=list)


class ElastoDynGenerator:
    """Generates ElastoDyn primary, blade, and tower input files."""

    def generate_main_file(self, config: ElastoDynConfig) -> str:
        """Generate the ElastoDyn primary input file.

        Format matches OpenFAST v4.1.2 reference (5MW_Land_DLL_WTurb).

        Parameters
        ----------
        config : ElastoDynConfig
            Full ElastoDyn configuration.

        Returns
        -------
        str
            Complete ElastoDyn primary input file content.
        """
        lines: list[str] = []
        _a = lines.append
        _f = _flag

        _a("------- ELASTODYN for OpenFAST INPUT FILE -------------------------------------------")
        _a("Generated by WindForge - ElastoDyn primary input file")

        # --- Simulation Control (v4.x: no ENVIRONMENTAL CONDITION section) ---
        _a("---------------------- SIMULATION CONTROL --------------------------------------")
        _a(f"{_f(config.echo):<14s}   Echo            - Echo input data to <RootName>.ech (flag)")
        _a(f"{config.method:<14d}   Method          - Integration method: {{1: RK4, 2: AB4, or 3: ABM4}} (-)")
        _a(f'{"\"" + config.dt.upper() + "\"":<14s}   DT              - Integration time step (s)')

        # --- Degrees of Freedom (v4.x includes TeetDOF) ---
        _a("---------------------- DEGREES OF FREEDOM --------------------------------------")
        _a(f"{_f(config.flap_dof1):<14s}   FlapDOF1        - First flapwise blade mode DOF (flag)")
        _a(f"{_f(config.flap_dof2):<14s}   FlapDOF2        - Second flapwise blade mode DOF (flag)")
        _a(f"{_f(config.edge_dof):<14s}   EdgeDOF         - First edgewise blade mode DOF (flag)")
        _a(f"{_f(config.teet_dof):<14s}   TeetDOF         - Rotor-teeter DOF (flag) [unused for 3 blades]")
        _a(f"{_f(config.drtr_dof):<14s}   DrTrDOF         - Drivetrain rotational-flexibility DOF (flag)")
        _a(f"{_f(config.gen_dof):<14s}   GenDOF          - Generator DOF (flag)")
        _a(f"{_f(config.yaw_dof):<14s}   YawDOF          - Yaw DOF (flag)")
        _a(f"{_f(config.tw_fa_dof1):<14s}   TwFADOF1        - First fore-aft tower bending-mode DOF (flag)")
        _a(f"{_f(config.tw_fa_dof2):<14s}   TwFADOF2        - Second fore-aft tower bending-mode DOF (flag)")
        _a(f"{_f(config.tw_ss_dof1):<14s}   TwSSDOF1        - First side-to-side tower bending-mode DOF (flag)")
        _a(f"{_f(config.tw_ss_dof2):<14s}   TwSSDOF2        - Second side-to-side tower bending-mode DOF (flag)")
        _a(f"{_f(config.ptfm_sg_dof):<14s}   PtfmSgDOF       - Platform horizontal surge translation DOF (flag)")
        _a(f"{_f(config.ptfm_sw_dof):<14s}   PtfmSwDOF       - Platform horizontal sway translation DOF (flag)")
        _a(f"{_f(config.ptfm_hv_dof):<14s}   PtfmHvDOF       - Platform vertical heave translation DOF (flag)")
        _a(f"{_f(config.ptfm_r_dof):<14s}   PtfmRDOF        - Platform roll tilt rotation DOF (flag)")
        _a(f"{_f(config.ptfm_p_dof):<14s}   PtfmPDOF        - Platform pitch tilt rotation DOF (flag)")
        _a(f"{_f(config.ptfm_y_dof):<14s}   PtfmYDOF        - Platform yaw rotation DOF (flag)")

        # --- Initial Conditions (v4.x uses TeetDefl not Teeter) ---
        _a("---------------------- INITIAL CONDITIONS --------------------------------------")
        _a(f"{config.oopo_a:<14.3f}   OoPDefl         - Initial out-of-plane blade-tip displacement (meters)")
        _a(f"{config.ipo_a:<14.3f}   IPDefl          - Initial in-plane blade-tip deflection (meters)")
        _a(f"{config.bl_pitch1:<14.3f}   BlPitch(1)      - Blade 1 initial pitch (degrees)")
        _a(f"{config.bl_pitch2:<14.3f}   BlPitch(2)      - Blade 2 initial pitch (degrees)")
        _a(f"{config.bl_pitch3:<14.3f}   BlPitch(3)      - Blade 3 initial pitch (degrees) [unused for 2 blades]")
        _a(f"{config.teeter:<14.3f}   TeetDefl        - Initial or fixed teeter angle (degrees) [unused for 3 blades]")
        _a(f"{config.azimuth:<14.3f}   Azimuth         - Initial azimuth angle for blade 1 (degrees)")
        _a(f"{config.rot_speed:<14.4f}   RotSpeed        - Initial or fixed rotor speed (rpm)")
        _a(f"{config.nac_yaw:<14.3f}   NacYaw          - Initial or fixed nacelle-yaw angle (degrees)")
        _a(f"{config.ttdspfa:<14.3f}   TTDspFA         - Initial fore-aft tower-top displacement (meters)")
        _a(f"{config.ttdspss:<14.3f}   TTDspSS         - Initial side-to-side tower-top displacement (meters)")
        _a(f"{config.ptfm_surge:<14.3f}   PtfmSurge       - Initial or fixed horizontal surge translational displacement of platform (meters)")
        _a(f"{config.ptfm_sway:<14.3f}   PtfmSway        - Initial or fixed horizontal sway translational displacement of platform (meters)")
        _a(f"{config.ptfm_heave:<14.3f}   PtfmHeave       - Initial or fixed vertical heave translational displacement of platform (meters)")
        _a(f"{config.ptfm_roll:<14.3f}   PtfmRoll        - Initial or fixed roll tilt rotational displacement of platform (degrees)")
        _a(f"{config.ptfm_pitch:<14.3f}   PtfmPitch       - Initial or fixed pitch tilt rotational displacement of platform (degrees)")
        _a(f"{config.ptfm_yaw:<14.3f}   PtfmYaw         - Initial or fixed yaw rotational displacement of platform (degrees)")

        # --- Turbine Configuration ---
        _a("---------------------- TURBINE CONFIGURATION -----------------------------------")
        _a(f"{config.num_bl:<14d}   NumBl           - Number of blades (-)")
        _a(f"{config.tip_rad:<14.4f}   TipRad          - The distance from the rotor apex to the blade tip (meters)")
        _a(f"{config.hub_rad:<14.4f}   HubRad          - The distance from the rotor apex to the blade root (meters)")
        _a(f"{config.pre_cone_1:<14.4f}   PreCone(1)      - Blade 1 cone angle (degrees)")
        _a(f"{config.pre_cone_2:<14.4f}   PreCone(2)      - Blade 2 cone angle (degrees)")
        _a(f"{config.pre_cone_3:<14.4f}   PreCone(3)      - Blade 3 cone angle (degrees) [unused for 2 blades]")
        _a(f"{config.hub_cm:<14.4f}   HubCM           - Distance from rotor apex to hub mass [positive downwind] (meters)")
        _a(f"{config.undslng:<14.4f}   UndSling        - Undersling length [distance from teeter pin to the rotor apex] (meters) [unused for 3 blades]")
        _a(f"{config.delta_3:<14.4f}   Delta3          - Delta-3 angle for teetering rotors (degrees) [unused for 3 blades]")
        _a(f"{config.azim_b1_up:<14.4f}   AzimB1Up        - Azimuth value to use for I/O when blade 1 points up (degrees)")
        _a(f"{config.overhang:<14.4f}   OverHang        - Distance from yaw axis to rotor apex [3 blades] or teeter pin [2 blades] (meters)")
        _a(f"{config.shft_gag_l:<14.4f}   ShftGagL        - Distance from rotor apex [3 blades] or teeter pin [2 blades] to shaft strain gages [positive for upwind rotors] (meters)")
        _a(f"{config.shft_tilt:<14.4f}   ShftTilt        - Rotor shaft tilt angle (degrees)")
        _a(f"{config.nacelle_cm_xn:<14.4f}   NacCMxn         - Downwind distance from the tower-top to the nacelle CM (meters)")
        _a(f"{config.nacelle_cm_yn:<14.4f}   NacCMyn         - Lateral  distance from the tower-top to the nacelle CM (meters)")
        _a(f"{config.nacelle_cm_zn:<14.4f}   NacCMzn         - Vertical distance from the tower-top to the nacelle CM (meters)")
        _a(f"{config.nc_imu_xn:<14.4f}   NcIMUxn         - Downwind distance from the tower-top to the nacelle IMU (meters)")
        _a(f"{config.nc_imu_yn:<14.4f}   NcIMUyn         - Lateral  distance from the tower-top to the nacelle IMU (meters)")
        _a(f"{config.nc_imu_zn:<14.4f}   NcIMUzn         - Vertical distance from the tower-top to the nacelle IMU (meters)")
        _a(f"{config.twr2shft:<14.5f}   Twr2Shft        - Vertical distance from the tower-top to the rotor shaft (meters)")
        _a(f"{config.tower_ht:<14.4f}   TowerHt         - Height of tower relative to ground level [onshore], MSL [offshore wind or floating MHK], or seabed [fixed MHK] (meters)")
        _a(f"{config.tower_bsht:<14.4f}   TowerBsHt       - Height of tower base relative to ground level [onshore], MSL [offshore wind or floating MHK], or seabed [fixed MHK] (meters)")
        _a(f"{config.ptfm_cm_xt:<14.4f}   PtfmCMxt        - Downwind distance from the ground level to the platform CM (meters)")
        _a(f"{config.ptfm_cm_yt:<14.4f}   PtfmCMyt        - Lateral distance from the ground level to the platform CM (meters)")
        _a(f"{config.ptfm_cm_zt:<14.4f}   PtfmCMzt        - Vertical distance from the ground level to the platform CM (meters)")
        _a(f"{config.ptfm_ref_zt:<14.4f}   PtfmRefzt       - Vertical distance from the ground level to the platform reference point (meters)")

        # --- Mass and Inertia (v4.x adds PtfmXYIner, PtfmYZIner, PtfmXZIner) ---
        _a("---------------------- MASS AND INERTIA ----------------------------------------")
        _a(f"{config.tip_mass_1:<14.1f}   TipMass(1)      - Tip-brake mass, blade 1 (kg)")
        _a(f"{config.tip_mass_2:<14.1f}   TipMass(2)      - Tip-brake mass, blade 2 (kg)")
        _a(f"{config.tip_mass_3:<14.1f}   TipMass(3)      - Tip-brake mass, blade 3 (kg) [unused for 2 blades]")
        _a(f"{config.hub_mass:<14.1f}   HubMass         - Hub mass (kg)")
        _a(f"{config.hub_iner:<14.1f}   HubIner         - Hub inertia about rotor axis [3 blades] or teeter axis [2 blades] (kg m^2)")
        _a(f"{config.gen_iner:<14.3f}   GenIner         - Generator inertia about HSS (kg m^2)")
        _a(f"{config.nac_mass:<14.1f}   NacMass         - Nacelle mass (kg)")
        _a(f"{config.nac_yiner:<14.1f}   NacYIner        - Nacelle inertia about yaw axis (kg m^2)")
        _a(f"{config.yaw_br_mass:<14.1f}   YawBrMass       - Yaw bearing mass (kg)")
        _a(f"{config.ptfm_mass:<14.1f}   PtfmMass        - Platform mass (kg)")
        _a(f"{config.ptfm_r_iner:<14.1f}   PtfmRIner       - Platform inertia for roll tilt rotation about the platform CM (kg m^2)")
        _a(f"{config.ptfm_p_iner:<14.1f}   PtfmPIner       - Platform inertia for pitch tilt rotation about the platform CM (kg m^2)")
        _a(f"{config.ptfm_y_iner:<14.1f}   PtfmYIner       - Platform inertia for yaw rotation about the platform CM (kg m^2)")
        _a(f"{config.ptfm_xy_iner:<14.1f}   PtfmXYIner      - Platform xy moment of inertia about the platform CM (kg m^2)")
        _a(f"{config.ptfm_yz_iner:<14.1f}   PtfmYZIner      - Platform yz moment of inertia about the platform CM (kg m^2)")
        _a(f"{config.ptfm_xz_iner:<14.1f}   PtfmXZIner      - Platform xz moment of inertia about the platform CM (kg m^2)")

        # --- Blade ---
        _a("---------------------- BLADE ---------------------------------------------------")
        _a(f"{config.bld_nodes:<14d}   BldNodes        - Number of blade nodes (per blade) used for analysis (-)")
        _a(f'{"\"" + config.blade_file + "\"":<40s}   BldFile(1)      - Name of file containing properties for blade 1 (quoted string)')
        _a(f'{"\"" + config.blade_file + "\"":<40s}   BldFile(2)      - Name of file containing properties for blade 2 (quoted string)')
        _a(f'{"\"" + config.blade_file + "\"":<40s}   BldFile(3)      - Name of file containing properties for blade 3 (quoted string) [unused for 2 blades]')

        # --- Rotor-Teeter ---
        _a("---------------------- ROTOR-TEETER --------------------------------------------")
        _a(f"{'0':<14s}   TeetMod         - Rotor-teeter spring/damper model {{0: none, 1: standard, 2: user-defined from routine UserTeet}} (switch) [unused for 3 blades]")
        _a(f"{'0.0':<14s}   TeetDmpP        - Rotor-teeter damper position (degrees) [used only for 2 blades and when TeetMod=1]")
        _a(f"{'0.0':<14s}   TeetDmp         - Rotor-teeter damping constant (N-m/(rad/s)) [used only for 2 blades and when TeetMod=1]")
        _a(f"{'0.0':<14s}   TeetCDmp        - Rotor-teeter rate-independent Coulomb-damping moment (N-m) [used only for 2 blades and when TeetMod=1]")
        _a(f"{'0.0':<14s}   TeetSStP        - Rotor-teeter soft-stop position (degrees) [used only for 2 blades and when TeetMod=1]")
        _a(f"{'0.0':<14s}   TeetHStP        - Rotor-teeter hard-stop position (degrees) [used only for 2 blades and when TeetMod=1]")
        _a(f"{'0.0':<14s}   TeetSSSp        - Rotor-teeter soft-stop linear-spring constant (N-m/rad) [used only for 2 blades and when TeetMod=1]")
        _a(f"{'0.0':<14s}   TeetHSSp        - Rotor-teeter hard-stop linear-spring constant (N-m/rad) [used only for 2 blades and when TeetMod=1]")

        # --- Yaw-Friction (v4.x new section) ---
        _a("---------------------- YAW-FRICTION --------------------------------------------")
        _a(f"{config.yaw_frct_mod:<14d}   YawFrctMod      - Yaw-friction model {{0: none, 1: friction, 2: Coulomb, 3: user defined}} (switch)")
        _a(f"{config.m_cs_max:<14.1f}   M_CSmax         - Maximum static Coulomb friction torque (N-m)")
        _a(f"{config.m_fcs_max:<14.1f}   M_FCSmax        - Maximum static Coulomb friction torque proportional to yaw bearing shear force (N-m)")
        _a(f"{config.m_mcs_max:<14.1f}   M_MCSmax        - Maximum static Coulomb friction torque proportional to yaw bearing bending moment (N-m)")
        _a(f"{config.m_cd:<14.1f}   M_CD            - Dynamic Coulomb friction moment (N-m)")
        _a(f"{config.m_fcd:<14.1f}   M_FCD           - Dynamic Coulomb friction moment proportional to yaw bearing shear force (N-m)")
        _a(f"{config.m_mcd:<14.1f}   M_MCD           - Dynamic Coulomb friction moment proportional to yaw bearing bending moment (N-m)")
        _a(f"{config.sig_v:<14.1f}   sig_v           - Linear viscous friction coefficient (N-m/(rad/s))")
        _a(f"{config.sig_v2:<14.1f}   sig_v2          - Quadratic viscous friction coefficient (N-m/(rad/s)^2)")
        _a(f"{config.omg_cut:<14.1f}   OmgCut          - Yaw angular velocity cutoff below which viscous friction is linearized (rad/s)")

        # --- Drivetrain ---
        _a("---------------------- DRIVETRAIN ----------------------------------------------")
        _a(f"{config.gb_eff:<14.4f}   GBoxEff         - Gearbox efficiency (%%)")
        _a(f"{config.gb_ratio:<14.4f}   GBRatio         - Gearbox ratio (-)")
        _a(f"{config.dt_tor_spr:<14.1f}   DTTorSpr        - Drivetrain torsional spring (N-m/rad)")
        _a(f"{config.dt_tor_dmp:<14.1f}   DTTorDmp        - Drivetrain torsional damper (N-m/(rad/s))")

        # --- Furling (v4.x adds FurlFile) ---
        _a("---------------------- FURLING -------------------------------------------------")
        _a(f"{_f(config.furling):<14s}   Furling         - Read in additional model properties for furling turbine (flag) [must currently be FALSE]")
        _a(f'{"\"unused\"":<14s}   FurlFile        - Name of file containing furling properties (quoted string) [unused when Furling=False]')

        # --- Tower ---
        _a("---------------------- TOWER ---------------------------------------------------")
        _a(f"{config.twr_nodes:<14d}   TwrNodes        - Number of tower nodes used for analysis (-)")
        _a(f'{"\"" + config.tower_file + "\"":<40s}   TwrFile         - Name of file containing tower properties (quoted string)')

        # --- Output (v4.x: TStart moved here, after OutFmt) ---
        _a("---------------------- OUTPUT --------------------------------------------------")
        _a(f"{_f(config.sum_print):<14s}   SumPrint        - Print summary data to <RootName>.sum (flag)")
        _a(f"{config.out_file:<14d}   OutFile         - Switch to determine where output will be placed: {{1: in module output file only; 2: in glue code output file only; 3: both}} (currently unused)")
        _a(f"{_f(config.tab_delim):<14s}   TabDelim        - Use tab delimiters in text tabular output file? (flag) (currently unused)")
        _a(f'{"\"" + config.out_fmt + "\"":<14s}   OutFmt          - Format used for text tabular output, excluding the time channel (quoted string) (currently unused)')
        _a(f"{config.t_start:<14.1f}   TStart          - Time to begin tabular output (s) (currently unused)")
        _a(f"{config.dec_fact:<14d}   DecFact         - Decimation factor for tabular output {{1: output every time step}} (-) (currently unused)")
        _a(f"{config.n_tw_gages:<14d}   NTwGages        - Number of tower nodes that have strain gages for output [0 to 9] (-)")
        if config.tw_gage_nds:
            _a(f"{', '.join(str(n) for n in config.tw_gage_nds):<40s}   TwrGagNd        - List of tower nodes that have strain gages [1 to TwrNodes] (-) [unused if NTwGages=0]")
        else:
            _a(f"{'0':<40s}   TwrGagNd        - List of tower nodes that have strain gages [1 to TwrNodes] (-) [unused if NTwGages=0]")
        _a(f"{config.n_bl_gages:<14d}   NBlGages        - Number of blade nodes that have strain gages for output [0 to 9] (-)")
        if config.bl_gage_nds:
            _a(f"{', '.join(str(n) for n in config.bl_gage_nds):<40s}   BldGagNd        - List of blade nodes that have strain gages [1 to BldNodes] (-) [unused if NBlGages=0]")
        else:
            _a(f"{'0':<40s}   BldGagNd        - List of blade nodes that have strain gages [1 to BldNodes] (-) [unused if NBlGages=0]")

        # --- OutList ---
        _a("              OutList             - The next line(s) contains a list of output parameters.  See OutListParameters.xlsx for a listing of available output channels, (-)")
        for out in config.out_list:
            _a(out)
        _a('END of OutList section (the word "END" must appear in the first 3 columns of the last OutList line)')
        _a("---------------------------------------------------------------------------------------")

        # --- ElastoDyn Nodal Outputs (v4.x) ---
        _a("              BldNd_BladesOut  - Number of blades to output all node information at.  Up to number of blades on turbine. (-)")
        _a(f'{"\"" + config.ed_bld_nd_bl_out_nd + "\"":<40s}   BldNd_BlOutNd   - Future feature will allow selecting a portion of the nodes to output. Not implemented; will always output all. (-)')
        _a("              OutList             - The next line(s) contains a list of output parameters.  See OutListParameters.xlsx for a listing of available output channels, (-)")
        for out in config.out_list_nodal:
            _a(out)
        _a('END (the word "END" must appear in the first 3 columns of this last OutList line in the optional nodal output section)')
        _a("====================================================================================================")

        return "\n".join(lines) + "\n"

    def generate_blade_file(self, config: ElastoDynBladeConfig) -> str:
        """Generate the ElastoDyn blade input file.

        Parameters
        ----------
        config : ElastoDynBladeConfig
            Blade structural properties and mode shapes.

        Returns
        -------
        str
            Complete ElastoDyn blade input file content.
        """
        lines: list[str] = []
        _a = lines.append

        _a("------- ELASTODYN V1.00.* INDIVIDUAL BLADE INPUT FILE --------------------------")
        _a("Generated by WindForge - ElastoDyn blade input file")

        # --- Blade Parameters ---
        _a("---------------------- BLADE PARAMETERS ----------------------------------------")
        _a(f"{config.n_bl_inp_st:>10d}   NBlInpSt    - Number of blade input stations (-)")
        _a(f"{config.bld_fl_dmp_1:>10.6f}   BldFlDmp(1) - Blade flap mode #1 structural damping in percent of critical (%%)")
        _a(f"{config.bld_fl_dmp_2:>10.6f}   BldFlDmp(2) - Blade flap mode #2 structural damping in percent of critical (%%)")
        _a(f"{config.bld_ed_dmp_1:>10.6f}   BldEdDmp(1) - Blade edge mode #1 structural damping in percent of critical (%%)")

        # --- Blade Adjustment Factors ---
        _a("---------------------- BLADE ADJUSTMENT FACTORS --------------------------------")
        _a(f"{'1':>10s}   FlStTunr(1) - Blade flapwise modal stiffness tuner, 1st mode (-)")
        _a(f"{'1':>10s}   FlStTunr(2) - Blade flapwise modal stiffness tuner, 2nd mode (-)")
        _a(f"{'1.04536':>10s}   AdjBlMs     - Factor to adjust blade mass density (-)")
        _a(f"{'1':>10s}   AdjFlSt     - Factor to adjust blade flap stiffness (-)")
        _a(f"{'1':>10s}   AdjEdSt     - Factor to adjust blade edge stiffness (-)")

        # --- Distributed Blade Properties ---
        _a("---------------------- DISTRIBUTED BLADE PROPERTIES ----------------------------")
        _a("    BlFract      PitchAxis      StrcTwst       BMassDen        FlpStff        EdgStff")
        _a("      (-)           (-)          (deg)          (kg/m)         (Nm^2)         (Nm^2)")
        for s in config.stations:
            _a(f"{s.bl_fract:13.7E}  {s.pitch_ax:13.7E}  {s.strc_twist:13.4f}  {s.b_mass_den:13.5E}  {s.flp_stff:14.7E}  {s.edg_stff:14.7E}")

        # --- Blade Mode Shapes ---
        _a("---------------------- BLADE MODE SHAPES ---------------------------------------")
        _a(f"{config.flp_mode_1[0]:>10.4f}   BldFl1Sh(2) - Flap mode 1, coeff of x^2")
        _a(f"{config.flp_mode_1[1]:>10.4f}   BldFl1Sh(3) -            , coeff of x^3")
        _a(f"{config.flp_mode_1[2]:>10.4f}   BldFl1Sh(4) -            , coeff of x^4")
        _a(f"{config.flp_mode_1[3]:>10.4f}   BldFl1Sh(5) -            , coeff of x^5")
        _a(f"{config.flp_mode_1[4]:>10.4f}   BldFl1Sh(6) -            , coeff of x^6")

        _a(f"{config.flp_mode_2[0]:>10.4f}   BldFl2Sh(2) - Flap mode 2, coeff of x^2")
        _a(f"{config.flp_mode_2[1]:>10.4f}   BldFl2Sh(3) -            , coeff of x^3")
        _a(f"{config.flp_mode_2[2]:>10.4f}   BldFl2Sh(4) -            , coeff of x^4")
        _a(f"{config.flp_mode_2[3]:>10.4f}   BldFl2Sh(5) -            , coeff of x^5")
        _a(f"{config.flp_mode_2[4]:>10.4f}   BldFl2Sh(6) -            , coeff of x^6")

        _a(f"{config.edg_mode_1[0]:>10.4f}   BldEdgSh(2) - Edge mode 1, coeff of x^2")
        _a(f"{config.edg_mode_1[1]:>10.4f}   BldEdgSh(3) -            , coeff of x^3")
        _a(f"{config.edg_mode_1[2]:>10.4f}   BldEdgSh(4) -            , coeff of x^4")
        _a(f"{config.edg_mode_1[3]:>10.4f}   BldEdgSh(5) -            , coeff of x^5")
        _a(f"{config.edg_mode_1[4]:>10.4f}   BldEdgSh(6) -            , coeff of x^6")

        return "\n".join(lines) + "\n"

    def generate_tower_file(self, config: ElastoDynTowerConfig) -> str:
        """Generate the ElastoDyn tower input file.

        Parameters
        ----------
        config : ElastoDynTowerConfig
            Tower structural properties and mode shapes.

        Returns
        -------
        str
            Complete ElastoDyn tower input file content.
        """
        lines: list[str] = []
        _a = lines.append

        _a("------- ELASTODYN V1.00.* TOWER INPUT FILE -------------------------------------")
        _a("Generated by WindForge - ElastoDyn tower input file")

        # --- Tower Parameters ---
        _a("---------------------- TOWER PARAMETERS ----------------------------------------")
        _a(f"{config.n_tw_inp_st:>10d}   NTwInpSt    - Number of input stations to specify tower geometry")
        _a(f"{config.twr_fa_dmp1:>10.0f}   TwrFADmp(1) - Tower 1st fore-aft mode structural damping ratio (%%)")
        _a(f"{config.twr_fa_dmp2:>10.0f}   TwrFADmp(2) - Tower 2nd fore-aft mode structural damping ratio (%%)")
        _a(f"{config.twr_ss_dmp1:>10.0f}   TwrSSDmp(1) - Tower 1st side-to-side mode structural damping ratio (%%)")
        _a(f"{config.twr_ss_dmp2:>10.0f}   TwrSSDmp(2) - Tower 2nd side-to-side mode structural damping ratio (%%)")

        # --- Tower Adjustment Factors ---
        _a("---------------------- TOWER ADJUSTMUNT FACTORS --------------------------------")
        _a(f"{'1':>10s}   FAStTunr(1) - Tower fore-aft modal stiffness tuner, 1st mode (-)")
        _a(f"{'1':>10s}   FAStTunr(2) - Tower fore-aft modal stiffness tuner, 2nd mode (-)")
        _a(f"{'1':>10s}   SSStTunr(1) - Tower side-to-side stiffness tuner, 1st mode (-)")
        _a(f"{'1':>10s}   SSStTunr(2) - Tower side-to-side stiffness tuner, 2nd mode (-)")
        _a(f"{'1':>10s}   AdjTwMa     - Factor to adjust tower mass density (-)")
        _a(f"{'1':>10s}   AdjFASt     - Factor to adjust tower fore-aft stiffness (-)")
        _a(f"{'1':>10s}   AdjSSSt     - Factor to adjust tower side-to-side stiffness (-)")

        # --- Distributed Tower Properties ---
        _a("---------------------- DISTRIBUTED TOWER PROPERTIES ----------------------------")
        _a("  HtFract       TMassDen         TwFAStif       TwSSStif")
        _a("   (-)           (kg/m)           (Nm^2)         (Nm^2)")
        for s in config.stations:
            _a(f"{s.ht_fract:13.7E}  {s.t_mass_den:13.7E}  {s.tw_fa_stif:14.7E}  {s.tw_ss_stif:14.7E}")

        # --- Tower Mode Shapes ---
        _a("---------------------- TOWER FORE-AFT MODE SHAPES ------------------------------")
        _a(f"{config.fa_mode_1[0]:>10.4f}   TwFAM1Sh(2) - Mode 1, coefficient of x^2 term")
        _a(f"{config.fa_mode_1[1]:>10.4f}   TwFAM1Sh(3) -       , coefficient of x^3 term")
        _a(f"{config.fa_mode_1[2]:>10.4f}   TwFAM1Sh(4) -       , coefficient of x^4 term")
        _a(f"{config.fa_mode_1[3]:>10.4f}   TwFAM1Sh(5) -       , coefficient of x^5 term")
        _a(f"{config.fa_mode_1[4]:>10.4f}   TwFAM1Sh(6) -       , coefficient of x^6 term")

        _a(f"{config.fa_mode_2[0]:>10.4f}   TwFAM2Sh(2) - Mode 2, coefficient of x^2 term")
        _a(f"{config.fa_mode_2[1]:>10.4f}   TwFAM2Sh(3) -       , coefficient of x^3 term")
        _a(f"{config.fa_mode_2[2]:>10.4f}   TwFAM2Sh(4) -       , coefficient of x^4 term")
        _a(f"{config.fa_mode_2[3]:>10.4f}   TwFAM2Sh(5) -       , coefficient of x^5 term")
        _a(f"{config.fa_mode_2[4]:>10.4f}   TwFAM2Sh(6) -       , coefficient of x^6 term")

        _a("---------------------- TOWER SIDE-TO-SIDE MODE SHAPES --------------------------")
        _a(f"{config.ss_mode_1[0]:>10.4f}   TwSSM1Sh(2) - Mode 1, coefficient of x^2 term")
        _a(f"{config.ss_mode_1[1]:>10.4f}   TwSSM1Sh(3) -       , coefficient of x^3 term")
        _a(f"{config.ss_mode_1[2]:>10.4f}   TwSSM1Sh(4) -       , coefficient of x^4 term")
        _a(f"{config.ss_mode_1[3]:>10.4f}   TwSSM1Sh(5) -       , coefficient of x^5 term")
        _a(f"{config.ss_mode_1[4]:>10.4f}   TwSSM1Sh(6) -       , coefficient of x^6 term")

        _a(f"{config.ss_mode_2[0]:>10.4f}   TwSSM2Sh(2) - Mode 2, coefficient of x^2 term")
        _a(f"{config.ss_mode_2[1]:>10.4f}   TwSSM2Sh(3) -       , coefficient of x^3 term")
        _a(f"{config.ss_mode_2[2]:>10.4f}   TwSSM2Sh(4) -       , coefficient of x^4 term")
        _a(f"{config.ss_mode_2[3]:>10.4f}   TwSSM2Sh(5) -       , coefficient of x^5 term")
        _a(f"{config.ss_mode_2[4]:>10.4f}   TwSSM2Sh(6) -       , coefficient of x^6 term")

        return "\n".join(lines) + "\n"


def _flag(value: bool) -> str:
    """Convert a boolean to OpenFAST flag format."""
    return "True" if value else "False"
