from setuptools import setup

setup(
    name="gps-model",
    version='0.1',
    packages=["gps"],
    package_data={"": ["cmodel/fft/libgmp.so.11", "cmodel/fft/libIp_xfft_v9_1_bitacc_cmodel.so"]}
)
