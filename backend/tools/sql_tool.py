import sqlite3
import pandas as pd
from typing import Dict, Any


def execute_sql(query: str, df: pd.DataFrame, table_name: str = "data") -> Dict[str, Any]:
    """
    Loads the DataFrame into an in-memory SQLite table and runs the SQL query.
    Returns the tabular rows, column headers, and execution status.
    """
    cleaned_query = query.strip()
    if cleaned_query.startswith("```sql"):
        cleaned_query = cleaned_query[len("```sql"):].strip()
    elif cleaned_query.startswith("```"):
        cleaned_query = cleaned_query[len("```"):].strip()
    if cleaned_query.endswith("```"):
        cleaned_query = cleaned_query[:-3].strip()

    conn = sqlite3.connect(":memory:")
    try:
        # Sanitize column names for SQLite (replace spaces, special chars)
        safe_df = df.copy()
        safe_df.columns = [c.strip().replace(" ", "_").replace("-", "_").lower() for c in safe_df.columns]
        safe_df.to_sql(table_name, conn, if_exists="replace", index=False)

        cursor = conn.cursor()
        cursor.execute(cleaned_query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        
        records = [dict(zip(columns, row)) for row in rows]
        
        return {
            "success": True,
            "columns": columns,
            "row_count": len(rows),
            "rows": rows[:100],  # cap at 100 for safety
            "records": records[:100],
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "row_count": 0,
            "rows": [],
            "records": [],
            "error": str(e),
        }
    finally:
        conn.close()
