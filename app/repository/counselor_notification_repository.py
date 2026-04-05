# app/repository/counselor_notification_repository.py
"""
Repository for resolving counselor notification targets from a student user ID.

Flow:
1) Get student program_id and email from users table
2) Resolve college_department_id from college_programs table
3) Find counselor user_ids in same department
"""

from typing import Any, Dict, List
from app.utils.db_utils import fetch_one, fetch_all


class CounselorNotificationRepository:
    """Data access for counselor notification routing."""

    async def resolve_targets_by_student_id(self, student_user_id: str) -> Dict[str, Any]:
        """
        Resolve notification targets for a student.

        Returns:
            {
                "student": {
                    "user_id": str,
                    "email": str | None,
                    "program_id": str | None,
                    "college_department_id": str | None,
                },
                "counselor_user_ids": list[str]
            }
        """
        student_query = """
            SELECT user_id, email, program_id
            FROM student
            WHERE user_id = :student_user_id
            LIMIT 1
        """
        student_row = await fetch_one(student_query, {"student_user_id": student_user_id})

        if not student_row:
            return {
                "student": {
                    "user_id": student_user_id,
                    "email": None,
                    "program_id": None,
                    "college_department_id": None,
                },
                "counselor_user_ids": [],
            }

        student = dict(student_row)
        program_id = student.get("program_id")
        college_department_id = None

        if program_id:
            department_query = """
                SELECT college_department_id
                FROM college_programs
                WHERE program_id = :program_id
                LIMIT 1
            """
            dept_row = await fetch_one(department_query, {"program_id": program_id})
            if dept_row:
                college_department_id = dept_row.get("college_department_id")

        counselor_user_ids: List[str] = []
        if college_department_id:
            counselors_query = """
                SELECT user_id
                FROM counselor
                WHERE department_id = :college_department_id
            """
            counselor_rows = await fetch_all(counselors_query, {"college_department_id": college_department_id})
            counselor_user_ids = [row["user_id"] for row in counselor_rows]

        return {
            "student": {
                "user_id": student.get("user_id"),
                "email": student.get("email"),
                "program_id": program_id,
                "college_department_id": college_department_id,
            },
            "counselor_user_ids": counselor_user_ids,
        }

