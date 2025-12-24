"""
Diagnostic Test API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from api.schemas import (
    DiagnosticQuestionSetRequest,
    DiagnosticQuestionSetResponse,
    QuestionResponse,
    QuestionDifficultyResponse,
    AllQuestionsResponse,
    QuestionStatistics,
    QuestionDistributions,
    DifficultyStatistics,
    DiscriminationStatistics,
    DifficultyDistribution,
    TopicDistribution,
    TopicInfo,
)
from api.shared import (
    load_questions_and_difficulties,
    get_question_selector,
)
from services.question_selector_service import QuestionSelectorService
from services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/diagnostic", tags=["Diagnostic Test"])


@router.post("/generate-initial-question-set", 
             response_model=DiagnosticQuestionSetResponse,
             summary="Sinh ra bộ câu hỏi đánh giá năng lực ban đầu")
async def generate_initial_question_set(
    request: DiagnosticQuestionSetRequest,
    selector: QuestionSelectorService = Depends(get_question_selector)
):
    """
    Sinh ra bộ câu hỏi đánh giá năng lực ban đầu cho Diagnostic Test
    
    API này sẽ:
    1. Load tất cả câu hỏi và độ khó từ dữ liệu
    2. Chọn bộ câu hỏi phù hợp dựa trên:
       - Số lượng yêu cầu
       - Topics cần bao phủ
       - Phân bố đều về độ khó
    
    **Các câu hỏi được chọn sẽ:**
    - Có độ khó đa dạng (từ dễ đến khó)
    - Bao phủ các topic quan trọng
    - Phù hợp để đánh giá năng lực ban đầu
    
    Returns:
        Danh sách câu hỏi với thông tin đầy đủ
    """
    try:
        all_questions, question_difficulties = load_questions_and_difficulties()
        
        selected_questions = selector.select_initial_question_set(
            all_questions=all_questions,
            question_difficulties=question_difficulties,
            num_questions=request.num_questions,
            coverage_topics=request.coverage_topics
        )
        
        question_responses = [
            QuestionResponse(
                question_id=q.question_id,
                main_topic_id=q.main_topic_id,
                sub_topic_id=q.sub_topic_id,
                difficulty=question_difficulties.get(q.question_id, q.difficulty),
                discrimination=q.discrimination
            )
            for q in selected_questions
        ]
        
        return DiagnosticQuestionSetResponse(
            questions=question_responses,
            total_questions=len(question_responses),
            message=f"Successfully generated {len(question_responses)} questions for diagnostic test"
        )
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi sinh câu hỏi: {str(e)}")


@router.get("/questions", 
            response_model=AllQuestionsResponse,
            summary="Lấy danh sách tất cả câu hỏi kèm phân tích và thống kê")
async def get_all_questions(limit: Optional[int] = None):
    """
    Lấy danh sách tất cả câu hỏi có sẵn trong hệ thống kèm phân tích và thống kê
    
    **Thống kê bao gồm:**
    - Tổng số câu hỏi
    - Thống kê về độ khó (min, max, mean, median, std)
    - Thống kê về độ phân biệt
    - Phân bố theo độ khó (dễ, trung bình, khó)
    - Phân bố theo topic (main topic và sub topic)
    - Top 5 topics có nhiều câu hỏi nhất
    
    Args:
        limit: Giới hạn số lượng câu hỏi trả về (None = trả về tất cả)
    
    Returns:
        Danh sách câu hỏi kèm phân tích và thống kê chi tiết
    """
    try:
        all_questions, question_difficulties = load_questions_and_difficulties()
        
        questions_to_return = all_questions
        limit_applied = False
        if limit is not None and limit > 0:
            questions_to_return = all_questions[:limit]
            limit_applied = True
        
        question_responses = [
            QuestionResponse(
                question_id=q.question_id,
                main_topic_id=q.main_topic_id,
                sub_topic_id=q.sub_topic_id,
                difficulty=question_difficulties.get(q.question_id, q.difficulty),
                discrimination=q.discrimination
            )
            for q in questions_to_return
        ]
        
        analysis = AnalysisService.analyze_questions(all_questions, question_difficulties)
        
        difficulty_stats = DifficultyStatistics(**analysis["statistics"]["difficulty"])
        discrimination_stats = DiscriminationStatistics(**analysis["statistics"]["discrimination"])
        statistics = QuestionStatistics(
            difficulty=difficulty_stats,
            discrimination=discrimination_stats
        )
        
        difficulty_dist = DifficultyDistribution(**analysis["distributions"]["difficulty"])
        topic_dist_data = analysis["distributions"]["topics"]
        top_topics = [TopicInfo(**t) for t in topic_dist_data["top_5_main_topics"]]
        topic_dist = TopicDistribution(
            by_main_topic=topic_dist_data["by_main_topic"],
            by_sub_topic=topic_dist_data["by_sub_topic"],
            total_main_topics=topic_dist_data["total_main_topics"],
            total_sub_topics=topic_dist_data["total_sub_topics"],
            top_5_main_topics=top_topics
        )
        distributions = QuestionDistributions(
            difficulty=difficulty_dist,
            topics=topic_dist
        )
        
        return AllQuestionsResponse(
            questions=question_responses,
            total_questions=analysis["total_questions"],
            statistics=statistics,
            distributions=distributions,
            limit_applied=limit_applied
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")


@router.get(
    "/question/{question_id}/difficulty",
    response_model=QuestionDifficultyResponse,
    summary="Lấy độ khó của câu hỏi theo question_id"
)
async def get_question_difficulty(question_id: str):
    """
    Lấy độ khó của một câu hỏi cụ thể theo question_id
    
    Args:
        question_id: ID của câu hỏi cần lấy độ khó
    
    Returns:
        Độ khó của câu hỏi trong thang Standard Normal [-3, +3]
    """
    try:
        _, question_difficulties = load_questions_and_difficulties()
        
        if question_id not in question_difficulties:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy câu hỏi với ID: {question_id}"
            )
        
        difficulty = question_difficulties[question_id]
        
        return QuestionDifficultyResponse(
            question_id=question_id,
            difficulty=difficulty
        )
    
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi lấy độ khó câu hỏi: {str(e)}"
        )
