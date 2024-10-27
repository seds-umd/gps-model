use cached::proc_macro::cached;
use numpy::{Complex32, PyArray1, ToPyArray};
use pyo3::prelude::*;

const SV_PARAMS: [[i8; 2]; 33] = [
    [-1, -1], // SV=0 unused
    [2, 6],
    [3, 7],
    [4, 8],
    [5, 9],
    [1, 9],
    [2, 10],
    [1, 8],
    [2, 9],
    [3, 10],
    [2, 3],
    [3, 4],
    [5, 6],
    [6, 7],
    [7, 8],
    [8, 9],
    [9, 10],
    [1, 4],
    [2, 5],
    [3, 6],
    [4, 7],
    [5, 8],
    [6, 9],
    [1, 3],
    [4, 6],
    [5, 7],
    [6, 8],
    [7, 9],
    [8, 10],
    [1, 6],
    [2, 7],
    [3, 8],
    [4, 9],
];

const CODE_LEN: usize = 1023;

fn prn_shift_g1(g1: &mut u16) -> u8 {
    let mut out: u8 = 0;
    out ^= (*g1 >> (10 - 1)) as u8;
    out &= 1;

    let mut fb: u8 = 0;
    fb ^= (*g1 >> (3 - 1)) as u8;
    fb ^= (*g1 >> (10 - 1)) as u8;
    fb &= 1;

    *g1 <<= 1;
    *g1 |= fb as u16;

    out
}

fn prn_shift_g2(g2: &mut u16, sv: u8) -> u8 {
    let mut out: u8 = 0;
    out ^= (*g2 >> (SV_PARAMS[sv as usize][0] - 1)) as u8;
    out ^= (*g2 >> (SV_PARAMS[sv as usize][1] - 1)) as u8;
    out &= 1;

    let mut fb: u8 = 0;
    fb ^= (*g2 >> (2 - 1)) as u8;
    fb ^= (*g2 >> (3 - 1)) as u8;
    fb ^= (*g2 >> (6 - 1)) as u8;
    fb ^= (*g2 >> (8 - 1)) as u8;
    fb ^= (*g2 >> (9 - 1)) as u8;
    fb ^= (*g2 >> (10 - 1)) as u8;
    fb &= 1;

    *g2 <<= 1;
    *g2 |= fb as u16;

    out
}

#[cached]
pub fn generate(sv: u8) -> [i8; CODE_LEN] {
    let mut g1: u16 = 0x3FF;
    let mut g2: u16 = 0x3FF;

    let mut ca: [i8; CODE_LEN] = [0; CODE_LEN];

    for x in ca.iter_mut() {
        let g1_out = prn_shift_g1(&mut g1);
        let g2_out = prn_shift_g2(&mut g2, sv);

        let res = g1_out ^ g2_out;

        // Scale to +- 1
        *x = ((res as i8) << 1) - 1;
    }

    ca
}

#[pyfunction]
#[pyo3(name = "generate")]
fn generate_py<'py>(py: Python<'py>, sv: u8) -> PyResult<Bound<'py, PyArray1<i8>>> {
    Ok(generate(sv).to_pyarray_bound(py))
}

pub fn sample(
    sv: u8,
    fs: f32,
    len: usize,
    offset_phase: u16,
    offset_samples: f32,
) -> Vec<Complex32> {
    let chip_rate: f32 = 1000f32 * CODE_LEN as f32;
    let code = generate(sv);

    (0..len)
        .map(|i| {
            let idx = (((i as f32 + offset_samples) * (chip_rate / fs) + 0.5).floor()
                + offset_phase as f32) as usize
                % CODE_LEN;
            Complex32::new(code[idx] as f32, 0.0)
        })
        .collect()
}

#[pyfunction]
#[pyo3(name = "sample")]
fn sample_py<'py>(
    py: Python<'py>,
    sv: u8,
    fs: f32,
    len: usize,
    offset_phase: u16,
    offset_samples: f32,
) -> PyResult<Bound<'py, PyArray1<Complex32>>> {
    Ok(sample(sv, fs, len, offset_phase, offset_samples).to_pyarray_bound(py))
}

pub fn register_module<'py>(parent_module: &Bound<'py, PyModule>) -> PyResult<()> {
    let prn_module = PyModule::new_bound(parent_module.py(), "prn")?;
    prn_module.add_function(wrap_pyfunction!(generate_py, &prn_module)?)?;
    prn_module.add_function(wrap_pyfunction!(sample_py, &prn_module)?)?;
    parent_module.add_submodule(&prn_module)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prn_generate() {
        let sv = 8;

        let code = generate(sv);

        println!("{:?}", code);

        assert_eq!(code[2], -1);
        assert_eq!(code[8], -1);
        assert_eq!(code[29], 1);
        assert_eq!(code[96], -1);
        assert_eq!(code[238], 1);
        assert_eq!(code[632], 1);
        assert_eq!(code[725], 1);
        assert_eq!(code[983], -1);
        assert_eq!(code[1022], -1);
    }
}
