"""CLI script to read a Parquet file and display its contents in the terminal.

Supports both local file paths and S3 URIs (s3://bucket/key).

Usage:
    python read_parquet.py path/to/file.parquet
    python read_parquet.py s3://my-bucket/processed/file.parquet
    python read_parquet.py --list-files s3://my-bucket/processed/
"""

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq
import typer
from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

S3_URI_PATTERN = re.compile(r"^s3://(?P<bucket>[^/]+)/(?P<key>.+)$")
S3_BUCKET_PATTERN = re.compile(r"^s3://(?P<bucket>[^/]+)/?(?P<prefix>.*)$")

console = Console()
app = typer.Typer(help="Read a Parquet file and display its contents in the terminal.")


def _read_local(file_path: Path) -> pd.DataFrame:
    """Read a local Parquet file.

    Args:
        file_path: Path to the local Parquet file.

    Returns:
        DataFrame containing the file contents.

    Raises:
        typer.Exit: If the file does not exist or cannot be read.
    """
    if not file_path.exists():
        console.print(f"[bold red]ERROR:[/] File not found: {file_path}")
        raise typer.Exit(code=1)

    try:
        return pq.read_table(file_path).to_pandas()
    except Exception as exc:
        console.print(f"[bold red]ERROR:[/] Failed to read Parquet file: {exc}")
        raise typer.Exit(code=1)


def _read_s3(bucket: str, key: str) -> pd.DataFrame:
    """Download and read a Parquet file from S3.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        DataFrame containing the file contents.

    Raises:
        typer.Exit: If the object cannot be fetched or parsed.
    """
    import io

    import boto3
    import botocore.exceptions

    s3 = boto3.client("s3")

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
    except botocore.exceptions.ClientError as exc:
        console.print(f"[bold red]ERROR:[/] Could not fetch s3://{bucket}/{key}: {exc}")
        raise typer.Exit(code=1)

    try:
        return pq.read_table(io.BytesIO(body)).to_pandas()
    except Exception as exc:
        console.print(f"[bold red]ERROR:[/] Failed to parse Parquet data: {exc}")
        raise typer.Exit(code=1)


def _list_s3(bucket: str, prefix: str) -> None:
    """List all Parquet files under an S3 bucket/prefix.

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix to filter by (may be empty string).

    Raises:
        typer.Exit: If the bucket cannot be accessed.
    """
    import boto3
    import botocore.exceptions

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    try:
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        objects = [
            obj
            for page in pages
            for obj in page.get("Contents", [])
            if obj["Key"].endswith(".parquet")
        ]
    except botocore.exceptions.ClientError as exc:
        console.print(f"[bold red]ERROR:[/] Could not list s3://{bucket}/{prefix}: {exc}")
        raise typer.Exit(code=1)

    if not objects:
        console.print(f"[yellow]No .parquet files found under s3://{bucket}/{prefix}[/]")
        return

    table = Table(
        title=f"s3://{bucket}/{prefix or ''}",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Key", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Last Modified", style="dim")

    for obj in objects:
        size_kb = f"{obj['Size'] / 1024:.1f} KB"
        modified = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S")
        table.add_column if False else None  # guard
        table.add_row(f"s3://{bucket}/{obj['Key']}", size_kb, modified)

    console.print(table)
    console.print(f"\n[bold]{len(objects)} file(s)[/]")


def _print_schema(df: pd.DataFrame) -> None:
    """Print column names and their dtypes as a rich table.

    Args:
        df: DataFrame whose schema to display.
    """
    table = Table(title="Schema", box=box.ROUNDED, show_lines=False)
    table.add_column("Column", style="cyan")
    table.add_column("Type", style="green")

    for col, dtype in df.dtypes.items():
        table.add_row(str(col), str(dtype))

    console.print(table)


def _print_data(df: pd.DataFrame) -> None:
    """Print DataFrame rows as a rich table.

    Args:
        df: DataFrame to display.
    """
    table = Table(title="Data", box=box.ROUNDED, show_lines=False)
    table.add_column("#", style="dim", justify="right")

    for col in df.columns:
        table.add_column(str(col), style="cyan")

    for idx, row in df.iterrows():
        table.add_row(str(idx), *[str(v) for v in row])

    console.print(table)
    console.print(f"\n[bold]{df.shape[0]} rows × {df.shape[1]} columns[/]")


@app.command()
def main(
    file: Optional[str] = typer.Argument(
        default=None, help="Local path or S3 URI (s3://bucket/key) to a .parquet file."
    ),
    list_files: Optional[str] = typer.Option(
        default=None,
        help="List all .parquet files under an S3 URI (s3://bucket or s3://bucket/prefix/).",
        metavar="S3_URI",
    ),
) -> None:
    """Read a Parquet file and display its schema and data."""
    if list_files is not None:
        match = S3_BUCKET_PATTERN.match(list_files)
        if not match:
            console.print(
                f"[bold red]ERROR:[/] --list-files value must be an S3 URI, got: {list_files}"
            )
            raise typer.Exit(code=1)
        _list_s3(bucket=match.group("bucket"), prefix=match.group("prefix"))
        return

    if file is None:
        console.print(
            "[bold red]ERROR:[/] provide a file path or use --list-files to browse the bucket."
        )
        raise typer.Exit(code=1)

    s3_match = S3_URI_PATTERN.match(file)
    if s3_match:
        df = _read_s3(bucket=s3_match.group("bucket"), key=s3_match.group("key"))
    else:
        df = _read_local(Path(file))

    _print_schema(df)
    _print_data(df)


if __name__ == "__main__":
    app()
