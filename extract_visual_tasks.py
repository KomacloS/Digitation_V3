import argparse
import platform
import subprocess
import sys
from typing import Dict

import pandas as pd

DRIVER = r"{Microsoft Access Driver (*.mdb, *.accdb)}"


def _load_with_pyodbc(path: str) -> pd.DataFrame:
    import pyodbc  # type: ignore

    conn_str = f"DRIVER={DRIVER};DBQ={path}"
    with pyodbc.connect(conn_str) as conn:
        query = (
            "SELECT Section, [Key], Value FROM InitInfo "
            "WHERE Section='Visual Tasks';"
        )
        return pd.read_sql(query, conn)


def _load_with_mdbtools(path: str) -> pd.DataFrame:
    try:
        result = subprocess.run(
            ["mdb-export", path, "InitInfo"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "mdb-export not found. Please install mdbtools via apt/brew."
        ) from exc
    data = pd.read_csv(pd.compat.StringIO(result.stdout))
    return data[data["Section"] == "Visual Tasks"][["Section", "Key", "Value"]]


def extract_visual_tasks(path: str) -> pd.DataFrame:
    if platform.system() == "Windows":
        try:
            return _load_with_pyodbc(path)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Failed to read MDB using ODBC. Ensure the Access ODBC driver is installed."
            ) from exc
    else:
        return _load_with_mdbtools(path)


def extract_visual_task_dict(path: str) -> Dict[str, str]:
    df = extract_visual_tasks(path)
    return dict(zip(df["Key"], df["Value"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Visual Tasks from MDB")
    parser.add_argument("mdb_path", help="Path to .mdb file")
    args = parser.parse_args()

    df = extract_visual_tasks(args.mdb_path)
    if df.empty:
        print("No Visual Tasks rows found.")
        sys.exit(1)

    try:
        from tabulate import tabulate  # type: ignore

        print(tabulate(df, headers="keys", tablefmt="psql", showindex=False))
    except Exception:
        print(df.to_string(index=False))




if __name__ == "__main__":
    main()
