use criterion::{criterion_group, criterion_main, Criterion};
use std::hint::black_box;

use gps_rust::*;

fn criterion_benchmark(c: &mut Criterion) {
    c.bench_function("prn_sample", |b| {
        b.iter(|| {
            prn::sample(
                black_box(20),
                black_box(4.092e6),
                black_box(4.092e6 as usize),
                black_box(0),
                black_box(0.0),
            )
        })
    });

    c.bench_function("generate_channel", |b| {
        b.iter(|| {
            sim::generate_channel(
                black_box(20),
                black_box(4.092e6),
                black_box(4.092e6 as usize),
                black_box(100.0),
                black_box(-10.0),
                black_box(0),
                black_box(0.0),
            )
        })
    });

    let configs = sim::random_config(8, 4.0, 5e3);
    c.bench_function("generate_signal", |b| {
        b.iter(|| sim::generate_signal(black_box(4.092e6), black_box(4.092e6 as usize), configs.clone()))
    });
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
