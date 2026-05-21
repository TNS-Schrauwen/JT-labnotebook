use anyhow::Result;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::{EnvFilter, Layer};

pub fn init(verbosity: u8) -> Result<()> {
    let env_filter = match verbosity {
        0 => EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| EnvFilter::new("warn")),
        1 => EnvFilter::new("biotrack=info,warn"),
        2 => EnvFilter::new("biotrack=debug,info"),
        3 => EnvFilter::new("trace"),
        _ => EnvFilter::new("trace"),
    };


    let fmt_layer = tracing_subscriber::fmt::layer()
        .with_target(verbosity >= 2)
        .with_thread_ids(verbosity >= 3)
        .with_file(verbosity >= 3)
        .with_line_number(verbosity >= 3)
        .compact()
        .with_filter(env_filter);

    tracing_subscriber::registry()
        .with(fmt_layer)
        .init();

    Ok(())
}