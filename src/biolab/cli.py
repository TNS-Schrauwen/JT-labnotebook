"""CLI interface for JT-labnotebook."""
import typer

app = typer.Typer(
    name="biolab",
    help="JT Lab Notebook — Bioinformatics Project Intelligence System",
    no_args_is_help=True,
)

@app.command()
def status():
    """Show notebook status."""
    typer.echo("JT-labnotebook is working!")

if __name__ == "__main__":
    app()
