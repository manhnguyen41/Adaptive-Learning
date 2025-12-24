"""
Passing Probability API endpoints
API để tính xác suất đậu bài thi thật của người học
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict
import random
import json
from api.schemas import (
    PassingProbabilityRequest,
    PassingProbabilityResponse,
)
from api.shared import (
    load_questions_and_difficulties,
    load_progress_data,
    get_question_topic_map,
    load_all_responses,
)
from services.user_response_loader_service import UserResponseLoaderService
from services.ability_estimator_service import AbilityEstimatorService
from services.passing_probability_service import PassingProbabilityService
from models.irt_model import IRTModel
from models.question import Question
from models.user_response import UserResponse

router = APIRouter(prefix="/api/passing-probability", tags=["Passing Probability"])


def _select_questions_from_topic_structure(
    all_questions: List[Question],
    question_difficulties: Dict[str, float],
    topic_structure,
    question_topic_map: Dict[str, Dict[str, str]]
) -> List[Dict]:
    """
    Chọn câu hỏi từ cấu trúc topic + difficulty counts
    
    Args:
        all_questions: Tất cả câu hỏi có sẵn
        question_difficulties: Dict mapping question_id -> difficulty
        topic_structure: ExamTopicStructure object
        question_topic_map: Dict mapping question_id -> {main_topic_id, sub_topic_id}
    
    Returns:
        List[Dict] với format: [{"question_id": str, "difficulty": float, "discrimination": float}]
    """
    topic_id = str(topic_structure.topic_id)
    topic_type = topic_structure.topic_type or "sub"
    difficulty_counts = topic_structure.difficulty_counts
    
    topic_key = "main_topic_id" if topic_type == "main" else "sub_topic_id"
    candidate_questions = []
    
    for q in all_questions:
        topic_info = question_topic_map.get(q.question_id, {})
        q_topic_id = str(topic_info.get(topic_key, ""))
        if q_topic_id == topic_id:
            difficulty = question_difficulties.get(q.question_id, q.difficulty)
            candidate_questions.append({
                "question": q,
                "difficulty": difficulty
            })
    
    easy_questions = []
    medium_questions = []
    hard_questions = []
    
    for item in candidate_questions:
        diff = item["difficulty"]
        if -3 <= diff < -1:
            easy_questions.append(item["question"])
        elif -1 <= diff <= 1:
            medium_questions.append(item["question"])
        elif 1 < diff <= 3:
            hard_questions.append(item["question"])
    
    selected_questions = []
    
    def select_from_list(questions_list, count):
        if count <= 0:
            return []
        if len(questions_list) <= count:
            return questions_list
        return random.sample(questions_list, count)
    
    selected_easy = select_from_list(easy_questions, difficulty_counts.easy)
    selected_questions.extend(selected_easy)
    
    selected_medium = select_from_list(medium_questions, difficulty_counts.medium)
    selected_questions.extend(selected_medium)
    
    selected_hard = select_from_list(hard_questions, difficulty_counts.hard)
    selected_questions.extend(selected_hard)
    
    result = []
    for q in selected_questions:
        difficulty = question_difficulties.get(q.question_id, q.difficulty)
        result.append({
            "question_id": q.question_id,
            "difficulty": difficulty,
            "discrimination": q.discrimination
        })
    
    return result


@router.post("/calculate", response_model=PassingProbabilityResponse)
async def calculate_passing_probability(request: PassingProbabilityRequest):
    """
    Tính xác suất đậu bài thi thật của người học
    
    Sử dụng IRT model để dự đoán xác suất trả lời đúng từng câu hỏi,
    sau đó tính xác suất tổng số câu đúng >= passing threshold.
    
    Trả về:
    - passing_probability: Xác suất đậu (0-100%)
    - confidence_score: Điểm tin cậy (0-1)
    - expected_score: Điểm số dự kiến (0-100%)
    """
    try:
        progress_data = load_progress_data()
        questions, question_difficulties = load_questions_and_difficulties()
        
        if request.user_responses:
            user_responses: List[UserResponse] = []
            for ans in request.user_responses:
                is_correct = False
                if ans.histories and len(ans.histories) > 0:
                    is_correct = ans.histories[-1] == 1
                
                choice_selected = -1
                if ans.choicesSelected and len(ans.choicesSelected) > 0:
                    choice_selected = ans.choicesSelected[0]
                
                response_time = 30.0 
                try:
                    played_times = json.loads(ans.playedTimes)
                    if played_times and len(played_times) > 0:
                        time_data = played_times[0]
                        start_time = time_data.get("startTime", 0)
                        end_time = time_data.get("endTime", 0)
                        if end_time > start_time:
                            response_time = (end_time - start_time) / 1000.0  
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass  
                
                user_responses.append(
                    UserResponse(
                        question_id=str(ans.questionId),
                        is_correct=is_correct,
                        response_time=response_time,
                        timestamp=0,
                        choice_selected=choice_selected,
                    )
                )
        else:
            user_responses = UserResponseLoaderService.load_user_responses(
                progress_data,
                request.user_id
            )
        
        if not user_responses:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Không có lịch sử trả lời để tính passing probability "
                    "(truyền user_responses hoặc đảm bảo có dữ liệu đã lưu)."
                )
            )
        
        irt_model = IRTModel(guessing_param=0.25)
        ability_estimator = AbilityEstimatorService(irt_model)
        passing_prob_service = PassingProbabilityService(irt_model, ability_estimator)
        
        all_responses = load_all_responses()
        
        exam_questions = []
        
        if request.exam_structure.questions:
            for q in request.exam_structure.questions:
                exam_questions.append({
                    "question_id": q.question_id,
                    "difficulty": q.difficulty,
                    "discrimination": q.discrimination
                })
        elif request.exam_structure.topics:
            question_topic_map = get_question_topic_map()
            for topic_structure in request.exam_structure.topics:
                selected = _select_questions_from_topic_structure(
                    all_questions=questions,
                    question_difficulties=question_difficulties,
                    topic_structure=topic_structure,
                    question_topic_map=question_topic_map
                )
                exam_questions.extend(selected)
        
        if not exam_questions:
            raise HTTPException(
                status_code=400,
                detail="Không thể tạo được danh sách câu hỏi từ cấu trúc đề thi"
            )
        
        question_topic_map = get_question_topic_map()
        
        passing_prob, confidence_score, expected_score, exam_info = \
            passing_prob_service.calculate_passing_probability(
                user_id=request.user_id,
                exam_questions=exam_questions,
                passing_threshold=request.exam_structure.passing_threshold,
                user_responses=user_responses,
                question_difficulties=question_difficulties,
                question_topic_map=question_topic_map,
                total_score=request.exam_structure.total_score,
                all_responses_for_expected_time=all_responses
            )
        
        return PassingProbabilityResponse(
            user_id=request.user_id,
            passing_probability=round(passing_prob, 2),
            confidence_score=round(confidence_score, 3),
            expected_score=round(expected_score, 2),
            passing_threshold=request.exam_structure.passing_threshold * 100.0,
            exam_info=exam_info,
            message="Passing probability calculated successfully"
        )
    
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tính passing probability: {str(e)}")
