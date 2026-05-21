use anyhow::Result;
use biotrack::cli::commands::Cli;
use clap::Parser;

fn main() -> Result<()> {
    let cli = Cli::parse();
    biotrack::run(cli)
}
