"""
Diagnostic Session API endpoints
API cho adaptive Diagnostic Test session (init, next question, submit answer, result)
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict
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
    DiagnosticUserAnswer,
    TopicAbility,
)
from api.shared import (
    load_questions_and_difficulties,
    get_question_selector,
    get_ability_estimator,
    get_question_topic_map,
    get_topic_meta_map,
)
from services.question_selector_service import QuestionSelectorService
from services.ability_estimator_service import AbilityEstimatorService
from models.question import Question
from models.user_response import UserResponse

router = APIRouter(prefix="/api/diagnostic", tags=["Diagnostic Session"])


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


def _get_current_active_topic(
    session: DiagnosticSessionProgress,
    topic_question_counts: Optional[Dict[str, int]],
    question_topic_map: Dict[str, Dict[str, str]],
) -> Optional[str]:
    """
    Xác định topic hiện tại đang làm.
    Logic: Làm lần lượt từng topic, hết số câu của topic này rồi mới đến topic khác.
    
    Returns:
        topic_id hiện tại đang làm, hoặc None nếu chưa có topic nào hoặc đã hết topic
    """
    if not topic_question_counts:
        return None
    
    topic_answered_counts: Dict[str, int] = {}
    for ans in session.answers:
        topic_info = question_topic_map.get(ans.question_id, {})
        main_topic_id = str(topic_info.get("main_topic_id", ""))
        sub_topic_id = str(topic_info.get("sub_topic_id", ""))
        
        if main_topic_id and main_topic_id in topic_question_counts:
            topic_answered_counts[main_topic_id] = topic_answered_counts.get(main_topic_id, 0) + 1
        elif sub_topic_id and sub_topic_id in topic_question_counts:
            topic_answered_counts[sub_topic_id] = topic_answered_counts.get(sub_topic_id, 0) + 1
    
    for topic_id, required_count in topic_question_counts.items():
        answered_count = topic_answered_counts.get(topic_id, 0)
        if answered_count < required_count:
            return topic_id
    
    return None


def _filter_questions_by_topic(
    questions: List[Question],
    topic_id: str,
) -> List[Question]:
    """Lọc câu hỏi chỉ từ topic cụ thể."""
    return [
        q
        for q in questions
        if str(q.main_topic_id) == topic_id or str(q.sub_topic_id) == topic_id
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
    """
    topic_meta_map = get_topic_meta_map()
    question_topic_map = get_question_topic_map()
    
    all_candidate_questions = _filter_questions_by_topics(questions, coverage_topics)
    
    current_topic_id = None
    if topic_question_counts:
        current_topic_id = _get_current_active_topic(
            session=session,
            topic_question_counts=topic_question_counts,
            question_topic_map=question_topic_map,
        )
        
        if current_topic_id is None:
            raise ValueError("Tất cả các topic đã hoàn thành. Không còn câu hỏi nào để chọn.")
        
        candidate_questions = _filter_questions_by_topic(
            all_candidate_questions,
            current_topic_id,
        )
    else:
        candidate_questions = all_candidate_questions

    user_responses: List[UserResponse] = []
    for ans in session.answers:
        user_responses.append(
            UserResponse(
                question_id=ans.question_id,
                is_correct=ans.is_correct,
                response_time=30.0,
                timestamp=0,
                choice_selected=-1,
            )
        )

    current_question = selector.select_next_question(
        candidate_questions=candidate_questions,
        user_responses=user_responses,
        question_difficulties=difficulties,
    )

    def _get_preview_candidate_questions(
        session_with_answer: DiagnosticSessionProgress,
        current_topic_id: Optional[str],
        all_candidate_questions: List[Question],
        current_question: Question,
        topic_question_counts: Optional[Dict[str, int]],
        question_topic_map: Dict[str, Dict[str, str]],
    ) -> List[Question]:
        """
        Lấy danh sách câu hỏi candidate cho preview next question.
        Nếu topic hiện tại vẫn còn câu hỏi thì chọn từ topic đó,
        nếu không thì chọn từ topic tiếp theo.
        """
        if not topic_question_counts:
            remaining = [
                q for q in all_candidate_questions
                if q.question_id != current_question.question_id
            ]
            return remaining
        
        next_topic_id = _get_current_active_topic(
            session=session_with_answer,
            topic_question_counts=topic_question_counts,
            question_topic_map=question_topic_map,
        )
        
        if next_topic_id is None:
            return []
        
        topic_questions = _filter_questions_by_topic(
            all_candidate_questions,
            next_topic_id,
        )
        
        answered_ids = {ans.question_id for ans in session_with_answer.answers}
        return [
            q for q in topic_questions
            if q.question_id not in answered_ids
        ]

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

    session_if_correct = DiagnosticSessionProgress(
        user_id=session.user_id,
        answers=session.answers + [
            DiagnosticUserAnswer(
                question_id=current_question.question_id,
                is_correct=True,
            )
        ],
    )
    session_if_incorrect = DiagnosticSessionProgress(
        user_id=session.user_id,
        answers=session.answers + [
            DiagnosticUserAnswer(
                question_id=current_question.question_id,
                is_correct=False,
            )
        ],
    )

    preview_candidates_if_correct = _get_preview_candidate_questions(
        session_if_correct,
        current_topic_id,
        all_candidate_questions,
        current_question,
        topic_question_counts,
        question_topic_map,
    )
    preview_candidates_if_incorrect = _get_preview_candidate_questions(
        session_if_incorrect,
        current_topic_id,
        all_candidate_questions,
        current_question,
        topic_question_counts,
        question_topic_map,
    )

    if preview_candidates_if_correct:
        next_if_correct = selector.select_next_question(
            candidate_questions=preview_candidates_if_correct,
            user_responses=user_responses + [answer_correct],
            question_difficulties=difficulties,
        )
    else:
        next_if_correct = current_question

    if preview_candidates_if_incorrect:
        next_if_incorrect = selector.select_next_question(
            candidate_questions=preview_candidates_if_incorrect,
            user_responses=user_responses + [answer_incorrect],
            question_difficulties=difficulties,
        )
    else:
        next_if_incorrect = current_question

    def _resolve_topic_info(q: Question) -> Dict[str, str]:
        topic_id = str(q.main_topic_id or q.sub_topic_id)
        topic_info = topic_meta_map.get(topic_id, {})
        topic_name = topic_info.get("name")
        return {"topic_id": topic_id, "topic_name": topic_name}

    current_topic_info = _resolve_topic_info(current_question)
    correct_topic_info = _resolve_topic_info(next_if_correct)
    incorrect_topic_info = _resolve_topic_info(next_if_incorrect)

    current_difficulty = difficulties.get(current_question.question_id, 0.0)
    correct_difficulty = difficulties.get(next_if_correct.question_id, 0.0)
    incorrect_difficulty = difficulties.get(next_if_incorrect.question_id, 0.0)

    current_preview = DiagnosticPreviewQuestion(
        question_id=current_question.question_id,
        topic_id=current_topic_info["topic_id"],
        topic_name=current_topic_info["topic_name"],
        difficulty=current_difficulty,
    )
    if_correct_preview = DiagnosticPreviewQuestion(
        question_id=next_if_correct.question_id,
        topic_id=correct_topic_info["topic_id"],
        topic_name=correct_topic_info["topic_name"],
        difficulty=correct_difficulty,
    )
    if_incorrect_preview = DiagnosticPreviewQuestion(
        question_id=next_if_incorrect.question_id,
        topic_id=incorrect_topic_info["topic_id"],
        topic_name=incorrect_topic_info["topic_name"],
        difficulty=incorrect_difficulty,
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

        covered_subtopics_set = set()
        for ans in request.answers:
            topic_info = question_topic_map.get(ans.question_id, {})
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
