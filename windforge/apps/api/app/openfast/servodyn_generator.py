"""
ServoDyn input file generator for OpenFAST v4.1.2.

Generates two files:
  1. ServoDyn primary input file (.dat)
  2. DISCON.IN controller parameter file (for ROSCO or Bladed-style DLLs)

Format verified against:
  r-test/v4.1.2/glue-codes/openfast/5MW_Land_DLL_WTurb/NRELOffshrBsline5MW_Onshore_ServoDyn.dat
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServoDynConfig:
    """Configuration for the ServoDyn primary input file."""

    # --- Simulation Control ---
    echo: bool = False
    dt: str = "default"

    # --- Pitch Control ---
    pc_mode: int = 5           # 0=none, 3=user routine, 4=Simulink, 5=Bladed DLL
    tpc_on: float = 0.0
    tpit_man_s_1: float = 9999.9
    tpit_man_s_2: float = 9999.9
    tpit_man_s_3: float = 9999.9
    pit_man_rat_1: float = 2.0
    pit_man_rat_2: float = 2.0
    pit_man_rat_3: float = 2.0
    bl_pitch_f_1: float = 0.0
    bl_pitch_f_2: float = 0.0
    bl_pitch_f_3: float = 0.0

    # --- Generator and Torque Control ---
    vs_contrl: int = 5         # 0=none, 1=simple VS, 3=user routine, 4=Simulink, 5=Bladed DLL
    gen_model: int = 1
    gen_eff: float = 94.4
    gen_ti_str: bool = True
    gen_ti_stp: bool = True
    spd_gen_on: float = 9999.9
    tim_gen_on: float = 0.0
    tim_gen_of: float = 9999.9

    # --- Simple Variable-Speed Torque Control ---
    vs_rt_gn_sp: float = 9999.9
    vs_rt_tq: float = 9999.9
    vs_rgn2_k: float = 0.0
    vs_sl_pc: float = 10.0

    # --- Simple Induction Generator ---
    sig_sl_pc: float = 1.0
    sig_sy_sp: float = 1500.0
    sig_rt_tq: float = 9999.9
    sig_port: float = 2.0

    # --- Thevenin-Equivalent Induction Generator ---
    tec_freq: float = 60.0
    tec_npol: int = 2
    tec_sres: float = 0.0
    tec_rres: float = 0.0
    tec_vll: float = 0.0
    tec_slr: float = 0.0
    tec_rlr: float = 0.0
    tec_mr: float = 0.0

    # --- HSS Brake ---
    hss_br_mode: int = 0      # 0=none, 1=simple, 3=user routine, 5=Bladed DLL
    thss_br_dp: float = 9999.9
    hss_br_dt: float = 9999.9
    hss_br_tqf: float = 9999.9

    # --- Nacelle-Yaw Control ---
    yc_mode: int = 0           # 0=none, 3=user routine, 4=Simulink, 5=Bladed DLL
    tyc_on: float = 0.0
    yaw_neut: float = 0.0
    yaw_spr: float = 0.0
    yaw_damp: float = 0.0
    tyaw_man_s: float = 9999.9
    yaw_man_rat: float = 0.25
    nac_yaw_f: float = 0.0

    # --- Aerodynamic Flow Control ---
    afc_mode: int = 0
    afc_mean: float = 0.0
    afc_amp: float = 0.0
    afc_phase: float = 0.0

    # --- Cable Control ---
    cc_mode: int = 0

    # --- Structural Control ---
    num_b_stc: int = 0
    b_stc_files: list[str] = field(default_factory=list)
    num_n_stc: int = 0
    n_stc_files: list[str] = field(default_factory=list)
    num_t_stc: int = 0
    t_stc_files: list[str] = field(default_factory=list)
    num_s_stc: int = 0
    s_stc_files: list[str] = field(default_factory=list)

    # --- Bladed Interface ---
    dll_file_name: str = ""  # Set dynamically from settings.ROSCO_LIB_PATH
    dll_in_file: str = "DISCON.IN"
    dll_proc_name: str = "DISCON"
    dll_dt: str = "default"
    dll_ramp: bool = False
    bp_cutoff: float = 9999.9
    nac_yaw_north: float = 0.0
    ptch_cntrl: int = 1       # 0=collective, 1=individual
    ptch_set_pnt: float = 0.0
    ptch_min: float = 0.0
    ptch_max: float = 90.0
    ptch_rate_min: float = -8.0
    ptch_rate_max: float = 8.0
    gain_om: float = 0.0
    gen_spd_min_om: float = 0.0
    gen_spd_max_om: float = 9999.9
    gen_spd_dem: float = 9999.9
    gen_trq_dem: float = 9999.9
    gen_pwr_dem: float = 9999.9

    # --- Bladed Interface Torque-Speed LUT ---
    dll_num_trq: int = 0

    # --- Output ---
    sum_print: bool = False
    out_file: int = 1
    tab_delim: bool = True
    out_fmt: str = "ES10.3E2"
    t_start: float = 0.0
    out_list: list[str] = field(default_factory=lambda: [
        '"GenPwr"', '"GenTq"',
    ])


@dataclass
class DISCONConfig:
    """Configuration for a ROSCO 2.10.1 DISCON.IN controller parameter file.

    All parameters match the ROSCO 2.10.1 reference file for NREL-5MW.
    """

    # --- Simulation Control ---
    logging_level: int = 1       # 0=no debug, 1=standard .dbg, 2=.dbg2, 3=.dbg3
    dt_out: int = 0              # Time step to output .dbg* files (0=match OpenFAST)
    ext_interface: int = 1       # 0=standard bladed, 1=extended DLL (OpenFAST 3.5+)
    echo: int = 0                # 0=no echo, 1=echo input

    # --- Controller Flags ---
    f_lp_type: int = 1           # 1=first-order, 2=second-order LP filter
    ipc_control_mode: int = 0    # 0=off, 1=1P, 2=1P+2P
    vs_control_mode: int = 2     # 0=none, 1=k*omega^2, 2=WSE TSR, 3=power TSR, 4=torque TSR
    vs_const_power: int = 1      # 0=constant torque, 1=constant power
    vs_fbp: int = 0              # Fixed blade pitch mode
    pc_control_mode: int = 1     # 0=no pitch, 1=active PI
    y_control_mode: int = 0      # 0=none, 1=yaw rate, 2=yaw-by-IPC
    ss_mode: int = 1             # 0=no smoothing, 1=setpoint smoothing
    prc_mode: int = 0            # Power reference tracking
    we_mode: int = 2             # 0=LP filtered, 1=I&I, 2=EKF
    ps_mode: int = 1             # 0=no saturation, 1=pitch saturation
    su_mode: int = 0             # Startup mode
    sd_mode: int = 0             # Shutdown mode
    fl_mode: int = 0             # Floating feedback
    td_mode: int = 0             # Tower damper
    tra_mode: int = 0            # Tower resonance avoidance
    flp_mode: int = 0            # Flap control
    ol_mode: int = 0             # Open loop control
    pa_mode: int = 0             # Pitch actuator model
    pf_mode: int = 0             # Pitch fault mode
    awc_mode: int = 0            # Active wake control
    ext_mode: int = 0            # External controller
    zmq_mode: int = 0            # ZeroMQ interface
    cc_mode: int = 0             # Cable control
    stc_mode: int = 0            # Structural control

    # --- Filters ---
    f_lp_corner_freq: float = 1.57080    # LP filter corner freq (rad/s)
    f_lp_damping: float = 0.0            # LP filter damping (for 2nd order)
    f_num_notch_filts: int = 0
    f_notch_freqs: str = "0.0000"
    f_notch_beta_num: str = "0.0000"
    f_notch_beta_den: str = "0.0000"
    f_gen_spd_notch_n: int = 0
    f_gen_spd_notch_ind: str = "0"
    f_twr_top_notch_n: int = 0
    f_twr_top_notch_ind: str = "0"
    f_ss_corner_freq: float = 0.62830    # Setpoint smoother corner freq (rad/s)
    f_we_corner_freq: float = 0.20944    # Wind speed estimate filter corner freq (rad/s)
    f_yaw_err: float = 0.17952           # Yaw controller LP filter corner freq (rad/s)
    f_fl_corner_freq: str = "0.0000   1.0000"  # Tower-top fore-aft filter (freq, damping)
    f_fl_high_pass_freq: float = 0.01042   # Nacelle fore-aft HP filter (rad/s)
    f_flp_corner_freq: str = "0.0000  1.0000"  # Blade root BM filter (freq, damping)
    f_vs_ref_spd_corner_freq: float = 0.20944  # Gen speed ref filter for TSR tracking (rad/s)

    # --- Blade Pitch Control ---
    pc_gs_n: int = 30
    pc_gs_angles: list[float] = field(default_factory=lambda: [
        0.057, 0.084, 0.106, 0.124, 0.141, 0.156, 0.170, 0.183, 0.196, 0.208,
        0.220, 0.232, 0.243, 0.253, 0.264, 0.274, 0.284, 0.294, 0.304, 0.314,
        0.323, 0.332, 0.341, 0.350, 0.359, 0.368, 0.377, 0.385, 0.394, 0.402,
    ])
    pc_gs_kp: list[float] = field(default_factory=lambda: [
        -2.075e-02, -1.823e-02, -1.619e-02, -1.450e-02, -1.308e-02,
        -1.187e-02, -1.082e-02, -9.913e-03, -9.113e-03, -8.404e-03,
        -7.772e-03, -7.204e-03, -6.692e-03, -6.227e-03, -5.803e-03,
        -5.415e-03, -5.059e-03, -4.731e-03, -4.427e-03, -4.146e-03,
        -3.884e-03, -3.640e-03, -3.411e-03, -3.198e-03, -2.997e-03,
        -2.809e-03, -2.631e-03, -2.463e-03, -2.305e-03, -2.155e-03,
    ])
    pc_gs_ki: list[float] = field(default_factory=lambda: [
        -8.417e-03, -7.536e-03, -6.822e-03, -6.232e-03, -5.735e-03,
        -5.312e-03, -4.947e-03, -4.629e-03, -4.350e-03, -4.102e-03,
        -3.881e-03, -3.682e-03, -3.503e-03, -3.341e-03, -3.192e-03,
        -3.057e-03, -2.932e-03, -2.818e-03, -2.712e-03, -2.613e-03,
        -2.522e-03, -2.436e-03, -2.357e-03, -2.282e-03, -2.212e-03,
        -2.146e-03, -2.084e-03, -2.025e-03, -1.970e-03, -1.917e-03,
    ])
    pc_gs_kd: list[float] = field(default_factory=lambda: [0.0] * 30)
    pc_gs_tf: list[float] = field(default_factory=lambda: [0.0] * 30)
    pc_max_pitch: float = 1.570       # Max pitch (rad)
    pc_min_pitch: float = 0.0         # Min pitch (rad)
    pc_max_rat: float = 0.1745        # Max pitch rate (rad/s)
    pc_min_rat: float = -0.1745       # Min pitch rate (rad/s)
    pc_ref_speed: float = 122.9097    # Reference HSS speed (rad/s)
    pc_fine_pitch: float = 0.0        # Below-rated pitch setpoint (rad)
    pc_switch: float = 0.01745        # Switch angle above min pitch (rad)

    # --- Individual Pitch Control ---
    ipc_vramp: str = "9.120        11.400"    # Start/end wind speeds for IPC ramp (m/s)
    ipc_sat_mode: int = 2
    ipc_int_sat: float = 0.3
    ipc_kp: str = "0.000e+00    0.000e+00"
    ipc_ki: str = "0.000e+00    0.000e+00"
    ipc_azi_offset: str = "0.000        0.000"
    ipc_corner_freq_act: float = 0.0

    # --- VS Torque Control ---
    vs_gen_eff: float = 94.4          # Generator efficiency (%)
    vs_ar_sat_tq: float = 43093.5     # Above-rated saturation torque (Nm)
    vs_max_rat: float = 40000.0       # Max torque rate (Nm/s)
    vs_max_tq: float = 47402.9       # Max generator torque (Nm)
    vs_min_tq: float = 0.0           # Min generator torque (Nm)
    vs_min_om_spd: float = 34.64286   # Min generator speed (rad/s)
    vs_rgn2_k: float = 2.31055       # Region 2 gain (Nm/(rad/s)^2)
    vs_rated_gen_pwr: float = 5000000.0  # Rated power (W)
    vs_rt_tq: float = 43093.5        # Rated torque (Nm)
    vs_ref_spd: float = 122.90967     # Rated generator speed (rad/s)
    vs_n: int = 1                     # Number of gen PI torque controller gains
    vs_kp: float = -697.771          # PI proportional gain
    vs_ki: float = -104.507          # PI integral gain (s)
    vs_tsr: float = 7.5              # Optimal TSR

    # --- Fixed Pitch Region 3 ---
    vs_fbp_n: int = 60
    vs_fbp_u: list[float] = field(default_factory=lambda: [
        3.0, 3.2897, 3.5793, 3.8690, 4.1586, 4.4483, 4.7379, 5.0276, 5.3172, 5.6069,
        5.8966, 6.1862, 6.4759, 6.7655, 7.0552, 7.3448, 7.6345, 7.9241, 8.2138, 8.5034,
        8.7931, 9.0828, 9.3724, 9.6621, 9.9517, 10.2414, 10.5310, 10.8207, 11.1103, 11.4000,
        11.8533, 12.3067, 12.7600, 13.2133, 13.6667, 14.1200, 14.5733, 15.0267, 15.4800, 15.9333,
        16.3867, 16.8400, 17.2933, 17.7467, 18.2000, 18.6533, 19.1067, 19.5600, 20.0133, 20.4667,
        20.9200, 21.3733, 21.8267, 22.2800, 22.7333, 23.1867, 23.6400, 24.0933, 24.5467, 25.0000,
    ])
    vs_fbp_omega: list[float] = field(default_factory=lambda: [
        3.4643e+01, 3.7988e+01, 4.1333e+01, 4.4677e+01, 4.8022e+01, 5.1367e+01,
        5.4712e+01, 5.8057e+01, 6.1401e+01, 6.4746e+01, 6.8091e+01, 7.1436e+01,
        7.4781e+01, 7.8126e+01, 8.1470e+01, 8.4815e+01, 8.8160e+01, 9.1505e+01,
        9.4850e+01, 9.8195e+01, 1.0154e+02, 1.0488e+02, 1.0823e+02, 1.1157e+02,
        1.1492e+02, 1.1826e+02, 1.2161e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02,
        1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02,
        1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02,
        1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02,
        1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02,
        1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02, 1.2291e+02,
    ])
    vs_fbp_tau: list[float] = field(default_factory=lambda: [
        2.7730e+03, 3.3343e+03, 3.9473e+03, 4.6120e+03, 5.3284e+03, 6.0966e+03,
        6.9164e+03, 7.7879e+03, 8.7111e+03, 9.6860e+03, 1.0713e+04, 1.1791e+04,
        1.2921e+04, 1.4103e+04, 1.5336e+04, 1.6621e+04, 1.7958e+04, 1.9347e+04,
        2.0787e+04, 2.2279e+04, 2.3822e+04, 2.5418e+04, 2.7065e+04, 2.8763e+04,
        3.0514e+04, 3.2316e+04, 3.4170e+04, 3.6641e+04, 3.9556e+04, 4.2557e+04,
        4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04,
        4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04,
        4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04,
        4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04,
        4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04, 4.2557e+04,
    ])

    # --- Setpoint Smoother ---
    ss_vsgain: float = 1.0
    ss_pcgain: float = 0.05

    # --- Power Reference Tracking ---
    prc_comm: int = 0
    prc_r_torque: float = 1.0
    prc_r_speed: float = 1.0
    prc_r_pitch: float = 1.0
    prc_table_n: int = 20
    prc_r_table: list[float] = field(default_factory=lambda: [
        0.0, 0.0526, 0.1053, 0.1579, 0.2105, 0.2632, 0.3158, 0.3684, 0.4211, 0.4737,
        0.5263, 0.5789, 0.6316, 0.6842, 0.7368, 0.7895, 0.8421, 0.8947, 0.9474, 1.0,
    ])
    prc_pitch_table: list[float] = field(default_factory=lambda: [
        0.1971, 0.1913, 0.1854, 0.1793, 0.1732, 0.1668, 0.1604, 0.1537, 0.1468, 0.1396,
        0.1321, 0.1243, 0.1159, 0.1070, 0.0975, 0.0867, 0.0748, 0.0608, 0.0421, 0.0,
    ])
    prc_gen_speeds_n: int = 2
    prc_lpf_freq: float = 0.07854
    prc_wind_speeds: list[float] = field(default_factory=lambda: [3.0, 25.0])
    prc_gen_speeds: list[float] = field(default_factory=lambda: [0.79168, 0.79168])

    # --- Wind Speed Estimator ---
    we_blade_radius: float = 63.0
    we_cp_n: int = 1
    we_cp: list[float] = field(default_factory=lambda: [0.0])
    we_gamma: float = 0.0
    we_gear_ratio: float = 97.0
    we_jtot: float = 43702538.057      # Total drivetrain inertia (kg*m^2)
    we_rho_air: float = 1.225          # Air density (kg/m^3)
    perf_file_name: str = "Cp_Ct_Cq.NREL5MW.txt"
    perf_table_size: str = "36      26"    # Blade pitch angles x TSR
    we_fo_poles_n: int = 60
    we_fo_poles_v: list[float] = field(default_factory=lambda: [
        3.0, 3.290, 3.579, 3.869, 4.159, 4.448, 4.738, 5.028, 5.317, 5.607,
        5.897, 6.186, 6.476, 6.766, 7.055, 7.345, 7.634, 7.924, 8.214, 8.503,
        8.793, 9.083, 9.372, 9.662, 9.952, 10.241, 10.531, 10.821, 11.110, 11.400,
        11.853, 12.307, 12.760, 13.213, 13.667, 14.120, 14.573, 15.027, 15.480, 15.933,
        16.387, 16.840, 17.293, 17.747, 18.200, 18.653, 19.107, 19.560, 20.013, 20.467,
        20.920, 21.373, 21.827, 22.280, 22.733, 23.187, 23.640, 24.093, 24.547, 25.0,
    ])
    we_fo_poles: list[float] = field(default_factory=lambda: [
        -1.647e-02, -1.806e-02, -1.965e-02, -2.124e-02, -2.283e-02,
        -2.442e-02, -2.601e-02, -2.760e-02, -2.919e-02, -3.078e-02,
        -3.237e-02, -3.396e-02, -3.555e-02, -3.714e-02, -3.873e-02,
        -4.032e-02, -4.191e-02, -4.350e-02, -4.509e-02, -4.668e-02,
        -4.827e-02, -4.986e-02, -5.145e-02, -5.304e-02, -5.463e-02,
        -5.622e-02, -5.781e-02, -5.907e-02, -5.977e-02, -5.994e-02,
        2.104e-02, 1.345e-02, 2.763e-03, -9.263e-03, -2.225e-02,
        -3.585e-02, -4.981e-02, -6.421e-02, -7.916e-02, -9.462e-02,
        -1.101e-01, -1.260e-01, -1.422e-01, -1.584e-01, -1.754e-01,
        -1.923e-01, -2.094e-01, -2.267e-01, -2.441e-01, -2.621e-01,
        -2.800e-01, -2.986e-01, -3.170e-01, -3.359e-01, -3.546e-01,
        -3.738e-01, -3.932e-01, -4.133e-01, -4.335e-01, -4.541e-01,
    ])

    # --- Yaw Control ---
    y_u_switch: float = 0.0
    y_err_thresh: str = "4.000        8.000"
    y_rate: float = 0.00870
    y_me_err_set: float = 0.0
    y_ipc_int_sat: float = 0.0
    y_ipc_kp: float = 0.0
    y_ipc_ki: float = 0.0

    # --- Tower Control ---
    tra_excl_speed: float = 0.0
    tra_excl_band: float = 0.0
    tra_rate_limit: float = 0.0
    fa_ki: float = 0.0
    fa_hpf_corner_freq: float = 0.0
    fa_int_sat: float = 0.0

    # --- Minimum Pitch Saturation ---
    ps_bld_pitch_min_n: int = 60
    ps_wind_speeds: list[float] = field(default_factory=lambda: [
        3.0, 3.2897, 3.5793, 3.8690, 4.1586, 4.4483, 4.7379, 5.0276, 5.3172, 5.6069,
        5.8966, 6.1862, 6.4759, 6.7655, 7.0552, 7.3448, 7.6345, 7.9241, 8.2138, 8.5034,
        8.7931, 9.0828, 9.3724, 9.6621, 9.9517, 10.2414, 10.5310, 10.8207, 11.1103, 11.4000,
        11.8533, 12.3067, 12.7600, 13.2133, 13.6667, 14.1200, 14.5733, 15.0267, 15.4800, 15.9333,
        16.3867, 16.8400, 17.2933, 17.7467, 18.2000, 18.6533, 19.1067, 19.5600, 20.0133, 20.4667,
        20.9200, 21.3733, 21.8267, 22.2800, 22.7333, 23.1867, 23.6400, 24.0933, 24.5467, 25.0,
    ])
    ps_bld_pitch_min: list[float] = field(default_factory=lambda: [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0145, 0.0272, 0.0368, 0.0447, 0.0524,
        0.0637, 0.0747, 0.0854, 0.0958, 0.1060, 0.1160, 0.1259, 0.1356, 0.1451, 0.1546,
        0.1639, 0.1732, 0.1823, 0.1914, 0.2004, 0.2093, 0.2181, 0.2269, 0.2355, 0.2442,
        0.2526, 0.2612, 0.2695, 0.2779, 0.2860, 0.2942, 0.3023, 0.3105, 0.3185, 0.3265,
    ])

    # --- Startup ---
    su_start_time: float = 120.0
    su_fw_min_duration: float = 200.0
    su_rotor_speed_thresh: float = 0.52
    su_rotor_speed_corner_freq: float = 0.41888
    su_load_stages_n: int = 2
    su_load_stages: str = "0.2000 1.0000"
    su_load_ramp_duration: str = "100.0000 100.0000"
    su_load_hold_duration: str = "200.0000 100.0000"

    # --- Shutdown ---
    sd_time_activate: int = 0
    sd_enable_pitch: int = 0
    sd_enable_yaw_error: int = 0
    sd_enable_gen_speed: int = 0
    sd_enable_time: int = 0
    sd_max_pit: float = 0.40205
    sd_pitch_corner_freq: float = 0.41888
    sd_max_yaw_error: float = 30.0
    sd_yaw_error_corner_freq: float = 0.41888
    sd_max_gen_spd: float = 147.4916
    sd_gen_spd_corner_freq: float = 0.41888
    sd_time: float = 9999.0
    sd_method: int = 1
    sd_stage_n: int = 1
    sd_stage_time: str = "1000.0000"
    sd_stage_pitch: str = "1.5708"
    sd_max_torque_rate: str = "2000.0000"
    sd_max_pitch_rate: str = "0.0218"

    # --- Floating ---
    fl_n: int = 1
    fl_kp: str = "0.0000"
    fl_u: str = "0.0000"

    # --- Flap Actuation ---
    flp_angle: float = 0.0
    flp_kp: float = 0.0
    flp_ki: float = 0.0
    flp_max_pit: float = 0.1745

    # --- Open Loop ---
    ol_filename: str = "unused"
    ol_bp_mode: int = 0
    ol_bp_filt_freq: float = 0.0
    ind_breakpoint: int = 0
    ind_bld_pitch: str = "0    0    0"
    ind_gen_tq: int = 0
    ind_yaw_rate: int = 0
    ind_azimuth: int = 0
    rp_gains: str = "0.0000   0.0000   0.0000   0.0000"
    ind_cable_control: int = 0
    ind_struct_control: int = 0
    ind_r_speed: int = 0
    ind_r_torque: int = 0
    ind_r_pitch: int = 0

    # --- Pitch Actuator ---
    pa_corner_freq: float = 3.14
    pa_damping: float = 0.707

    # --- Pitch Faults ---
    pf_offsets: str = "0.0000     0.0000     0.0000"
    pf_time_stuck: str = "9999.0000  9999.0000  9999.0000"

    # --- Active Wake Control ---
    awc_num_modes: int = 1
    awc_n: int = 1
    awc_harmonic: int = 1
    awc_freq: float = 0.05
    awc_amp: float = 1.0
    awc_clock_angle: float = 0.0
    awc_phase_offset: float = 0.0
    awc_cntr_gains: str = "0.0000 0.0000"

    # --- External Controller ---
    ext_dll_filename: str = "unused"
    ext_dll_infile: str = "unused"
    ext_dll_procname: str = "DISCON"

    # --- ZeroMQ ---
    zmq_comm_address: str = "tcp://localhost:5555"
    zmq_update_period: float = 1.0
    zmq_id: int = 0

    # --- Cable Control ---
    cc_group_n: int = 1
    cc_group_index: int = 0
    cc_act_tau: float = 20.0

    # --- Structural Controllers ---
    stc_group_n: int = 1
    stc_group_index: int = 0


class ServoDynGenerator:
    """Generates ServoDyn primary and DISCON.IN controller input files."""

    def generate_servodyn_file(self, config: ServoDynConfig) -> str:
        """Generate the ServoDyn primary input file.

        Parameters
        ----------
        config : ServoDynConfig
            Complete ServoDyn configuration.

        Returns
        -------
        str
            Complete ServoDyn primary input file content.
        """
        lines: list[str] = []
        _a = lines.append
        _f = _flag

        _a("------- SERVODYN INPUT FILE --------------------------------------------")
        _a("Generated by WindForge - ServoDyn primary input file")

        # --- Simulation Control ---
        _a("---------------------- SIMULATION CONTROL --------------------------------------")
        _a(f"{_f(config.echo):<14s}   Echo         - Echo input data to <RootName>.ech (flag)")
        _a(f'{"\"" + config.dt + "\"":<14s}   DT           - Communication interval for controllers (s) (or \"default\")')

        # --- Pitch Control ---
        _a("---------------------- PITCH CONTROL -----------------------------------------------")
        _a(f"{config.pc_mode:<14d}   PCMode       - Pitch control mode {{0: none, 3: user-defined from routine PitchCntrl, 4: user-defined from Simulink/Labview, 5: user-defined from Bladed-style DLL}} (switch)")
        _a(f"{config.tpc_on:<14.1f}   TPCOn        - Time to enable active pitch control [unused when PCMode = 0] (s)")
        _a(f"{config.tpit_man_s_1:<14.1f}   TPitManS(1)  - Time to start override pitch maneuver for blade 1 and target pitch angle for pitch controller setpoints (s)")
        _a(f"{config.tpit_man_s_2:<14.1f}   TPitManS(2)  - Time to start override pitch maneuver for blade 2 and target pitch angle for pitch controller setpoints (s)")
        _a(f"{config.tpit_man_s_3:<14.1f}   TPitManS(3)  - Time to start override pitch maneuver for blade 3 and target pitch angle for pitch controller setpoints (s) [unused for 2 blades]")
        _a(f"{config.pit_man_rat_1:<14.4f}   PitManRat(1) - Pitch rate at which override pitch maneuver heads toward final pitch angle for blade 1 (deg/s)")
        _a(f"{config.pit_man_rat_2:<14.4f}   PitManRat(2) - Pitch rate at which override pitch maneuver heads toward final pitch angle for blade 2 (deg/s)")
        _a(f"{config.pit_man_rat_3:<14.4f}   PitManRat(3) - Pitch rate at which override pitch maneuver heads toward final pitch angle for blade 3 (deg/s) [unused for 2 blades]")
        _a(f"{config.bl_pitch_f_1:<14.4f}   BlPitchF(1)  - Blade 1 final pitch for override pitch maneuvers (degrees)")
        _a(f"{config.bl_pitch_f_2:<14.4f}   BlPitchF(2)  - Blade 2 final pitch for override pitch maneuvers (degrees)")
        _a(f"{config.bl_pitch_f_3:<14.4f}   BlPitchF(3)  - Blade 3 final pitch for override pitch maneuvers (degrees) [unused for 2 blades]")

        # --- Generator and Torque Control ---
        _a("---------------------- GENERATOR AND TORQUE CONTROL --------------------------------")
        _a(f"{config.vs_contrl:<14d}   VSContrl     - Variable-speed control mode {{0: none, 1: simple VS, 3: user-defined from routine UserVSCont, 4: user-defined from Simulink/Labview, 5: user-defined from Bladed-style DLL}} (switch)")
        _a(f"{config.gen_model:<14d}   GenModel     - Generator model {{1: simple, 2: Thevenin, 3: user-defined from routine UserGen}} (switch) [used only when VSContrl=0]")
        _a(f"{config.gen_eff:<14.2f}   GenEff       - Generator efficiency [ignored by the Thevenin and user-defined generator models] (%%)")
        _a(f"{_f(config.gen_ti_str):<14s}   GenTiStr     - Method to start the generator {{T: timed using TimGenOn, F: generator speed using SpdGenOn}} (flag)")
        _a(f"{_f(config.gen_ti_stp):<14s}   GenTiStp     - Method to stop the generator {{T: timed using TimGenOf, F: when generator power = 0}} (flag)")
        _a(f"{config.spd_gen_on:<14.1f}   SpdGenOn     - Generator speed to turn on the generator for a startup (HSS speed) (rpm) [used only when GenTiStr=False]")
        _a(f"{config.tim_gen_on:<14.1f}   TimGenOn     - Time to turn on the generator for a startup (s) [used only when GenTiStr=True]")
        _a(f"{config.tim_gen_of:<14.1f}   TimGenOf     - Time to turn off the generator (s) [used only when GenTiStp=True]")

        # --- Simple Variable-Speed Torque Control ---
        _a("---------------------- SIMPLE VARIABLE-SPEED TORQUE CONTROL ------------------------")
        _a(f"{config.vs_rt_gn_sp:<14.1f}   VS_RtGnSp    - Rated generator speed for simple variable-speed generator control (HSS side) (rpm) [used only when VSContrl=1]")
        _a(f"{config.vs_rt_tq:<14.1f}   VS_RtTq      - Rated generator torque/constant generator torque in Region 3 for simple variable-speed generator control (HSS side) (N-m) [used only when VSContrl=1]")
        _a(f"{config.vs_rgn2_k:<14.6f}   VS_Rgn2K     - Generator torque constant in Region 2 for simple variable-speed generator control (HSS side) (N-m/rpm^2) [used only when VSContrl=1]")
        _a(f"{config.vs_sl_pc:<14.2f}   VS_SlPc      - Rated generator slip percentage in Region 2 1/2 for simple variable-speed generator control (%%)[used only when VSContrl=1]")

        # --- Simple Induction Generator ---
        _a("---------------------- SIMPLE INDUCTION GENERATOR ----------------------------------")
        _a(f"{config.sig_sl_pc:<14.2f}   SIG_SlPc     - Rated generator slip percentage (%%)[used only when VSContrl=0 and GenModel=1]")
        _a(f"{config.sig_sy_sp:<14.1f}   SIG_SySp     - Synchronous (zero-torque) generator speed (rpm) [used only when VSContrl=0 and GenModel=1]")
        _a(f"{config.sig_rt_tq:<14.1f}   SIG_RtTq     - Rated torque (N-m) [used only when VSContrl=0 and GenModel=1]")
        _a(f"{config.sig_port:<14.2f}   SIG_PORt     - Pull-out ratio (Tpullout/Trated) (-) [used only when VSContrl=0 and GenModel=1]")

        # --- Thevenin-Equivalent Induction Generator ---
        _a("---------------------- THEVENIN-EQUIVALENT INDUCTION GENERATOR ---------------------")
        _a(f"{config.tec_freq:<14.1f}   TEC_Freq     - Line frequency [50 or 60] (Hz) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_npol:<14d}   TEC_NPol     - Number of poles [even integer > 0] (-) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_sres:<14.4f}   TEC_SRes     - Stator resistance (ohms) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_rres:<14.4f}   TEC_RRes     - Rotor resistance (ohms) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_vll:<14.4f}   TEC_VLL      - Line-to-line RMS voltage (volts) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_slr:<14.4f}   TEC_SLR      - Stator leakage reactance (ohms) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_rlr:<14.4f}   TEC_RLR      - Rotor leakage reactance (ohms) [used only when VSContrl=0 and GenModel=2]")
        _a(f"{config.tec_mr:<14.4f}   TEC_MR       - Magnetizing reactance (ohms) [used only when VSContrl=0 and GenModel=2]")

        # --- HSS Brake ---
        _a("---------------------- HIGH-SPEED SHAFT BRAKE --------------------------------------")
        _a(f"{config.hss_br_mode:<14d}   HSSBrMode    - HSS brake model {{0: none, 1: simple, 3: user-defined from routine UserHSSBr, 4: user-defined from Simulink/Labview, 5: user-defined from Bladed-style DLL}} (switch)")
        _a(f"{config.thss_br_dp:<14.1f}   THSSBrDp     - Time to initiate deployment of the HSS brake (s)")
        _a(f"{config.hss_br_dt:<14.1f}   HSSBrDT      - Time for HSS-brake to reach full deployment once initiated (used only when HSSBrMode=1) (s)")
        _a(f"{config.hss_br_tqf:<14.1f}   HSSBrTqF     - Fully deployed HSS-brake torque (N-m)")

        # --- Nacelle-Yaw Control ---
        _a("---------------------- NACELLE-YAW CONTROL -----------------------------------------")
        _a(f"{config.yc_mode:<14d}   YCMode       - Yaw control mode {{0: none, 3: user-defined from routine UserYawCont, 4: user-defined from Simulink/Labview, 5: user-defined from Bladed-style DLL}} (switch)")
        _a(f"{config.tyc_on:<14.1f}   TYCOn        - Time to enable active yaw control [unused when YCMode=0] (s)")
        _a(f"{config.yaw_neut:<14.4f}   YawNeut      - Neutral yaw position--yaw spring force is zero at this yaw (degrees)")
        _a(f"{config.yaw_spr:<14.1f}   YawSpr       - Nacelle-yaw spring constant (N-m/rad)")
        _a(f"{config.yaw_damp:<14.1f}   YawDamp      - Nacelle-yaw damping constant (N-m/(rad/s))")
        _a(f"{config.tyaw_man_s:<14.1f}   TYawManS     - Time to start override yaw maneuver and target yaw angle (s)")
        _a(f"{config.yaw_man_rat:<14.4f}   YawManRat    - Yaw maneuver rate (in absolute value) (deg/s)")
        _a(f"{config.nac_yaw_f:<14.4f}   NacYawF      - Final yaw angle for override yaw maneuvers (degrees)")

        # --- Aerodynamic Flow Control ---
        _a("---------------------- AERODYNAMIC FLOW CONTROL ------------------------------------")
        _a(f"{config.afc_mode:<14d}   AfCmode      - Airfoil control mode {{0: none, 1: sine wave cycle, 4: user-defined from Simulink/Labview, 5: user-defined from Bladed-style DLL}} (switch)")
        _a(f"{config.afc_mean:<14.4f}   AfC_Mean     - Mean level for cosine cycling or steady value (-) [used only with AfCmode==1]")
        _a(f"{config.afc_amp:<14.4f}   AfC_Amp      - Amplitude for cosine cycling of flap signal (-) [used only with AfCmode==1]")
        _a(f"{config.afc_phase:<14.4f}   AfC_Phase    - Phase relative to the blade azimuth (0 is vertical) for cosine cycling of flap signal (degrees) [used only with AfCmode==1]")

        # --- Structural Control --- (must come before Cable Control in v4.1.2)
        _a("---------------------- STRUCTURAL CONTROL ------------------------------------------")
        _a(f"{config.num_b_stc:<14d}   NumBStC      - Number of blade structural controllers (integer)")
        if config.b_stc_files:
            b_stc_str = "  ".join('"' + f + '"' for f in config.b_stc_files)
            _a(f"{b_stc_str:<40s}   BStCfiles    - Name of the files for blade structural controllers (quoted strings) [unused when NumBStC==0]")
        else:
            unused = '"unused"'
            _a(f"{unused:<40s}   BStCfiles    - Name of the files for blade structural controllers (quoted strings) [unused when NumBStC==0]")
        _a(f"{config.num_n_stc:<14d}   NumNStC      - Number of nacelle structural controllers (integer)")
        if config.n_stc_files:
            n_stc_str = "  ".join('"' + f + '"' for f in config.n_stc_files)
            _a(f"{n_stc_str:<40s}   NStCfiles    - Name of the files for nacelle structural controllers (quoted strings) [unused when NumNStC==0]")
        else:
            unused = '"unused"'
            _a(f"{unused:<40s}   NStCfiles    - Name of the files for nacelle structural controllers (quoted strings) [unused when NumNStC==0]")
        _a(f"{config.num_t_stc:<14d}   NumTStC      - Number of tower structural controllers (integer)")
        if config.t_stc_files:
            t_stc_str = "  ".join('"' + f + '"' for f in config.t_stc_files)
            _a(f"{t_stc_str:<40s}   TStCfiles    - Name of the files for tower structural controllers (quoted strings) [unused when NumTStC==0]")
        else:
            unused = '"unused"'
            _a(f"{unused:<40s}   TStCfiles    - Name of the files for tower structural controllers (quoted strings) [unused when NumTStC==0]")
        _a(f"{config.num_s_stc:<14d}   NumSStC      - Number of substructure structural controllers (integer)")
        if config.s_stc_files:
            s_stc_str = "  ".join('"' + f + '"' for f in config.s_stc_files)
            _a(f"{s_stc_str:<40s}   SStCfiles    - Name of the files for substructure structural controllers (quoted strings) [unused when NumSStC==0]")
        else:
            unused = '"unused"'
            _a(f"{unused:<40s}   SStCfiles    - Name of the files for substructure structural controllers (quoted strings) [unused when NumSStC==0]")

        # --- Cable Control ---
        _a("---------------------- CABLE CONTROL -----------------------------------------------")
        _a(f"{config.cc_mode:<14d}   CCmode       - Cable control mode {{0: none, 4: user-defined from Simulink/Labview, 5: user-defined from Bladed-style DLL}} (switch)")

        # --- Bladed Interface ---
        _a("---------------------- BLADED INTERFACE ---------------------------------------- [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f'{"\"" + config.dll_file_name + "\"":<40s}   DLL_FileName - Name/location of the dynamic library {{.dll [Windows] or .so [Linux]}} in the Bladed-DLL format (-) [used with PCMode=5, VSContrl=5, or YCMode=5]')
        _a(f'{"\"" + config.dll_in_file + "\"":<40s}   DLL_InFile   - Name of input file sent to the DLL (-) [used with PCMode=5, VSContrl=5, or YCMode=5]')
        _a(f'{"\"" + config.dll_proc_name + "\"":<40s}   DLL_ProcName - Name of procedure in DLL to be called (-) [case sensitive; used with PCMode=5, VSContrl=5, or YCMode=5]')
        _a(f'{"\"" + config.dll_dt + "\"":<14s}   DLL_DT       - Communication interval for dynamic library (s) (or \"default\") [used with PCMode=5, VSContrl=5, or YCMode=5]')
        _a(f"{_f(config.dll_ramp):<14s}   DLL_Ramp     - Whether a linear ramp should be used between DLL_DT time steps [introduces time shift when true] (flag) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.bp_cutoff:<14.1f}   BPCutoff     - Cutoff frequency for low-pass filter on blade pitch from DLL (Hz) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.nac_yaw_north:<14.1f}   NacYaw_North - Reference yaw angle of the nacelle when the upwind end points due North (deg) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.ptch_cntrl:<14d}   Ptch_Cntrl   - Record 28: Use individual pitch control {{0: collective pitch; 1: individual pitch control}} (switch) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.ptch_set_pnt:<14.4f}   Ptch_SetPnt  - Record  5: Below-rated pitch angle set-point (deg) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.ptch_min:<14.4f}   Ptch_Min     - Record  6: Minimum pitch angle (deg) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.ptch_max:<14.4f}   Ptch_Max     - Record  7: Maximum pitch angle (deg) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.ptch_rate_min:<14.4f}   PtchRate_Min - Record  8: Minimum pitch rate (most negative value allowed) (deg/s) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.ptch_rate_max:<14.4f}   PtchRate_Max - Record  9: Maximum pitch rate  (deg/s) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.gain_om:<14.4f}   Gain_OM      - Record 16: Optimal mode gain (N-m/(rad/s)^2) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.gen_spd_min_om:<14.4f}   GenSpd_MinOM - Record 17: Minimum generator speed (rpm) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.gen_spd_max_om:<14.4f}   GenSpd_MaxOM - Record 18: Optimal mode maximum speed (rpm) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.gen_spd_dem:<14.4f}   GenSpd_Dem   - Record 19: Demanded generator speed above rated (rpm) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.gen_trq_dem:<14.4f}   GenTrq_Dem   - Record 22: Demanded generator torque above rated (N-m) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a(f"{config.gen_pwr_dem:<14.1f}   GenPwr_Dem   - Record 13: Demanded power (W) [used with PCMode=5, VSContrl=5, or YCMode=5]")

        # --- Bladed Interface Torque-Speed LUT ---
        _a("---------------------- BLADED INTERFACE TORQUE-SPEED LOOK-UP TABLE -----------------")
        _a(f"{config.dll_num_trq:<14d}   DLL_NumTrq   - Record 26: No. of points in torque-speed look-up table {{0 = none and use the optimal mode parameters; nonzero = ignore the optimal mode PARAMETERs by setting Record 16 to 0.0}} (-) [used with PCMode=5, VSContrl=5, or YCMode=5]")
        _a("GenSpd_TLU   GenTrq_TLU")
        _a("(rpm)        (N-m)")

        # --- Output ---
        _a("---------------------- OUTPUT --------------------------------------------------")
        _a(f"{_f(config.sum_print):<14s}   SumPrint     - Print summary data to <RootName>.sum (flag) (currently unused)")
        _a(f"{config.out_file:<14d}   OutFile      - Switch to determine where output will be placed: {{1: in module output file only; 2: in glue code output file only; 3: both}} (currently unused)")
        _a(f"{_f(config.tab_delim):<14s}   TabDelim     - Use tab delimiters in text tabular output file? (flag) (currently unused)")
        _a(f'{"\"" + config.out_fmt + "\"":<14s}   OutFmt       - Format used for text tabular output (except time).  Resulting field should be 10 characters. (quoted string) (currently unused)')
        _a(f"{config.t_start:<14.1f}   TStart       - Time to begin tabular output (s) (currently unused)")
        _a("                   OutList             - The next line(s) contains a list of output parameters.  See OutListParameters.xlsx for a listing of available output channels, (-)")
        for out in config.out_list:
            _a(out)
        _a('END of input file (the word "END" must appear in the first 3 columns of this last OutList line)')
        _a("---------------------------------------------------------------------------------------")

        return "\n".join(lines) + "\n"

    def generate_discon_in(self, config: DISCONConfig) -> str:
        """Generate a ROSCO 2.10.1 DISCON.IN controller parameter file.

        Matches the complete format from the ROSCO 2.10.1 NREL-5MW reference.

        Parameters
        ----------
        config : DISCONConfig
            ROSCO controller configuration parameters.

        Returns
        -------
        str
            Complete DISCON.IN file content.
        """
        lines: list[str] = []
        _a = lines.append

        def _arr(values: list[float], fmt: str = ".4f") -> str:
            """Format a list of floats as a space-separated string."""
            if fmt == "e":
                return "   ".join(f"{v:.3e}" for v in values)
            return "   ".join(f"{v:{fmt}}" for v in values)

        def _s(val: str, width: int = 20) -> str:
            """Pad a string value to ensure whitespace before comment marker."""
            if len(val) < width:
                return f"{val:<{width}s}"
            return val + "  "  # Always at least 2 spaces after

        _a("! Controller parameter input file for the NREL-5MW wind turbine")
        _a("!    - File written using ROSCO version 2.10.1 controller tuning logic")
        _a("!    - Generated by WindForge")
        _a("")

        # --- Simulation Control ---
        _a("!------- SIMULATION CONTROL ------------------------------------------------------------")
        _a(f"{config.logging_level:<20d}! LoggingLevel\t\t- 0: write no debug files, 1: write standard output .dbg-file, 2: LoggingLevel 1 + ROSCO LocalVars (.dbg2) 3: LoggingLevel 2 + complete avrSWAP-array (.dbg3)")
        _a(f"{config.dt_out:<20d}! DT_Out    \t\t  - Time step to output .dbg* files, or 0 to match sampling period of OpenFAST")
        _a(f"{config.ext_interface:<20d}! Ext_Interface\t\t- (0 - use standard bladed interface, 1 - Use the extened DLL interface introduced in OpenFAST 3.5.0.)")
        _a(f"{config.echo:<20d}! Echo\t\t        - (0 - no Echo, 1 - Echo input data to <RootName>.echo)")
        _a("")

        # --- Controller Flags ---
        _a("!------- CONTROLLER FLAGS -------------------------------------------------")
        _a(f"{config.f_lp_type:<20d}! F_LPFType       - 1: first-order low-pass filter, 2: second-order low-pass filter, [rad/s] (currently filters generator speed and pitch control signals")
        _a(f"{config.ipc_control_mode:<20d}! IPC_ControlMode - Turn Individual Pitch Control (IPC) for fatigue load reductions (pitch contribution) (0: off, 1: 1P reductions, 2: 1P+2P reductions)")
        _a(f"{config.vs_control_mode:<20d}! VS_ControlMode  - Generator torque control mode in above rated conditions (0- no torque control, 1- k*omega^2 with PI transitions, 2- WSE TSR Tracking, 3- Power-based TSR Tracking, 4- Torque-based TSR Tracking)")
        _a(f"{config.vs_const_power:<20d}! VS_ConstPower   - Do constant power torque control, where above rated torque varies, 0 for constant torque)")
        _a(f"{config.vs_fbp:<20d}! VS_FBP          - Fixed blade pitch configuration mode (0- variable pitch (disabled), 1- constant power overspeed, 2- WSE-lookup reference tracking, 3- torque-lookup reference tracking)")
        _a(f"{config.pc_control_mode:<20d}! PC_ControlMode  - Blade pitch control mode (0: No pitch, fix to fine pitch, 1: active PI blade pitch control)")
        _a(f"{config.y_control_mode:<20d}! Y_ControlMode   - Yaw control mode (0: no yaw control, 1: yaw rate control, 2: yaw-by-IPC)")
        _a(f"{config.ss_mode:<20d}! SS_Mode         - Setpoint Smoother mode (0: no setpoint smoothing, 1: introduce setpoint smoothing)")
        _a(f"{config.prc_mode:<20d}! PRC_Mode        - Power reference tracking mode (0: power control disabled, 1: lookup table from wind speed to generator speed setpoints, 2: change speed, torque, pitch to control power)")
        _a(f"{config.we_mode:<20d}! WE_Mode         - Wind speed estimator mode (0: One-second low pass filtered hub height wind speed, 1: Immersion and Invariance Estimator, 2: Extended Kalman Filter)")
        _a(f"{config.ps_mode:<20d}! PS_Mode         - Pitch saturation mode (0: no pitch saturation, 1: implement pitch saturation)")
        _a(f"{config.su_mode:<20d}! SU_Mode         - Startup mode (0: no startup procedure, 1: startup enabled)")
        _a(f"{config.sd_mode:<20d}! SD_Mode         - Shutdown mode (0: no shutdown procedure, 1: shutdown enabled)")
        _a(f"{config.fl_mode:<20d}! Fl_Mode         - Floating specific feedback mode (0: no nacelle velocity feedback, 1: feed back translational velocity, 2: feed back rotational velocity)")
        _a(f"{config.td_mode:<20d}! TD_Mode         - Tower damper mode (0- no tower damper, 1- feed back translational nacelle accelleration to pitch angle")
        _a(f"{config.tra_mode:<20d}! TRA_Mode        - Tower resonance avoidance mode (0- no tower resonsnace avoidance, 1- use torque control setpoints to avoid a specific frequency")
        _a(f"{config.flp_mode:<20d}! Flp_Mode        - Flap control mode (0: no flap control, 1: steady state flap angle, 2: Proportional flap control, 2: Cyclic (1P) flap control)")
        _a(f"{config.ol_mode:<20d}! OL_Mode         - Open loop control mode (0: no open loop control, 1: open loop control vs. time, 2: rotor position control)")
        _a(f"{config.pa_mode:<20d}! PA_Mode         - Pitch actuator mode (0 - not used, 1 - first order filter, 2 - second order filter)")
        _a(f"{config.pf_mode:<20d}! PF_Mode         - Pitch fault mode (0 - not used, 1 - constant offset on one or more blades)")
        _a(f"{config.awc_mode:<20d}! AWC_Mode        - Active wake control (0 - not used, 1 - complex number method, 2 - Coleman transform method)")
        _a(f"{config.ext_mode:<20d}! Ext_Mode        - External control mode (0 - not used, 1 - call external dynamic library)")
        _a(f"{config.zmq_mode:<20d}! ZMQ_Mode        - Fuse ZeroMQ interface (0: unused, 1: Yaw Control)")
        _a(f"{config.cc_mode:<20d}! CC_Mode         - Cable control mode [0- unused, 1- User defined, 2- Open loop control]")
        _a(f"{config.stc_mode:<20d}! StC_Mode        - Structural control mode [0- unused, 1- User defined, 2- Open loop control]")
        _a("")

        # --- Filters ---
        _a("!------- FILTERS ----------------------------------------------------------")
        _a(f"{config.f_lp_corner_freq:<20.5f}! F_LPFCornerFreq\t  - Corner frequency (-3dB point) in the low-pass filters, [rad/s]")
        _a(f"{config.f_lp_damping:<20.5f}! F_LPFDamping\t\t  - Damping coefficient (used only when F_FilterType = 2) [-]")
        _a(f"{config.f_num_notch_filts:<20d}! F_NumNotchFilts   - Number of notch filters placed on sensors")
        _a(f"{_s(config.f_notch_freqs)}! F_NotchFreqs      - Natural frequency of the notch filters. Array with length F_NumNotchFilts")
        _a(f"{_s(config.f_notch_beta_num)}! F_NotchBetaNum    - Damping value of numerator (determines the width of notch). Array with length F_NumNotchFilts, [-]")
        _a(f"{_s(config.f_notch_beta_den)}! F_NotchBetaDen    - Damping value of denominator (determines the depth of notch). Array with length F_NumNotchFilts, [-]")
        _a(f"{config.f_gen_spd_notch_n:<20d}! F_GenSpdNotch_N   - Number of notch filters on generator speed")
        _a(f"{_s(config.f_gen_spd_notch_ind)}! F_GenSpdNotch_Ind - Indices of notch filters on generator speed")
        _a(f"{config.f_twr_top_notch_n:<20d}! F_TwrTopNotch_N   - Number of notch filters on tower top acceleration signal")
        _a(f"{_s(config.f_twr_top_notch_ind)}! F_TwrTopNotch_Ind - Indices of notch filters on tower top acceleration signal")
        _a(f"{config.f_ss_corner_freq:<20.5f}! F_SSCornerFreq    - Corner frequency (-3dB point) in the first order low pass filter for the setpoint smoother, [rad/s].")
        _a(f"{config.f_we_corner_freq:<20.5f}! F_WECornerFreq    - Corner frequency (-3dB point) in the first order low pass filter for the wind speed estimate [rad/s].")
        _a(f"{config.f_yaw_err:<20.5f}! F_YawErr          - Low pass filter corner frequency for yaw controller [rad/s].")
        _a(f"{_s(config.f_fl_corner_freq)}! F_FlCornerFreq    - Natural frequency and damping in the second order low pass filter of the tower-top fore-aft motion for floating feedback control [rad/s, -].")
        _a(f"{config.f_fl_high_pass_freq:<20.5f}! F_FlHighPassFreq  - Natural frequency of first-order high-pass filter for nacelle fore-aft motion [rad/s].")
        _a(f"{_s(config.f_flp_corner_freq)}! F_FlpCornerFreq   - Corner frequency and damping in the second order low pass filter of the blade root bending moment for flap control")
        _a(f"{config.f_vs_ref_spd_corner_freq:<20.5f}! F_VSRefSpdCornerFreq\t\t- Corner frequency (-3dB point) in the first order low pass filter of the generator speed reference used for TSR tracking torque control [rad/s].")
        _a("")

        # --- Blade Pitch Control ---
        _a("!------- BLADE PITCH CONTROL ----------------------------------------------")
        _a(f"{config.pc_gs_n:<20d}! PC_GS_n\t\t\t- Amount of gain-scheduling table entries")
        _a(f"{_arr(config.pc_gs_angles, '.3f')}                      ! PC_GS_angles\t    - Gain-schedule table: pitch angles [rad].")
        _a(f"{_arr(config.pc_gs_kp, 'e')}                 ! PC_GS_KP\t\t- Gain-schedule table: pitch controller kp gains [s].")
        _a(f"{_arr(config.pc_gs_ki, 'e')}                 ! PC_GS_KI\t\t- Gain-schedule table: pitch controller ki gains [-].")
        _a(f"{_arr(config.pc_gs_kd, 'e')}                  ! PC_GS_KD\t\t\t- Gain-schedule table: pitch controller kd gains")
        _a(f"{_arr(config.pc_gs_tf, 'e')}                  ! PC_GS_TF\t\t\t- Gain-schedule table: pitch controller tf gains (derivative filter)")
        _a(f"{config.pc_max_pitch:<20.12f}! PC_MaxPit\t\t\t- Maximum physical pitch limit, [rad].")
        _a(f"{config.pc_min_pitch:<20.12f}! PC_MinPit\t\t\t- Minimum physical pitch limit, [rad].")
        _a(f"{config.pc_max_rat:<20.12f}! PC_MaxRat\t\t\t- Maximum pitch rate (in absolute value) in pitch controller, [rad/s].")
        _a(f"{config.pc_min_rat:<20.12f}! PC_MinRat\t\t\t- Minimum pitch rate (in absolute value) in pitch controller, [rad/s].")
        _a(f"{config.pc_ref_speed:<20.10f}! PC_RefSpd\t\t\t- Desired (reference) HSS speed for pitch controller, [rad/s].")
        _a(f"{config.pc_fine_pitch:<20.12f}! PC_FinePit\t\t- Record 5: Below-rated pitch angle set-point, [rad]")
        _a(f"{config.pc_switch:<20.12f}! PC_Switch\t\t\t- Angle above lowest minimum pitch angle for switch, [rad]")
        _a("")

        # --- Individual Pitch Control ---
        _a("!------- INDIVIDUAL PITCH CONTROL -----------------------------------------")
        _a(f"{config.ipc_vramp}       ! IPC_Vramp\t\t- Start and end wind speeds for cut-in ramp function. First entry: IPC inactive, second entry: IPC fully active. [m/s]")
        _a(f"{config.ipc_sat_mode:<20d}! IPC_SatMode\t\t- IPC Saturation method (0 - no saturation (except by PC_MinPit), 1 - saturate by PS_BldPitchMin, 2 - saturate sotfly (full IPC cycle) by PC_MinPit, 3 - saturate softly by PS_BldPitchMin)")
        _a(f"{config.ipc_int_sat:<20.1f}! IPC_IntSat\t\t- Integrator saturation (maximum signal amplitude contribution to pitch from IPC), [rad]")
        _a(f"{config.ipc_kp}    ! IPC_KP\t\t\t- Proportional gain for the individual pitch controller: first parameter for 1P reductions, second for 2P reductions, [-]")
        _a(f"{config.ipc_ki}    ! IPC_KI\t\t\t- Integral gain for the individual pitch controller: first parameter for 1P reductions, second for 2P reductions, [-]")
        _a(f"{config.ipc_azi_offset}       ! IPC_aziOffset\t\t- Phase offset added to the azimuth angle for the individual pitch controller, [rad].")
        _a(f"{config.ipc_corner_freq_act:<20.1f}! IPC_CornerFreqAct - Corner frequency of the first-order actuators model, to induce a phase lag in the IPC signal (0: Disable), [rad/s]")
        _a("")

        # --- VS Torque Control ---
        _a("!------- VS TORQUE CONTROL ------------------------------------------------")
        _a(f"{config.vs_gen_eff:<20.5f}! VS_GenEff\t\t\t- Generator efficiency mechanical power -> electrical power, [should match the efficiency defined in the generator properties!], [%]")
        _a(f"{config.vs_ar_sat_tq:<20.5e}! VS_ArSatTq\t\t- Above rated generator torque PI control saturation, [Nm]")
        _a(f"{config.vs_max_rat:<20.5e}! VS_MaxRat\t\t\t- Maximum torque rate (in absolute value) in torque controller, [Nm/s].")
        _a(f"{config.vs_max_tq:<20.5e}! VS_MaxTq\t\t\t- Maximum generator torque in Region 3 (HSS side), [Nm].")
        _a(f"{config.vs_min_tq:<20.5e}! VS_MinTq\t\t\t- Minimum generator torque (HSS side), [Nm].")
        _a(f"{config.vs_min_om_spd:<20.5f}! VS_MinOMSpd\t\t- Minimum generator speed [rad/s]")
        _a(f"{config.vs_rgn2_k:<20.5e}! VS_Rgn2K\t\t- Generator torque constant in Region 2 (HSS side). Only used in VS_ControlMode = 1,3,4")
        _a(f"{config.vs_rated_gen_pwr:<20.5e}! VS_RtPwr\t\t\t- Wind turbine rated power [W]")
        _a(f"{config.vs_rt_tq:<20.5e}! VS_RtTq\t\t\t- Rated torque, [Nm].")
        _a(f"{config.vs_ref_spd:<20.5f}! VS_RefSpd\t\t\t- Rated generator speed [rad/s]")
        _a(f"{config.vs_n:<20d}! VS_n\t\t\t\t- Number of generator PI torque controller gains")
        _a(f"{config.vs_kp:<20.5e}! VS_KP\t\t\t\t- Proportional gain for generator PI torque controller [-]. (Only used in the transitional 2.5 region if VS_ControlMode =/ 2)")
        _a(f"{config.vs_ki:<20.5e}! VS_KI\t\t\t\t- Integral gain for generator PI torque controller [s]. (Only used in the transitional 2.5 region if VS_ControlMode =/ 2)")
        _a(f"{config.vs_tsr:<20.5f}! VS_TSRopt\t\t    - Power-maximizing region 2 tip-speed-ratio. Only used in VS_ControlMode = 2.")
        _a("")

        # --- Fixed Pitch Region 3 ---
        _a("!------- FIXED PITCH REGION 3 TORQUE CONTROL ------------------------------------------------")
        _a(f"{config.vs_fbp_n:<20d}! VS_FBP_n          - Number of gain-scheduling table entries")
        _a(f"{_arr(config.vs_fbp_u, '.4f')}                    ! VS_FBP_U          - Operating schedule table: Wind speeds [m/s].")
        _a(f"{_arr(config.vs_fbp_omega, '.4e')}                 ! VS_FBP_Omega      - Operating schedule table: Generator speeds [rad/s].")
        _a(f"{_arr(config.vs_fbp_tau, '.4e')}                 ! VS_FBP_Tau        - Operating schedule table: Generator torques [N m].")
        _a("")

        # --- Setpoint Smoother ---
        _a("!------- SETPOINT SMOOTHER ---------------------------------------------")
        _a(f"{config.ss_vsgain:<20.5f}! SS_VSGain         - Variable speed torque controller setpoint smoother gain, [-].")
        _a(f"{config.ss_pcgain:<20.5f}! SS_PCGain         - Collective pitch controller setpoint smoother gain, [-].")
        _a("")

        # --- Power Reference Tracking ---
        _a("!------- POWER REFERENCE TRACKING --------------------------------------")
        _a(f"{config.prc_comm:<20d}! PRC_Comm   - Power reference communication mode when PRC_Mode = 2, 0- use constant DISCON inputs, 1- use open loop inputs, 2- use ZMQ inputs")
        _a(f"{config.prc_r_torque:<20.5f}! PRC_R_Torque   - Constant power rating through changing the rated torque, used if PRC_Mode = 2, PRC_Comm = 0, default is 1, effective above rated [-]")
        _a(f"{config.prc_r_speed:<20.5f}! PRC_R_Speed   - Constant power rating through changing the rated generator speed, used if PRC_Mode = 2, PRC_Comm = 0, default is 1, effective above rated [-]")
        _a(f"{config.prc_r_pitch:<20.5f}! PRC_R_Pitch   - Constant power rating through changing the fine pitch angle, used if PRC_Mode = 2, PRC_Comm = 0, default is 1, effective below rated [-]")
        _a(f"{config.prc_table_n:<20d}! PRC_Table_n   - Number of elements in PRC_R to _Pitch table.  Used if PRC_Mode = 1.")
        _a(f"{_arr(config.prc_r_table, '.4f')}            ! PRC_R_Table   - Table of turbine rating versus fine pitch (PRC_Pitch_Table), length should be PRC_Table_n, default is 1 [-].  Used if PRC_Mode = 1.")
        _a(f"{_arr(config.prc_pitch_table, '.4f')}            ! PRC_Pitch_Table   - Table of fine pitch versus PRC_R_Table, length should be PRC_Table_n [rad].  Used if PRC_Mode = 1.")
        _a(f"{config.prc_gen_speeds_n:<20d}! PRC_n\t\t\t    -  Number of elements in PRC_WindSpeeds and PRC_GenSpeeds array")
        _a(f"{config.prc_lpf_freq:<20.5f}! PRC_LPF_Freq   - Frequency of the low pass filter on the wind speed estimate used to set PRC_GenSpeeds [rad/s]")
        _a(f"{_arr(config.prc_wind_speeds, '.4f')}           ! PRC_WindSpeeds   - Array of wind speeds used in rotor speed vs. wind speed lookup table [m/s]")
        _a(f"{_arr(config.prc_gen_speeds, '.4e')}         ! PRC_GenSpeeds   - Array of generator speeds corresponding to PRC_WindSpeeds [rad/s]")
        _a("")

        # --- Wind Speed Estimator ---
        _a("!------- WIND SPEED ESTIMATOR ---------------------------------------------")
        _a(f"{config.we_blade_radius:<20.3f}! WE_BladeRadius\t- Blade length (distance from hub center to blade tip), [m]")
        _a(f"{config.we_cp_n:<20d}! WE_CP_n\t\t\t- Amount of parameters in the Cp array")
        we_cp_str = "  ".join(f"{v:.1f}" for v in config.we_cp)
        _a(f"{we_cp_str:<20s}  ! WE_CP - Parameters that define the parameterized CP(lambda) function")
        _a(f"{config.we_gamma:<20.1f}! WE_Gamma\t\t\t- Adaption gain of the wind speed estimator algorithm [m/rad]")
        _a(f"{config.we_gear_ratio:<20.1f}! WE_GearboxRatio\t- Gearbox ratio [>=1],  [-]")
        _a(f"{config.we_jtot:<20.5f}! WE_Jtot\t\t\t- Total drivetrain inertia, including blades, hub and casted generator inertia to LSS, [kg m^2]")
        _a(f"{config.we_rho_air:<20.3f}! WE_RhoAir\t\t\t- Air density, [kg m^-3]")
        _a(f'"{config.perf_file_name}"{"":20s}! PerfFileName      - File containing rotor performance tables (Cp,Ct,Cq) (absolute path or relative to this file)')
        _a(f"{_s(config.perf_table_size)}! PerfTableSize     - Size of rotor performance tables, first number refers to number of blade pitch angles, second number referse to number of tip-speed ratios")
        _a(f"{config.we_fo_poles_n:<20d}! WE_FOPoles_N      - Number of first-order system poles used in EKF")
        _a(f"{_arr(config.we_fo_poles_v, '.3f')}                     ! WE_FOPoles_v      - Wind speeds corresponding to first-order system poles [m/s]")
        _a(f"{_arr(config.we_fo_poles, 'e')}                 ! WE_FOPoles        - First order system poles [1/s]")
        _a("")

        # --- Yaw Control ---
        _a("!------- YAW CONTROL ------------------------------------------------------")
        _a(f"{config.y_u_switch:<20.5f}! Y_uSwitch\t\t- Wind speed to switch between Y_ErrThresh. If zero, only the second value of Y_ErrThresh is used [m/s]")
        _a(f"{_s(config.y_err_thresh)}! Y_ErrThresh    - Yaw error threshold/deadbands. Turbine begins to yaw when it passes this. If Y_uSwitch is zero, only the second value is used. [deg].")
        _a(f"{config.y_rate:<20.5f}! Y_Rate\t\t\t- Yaw rate [rad/s]")
        _a(f"{config.y_me_err_set:<20.5f}! Y_MErrSet\t\t- Integrator saturation (maximum signal amplitude contribution to pitch from yaw-by-IPC), [rad]")
        _a(f"{config.y_ipc_int_sat:<20.5f}! Y_IPC_IntSat\t\t- Integrator saturation (maximum signal amplitude contribution to pitch from yaw-by-IPC), [rad]")
        _a(f"{config.y_ipc_kp:<20.5f}! Y_IPC_KP\t\t\t- Yaw-by-IPC proportional controller gain Kp")
        _a(f"{config.y_ipc_ki:<20.5f}! Y_IPC_KI\t\t\t- Yaw-by-IPC integral controller gain Ki")
        _a("")

        # --- Tower Control ---
        _a("!------- TOWER CONTROL ------------------------------------------------------")
        _a(f"{config.tra_excl_speed:<20.5f}! TRA_ExclSpeed\t    - Rotor speed for exclusion [LSS, rad/s]")
        _a(f"{config.tra_excl_band:<20.5f}! TRA_ExclBand\t    - Size of the rotor frequency exclusion band [LSS, rad/s]. Torque controller reference will be TRA_ExclSpeed +/- TRA_ExlBand/2")
        _a(f"{config.tra_rate_limit:<20.5e}! TRA_RateLimit\t    - Rate limit of change in rotor speed reference [LSS, rad/s].  Suggested to be VS_RefSpd/400.")
        _a(f"{config.fa_ki:<20.5f}! FA_KI\t\t\t\t- Integral gain for the fore-aft tower damper controller,  [rad*s/m]")
        _a(f"{config.fa_hpf_corner_freq:<20.5f}! FA_HPFCornerFreq\t- Corner frequency (-3dB point) in the high-pass filter on the fore-aft acceleration signal [rad/s]")
        _a(f"{config.fa_int_sat:<20.5f}! FA_IntSat\t\t\t- Integrator saturation (maximum signal amplitude contribution to pitch from FA damper), [rad]")
        _a("")

        # --- Minimum Pitch Saturation ---
        _a("!------- MINIMUM PITCH SATURATION -------------------------------------------")
        _a(f"{config.ps_bld_pitch_min_n:<20d}! PS_BldPitchMin_N  - Number of values in minimum blade pitch lookup table (should equal number of values in PS_WindSpeeds and PS_BldPitchMin)")
        _a(f"{_arr(config.ps_wind_speeds, '.4f')}                 ! PS_WindSpeeds     - Wind speeds corresponding to minimum blade pitch angles [m/s]")
        _a(f"{_arr(config.ps_bld_pitch_min, '.4f')}                  ! PS_BldPitchMin    - Minimum blade pitch angles [rad]")
        _a("")

        # --- Startup ---
        _a("!------- STARTUP -----------------------------------------------------------")
        _a(f"{config.su_start_time:<20.10f}! SU_StartTime            - Time to start startup routine [s]")
        _a(f"{config.su_fw_min_duration:<20.10f}! SU_FW_MinDuration       - Free-wheel minimum duration [s]")
        _a(f"{config.su_rotor_speed_thresh:<20.12f}! SU_RotorSpeedThresh     - Rotor speed threshhold to switch from freewheel to loads [rad/s]")
        _a(f"{config.su_rotor_speed_corner_freq:<20.12f}! SU_RotorSpeedCornerFreq - Cutoff Frequency for first order low-pass filter for rotor speed for startup [rad/s]")
        _a(f"{config.su_load_stages_n:<20d}! SU_LoadStages_N           - Number of load staged for startup (should equal number of values in SU_LoadStages, SU_LoadRampDuration and SU_LoadHoldDuration)")
        _a(f"{_s(config.su_load_stages)}! SU_LoadStages        - Array containing loads as a fraction of full generator torque during startup")
        _a(f"{_s(config.su_load_ramp_duration)}! SU_LoadRampDuration  - Array containing ramp duration to reach the corresponding partial loads during startup [s]")
        _a(f"{_s(config.su_load_hold_duration)}! SU_LoadHoldDuration  - Array containing duration to hold the partial loads during startup [s]")
        _a("")

        # --- Shutdown ---
        _a("!------- SHUTDOWN -----------------------------------------------------------")
        _a(f"{config.sd_time_activate:<20d}! SD_TimeActivate        - Time to acitvate shutdown modes; no shutdown events will occur before this time. [s]")
        _a(f"{config.sd_enable_pitch:<20d}! SD_EnablePitch         - Shutdown when collective blade pitch exceeds a threshold, [-]")
        _a(f"{config.sd_enable_yaw_error:<20d}! SD_EnableYawError      - Shutdown when yaw error exceeds a threshold, [-]")
        _a(f"{config.sd_enable_gen_speed:<20d}! SD_EnableGenSpeed      - Shutdown when generator speed exceeds a threshold, [-]")
        _a(f"{config.sd_enable_time:<20d}! SD_EnableTime          - Shutdown at a predefined time, [-]")
        _a(f"{config.sd_max_pit:<20.12f}! SD_MaxPit              - Maximum blade pitch angle to initiate shutdown, [rad]")
        _a(f"{config.sd_pitch_corner_freq:<20.12f}! SD_PitchCornerFreq     - Cutoff Frequency for first order low-pass filter for blade pitch angle for shutdown, [rad/s]")
        _a(f"{config.sd_max_yaw_error:<20.11f}! SD_MaxYawError         - Maximum yaw error to initiate shutdown, [deg]")
        _a(f"{config.sd_yaw_error_corner_freq:<20.12f}! SD_YawErrorCornerFreq  - Cutoff Frequency for first order low-pass filter for yaw error for shutdown, [rad/s]")
        _a(f"{config.sd_max_gen_spd:<20.10f}! SD_MaxGenSpd           - Maximum generator speed to initiate shutdown, [rad/s]")
        _a(f"{config.sd_gen_spd_corner_freq:<20.12f}! SD_GenSpdCornerFreq    - Cutoff Frequency for first order low-pass filter for generator speed for shutdown, [rad/s]")
        _a(f"{config.sd_time:<20.9f}! SD_Time                - Shutdown time, [s]")
        _a(f"{config.sd_method:<20d}! SD_Method              - Shutdown method {{1- Reduce generator torque and increase blade pitch in timed stages (SD_StageTime), 2- stages depend on pitch angle (SD_StagePitch)}}")
        _a(f"{config.sd_stage_n:<20d}! SD_Stage_N             - Number of shutdown stages (should equal number of values in SD_MaxPitchRate and SD_MaxTorqueRate) [-]")
        _a(f"{_s(config.sd_stage_time)}! SD_StageTime           - Array containing the time to spend in each shutdown stage [s]")
        _a(f"{_s(config.sd_stage_pitch)}! SD_StagePitch          - Array with pitch angles to reach in each shutdown stage [rad]. If the pitch < SD_StagePitch[i], the SD_Stage = i.  If pitch > SD_StagePitch[SD_Stage_N], the maximum rates are used.")
        _a(f"{_s(config.sd_max_torque_rate)}! SD_MaxTorqueRate       - Maximum torque rate for shutdown [Nm/s]")
        _a(f"{_s(config.sd_max_pitch_rate)}! SD_MaxPitchRate        - Maximum pitch rate used for shutdown [rad/s]")
        _a("")

        # --- Floating ---
        _a("!------- Floating -----------------------------------------------------------")
        _a(f"{config.fl_n:<20d}! Fl_n              - Number of Fl_Kp gains in gain scheduling, optional with default of 1")
        _a(f"{_s(config.fl_kp)}! Fl_Kp             - Nacelle velocity proportional feedback gain [s]")
        _a(f"{_s(config.fl_u)}! Fl_U              - Wind speeds for scheduling Fl_Kp, optional if Fl_Kp is single value [m/s]")
        _a("")

        # --- Flap Actuation ---
        _a("!------- FLAP ACTUATION -----------------------------------------------------")
        _a(f"{config.flp_angle:<20.12f}! Flp_Angle         - Initial or steady state flap angle [rad]")
        _a(f"{config.flp_kp:<20.8e}! Flp_Kp            - Blade root bending moment proportional gain for flap control [s]")
        _a(f"{config.flp_ki:<20.8e}! Flp_Ki            - Flap displacement integral gain for flap control [-]")
        _a(f"{config.flp_max_pit:<20.12f}! Flp_MaxPit        - Maximum (and minimum) flap pitch angle [rad]")
        _a("")

        # --- Open Loop ---
        _a("!------- Open Loop Control -----------------------------------------------------")
        _a(f'"{config.ol_filename}"{"":12s}! OL_Filename       - Input file with open loop timeseries (absolute path or relative to this file)')
        _a(f"{config.ol_bp_mode:<20d}! OL_BP_Mode        - Breakpoint mode for open loop control, 0 - indexed by time (default), 1 - indexed by wind speed]")
        _a(f"{config.ol_bp_filt_freq:<20.6f}! OL_BP_FiltFreq    - Natural frequency of 1st order filter on breakpoint for open loop control. 0 will skip filter.")
        _a(f"{config.ind_breakpoint:<20d}! Ind_Breakpoint    - The column in OL_Filename that contains the breakpoint (time if OL_Mode = 1)")
        _a(f"{_s(config.ind_bld_pitch)}! Ind_BldPitch      - The columns in OL_Filename that contains the blade pitch (1,2,3) inputs in rad [array]")
        _a(f"{config.ind_gen_tq:<20d}! Ind_GenTq         - The column in OL_Filename that contains the generator torque in Nm")
        _a(f"{config.ind_yaw_rate:<20d}! Ind_YawRate       - The column in OL_Filename that contains the yaw rate in rad/s")
        _a(f"{config.ind_azimuth:<20d}! Ind_Azimuth       - The column in OL_Filename that contains the desired azimuth position in rad (used if OL_Mode = 2)")
        _a(f"{_s(config.rp_gains)}! RP_Gains - PID gains and Tf of derivative for rotor position control (used if OL_Mode = 2)")
        _a(f"{config.ind_cable_control:<20d}! Ind_CableControl  - The column(s) in OL_Filename that contains the cable control inputs in m [Used with CC_Mode = 2, must be the same size as CC_Group_N]")
        _a(f"{config.ind_struct_control:<20d}! Ind_StructControl - The column(s) in OL_Filename that contains the structural control inputs [Used with StC_Mode = 2, must be the same size as StC_Group_N]")
        _a(f"{config.ind_r_speed:<20d}! Ind_R_Speed       - Index (column, 1-indexed) of power rating via speed offset")
        _a(f"{config.ind_r_torque:<20d}! Ind_R_Torque      - Index (column, 1-indexed) of power rating via torque offset")
        _a(f"{config.ind_r_pitch:<20d}! Ind_R_Pitch       - Index (column, 1-indexed) of power rating via pitch offset")
        _a("")

        # --- Pitch Actuator ---
        _a("!------- Pitch Actuator Model -----------------------------------------------------")
        _a(f"{config.pa_corner_freq:<20.12f}! PA_CornerFreq     - Pitch actuator bandwidth/cut-off frequency [rad/s]")
        _a(f"{config.pa_damping:<20.12f}! PA_Damping        - Pitch actuator damping ratio [-, unused if PA_Mode = 1]")
        _a("")

        # --- Pitch Faults ---
        _a("!------- Pitch Actuator Faults -----------------------------------------------------")
        _a(f"{_s(config.pf_offsets, 40)}! PF_Offsets     - Pitch angle offsets for each blade (array with length of 3), only used if PF_Mode = 1")
        _a(f"{_s(config.pf_time_stuck, 40)}! PF_TimeStuck     - Time pitch actuator becomes stuck at last value for each blade (array with length of 3), only used if PF_Mode = 2")
        _a("")

        # --- Active Wake Control ---
        _a("!------- Active Wake Control -----------------------------------------------------")
        _a(f"{config.awc_num_modes:<20d}! AWC_NumModes       - Number of user-defined AWC forcing modes")
        _a(f"{config.awc_n:<20d}! AWC_n              - Azimuthal mode number(s) (i.e., the number and direction of the lobes of the wake structure)")
        _a(f"{config.awc_harmonic:<20d}! AWC_harmonic       - Harmonic(s) to apply in the AWC Inverse Coleman Transformation (only used when AWC_Mode = 2)")
        _a(f"{config.awc_freq:<20.4f}! AWC_freq           - Frequency(s) of forcing mode(s) [Hz]")
        _a(f"{config.awc_amp:<20.4f}! AWC_amp            - Pitch amplitude(s) of individual forcing mode(s) [deg]")
        _a(f"{config.awc_clock_angle:<20.4f}! AWC_clockangle     - Initial angle(s) of forcing mode(s) [deg]")
        _a(f"{config.awc_phase_offset:<20.12f}! AWC_phaseoffset \t - Azimuth offset in the Coleman transformation [deg]")
        _a(f"{_s(config.awc_cntr_gains)}! AWC_CntrGains           - KP and KI/KR gain of the active wake controller [-]")
        _a("")

        # --- External Controller ---
        _a("!------- External Controller Interface -----------------------------------------------------")
        _a(f'"{config.ext_dll_filename}"{"":12s}! DLL_FileName        - Name/location of the dynamic library in the Bladed-DLL format')
        _a(f'"{config.ext_dll_infile}"{"":12s}! DLL_InFile          - Name of input file sent to the DLL (-)')
        _a(f'"{config.ext_dll_procname}"{"":12s}! DLL_ProcName        - Name of procedure in DLL to be called (-)')
        _a("")

        # --- ZeroMQ ---
        _a("!------- ZeroMQ Interface ---------------------------------------------------------")
        _a(f'"{config.zmq_comm_address}"{"":12s}! ZMQ_CommAddress     - Communication address for ZMQ server, (e.g. "tcp://localhost:5555")')
        _a(f"{config.zmq_update_period:<20.6f}! ZMQ_UpdatePeriod    - Update period at zmq interface to send measurements and wait for setpoint [sec.]")
        _a(f"{config.zmq_id:<20d}! ZMQ_ID       - Integer identifier of turbine")
        _a("")

        # --- Cable Control ---
        _a("!------- Cable Control ---------------------------------------------------------")
        _a(f"{config.cc_group_n:<20d}! CC_Group_N        - Number of cable control groups")
        _a(f"{config.cc_group_index:<20d}! CC_GroupIndex     - First index for cable control group, should correspond to deltaL")
        _a(f"{config.cc_act_tau:<20.6f}! CC_ActTau         - Time constant for line actuator [s]")
        _a("")

        # --- Structural Controllers ---
        _a("!------- Structural Controllers ---------------------------------------------------------")
        _a(f"{config.stc_group_n:<20d}! StC_Group_N       - Number of cable control groups")
        _a(f"{config.stc_group_index:<20d}! StC_GroupIndex    - First index for structural control group, options specified in ServoDyn summary output")
        _a("")

        return "\n".join(lines) + "\n"


def _flag(value: bool) -> str:
    """Convert a boolean to OpenFAST flag format."""
    return "True" if value else "False"
