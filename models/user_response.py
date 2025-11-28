"""
UserResponse Model
"""

from dataclasses import dataclass

@dataclass
class UserResponse:
    """Phản hồi của người dùng"""
    question_id: str
    is_correct: bool
    response_time: float 
    timestamp: int
    choice_selected: int = -1

