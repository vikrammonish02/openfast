"""
TurbSim input file generator.

Generates input files for the TurbSim stochastic turbulence simulator
used to create full-field wind files for OpenFAST simulations.

Supports IEC Kaimal (IECKAI) and IEC von Karman (IECVKM) spectral models,
as well as IEC wind types (NTM, ETM, EWM).

IMPORTANT: TurbSim reads input files *positionally* — every line must be
present and in the exact order shown in the reference template.  Adding or
removing lines will cause cryptic "Invalid logical input" errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random


class TurbulenceModel(str, Enum):
    """IEC turbulence spectral model."""
    IECKAI = "IECKAI"   # IEC Kaimal
    IECVKM = "IECVKM"   # IEC von Karman


class IECWindType(str, Enum):
    """IEC wind type for TurbSim."""
    NTM = "NTM"     # Normal Turbulence Model
    xETM = "xETM"   # Extreme Turbulence Model (x = turbine class)
    xEWM1 = "xEWM1" # Extreme Wind Model - 1 year recurrence
    xEWM50 = "xEWM50" # Extreme Wind Model - 50 year recurrence


class IECTurbulenceClass(str, Enum):
    """IEC turbulence characteristic (category)."""
    A = "A"   # High turbulence (Iref = 0.16)
    B = "B"   # Medium turbulence (Iref = 0.14)
    C = "C"   # Low turbulence (Iref = 0.12)


@dataclass
class TurbSimConfig:
    """Configuration for the TurbSim input file."""

    # --- Runtime Options ---
    echo: bool = False
    rand_seed1: int = -1          # First random seed (-2147483648 to 2147483647). -1 = auto-generate
    rand_seed2: str = "RanLux"    # Second random seed: "RanLux" or "RNSNLW"
    wrap_files: bool = False

    # --- Turbine/Model Specifications ---
    num_grid_z: int = 15          # Vertical grid points
    num_grid_y: int = 15          # Horizontal grid points
    time_step: float = 0.05       # Time step (s)
    analysis_time: float = 660.0  # Length of analysis time series (s) (use 630s + 30s spinup)
    usable_time: str = "ALL"      # Usable time (s) or "ALL"
    hub_ht: float = 90.0          # Hub height (m)
    grid_height: float = 150.0    # Grid height (m)
    grid_width: float = 150.0     # Grid width (m)
    v_flow_ang: float = 0.0       # Vertical mean flow angle (deg)
    h_flow_ang: float = 0.0       # Horizontal mean flow angle (deg)

    # --- Meteorological Boundary Conditions ---
    turb_model: TurbulenceModel = TurbulenceModel.IECKAI
    usable_turb_model: str = "default"  # Usually same as TurbModel
    iec_standard: str = "1-ED3"    # IEC standard edition (1-ED2, 1-ED3, 1-ED4)
    iec_turbc: str = "B"           # IEC turbulence characteristic (A, B, C, or TI in %%)
    iec_wind_type: str = "NTM"     # IEC wind type (NTM, xETM, xEWM1, xEWM50)
    etm_c: str = "default"        # IEC ETM c parameter (m/s) or "default"
    wind_profile_type: str = "IEC" # Wind profile type (LOG, PL, IEC, JET, default)
    profile_file: str = "unused"   # Wind profile data file
    ref_ht: float = 90.0          # Reference height for wind speed (m)
    u_ref: float = 11.4           # Reference mean wind speed at RefHt (m/s)
    z_jet: str = "default"        # Jet height (m) or "default"
    pl_exp: str = "default"       # Power law exponent or "default"
    z0: str = "default"           # Surface roughness length (m) or "default"

    # --- Non-IEC Meteorological Parameters ---
    latitude: str = "default"
    rich_no: float = 0.05
    usr_vkm: str = "default"
    usr_vkm_l: str = "default"
    ustar_file: str = "default"
    ustar_profile: str = "default"

    # --- Spatial Coherence Parameters ---
    scy_lux: str = "default"      # u-component coherence scale
    incdc1: str = "default"
    incdc2: str = "default"
    coh_exp: str = "default"      # Coherence exponent

    # --- Coherent Turbulence Scaling Parameters ---
    ct_event_path: str = "unused"
    ct_event_file: str = "random"
    randomize: bool = True
    num_events: int = 1000
    ct_scaling: str = "default"

    # --- Output ---
    wr_bts: bool = True           # Write .bts binary output?
    wr_formatted: bool = False    # Write formatted output?
    wr_ats: bool = False          # Write .ats (AeroDyn) output?
    wr_bladed: bool = False       # Write Bladed-style output?
    wr_hawc: bool = False         # Write HAWC format output?
    wr_vtk: bool = False          # Write VTK output?
    wr_twrs: bool = False         # Write tower data?

    @property
    def actual_seed1(self) -> int:
        """Return the random seed, generating one if set to -1."""
        if self.rand_seed1 == -1:
            return random.randint(1, 2147483647)
        return self.rand_seed1


def _flag(value: bool) -> str:
    """Convert a boolean to TurbSim flag format."""
    return "True" if value else "False"


def _q(value: str) -> str:
    """Wrap a string value in double quotes for TurbSim."""
    return f'"{value}"'


def _ln(value: str, name: str, comment: str) -> str:
    """Format a single TurbSim input line: value + name + comment.

    Matches the reference format with value right-justified in a 14-char
    field, followed by three spaces and the parameter name.
    """
    return f"{value:>14s}   {name:<16s}- {comment}"


class TurbSimGenerator:
    """Generates TurbSim input files for wind field generation."""

    def generate_turbsim_input(self, config: TurbSimConfig) -> str:
        """Generate the TurbSim input file.

        The output follows the EXACT line-by-line structure of the
        OpenFAST v4.x reference file (docs/source/user/turbsim/examples/TurbSim.inp).
        TurbSim reads positionally — every line must be present in the
        correct order.

        Parameters
        ----------
        config : TurbSimConfig
            Complete TurbSim configuration.

        Returns
        -------
        str
            Complete TurbSim input file content.
        """
        lines: list[str] = []
        a = lines.append

        # --- Header (2 lines exactly) ---
        a("---------TurbSim v2 (OpenFAST) Input File------------------")
        a("Generated by WindForge for IEC wind turbine load analysis")

        # --- Runtime Options (lines 3-16 in the reference) ---
        a("--------Runtime Options-----------------------------------")
        a(_ln(_flag(config.echo), "Echo", "Echo input data to <RootName>.ech (flag)"))
        a(_ln(str(config.actual_seed1), "RandSeed1", "First random seed  (-2147483648 to 2147483647)"))
        a(_ln(_q(config.rand_seed2), "RandSeed2", 'Second random seed (-2147483648 to 2147483647) for intrinsic pRNG, or an alternative pRNG: "RanLux" or "RNSNLW"'))
        a(_ln(_flag(config.wrap_files), "WrBHHTP", "Output hub-height turbulence parameters in binary form?  (Generates RootName.bin)"))
        a(_ln(_flag(False), "WrFHHTP", "Output hub-height turbulence parameters in formatted form?  (Generates RootName.dat)"))
        a(_ln(_flag(False), "WrADHH", "Output hub-height time-series data in AeroDyn form?  (Generates RootName.hh)"))
        a(_ln(_flag(config.wr_bts), "WrADFF", "Output full-field time-series data in TurbSim/AeroDyn form? (Generates RootName.bts)"))
        a(_ln(_flag(config.wr_bladed), "WrBLFF", "Output full-field time-series data in BLADED/AeroDyn form?  (Generates RootName.wnd)"))
        a(_ln(_flag(config.wr_twrs), "WrADTWR", "Output tower time-series data? (Generates RootName.twr)"))
        a(_ln(_flag(config.wr_hawc), "WrHAWCFF", "Output full-field time-series data in HAWC form?  (Generates RootName-u.bin, RootName-v.bin, RootName-w.bin, RootName.hawc)"))
        a(_ln(_flag(config.wr_formatted), "WrFMTFF", "Output full-field time-series data in formatted (readable) form?  (Generates RootName.u, RootName.v, RootName.w)"))
        a(_ln(_flag(False), "WrACT", "Output coherent turbulence time steps in AeroDyn form? (Generates RootName.cts)"))
        a(_ln("0", "ScaleIEC", "Scale IEC turbulence models to exact target standard deviation? [0=no additional scaling; 1=use hub scale uniformly; 2=use individual scales]"))
        a("")

        # --- Turbine/Model Specifications (lines 18-28 in the reference) ---
        a("--------Turbine/Model Specifications-----------------------")
        a(_ln(str(config.num_grid_z), "NumGrid_Z", "Vertical grid-point matrix dimension"))
        a(_ln(str(config.num_grid_y), "NumGrid_Y", "Horizontal grid-point matrix dimension"))
        a(_ln(f"{config.time_step:.4f}", "TimeStep", "Time step [seconds]"))
        a(_ln(f"{config.analysis_time:.1f}", "AnalysisTime", "Length of analysis time series [seconds] (program will add time if necessary: AnalysisTime = MAX(AnalysisTime, UsableTime+GridWidth/MeanHHWS) )"))
        a(_ln(_q(config.usable_time), "UsableTime", 'Usable length of output time series [seconds] (program will add GridWidth/MeanHHWS seconds unless UsableTime is "ALL")'))
        a(_ln(f"{config.hub_ht:.1f}", "HubHt", "Hub height [m] (should be > 0.5*GridHeight)"))
        a(_ln(f"{config.grid_height:.1f}", "GridHeight", "Grid height [m]"))
        a(_ln(f"{config.grid_width:.1f}", "GridWidth", "Grid width [m] (should be >= 2*(RotorRadius+ShaftLength))"))
        a(_ln(f"{config.v_flow_ang:.1f}", "VFlowAng", "Vertical mean flow (uptilt) angle [degrees]"))
        a(_ln(f"{config.h_flow_ang:.1f}", "HFlowAng", "Horizontal mean flow (skew) angle [degrees]"))
        a("")

        # --- Meteorological Boundary Conditions (lines 30-43 in the reference) ---
        a("--------Meteorological Boundary Conditions-------------------")
        a(_ln(_q(config.turb_model.value), "TurbModel", 'Turbulence model ("IECKAI","IECVKM","GP_LLJ","NWTCUP","SMOOTH","WF_UPW","WF_07D","WF_14D","TIDAL","API","USRINP","USRVKM","TIMESR", or "NONE")'))
        a(f'{_q("unused") + ", " + _q("unused"):>40s}   {"UserFile":<16s}- Name of the file that contains inputs for user-defined spectra or time series inputs (used only for "USRINP" and "TIMESR" models)')
        a(_ln(_q(config.iec_standard), "IECstandard", 'Number of IEC 61400-x standard (x=1,2, or 3 with optional 61400-1 edition number (i.e. "1-Ed2") )'))
        a(_ln(_q(config.iec_turbc), "IECturbc", 'IEC turbulence characteristic ("A", "B", "C" or the turbulence intensity in percent) ("KHTEST" option with NWTCUP model, not used for other models)'))
        a(_ln(_q(config.iec_wind_type), "IEC_WindType", 'IEC turbulence type ("NTM"=normal, "xETM"=extreme turbulence, "xEWM1"=extreme 1-year wind, "xEWM50"=extreme 50-year wind, where x=wind turbine class 1, 2, or 3)'))
        a(_ln(_q(config.etm_c), "ETMc", 'IEC Extreme Turbulence Model "c" parameter [m/s]'))
        a(_ln(_q(config.wind_profile_type), "WindProfileType", 'Velocity profile type ("LOG";"PL"=power law;"JET";"H2L"=Log law for TIDAL model;"API";"USR";"TS";"IEC"=PL on rotor disk, LOG elsewhere; or "default")'))
        a(f'{_q(config.profile_file):>40s}   {"ProfileFile":<16s}- Name of the file that contains input profiles for WindProfileType="USR" and/or TurbModel="USRVKM" [-]')
        a(_ln(f"{config.ref_ht:.1f}", "RefHt", "Height of the reference velocity (URef) [m]"))
        a(_ln(f"{config.u_ref:.2f}", "URef", 'Mean (total) velocity at the reference height [m/s] (or "default" for JET velocity profile) [must be 1-hr mean for API model; otherwise is the mean over AnalysisTime seconds]'))
        a(_ln(_q(config.z_jet), "ZJetMax", "Jet height [m] (used only for JET velocity profile, valid 70-490 m)"))
        a(_ln(_q(config.pl_exp), "PLExp", 'Power law exponent [-] (or "default")'))
        a(_ln(_q(config.z0), "Z0", 'Surface roughness length [m] (or "default")'))
        a("")

        # --- Non-IEC Meteorological Boundary Conditions (lines 45-52 in the reference) ---
        a("--------Non-IEC Meteorological Boundary Conditions------------")
        a(_ln(_q(config.latitude), "Latitude", 'Site latitude [degrees] (or "default")'))
        a(_ln(f"{config.rich_no:.2f}", "RICH_NO", "Gradient Richardson number [-]"))
        a(_ln(_q(config.usr_vkm), "UStar", 'Friction or shear velocity [m/s] (or "default")'))
        a(_ln(_q(config.usr_vkm_l), "ZI", 'Mixing layer depth [m] (or "default")'))
        a(_ln(_q(config.ustar_file), "PC_UW", 'Hub mean u\'w\' Reynolds stress [m^2/s^2] (or "default" or "none")'))
        a(_ln(_q(config.ustar_profile), "PC_UV", 'Hub mean u\'v\' Reynolds stress [m^2/s^2] (or "default" or "none")'))
        a(_ln(_q("default"), "PC_VW", 'Hub mean v\'w\' Reynolds stress [m^2/s^2] (or "default" or "none")'))
        a("")

        # --- Spatial Coherence Parameters (lines 54-61 in the reference) ---
        a("--------Spatial Coherence Parameters----------------------------")
        a(_ln(_q(config.scy_lux), "SCMod1", 'u-component coherence model ("GENERAL","IEC","API","NONE", or "default")'))
        a(_ln(_q(config.incdc1), "SCMod2", 'v-component coherence model ("GENERAL","IEC","NONE", or "default")'))
        a(_ln(_q(config.incdc2), "SCMod3", 'w-component coherence model ("GENERAL","IEC","NONE", or "default")'))
        a(_ln(_q(config.coh_exp), "InCDec1", 'u-component coherence parameters for general or IEC models [-, m^-1] (e.g. "10.0  0.3e-3" in quotes) (or "default")'))
        a(_ln(_q("default"), "InCDec2", 'v-component coherence parameters for general or IEC models [-, m^-1] (e.g. "10.0  0.3e-3" in quotes) (or "default")'))
        a(_ln(_q("default"), "InCDec3", 'w-component coherence parameters for general or IEC models [-, m^-1] (e.g. "10.0  0.3e-3" in quotes) (or "default")'))
        a(_ln(_q("default"), "CohExp", 'Coherence exponent for general model [-] (or "default")'))
        a("")

        # --- Coherent Turbulence Scaling Parameters (lines 63-70 in the reference) ---
        a("--------Coherent Turbulence Scaling Parameters------------------- [used only when WrACT=TRUE]")
        a(f'{_q(config.ct_event_path):>40s}   {"CTEventPath":<16s}- Name of the path where event data files are located')
        a(_ln(_q(config.ct_event_file), "CTEventFile", 'Type of event files ("LES", "DNS", or "RANDOM")'))
        a(_ln(_flag(config.randomize).lower(), "Randomize", "Randomize the disturbance scale and locations? (true/false)"))
        a(_ln("1", "DistScl", "Disturbance scale [-] (ratio of event dataset height to rotor disk). (Ignored when Randomize = true.)"))
        a(_ln("0.5", "CTLy", "Fractional location of tower centerline from right [-] (looking downwind) to left side of the dataset. (Ignored when Randomize = true.)"))
        a(_ln("0.5", "CTLz", "Fractional location of hub height from the bottom of the dataset. [-] (Ignored when Randomize = true.)"))
        a(_ln("10", "CTStartTime", "Minimum start time for coherent structures in RootName.cts [seconds]"))
        a("")

        return "\n".join(lines) + "\n"
