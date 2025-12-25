"""
API Schemas - Request/Response models
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field, model_validator

class QuestionResponse(BaseModel):
    """Schema cho câu hỏi trong response"""
    question_id: str
    main_topic_id: str
    sub_topic_id: str
    difficulty: float = Field(..., description="Độ khó trong thang Standard Normal [-3, +3]")
    discrimination: float = Field(default=1.0, description="Độ phân biệt")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_id": "4515379877511168",
                "main_topic_id": "5878262490202112",
                "sub_topic_id": "6140467079020544",
                "difficulty": 0.5,
                "discrimination": 1.0
            }
        }

class QuestionDifficultyResponse(BaseModel):
    """Response cho API lấy độ khó của câu hỏi"""
    question_id: str
    difficulty: float = Field(..., description="Độ khó trong thang Standard Normal [-3, +3]")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_id": "4515379877511168",
                "difficulty": 0.5
            }
        }

class DiagnosticQuestionSetRequest(BaseModel):
    """Request để tạo bộ câu hỏi Diagnostic Test"""
    num_questions: int = Field(default=20, ge=1, le=100, description="Số lượng câu hỏi cần chọn")
    coverage_topics: Optional[List[str]] = Field(default=None, description="Danh sách topic cần bao phủ")
    app_id: Optional[str] = Field(default="5074526257807360", description="ID của app")
    
    class Config:
        json_schema_extra = {
            "example": {
                "num_questions": 20,
                "coverage_topics": ["5878262490202112", "5533861310103552"],
                "app_id": "5074526257807360"
            }
        }

class DiagnosticQuestionSetResponse(BaseModel):
    """Response cho bộ câu hỏi Diagnostic Test"""
    questions: List[QuestionResponse]
    total_questions: int
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    {
                        "question_id": "4515379877511168",
                        "main_topic_id": "5878262490202112",
                        "sub_topic_id": "6140467079020544",
                        "difficulty": 0.5,
                        "discrimination": 1.0,
                    }
                ],
                "total_questions": 20,
                "message": "Successfully generated diagnostic question set",
            }
        }


# =============== Diagnostic adaptive session (current + preview next) ===============


class DiagnosticPreviewQuestion(BaseModel):
    """
    Thông tin câu hỏi dùng cho luồng preview (ID + topic).
    Lưu ý: topic_id ở đây thường map với main_topic_id trong dữ liệu nội bộ.
    """

    question_id: str
    topic_id: str
    topic_name: Optional[str] = Field(
        default=None, description="Tên topic tương ứng (nếu có sẵn)"
    )
    difficulty: float = Field(..., description="Độ khó trong thang Standard Normal [-3, +3]")


class DiagnosticPreviewBranches(BaseModel):
    """Nhánh câu hỏi tiếp theo nếu đúng / sai."""

    if_correct: DiagnosticPreviewQuestion
    if_incorrect: DiagnosticPreviewQuestion


class DiagnosticPreviewResponse(BaseModel):
    """
    Response chung cho:
    - API init Diagnostic
    - API get next preview question

    Cấu trúc giống ví dụ trong yêu cầu:
    {
      "current_question": {...},
      "preview_next_question": {
        "if_correct": {...},
        "if_incorrect": {...}
      },
      "overall_ability": 0.5,
      "confidence": 0.85
    }
    """

    current_question: DiagnosticPreviewQuestion
    preview_next_question: DiagnosticPreviewBranches
    overall_ability: float = Field(..., description="Năng lực tổng thể hiện tại của người dùng (Standard Normal)")
    confidence: float = Field(..., description="Độ tin cậy của ước tính năng lực (0-1)")

    class Config:
        json_schema_extra = {
            "example": {
                "current_question": {
                    "question_id": "6448245131706368",
                    "topic_id": "5878262490202112",
                    "difficulty": 0.5,
                },
                "preview_next_question": {
                    "if_correct": {
                        "question_id": "5008459000971264",
                        "topic_id": "5878262490202112",
                        "difficulty": 0.8,
                    },
                    "if_incorrect": {
                        "question_id": "5430671466037248",
                        "topic_id": "5878262490202112",
                        "difficulty": 0.3,
                    },
                },
                "overall_ability": 0.5,
                "confidence": 0.85,
            }
        }


class DiagnosticUserAnswer(BaseModel):
    """Một câu trả lời trong phiên Diagnostic."""

    question_id: str
    is_correct: bool


class DiagnosticSessionProgress(BaseModel):
    """
    Trạng thái progress của bài Diagnostic do client gửi lên.
    Backend không lưu session, client giữ list các câu đã làm.
    """

    user_id: str
    answers: List[DiagnosticUserAnswer] = Field(
        default_factory=list,
        description="Danh sách các câu đã làm trong phiên Diagnostic hiện tại",
    )


class DiagnosticInitRequest(BaseModel):
    """
    Request cho API init Diagnostic.

    - user_id: định danh user
    - coverage_topics: (optional) danh sách topic/subtopic mà bài Diagnostic cần cover.
    - topic_question_counts: (optional) số lượng câu hỏi cần cho từng topic_id.
    """

    user_id: str
    coverage_topics: Optional[List[str]] = Field(
        default=None,
        description=(
            "Danh sách topic cần bao phủ (nếu bỏ trống sẽ dùng toàn bộ topic có trong dữ liệu)"
        ),
    )
    topic_question_counts: Optional[Dict[str, int]] = Field(
        default=None,
        description="Số lượng câu hỏi cần cho từng topic_id. Nếu topic đã đủ số câu thì không gen thêm.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "coverage_topics": ["5878262490202112", "5533861310103552"],
                "topic_question_counts": {
                    "5878262490202112": 5,
                    "5533861310103552": 10
                },
            }
        }


class DiagnosticNextQuestionRequest(BaseModel):
    """
    Request cho API lấy câu tiếp theo + preview (sau khi user đã làm một số câu).

    Truyền toàn bộ progress của phiên Diagnostic hiện tại.
    """

    session: DiagnosticSessionProgress
    coverage_topics: Optional[List[str]] = Field(
        default=None,
        description="Danh sách topic cần bao phủ (cùng format với init)",
    )
    topic_question_counts: Optional[Dict[str, int]] = Field(
        default=None,
        description="Số lượng câu hỏi cần cho từng topic_id. Nếu topic đã đủ số câu thì không gen thêm.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session": {
                    "user_id": "user_123",
                    "answers": [
                        {
                            "question_id": "6448245131706368",
                            "is_correct": True,
                        }
                    ],
                },
                "coverage_topics": ["5878262490202112"],
                "topic_question_counts": {
                    "5878262490202112": 5,
                    "5533861310103552": 10
                },
            }
        }


class DiagnosticSubmitAnswerRequest(BaseModel):
    """
    API submit một câu trả lời.
    Backend hiện tại không lưu DB, nên API này chủ yếu để logging / future extension.
    """

    session: DiagnosticSessionProgress
    latest_answer: DiagnosticUserAnswer

    class Config:
        json_schema_extra = {
            "example": {
                "session": {
                    "user_id": "user_123",
                    "answers": [],
                },
                "latest_answer": {
                    "question_id": "6448245131706368",
                    "is_correct": True,
                },
            }
        }


class DiagnosticSubmitAnswerResponse(BaseModel):
    """Response đơn giản xác nhận submit thành công."""

    success: bool
    message: str
    overall_ability: float = Field(..., description="Năng lực tổng thể hiện tại của người dùng sau khi trả lời (Standard Normal)")
    confidence: float = Field(..., description="Độ tin cậy của ước tính năng lực (0-1)")

class DifficultyStatistics(BaseModel):
    """Thống kê về độ khó"""
    min: float
    max: float
    mean: float
    median: float
    std: float

class DiscriminationStatistics(BaseModel):
    """Thống kê về độ phân biệt"""
    min: float
    max: float
    mean: float
    median: float

class DifficultyDistribution(BaseModel):
    """Phân bố theo độ khó"""
    easy: int = Field(..., description="Số câu hỏi dễ (độ khó [-3, -1))")
    medium: int = Field(..., description="Số câu hỏi trung bình (độ khó [-1, 1])")
    hard: int = Field(..., description="Số câu hỏi khó (độ khó (1, 3])")

class TopicInfo(BaseModel):
    """Thông tin topic"""
    topic_id: str
    question_count: int

class TopicDistribution(BaseModel):
    """Phân bố theo topic"""
    by_main_topic: Dict[str, int]
    by_sub_topic: Dict[str, int]
    total_main_topics: int
    total_sub_topics: int
    top_5_main_topics: List[TopicInfo]

class QuestionStatistics(BaseModel):
    """Thống kê tổng hợp về câu hỏi"""
    difficulty: DifficultyStatistics
    discrimination: DiscriminationStatistics

class QuestionDistributions(BaseModel):
    """Phân bố câu hỏi"""
    difficulty: DifficultyDistribution
    topics: TopicDistribution

class AllQuestionsResponse(BaseModel):
    """Response cho API lấy tất cả câu hỏi kèm phân tích"""
    questions: List[QuestionResponse]
    total_questions: int
    statistics: QuestionStatistics
    distributions: QuestionDistributions
    limit_applied: Optional[bool] = Field(default=False, description="Có giới hạn số lượng câu hỏi trả về không")
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": [],
                "total_questions": 1500,
                "statistics": {
                    "difficulty": {
                        "min": -2.5,
                        "max": 2.8,
                        "mean": 0.1,
                        "median": 0.0,
                        "std": 1.2,
                    },
                    "discrimination": {
                        "min": 1.0,
                        "max": 1.0,
                        "mean": 1.0,
                        "median": 1.0,
                    },
                },
                "distributions": {
                    "difficulty": {
                        "easy": 300,
                        "medium": 900,
                        "hard": 300,
                    },
                    "topics": {
                        "by_main_topic": {},
                        "by_sub_topic": {},
                        "total_main_topics": 10,
                        "total_sub_topics": 50,
                        "top_5_main_topics": [],
                    },
                },
                "limit_applied": False,
            }
        }


class UserAnswerDetail(BaseModel):
    type: int = Field(..., description="Loại câu hỏi")
    questionId: int = Field(..., description="ID của câu hỏi")
    playedTimes: str = Field(..., description="JSON string chứa thời gian chơi")
    choicesSelected: List[int] = Field(..., description="Danh sách lựa chọn đã chọn")
    histories: List[int] = Field(..., description="Lịch sử trả lời (phần tử cuối cùng: 0=sai, 1=đúng)")


class EstimateAbilityRequest(BaseModel):
    """Request để tính ability của một user"""
    user_id: str = Field(..., description="ID của user cần tính ability")
    user_responses: Optional[List[UserAnswerDetail]] = Field(
        default=None,
        description=(
            "Lịch sử trả lời câu hỏi của user (nếu truyền sẽ dùng thay vì load từ file). "
        ),
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "77wmmksb6r@privaterelay.appleid.com",
                "user_responses": [
                    {
                        "type": 10,
                        "questionId": 4515379877511168,
                        "playedTimes": "[{\"startTime\":1743147855291,\"endTime\":1743147860256}]",
                        "choicesSelected": [3],
                        "histories": [0, 1, 1]
                    },
                ],
            }
        }


class TopicAbility(BaseModel):
    """Năng lực theo từng topic"""
    topic_id: str
    ability: float = Field(..., description="Năng lực (Standard Normal)")
    confidence: float = Field(..., description="Độ tin cậy (0-1)")
    num_responses: int = Field(..., description="Số câu hỏi đã trả lời trong topic này")

class UserAbilityResponse(BaseModel):
    """Response cho ability của user"""
    user_id: str
    overall_ability: float = Field(..., description="Năng lực tổng thể (Standard Normal)")
    confidence: float = Field(..., description="Độ tin cậy của ước tính (0-1)")
    num_responses: int = Field(..., description="Số lượng câu hỏi đã trả lời")
    main_topic_abilities: List[TopicAbility] = Field(default=[], description="Năng lực theo main topic")
    sub_topic_abilities: List[TopicAbility] = Field(default=[], description="Năng lực theo sub topic")
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "77wmmksb6r@privaterelay.appleid.com",
                "overall_ability": 0.5,
                "confidence": 0.85,
                "num_responses": 20,
                "main_topic_abilities": [
                    {
                        "topic_id": "5878262490202112",
                        "ability": 0.6,
                        "confidence": 0.8,
                        "num_responses": 5,
                    }
                ],
                "sub_topic_abilities": [
                    {
                        "topic_id": "6140467079020544",
                        "ability": 0.7,
                        "confidence": 0.75,
                        "num_responses": 3,
                    }
                ],
                "message": "Ability estimated successfully",
            }
        }


class DiagnosticResultResponse(BaseModel):
    """
    Kết quả tổng hợp cho một bài Diagnostic.
    """

    user_id: str
    overall_ability: float = Field(..., description="Năng lực tổng thể (Standard Normal)")
    confidence: float = Field(..., description="Độ tin cậy của ước tính (0-1)")
    main_topic_abilities: List[TopicAbility] = Field(
        default_factory=list,
        description="Năng lực theo main topic trong bài Diagnostic",
    )
    sub_topic_abilities: List[TopicAbility] = Field(
        default_factory=list,
        description="Năng lực theo sub topic trong bài Diagnostic",
    )
    covered_subtopics: List[str] = Field(
        default_factory=list,
        description="Danh sách subtopic đã được hỏi trong bài Diagnostic",
    )
    completed_all_subtopics: bool = Field(
        ..., description="True nếu tất cả subtopic yêu cầu đã được hỏi"
    )
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "overall_ability": 0.4,
                "confidence": 0.8,
                "main_topic_abilities": [],
                "sub_topic_abilities": [],
                "covered_subtopics": ["6140467079020544"],
                "completed_all_subtopics": True,
                "message": "Diagnostic result calculated successfully",
            }
        }


class EstimateAbilitiesBatchRequest(BaseModel):
    """Request để tính ability của nhiều user"""
    user_ids: List[str] = Field(..., description="Danh sách ID của các user cần tính ability", min_items=1, max_items=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": [
                    "77wmmksb6r@privaterelay.appleid.com",
                    "2mkx8c7f5j@privaterelay.appleid.com",
                    "986542fxj6@privaterelay.appleid.com",
                ]
            }
        }


class BatchUserAbilityResponse(BaseModel):
    """Response cho một user trong batch"""
    user_id: str
    overall_ability: Optional[float] = Field(None, description="Năng lực tổng thể (Standard Normal). None nếu không có dữ liệu")
    confidence: Optional[float] = Field(None, description="Độ tin cậy của ước tính (0-1)")
    num_responses: int = Field(..., description="Số lượng câu hỏi đã trả lời")
    main_topic_abilities: Optional[List[TopicAbility]] = Field(default=None, description="Năng lực theo main topic")
    sub_topic_abilities: Optional[List[TopicAbility]] = Field(default=None, description="Năng lực theo sub topic")
    error: Optional[str] = Field(None, description="Thông báo lỗi nếu có")

class EstimateAbilitiesBatchResponse(BaseModel):
    """Response cho batch ability estimation"""
    results: List[BatchUserAbilityResponse]
    total_users: int
    successful_count: int
    failed_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "user_id": "77wmmksb6r@privaterelay.appleid.com",
                        "overall_ability": 0.5,
                        "confidence": 0.85,
                        "num_responses": 20,
                        "error": None,
                    }
                ],
                "total_users": 3,
                "successful_count": 2,
                "failed_count": 1,
            }
        }


class ExamQuestion(BaseModel):
    """Một câu hỏi trong đề thi thật"""
    question_id: str = Field(..., description="ID của câu hỏi")
    difficulty: Optional[float] = Field(None, description="Độ khó (Standard Normal). Nếu None, sẽ tự động tính từ dữ liệu")
    discrimination: float = Field(default=1.0, description="Độ phân biệt")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_id": "4515379877511168",
                "difficulty": 0.5,
                "discrimination": 1.0,
            }
        }


class ExamTopicDifficultyCounts(BaseModel):
    """Số lượng câu hỏi theo mức độ khó cho một topic"""
    easy: int = Field(default=0, ge=0, description="Số câu hỏi dễ (difficulty ∈ [-3, -1))")
    medium: int = Field(default=0, ge=0, description="Số câu hỏi trung bình (difficulty ∈ [-1, 1])")
    hard: int = Field(default=0, ge=0, description="Số câu hỏi khó (difficulty ∈ (1, 3])")


class ExamTopicStructure(BaseModel):
    """Cấu trúc đề thi theo topic và mức độ khó"""
    topic_id: str = Field(..., description="ID của topic (main_topic_id hoặc sub_topic_id)")
    topic_type: Optional[str] = Field(default="sub", description="Loại topic: 'main' hoặc 'sub' (mặc định: 'sub')")
    difficulty_counts: ExamTopicDifficultyCounts = Field(..., description="Số lượng câu hỏi theo mức độ khó")
    
    class Config:
        json_schema_extra = {
            "example": {
                "topic_id": "5878262490202112",
                "topic_type": "main",
                "difficulty_counts": {
                    "easy": 5,
                    "medium": 10,
                    "hard": 5
                }
            }
        }


class ExamStructure(BaseModel):
    """Cấu trúc đề thi thật
    
    Hỗ trợ 2 cách:
    1. questions: Danh sách câu hỏi cụ thể (question_id)
    2. topics: Cấu trúc theo topic và số câu theo mức độ khó (sẽ tự động chọn câu hỏi)
    
    Phải có một trong hai: questions hoặc topics.
    """
    questions: Optional[List[ExamQuestion]] = Field(
        default=None,
        description="Danh sách câu hỏi cụ thể trong đề thi. Nếu None, phải có topics."
    )
    topics: Optional[List[ExamTopicStructure]] = Field(
        default=None,
        description="Cấu trúc đề thi theo topic và số câu theo mức độ khó. Nếu None, phải có questions."
    )
    passing_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Ngưỡng đậu (tỷ lệ câu đúng cần thiết, ví dụ: 0.7 = 70%)")
    total_score: Optional[int] = Field(None, description="Tổng điểm của đề thi. Nếu None, sẽ dùng số lượng câu hỏi")
    
    @model_validator(mode='after')
    def validate_questions_or_topics(self):
        """Validate: phải có questions hoặc topics"""
        if not self.questions and not self.topics:
            raise ValueError("Phải có 'questions' hoặc 'topics'")
        if self.questions and self.topics:
            raise ValueError("Chỉ được có một trong hai: 'questions' hoặc 'topics'")
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "topics": [
                    {
                        "topic_id": "5878262490202112",
                        "topic_type": "main",
                        "difficulty_counts": {
                            "easy": 5,
                            "medium": 10,
                            "hard": 5
                        }
                    }
                ],
                "passing_threshold": 0.7,
                "total_score": 100,
            }
        }


class PassingProbabilityRequest(BaseModel):
    """Request để tính passing probability"""
    user_id: str = Field(..., description="ID của user cần tính xác suất đậu")
    exam_structure: ExamStructure = Field(..., description="Cấu trúc đề thi thật")
    user_responses: Optional[List[UserAnswerDetail]] = Field(
        default=None,
        description=(
            "Lịch sử trả lời câu hỏi của user trong bài diagnostic (nếu truyền sẽ dùng thay vì load từ file). "
        ),
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "77wmmksb6r@privaterelay.appleid.com",
                "exam_structure": {
                    "topics": [
                        {
                            "topic_id": "5878262490202112",
                            "topic_type": "main",
                            "difficulty_counts": {
                                "easy": 5,
                                "medium": 10,
                                "hard": 5
                            }
                        }
                    ],
                    "passing_threshold": 0.7,
                },
                "user_responses": [
                    {
                        "type": 10,
                        "questionId": 4515379877511168,
                        "playedTimes": "[{\"startTime\":1743147855291,\"endTime\":1743147860256}]",
                        "choicesSelected": [3],
                        "histories": [0, 1, 1]
                    },
                ],
            }
        }


class PassingProbabilityResponse(BaseModel):
    """Response cho passing probability"""
    user_id: str
    passing_probability: float = Field(..., description="Xác suất đậu (0-100%)")
    confidence_score: float = Field(..., description="Điểm tin cậy (0-1)")
    expected_score: float = Field(..., description="Điểm số dự kiến (0-100%)")
    passing_threshold: float = Field(..., description="Ngưỡng đậu (0-100%)")
    exam_info: Dict = Field(..., description="Thông tin về đề thi")
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "4515379877511168",
                "passing_probability": 75.5,
                "confidence_score": 0.85,
                "expected_score": 78.2,
                "passing_threshold": 70.0,
                "exam_info": {
                    "total_questions": 50,
                    "average_difficulty": 0.3,
                },
                "message": "Passing probability calculated successfully",
            }
        }

