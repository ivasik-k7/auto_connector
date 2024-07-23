import json

import requests

from app.utils import setup_logger

logger = setup_logger(__name__)


class LeetcodeStats:
    GRAPHQL_URL = "https://leetcode.com/graphql/"

    def __init__(self):
        self.headers = {"Content-Type": "application/json"}

    def get_statistics(self, username: str):
        query = self._build_query(username)
        try:
            response = requests.post(self.GRAPHQL_URL, headers=self.headers, json=query)
            response.raise_for_status()

            return self._process_response(response.json())
        except requests.RequestException as e:
            logger.exception(f"Leetcode GraphQl issue: ${e}")
            return {}
        except json.JSONDecodeError as e:
            logger.exception(f"Leetcode JsonDecode issue: ${e}")
            return {}
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {str(e)}")
            return {}

    def _build_query(self, username: str):
        return {
            "query": """
                query getUserProfile($username: String!) {
                    allQuestionsCount { difficulty count }
                    matchedUser(username: $username) {
                        contributions { points }
                        profile { reputation ranking }
                        submissionCalendar
                        submitStats {
                            acSubmissionNum { difficulty count submissions }
                            totalSubmissionNum { difficulty count submissions }
                        }
                    }
                }
            """,
            "variables": {"username": username},
        }

    def _process_response(self, response_data: dict):
        try:
            data = response_data.get("data", {})
            all_questions = data.get("allQuestionsCount", [])
            matched_user = data.get("matchedUser", {})

            if not matched_user:
                raise ValueError("The user has not been found!")

            submit_stats = matched_user.get("submitStats", {})
            actual_submissions = submit_stats.get("acSubmissionNum", [])
            total_submissions = submit_stats.get("totalSubmissionNum", [])

            total_questions = self._sum_question_counts(all_questions)
            total_easy = self._get_question_count(all_questions, "Easy")
            total_medium = self._get_question_count(all_questions, "Medium")
            total_hard = self._get_question_count(all_questions, "Hard")

            easy_solved = self._get_submission_count(actual_submissions, "Easy")
            medium_solved = self._get_submission_count(actual_submissions, "Medium")
            hard_solved = self._get_submission_count(actual_submissions, "Hard")
            total_solved = easy_solved + medium_solved + hard_solved

            total_accept_count = self._get_submission_stat(
                actual_submissions, "Easy", "submissions"
            )
            total_sub_count = self._get_submission_stat(
                total_submissions, "Easy", "submissions"
            )
            acceptance_rate = self._calculate_acceptance_rate(
                total_accept_count, total_sub_count
            )

            reputation = matched_user.get("profile", {}).get("reputation", 0)
            ranking = matched_user.get("profile", {}).get("ranking", 0)

            return {
                "total_solved": total_solved,
                "easy_solved": easy_solved,
                "medium_solved": medium_solved,
                "hard_solved": hard_solved,
                "acceptance_rate": acceptance_rate,
                "total_questions": total_questions,
                "ranking": ranking,
                "reputation": reputation,
                "total_hard": total_hard,
                "total_medium": total_medium,
                "total_easy": total_easy,
            }

        except KeyError as e:
            logger.exception(f"Missing key in response: {e}")
            return {}
        except (TypeError, ValueError) as e:
            logger.exception(f"Data processing error: {e}")
            return {}

    def _sum_question_counts(self, questions: list) -> int:
        return sum(q.get("count", 0) for q in questions)

    def _sum_submission_counts(self, submissions: list) -> int:
        return sum(sub.get("count", 0) for sub in submissions)

    def _get_question_count(self, questions: list, difficulty: str) -> int:
        return next(
            (q.get("count", 0) for q in questions if q.get("difficulty") == difficulty),
            0,
        )

    def _get_submission_count(self, submissions: list, difficulty: str) -> int:
        return next(
            (
                sub.get("count", 0)
                for sub in submissions
                if sub.get("difficulty") == difficulty
            ),
            0,
        )

    def _get_submission_stat(
        self, submissions: list, difficulty: str, stat: str
    ) -> int:
        return next(
            (
                sub.get(stat, 0)
                for sub in submissions
                if sub.get("difficulty") == difficulty
            ),
            0,
        )

    def _calculate_acceptance_rate(self, accept_count: int, total_count: int) -> float:
        return (
            self._round((accept_count / total_count) * 100, 2)
            if total_count != 0
            else 0
        )

    def _parse_submission_calendar(self, calendar_str: str) -> dict:
        try:
            calendar = json.loads(calendar_str)
            return dict(sorted(calendar.items()))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _round(value: float, decimal_place: int) -> float:
        return round(value, decimal_place)
