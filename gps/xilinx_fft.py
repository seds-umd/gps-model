import ctypes
import os
import sys
import numpy as np
from pathlib import Path


def _load_cmodel():
    """Load Xilinx's bit-accurate FFT model for this platform.

    The Linux x86_64 library is packaged in cmodel/fft. The Windows build is
    not: it ships with Vivado as
    <Vivado>/data/ip/xilinx/xfft_v9_1/cmodel/xfft_v9_1_bitacc_cmodel_nt64.zip.
    Copy the four DLLs from that archive into cmodel/fft, or unpack it anywhere
    and set XFFT_CMODEL_DIR to the folder.
    """
    directory = Path(os.environ.get("XFFT_CMODEL_DIR") or Path(__file__).parent / "cmodel" / "fft")

    if sys.platform == "win32":
        library = directory / "libIp_xfft_v9_1_bitacc_cmodel.dll"
        if not library.exists():
            raise OSError(
                f"{library} not found. The Windows FFT model ships with Vivado in "
                "data/ip/xilinx/xfft_v9_1/cmodel/xfft_v9_1_bitacc_cmodel_nt64.zip: copy its DLLs into "
                f"{directory} or set XFFT_CMODEL_DIR."
            )
        # The model depends on libgmp, libmpfr and the floating-point model beside it.
        os.add_dll_directory(str(directory))
        return ctypes.CDLL(str(library))

    if sys.platform != "linux":
        raise OSError(f"Xilinx provides the FFT bit-accurate model for Linux and Windows only, not {sys.platform}")
    # Keep a reference to libgmp: the model resolves its symbols from it.
    global _gmp
    _gmp = ctypes.CDLL(str(directory / "libgmp.so.11"))
    return ctypes.CDLL(str(directory / "libIp_xfft_v9_1_bitacc_cmodel.so"))


_gmp = None
_fft_cmodel = _load_cmodel()

class FftGenerics(ctypes.Structure):
    C_NFFT_MAX: ctypes.c_int
    C_ARCH: ctypes.c_int
    C_HAS_NFFT: ctypes.c_int
    C_USE_FLT_PT: ctypes.c_int
    C_INPUT_WIDTH: ctypes.c_int
    C_TWIDDLE_WIDTH: ctypes.c_int
    C_HAS_SCALING: ctypes.c_int
    C_HAS_BFP: ctypes.c_int
    C_HAS_ROUNDING: ctypes.c_int
    C_NSSR: ctypes.c_int
    C_SYSTOLICFFT_INV: ctypes.c_int

    # Newer releases of the model (the one in Vivado 2025.2, for example) append
    # C_NSSR and C_SYSTOLICFFT_INV. The structure is passed and returned by
    # value in memory, so an older library simply never looks at the extra words.
    _fields_ = [
        ("C_NFFT_MAX", ctypes.c_int),
        ("C_ARCH", ctypes.c_int),
        ("C_HAS_NFFT", ctypes.c_int),
        ("C_USE_FLT_PT", ctypes.c_int),
        ("C_INPUT_WIDTH", ctypes.c_int),
        ("C_TWIDDLE_WIDTH", ctypes.c_int),
        ("C_HAS_SCALING", ctypes.c_int),
        ("C_HAS_BFP", ctypes.c_int),
        ("C_HAS_ROUNDING", ctypes.c_int),
        ("C_NSSR", ctypes.c_int),
        ("C_SYSTOLICFFT_INV", ctypes.c_int),
    ]

class FftState(ctypes.Structure):
    pass

class FftInputs(ctypes.Structure):
    nfft: ctypes.c_int
    xn_re: ctypes.POINTER(ctypes.c_double)
    xn_re_size: int
    xn_im: ctypes.POINTER(ctypes.c_double)
    xn_im_size: ctypes.c_int
    scaling_sch: ctypes.POINTER(ctypes.c_int)
    scaling_sch_size: ctypes.c_int
    direction: ctypes.c_int

    _fields_ = [
        ("nfft", ctypes.c_int),
        ("xn_re", ctypes.POINTER(ctypes.c_double)),
        # ("xn_re", np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C')),
        ("xn_re_size", ctypes.c_int),
        ("xn_im", ctypes.POINTER(ctypes.c_double)),
        # ("xn_im", np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C')),
        ("xn_im_size", ctypes.c_int),
        ("scaling_sch", ctypes.POINTER(ctypes.c_int)),
        ("scaling_sch_size", ctypes.c_int),
        ("direction", ctypes.c_int),
    ]

class FftOutputs(ctypes.Structure):
    xk_re: ctypes.POINTER(ctypes.c_double)
    xk_re_size: int
    xk_im: ctypes.POINTER(ctypes.c_double)
    xk_im_size: ctypes.c_int
    blk_exp: ctypes.c_int
    overflow: ctypes.c_int

    _fields_ = [
        ("xk_re", ctypes.POINTER(ctypes.c_double)),
        ("xk_re_size", ctypes.c_int),
        ("xk_im", ctypes.POINTER(ctypes.c_double)),
        ("xk_im_size", ctypes.c_int),
        ("blk_exp", ctypes.c_int),
        ("overflow", ctypes.c_int),
    ]

_fft_cmodel.xilinx_ip_xfft_v9_1_get_default_generics.restype = FftGenerics

_fft_cmodel.xilinx_ip_xfft_v9_1_create_state.argtypes = [FftGenerics]
_fft_cmodel.xilinx_ip_xfft_v9_1_create_state.restype = ctypes.POINTER(FftState)

_fft_cmodel.xilinx_ip_xfft_v9_1_destroy_state.argtypes = [ctypes.POINTER(FftState)]

_fft_cmodel.xilinx_ip_xfft_v9_1_bitacc_simulate.argtypes = [ctypes.POINTER(FftState), FftInputs, ctypes.POINTER(FftOutputs)]
_fft_cmodel.xilinx_ip_xfft_v9_1_bitacc_simulate.restype = ctypes.c_int

class Fft:
    def __init__(self, size=6, arch=2, input_width=8, twiddle_width=10):
        """Configure and create FFT state.

        Args:
            size (int, optional): log2 of FFT width. Defaults to 6.
            arch (int, optional): 1=radix 4, 2=radix 2, 3=pipelined, 4=radix 2 lite. Defaults to 2.
            input_width (int, optional): Input width, 8-34. Defaults to 8.
            twiddle_width (int, optional): Twiddle width, 8-34. Defaults to 10.
        """

        self.generics: FftGenerics = _fft_cmodel.xilinx_ip_xfft_v9_1_get_default_generics()

        self.generics.C_NFFT_MAX = size
        self.generics.C_ARCH = arch
        self.generics.C_HAS_NFFT = 0
        self.generics.C_USE_FLT_PT = 0
        self.generics.C_INPUT_WIDTH = input_width
        self.generics.C_TWIDDLE_WIDTH = twiddle_width
        self.generics.C_HAS_SCALING = 1
        self.generics.C_HAS_BFP = 1
        self.generics.C_HAS_ROUNDING = 1
        # One sample per clock (no super-sample-rate), forward/inverse chosen per run.
        self.generics.C_NSSR = 1
        self.generics.C_SYSTOLICFFT_INV = 0

        self.state = _fft_cmodel.xilinx_ip_xfft_v9_1_create_state(self.generics)

        self.inputs = FftInputs()
        self.outputs = FftOutputs()

        self.output_re = np.zeros(2**size, dtype=np.float64)
        self.output_im = np.zeros(2**size, dtype=np.float64)

        self.outputs.xk_re = np.ctypeslib.as_ctypes(self.output_re)
        self.outputs.xk_im = np.ctypeslib.as_ctypes(self.output_im)
        self.outputs.xk_re_size = len(self.output_re)
        self.outputs.xk_im_size = len(self.output_im)
    
    def __del__(self):
        _fft_cmodel.xilinx_ip_xfft_v9_1_destroy_state(self.state)

    def run(self, x: np.ndarray, inv=False) -> np.ndarray:
        """Perform FFT. Input values must be in range -1 <= x < 1.

        Args:
            x (np.ndarray): Input values. Must match FFT size and be type complex128.

        Returns:
            np.ndarray: Output values.
        """        
        
        self.inputs.nfft = int(np.log2(len(x)))
        self.inputs.xn_re = np.ctypeslib.as_ctypes(x.real.astype(np.float64))
        self.inputs.xn_im = np.ctypeslib.as_ctypes(x.imag.astype(np.float64))
        self.inputs.xn_re_size = len(x)
        self.inputs.xn_im_size = len(x)
        self.inputs.direction = 0 if inv else 1

        res = _fft_cmodel.xilinx_ip_xfft_v9_1_bitacc_simulate(self.state, self.inputs, ctypes.byref(self.outputs))
        assert res == 0, "FFT Error"

        return self.output_re + self.output_im * 1j
