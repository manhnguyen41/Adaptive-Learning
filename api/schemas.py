"""
API Schemas - Request/Response models
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field

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
                        "discrimination": 1.0
                    }
                ],
                "total_questions": 20,
                "message": "Successfully generated diagnostic question set"
            }
        }

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
                        "std": 1.2
                    },
                    "discrimination": {
                        "min": 1.0,
                        "max": 1.0,
                        "mean": 1.0,
                        "median": 1.0
                    }
                },
                "distributions": {
                    "difficulty": {
                        "easy": 300,
                        "medium": 900,
                        "hard": 300
                    },
                    "topics": {
                        "by_main_topic": {},
                        "by_sub_topic": {},
                        "total_main_topics": 10,
                        "total_sub_topics": 50,
                        "top_5_main_topics": []
                    }
                },
                "limit_applied": False
            }
        }

class EstimateAbilityRequest(BaseModel):
    """Request để tính ability của một user"""
    user_id: str = Field(..., description="ID của user cần tính ability")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "4515379877511168"
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
                "user_id": "4515379877511168",
                "overall_ability": 0.5,
                "confidence": 0.85,
                "num_responses": 20,
                "main_topic_abilities": [
                    {
                        "topic_id": "5878262490202112",
                        "ability": 0.6,
                        "confidence": 0.8,
                        "num_responses": 5
                    }
                ],
                "sub_topic_abilities": [
                    {
                        "topic_id": "6140467079020544",
                        "ability": 0.7,
                        "confidence": 0.75,
                        "num_responses": 3
                    }
                ],
                "message": "Ability estimated successfully"
            }
        }

class EstimateAbilitiesBatchRequest(BaseModel):
    """Request để tính ability của nhiều user"""
    user_ids: List[str] = Field(..., description="Danh sách ID của các user cần tính ability", min_items=1, max_items=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": ["4515379877511168", "5515379877511169", "6515379877511170"]
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
                        "user_id": "4515379877511168",
                        "overall_ability": 0.5,
                        "confidence": 0.85,
                        "num_responses": 20,
                        "error": None
                    }
                ],
                "total_users": 3,
                "successful_count": 2,
                "failed_count": 1
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
                "discrimination": 1.0
            }
        }

class ExamStructure(BaseModel):
    """Cấu trúc đề thi thật"""
    questions: List[ExamQuestion] = Field(..., description="Danh sách câu hỏi trong đề thi", min_items=1)
    passing_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Ngưỡng đậu (tỷ lệ câu đúng cần thiết, ví dụ: 0.7 = 70%)")
    total_score: Optional[int] = Field(None, description="Tổng điểm của đề thi. Nếu None, sẽ dùng số lượng câu hỏi")
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    {
                        "question_id": "4515379877511168",
                        "difficulty": 0.5,
                        "discrimination": 1.0
                    }
                ],
                "passing_threshold": 0.7,
                "total_score": 100
            }
        }

class PassingProbabilityRequest(BaseModel):
    """Request để tính passing probability"""
    user_id: str = Field(..., description="ID của user cần tính xác suất đậu")
    exam_structure: ExamStructure = Field(..., description="Cấu trúc đề thi thật")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "4515379877511168",
                "exam_structure": {
                    "questions": [
                        {
                            "question_id": "4515379877511168",
                            "difficulty": 0.5,
                            "discrimination": 1.0
                        }
                    ],
                    "passing_threshold": 0.7
                }
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
                    "average_difficulty": 0.3
                },
                "message": "Passing probability calculated successfully"
            }
        }

