import ctypes
import numpy as np

_gmp = ctypes.CDLL("gps/cmodel/libgmp.so.11")
_fft_cmodel = ctypes.CDLL("gps/cmodel/libIp_xfft_v9_1_bitacc_cmodel.so")

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
        self.generics.C_HAS_ROUNDING = 0

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
