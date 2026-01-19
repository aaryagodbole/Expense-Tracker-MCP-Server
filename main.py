from fastmcp import FastMCP
import os
import json
import aiosqlite
import tempfile
import sqlite3
from typing import Optional

# -----------------------------
# Paths (FastMCP-safe)
# -----------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

print(f"[INIT] Database path: {DB_PATH}")

# -----------------------------
# MCP App
# -----------------------------
mcp = FastMCP("ExpenseTracker")

# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
                """
            )
        print("[INIT] Database initialized successfully")
    except Exception as e:
        print(f"[INIT ERROR] Database init failed: {e}")
        raise

init_db()

# -----------------------------
# Tools
# -----------------------------
@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: Optional[str] = None,
    note: Optional[str] = None,
):
    """Add a new expense entry to the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                """
                INSERT INTO expenses (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    date,
                    amount,
                    category,
                    subcategory or "",
                    note or "",
                ),
            )
            await db.commit()
            return {
                "status": "success",
                "id": cur.lastrowid,
                "message": "Expense added successfully",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def list_expenses(
    start_date: str,
    end_date: str,
):
    """List expense entries within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date),
            )
            rows = await cur.fetchall()
            cols = [col[0] for col in cur.description]
            return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: Optional[str] = None,
):
    """Summarize expenses by category within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cur = await db.execute(query, params)
            rows = await cur.fetchall()
            cols = [col[0] for col in cur.description]
            return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -----------------------------
# Resource
# -----------------------------
@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    try:
        if os.path.exists(CATEGORIES_PATH):
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()

        # fallback
        return json.dumps(
            {
                "categories": [
                    "food",
                    "transport",
                    "housing",
                    "utilities",
                    "health",
                    "education",
                    "shopping",
                    "entertainment",
                    "travel",
                    "business",
                    "misc",
                ]
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

# -----------------------------
# Export for FastMCP Cloud
# -----------------------------
app = mcp

# -----------------------------
# Local run (ignored in cloud)
# -----------------------------
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
