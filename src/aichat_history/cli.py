"""CLI entry point for aichat-history."""

import click
import uvicorn


@click.group()
def main():
    """Browse AI coding chat history from Cursor, Claude Code, and OpenCode."""
    pass


@main.command()
@click.option("--port", default=8080, help="Port to serve on.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
def serve(port: int, host: str):
    """Start the web interface."""
    click.echo(f"Starting aichat-history on http://{host}:{port}")
    uvicorn.run("aichat_history.server:app", host=host, port=port, reload=False)
