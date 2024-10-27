use pyo3::prelude::*;

pub mod prn;
pub mod sim;

#[pymodule]
fn rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    prn::register_module(&m)?;
    sim::register_module(&m)?;
    Ok(())
}
