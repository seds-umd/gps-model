use crate::prn;
use numpy::{Complex32, PyArray1, ToPyArray};
use pyo3::prelude::*;
use rand::prelude::*;
use rayon::prelude::*;
use std::f32::consts::PI;

pub fn generate_channel(
    sv: u8,
    fs: f32,
    len: usize,
    doppler: f32,
    doppler_rate: f32,
    code_phase: u16,
    sample_phase: f32,
) -> Vec<Complex32> {
    let code = prn::sample(sv, fs, len, code_phase, sample_phase);

    let block = (fs / 50.0).ceil() as usize;

    let mut rng = rand::thread_rng();
    let bits: Vec<bool> = (0..len / block).map(|_| rng.gen_bool(0.5)).collect();

    let samples = (0..len)
        .map(|i| {
            let mut x = code[i % code.len()];

            if bits[i / block] {
                x *= -1.0;
            }

            let t = (i as f32) / fs;
            x * Complex32::new(0.0, 2.0 * PI * (doppler + t * doppler_rate) * t).exp()
        })
        .collect();

    samples
}

#[pyfunction]
#[pyo3(name = "generate_channel")]
fn generate_channel_py<'py>(
    py: Python<'py>,
    sv: u8,
    fs: f32,
    len: usize,
    doppler: f32,
    doppler_rate: f32,
    code_phase: u16,
    sample_phase: f32,
) -> PyResult<Bound<'py, PyArray1<Complex32>>> {
    Ok(
        generate_channel(sv, fs, len, doppler, doppler_rate, code_phase, sample_phase)
            .to_pyarray_bound(py),
    )
}

#[pyclass]
#[derive(Copy, Clone, Debug)]
pub struct SvConfig {
    #[pyo3(get)]
    sv: u8, // SV number
    #[pyo3(get)]
    power: f32, // Power ratio (nondimensional, result is just multiplied by this)
    #[pyo3(get)]
    phase_offset: u16,
    #[pyo3(get)]
    sample_offset: f32,
    #[pyo3(get)]
    doppler: f32,
    #[pyo3(get)]
    doppler_rate: f32,
}

#[pymethods]
impl SvConfig {
    #[new]
    pub fn new(
        sv: u8,
        power: f32,
        phase_offset: u16,
        sample_offset: f32,
        doppler: f32,
        doppler_rate: f32,
    ) -> Self {
        SvConfig {
            sv: sv,
            power: power,
            phase_offset: phase_offset,
            sample_offset: sample_offset,
            doppler: doppler,
            doppler_rate: doppler_rate,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "SvConfig({:}, {:}, {:}, {:}, {:}, {:})",
            self.sv,
            self.power,
            self.phase_offset,
            self.sample_offset,
            self.doppler,
            self.doppler_rate
        )
    }

    fn __str__(&self) -> String {
        format!("{:?}", self)
    }
}

#[pyfunction]
pub fn random_config(count: u8, power_range: f32, doppler_range: f32) -> Vec<SvConfig> {
    assert!(count <= 32);

    let mut rng = rand::thread_rng();
    let mut svs = (1..33).collect::<Vec<u8>>();
    svs.shuffle(&mut rng);

    (0..count)
        .map(|_| SvConfig {
            sv: svs.pop().unwrap(),
            power: rng.gen_range(-power_range..=power_range).exp2(),
            phase_offset: rng.gen_range(0..=1023),
            sample_offset: 0.0,
            doppler: rng.gen_range(-doppler_range..=doppler_range),
            doppler_rate: 0.0,
        })
        .collect()
}

pub fn generate_signal(fs: f32, len: usize, configs: Vec<SvConfig>) -> Vec<Complex32> {
    configs
        .par_iter()
        .map(|c| {
            generate_channel(
                c.sv,
                fs,
                len,
                c.doppler,
                c.doppler_rate,
                c.phase_offset,
                c.sample_offset,
            )
        })
        .reduce_with(|a, b| a.iter().zip(b.iter()).map(|(x, y)| x + y).collect())
        .unwrap()
}

#[pyfunction]
#[pyo3(name = "generate_signal")]
pub fn generate_signal_py<'py>(
    py: Python<'py>,
    fs: f32,
    len: usize,
    configs: Vec<SvConfig>,
) -> PyResult<Bound<'py, PyArray1<Complex32>>> {
    Ok(generate_signal(fs, len, configs).to_pyarray_bound(py))
}

pub fn register_module<'py>(parent_module: &Bound<'py, PyModule>) -> PyResult<()> {
    let module = PyModule::new_bound(parent_module.py(), "sim")?;
    module.add_function(wrap_pyfunction!(generate_channel_py, &module)?)?;
    module.add_class::<SvConfig>()?;
    module.add_function(wrap_pyfunction!(random_config, &module)?)?;
    module.add_function(wrap_pyfunction!(generate_signal_py, &module)?)?;
    parent_module.add_submodule(&module)
}
