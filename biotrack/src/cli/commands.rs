use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "biotrack")]
#[command(version, about, long_about = None)]
#[command(propagate_version = true)]
pub struct Cli {

    #[arg(short, long, action = clap::ArgAction::Count, global = true)]
    pub verbose: u8,

    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Debug, Subcommand)]
pub enum Commands {

    Scan {

        #[arg(default_value = ".")]
        path: PathBuf,


        #[arg(short, long)]
        config: Option<PathBuf>,


        #[arg(long, default_value_t = false)]
        full: bool,


        #[arg(long, default_value_t = false)]
        dry_run: bool,
    },


    Status {

        #[arg(default_value = ".")]
        path: PathBuf,


        #[arg(short, long)]
        config: Option<PathBuf>,
    },


    Init {

        #[arg(default_value = ".")]
        path: PathBuf,
    },


    Tree {

        #[arg(default_value = ".")]
        path: PathBuf,


        #[arg(short, long)]
        config: Option<PathBuf>,


        #[arg(short = 'd', long)]
        max_depth: Option<usize>,


        #[arg(long, default_value_t = true)]
        classify: bool,
    },
}