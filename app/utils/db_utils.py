# app/repository/db_utils.py
"""
Utility functions for performing direct SQL queries using SQLAlchemy.
"""

from sqlalchemy import text
from app.config.datasource_config import SessionLocal

async def fetch_one(query: str, params: dict | None = None):
    """
    Executes a single SQL query and fetches the first result.

    This function uses SQLAlchemy to execute the provided SQL query asynchronously.
    It returns the first result of the query as a mapping (dictionary-like object).

    Args:
        query (str): The SQL query to execute.
        params (dict | None, optional): A dictionary of parameters to bind to the query. Defaults to None.

    Returns:
        Mapping or None: The first result of the query as a mapping, or None if no results are found.

    Example:
        result = await fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
        print(result)  # Output: {'id': 1, 'name': 'John Doe'}
    """
    async with SessionLocal() as session:
        result = await session.execute(text(query), params or {})
        return result.mappings().first()

async def fetch_all(query: str, params: dict | None = None):
    async with SessionLocal() as session:
        result = await session.execute(text(query), params or {})
        return result.mappings().all()

async def execute_query(query: str, params: dict | None = None):
    async with SessionLocal() as session:
        await session.execute(text(query), params or {})
        await session.commit()
