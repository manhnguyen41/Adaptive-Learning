"""
Diagnostic Session API endpoints
API cho adaptive Diagnostic Test session (init, next question, submit answer, result)
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict
import json
import os
import csv
from api.schemas import (
    DiagnosticInitRequest,
    DiagnosticNextQuestionRequest,
    DiagnosticPreviewResponse,
    DiagnosticSessionProgress,
    DiagnosticSubmitAnswerRequest,
    DiagnosticSubmitAnswerResponse,
    DiagnosticResultResponse,
    DiagnosticPreviewQuestion,
    DiagnosticPreviewBranches,
    TopicAbility,
)
from services.question_selector_service import QuestionSelectorService
from services.data_loader_service import DataLoaderService
from services.ability_estimator_service import AbilityEstimatorService
from models.irt_model import IRTModel
from models.question import Question
from models.user_response import UserResponse

router = APIRouter(prefix="/api/diagnostic", tags=["Diagnostic Session"])

_questions_cache = None
_difficulties_cache = None

def get_question_selector() -> QuestionSelectorService:
    """Dependency để tạo QuestionSelectorService"""
    irt_model = IRTModel(guessing_param=0.25)
    return QuestionSelectorService(irt_model)

def load_questions_and_difficulties():
    """Load câu hỏi và độ khó """
    global _questions_cache, _difficulties_cache
    
    if _questions_cache is not None and _difficulties_cache is not None:
        return _questions_cache, _difficulties_cache
    
    progress_file = "user_question_progress_100000.json"
    topic_file = "topic_questions_asvab.csv"
    
    if not os.path.exists(progress_file):
        raise FileNotFoundError(f"File không tồn tại: {progress_file}")
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        progress_data = json.load(f)
    
    topic_data = []
    if os.path.exists(topic_file):
        with open(topic_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            first_field = reader.fieldnames[0]
            
            if '|' in first_field:
                columns = first_field.split('|')
                for row in reader:
                    values = row[first_field].split('|')
                    if len(values) == len(columns):
                        topic_data.append(dict(zip(columns, values)))
            else:
                topic_data = list(reader)
    
    questions = DataLoaderService.load_questions_from_data(progress_data, topic_data)
    difficulties = DataLoaderService.calculate_question_difficulties(progress_data)
    
    _questions_cache = questions
    _difficulties_cache = difficulties
    
    return questions, difficulties

def get_ability_estimator() -> AbilityEstimatorService:
    """Dependency để tạo AbilityEstimatorService"""
    irt_model = IRTModel(guessing_param=0.25)
    return AbilityEstimatorService(irt_model)

def get_question_topic_map() -> Dict[str, Dict[str, str]]:
    """Tạo mapping question_id -> topic info từ questions cache"""
    all_questions, _ = load_questions_and_difficulties()
    
    question_topic_map = {}
    for q in all_questions:
        question_topic_map[q.question_id] = {
            "main_topic_id": q.main_topic_id,
            "sub_topic_id": q.sub_topic_id
        }
    
    return question_topic_map

def _filter_questions_by_topics(
    all_questions: List[Question], coverage_topics: Optional[List[str]]
) -> List[Question]:
    """Lọc danh sách câu hỏi theo coverage_topics."""
    if not coverage_topics:
        return all_questions

    coverage_set = set(str(t) for t in coverage_topics)
    return [
        q
        for q in all_questions
        if q.main_topic_id in coverage_set or q.sub_topic_id in coverage_set
    ]


def _build_preview_response_for_session(
    selector: QuestionSelectorService,
    questions: List[Question],
    difficulties: Dict[str, float],
    session: DiagnosticSessionProgress,
    coverage_topics: Optional[List[str]] = None,
    topic_question_counts: Optional[Dict[str, int]] = None,
) -> DiagnosticPreviewResponse:
    """
    Core logic: từ session Diagnostic (các câu đã làm) => chọn current_question
    và preview trước 2 nhánh if_correct / if_incorrect cho current_question đó.
    
    Nếu topic_question_counts được cung cấp, sẽ lọc các topic đã đủ số câu hỏi.
    """
    candidate_questions = _filter_questions_by_topics(questions, coverage_topics)
    
    if topic_question_counts:
        question_topic_map = get_question_topic_map()
        
        topic_answered_counts: Dict[str, int] = {}
        for ans in session.answers:
            topic_info = question_topic_map.get(ans.question_id, {})
            main_topic_id = str(topic_info.get("main_topic_id", ""))
            sub_topic_id = str(topic_info.get("sub_topic_id", ""))
            
            if main_topic_id and main_topic_id in topic_question_counts:
                topic_answered_counts[main_topic_id] = topic_answered_counts.get(main_topic_id, 0) + 1
            elif sub_topic_id and sub_topic_id in topic_question_counts:
                topic_answered_counts[sub_topic_id] = topic_answered_counts.get(sub_topic_id, 0) + 1
        
        filtered_candidate_questions = []
        for q in candidate_questions:
            main_topic_id = str(q.main_topic_id) if q.main_topic_id else ""
            sub_topic_id = str(q.sub_topic_id) if q.sub_topic_id else ""
            
            # Kiểm tra xem topic này có bị giới hạn số câu không
            should_include = True
            if main_topic_id in topic_question_counts:
                required_count = topic_question_counts[main_topic_id]
                answered_count = topic_answered_counts.get(main_topic_id, 0)
                if answered_count >= required_count:
                    should_include = False
            elif sub_topic_id in topic_question_counts:
                required_count = topic_question_counts[sub_topic_id]
                answered_count = topic_answered_counts.get(sub_topic_id, 0)
                if answered_count >= required_count:
                    should_include = False
            
            if should_include:
                filtered_candidate_questions.append(q)
        
        candidate_questions = filtered_candidate_questions

    user_responses: List[UserResponse] = []
    for ans in session.answers:
        user_responses.append(
            UserResponse(
                question_id=ans.question_id,
                is_correct=ans.is_correct,
                response_time=30.0, #
                timestamp=0, #
                choice_selected=-1,
            )
        )

    current_question = selector.select_next_question(
        candidate_questions=candidate_questions,
        user_responses=user_responses,
        question_difficulties=difficulties,
    )

    answer_correct = UserResponse(
        question_id=current_question.question_id,
        is_correct=True,
        response_time=30.0,
        timestamp=0,
        choice_selected=-1,
    )
    answer_incorrect = UserResponse(
        question_id=current_question.question_id,
        is_correct=False,
        response_time=30.0,
        timestamp=0,
        choice_selected=-1,
    )

    next_if_correct = selector.select_next_question(
        candidate_questions=candidate_questions,
        user_responses=user_responses + [answer_correct],
        question_difficulties=difficulties,
    )

    next_if_incorrect = selector.select_next_question(
        candidate_questions=candidate_questions,
        user_responses=user_responses + [answer_incorrect],
        question_difficulties=difficulties,
    )

    current_preview = DiagnosticPreviewQuestion(
        question_id=current_question.question_id,
        topic_id=str(current_question.main_topic_id or current_question.sub_topic_id),
    )
    if_correct_preview = DiagnosticPreviewQuestion(
        question_id=next_if_correct.question_id,
        topic_id=str(
            next_if_correct.main_topic_id or next_if_correct.sub_topic_id
        ),
    )
    if_incorrect_preview = DiagnosticPreviewQuestion(
        question_id=next_if_incorrect.question_id,
        topic_id=str(
            next_if_incorrect.main_topic_id or next_if_incorrect.sub_topic_id
        ),
    )

    return DiagnosticPreviewResponse(
        current_question=current_preview,
        preview_next_question=DiagnosticPreviewBranches(
            if_correct=if_correct_preview,
            if_incorrect=if_incorrect_preview,
        ),
    )


@router.post(
    "/init-session",
    response_model=DiagnosticPreviewResponse,
    summary="Init Diagnostic: trả về current_question + preview next (if_correct/if_incorrect)",
)
async def init_diagnostic_session(
    request: DiagnosticInitRequest,
    selector: QuestionSelectorService = Depends(get_question_selector),
):
    """
    API init Diagnostic:
    - Không cần truyền progress
    - Trả về:
        {
          "current_question": {...},
          "preview_next_question": { "if_correct": {...}, "if_incorrect": {...} }
        }
    """
    try:
        questions, difficulties = load_questions_and_difficulties()

        empty_session = DiagnosticSessionProgress(user_id=request.user_id, answers=[])

        return _build_preview_response_for_session(
            selector=selector,
            questions=questions,
            difficulties=difficulties,
            session=empty_session,
            coverage_topics=request.coverage_topics,
            topic_question_counts=request.topic_question_counts,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi init Diagnostic: {str(e)}")


@router.post(
    "/next-question",
    response_model=DiagnosticPreviewResponse,
    summary="Lấy câu tiếp theo + preview next cho bài Diagnostic hiện tại",
)
async def get_next_preview_question(
    request: DiagnosticNextQuestionRequest,
    selector: QuestionSelectorService = Depends(get_question_selector),
):
    """
    API get next preview question:
    - Input: toàn bộ session progress (các câu đã làm trong bài Diagnostic hiện tại)
    - Output: {
        "current_question": {
            "question_id": "6448245131706368",
            "topic_id": 5878262490202112
        },
        "preview_next_question": {
            "if_correct": {
            "question_id": "5008459000971264",
            "topic_id": 5878262490202112,
            },
            "if_incorrect": {
            "question_id": "5430671466037248",
            "topic_id": 5878262490202112,
            }
        }
    """
    try:
        questions, difficulties = load_questions_and_difficulties()
        return _build_preview_response_for_session(
            selector=selector,
            questions=questions,
            difficulties=difficulties,
            session=request.session,
            coverage_topics=request.coverage_topics,
            topic_question_counts=request.topic_question_counts,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        # Ví dụ: không còn câu hỏi nào để chọn
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi lấy next preview question: {str(e)}"
        )


@router.post(
    "/submit-answer",
    response_model=DiagnosticSubmitAnswerResponse,
    summary="Submit câu trả lời cho một câu trong bài Diagnostic",
)
async def submit_diagnostic_answer(request: DiagnosticSubmitAnswerRequest):
    """
    API submit câu trả lời của người dùng.

    """
    return DiagnosticSubmitAnswerResponse(
        success=True,
        message="Answer submitted successfully (no server-side session persisted).",
    )


@router.post(
    "/result",
    response_model=DiagnosticResultResponse,
    summary="Tính kết quả bài Diagnostic từ user question progress của phần Diagnostic",
)
async def calculate_diagnostic_result(
    request: DiagnosticSessionProgress,
    selector: QuestionSelectorService = Depends(get_question_selector),
):
    """
    Tính kết quả cho một bài Diagnostic dựa trên progress (các câu đã làm trong bài Diagnostic).

    - Input: toàn bộ `DiagnosticSessionProgress` của bài Diagnostic.
    - Output: overall_ability + ability theo main/sub topic, kèm thông tin các subtopic đã cover.
    """
    try:
        _, question_difficulties = load_questions_and_difficulties()
        user_responses: List[UserResponse] = [
            UserResponse(
                question_id=ans.question_id,
                is_correct=ans.is_correct,
                response_time=30.0,
                timestamp=0,
                choice_selected=-1,
            )
            for ans in request.answers
        ]
        
        if not user_responses:
            raise HTTPException(
                status_code=400,
                detail="Session Diagnostic không có câu trả lời nào.",
            )

        estimator: AbilityEstimatorService = get_ability_estimator()

        ability, confidence = estimator.estimate_ability(
            user_responses, question_difficulties
        )

        question_topic_map = get_question_topic_map()

        main_topic_abilities_dict = estimator.estimate_topic_abilities(
            user_responses,
            question_topic_map,
            question_difficulties,
            topic_type="main",
            min_responses=1,
        )

        sub_topic_abilities_dict = estimator.estimate_topic_abilities(
            user_responses,
            question_topic_map,
            question_difficulties,
            topic_type="sub",
            min_responses=1,
        )

        main_topic_abilities = [
            TopicAbility(
                topic_id=topic_id,
                ability=ability_val,
                confidence=conf,
                num_responses=num_resp,
            )
            for topic_id, (ability_val, conf, num_resp) in main_topic_abilities_dict.items()
        ]

        sub_topic_abilities = [
            TopicAbility(
                topic_id=topic_id,
                ability=ability_val,
                confidence=conf,
                num_responses=num_resp,
            )
            for topic_id, (ability_val, conf, num_resp) in sub_topic_abilities_dict.items()
        ]

        question_topic_full_map = get_question_topic_map()
        covered_subtopics_set = set()
        for ans in request.answers:
            topic_info = question_topic_full_map.get(ans.question_id, {})
            sub_topic_id = topic_info.get("sub_topic_id")
            if sub_topic_id:
                covered_subtopics_set.add(str(sub_topic_id))

        covered_subtopics = sorted(list(covered_subtopics_set))
        completed_all_subtopics = bool(covered_subtopics)

        return DiagnosticResultResponse(
            user_id=request.user_id,
            overall_ability=ability,
            confidence=confidence,
            main_topic_abilities=main_topic_abilities,
            sub_topic_abilities=sub_topic_abilities,
            covered_subtopics=covered_subtopics,
            completed_all_subtopics=completed_all_subtopics,
            message="Diagnostic result calculated successfully",
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi tính kết quả Diagnostic: {str(e)}"
        )

