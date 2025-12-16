"""
Diagnostic Test API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict
import json
import os
import csv
import random
from api.schemas import (
    DiagnosticQuestionSetRequest,
    DiagnosticQuestionSetResponse,
    QuestionResponse,
    AllQuestionsResponse,
    QuestionStatistics,
    QuestionDistributions,
    DifficultyStatistics,
    DiscriminationStatistics,
    DifficultyDistribution,
    TopicDistribution,
    TopicInfo,
    EstimateAbilityRequest,
    UserAbilityResponse,
    TopicAbility,
    EstimateAbilitiesBatchRequest,
    EstimateAbilitiesBatchResponse,
    BatchUserAbilityResponse,
    PassingProbabilityRequest,
    PassingProbabilityResponse,
    DiagnosticUserAnswer,
)
from services.question_selector_service import QuestionSelectorService
from services.data_loader_service import DataLoaderService
from services.analysis_service import AnalysisService
from services.user_response_loader_service import UserResponseLoaderService
from services.ability_estimator_service import AbilityEstimatorService
from services.passing_probability_service import PassingProbabilityService
from models.irt_model import IRTModel
from models.question import Question
from models.user_response import UserResponse

router = APIRouter(prefix="/api/diagnostic", tags=["Diagnostic Test"])

_questions_cache = None
_difficulties_cache = None
_progress_data_cache = None

def get_question_selector() -> QuestionSelectorService:
    """Dependency để tạo QuestionSelectorService"""
    irt_model = IRTModel(guessing_param=0.25)
    return QuestionSelectorService(irt_model)

def load_questions_and_difficulties():
    """Load câu hỏi và độ khó (có cache)"""
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

def load_progress_data():
    """Load progress data (có cache)"""
    global _progress_data_cache
    
    if _progress_data_cache is not None:
        return _progress_data_cache
    
    progress_file = "user_question_progress_100000.json"
    if not os.path.exists(progress_file):
        raise FileNotFoundError(f"File không tồn tại: {progress_file}")
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        _progress_data_cache = json.load(f)
    
    return _progress_data_cache

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


@router.post("/estimate-ability",
             response_model=UserAbilityResponse,
             summary="Tính toán năng lực (ability) của một user cụ thể")
async def estimate_ability(
    request: EstimateAbilityRequest,
    estimator: AbilityEstimatorService = Depends(get_ability_estimator)
):
    """
    Tính toán năng lực (ability) của một user cụ thể dựa trên lịch sử trả lời
    
    API này sẽ:
    1. Load lịch sử trả lời của user từ dữ liệu
    2. Tính toán ability sử dụng IRT model (MLE)
    3. Trả về ability và độ tin cậy
    
    **Ability được tính trong thang Standard Normal:**
    - Giá trị âm: Năng lực dưới trung bình
    - Giá trị dương: Năng lực trên trung bình
    - Giá trị 0: Năng lực trung bình
    
    Args:
        request: Request chứa user_id
    
    Returns:
        UserAbilityResponse với overall_ability, confidence và số câu đã trả lời
    """
    try:
        progress_data = load_progress_data()
        _, question_difficulties = load_questions_and_difficulties()
        
        user_responses = UserResponseLoaderService.load_user_responses(
            progress_data, 
            request.user_id
        )
        
        if not user_responses:
            raise HTTPException(
                status_code=404, 
                detail=f"Không tìm thấy dữ liệu trả lời cho user {request.user_id}"
            )
        
        ability, confidence = estimator.estimate_ability(
            user_responses,
            question_difficulties
        )
        
        question_topic_map = get_question_topic_map()
        
        main_topic_abilities_dict = estimator.estimate_topic_abilities(
            user_responses,
            question_topic_map,
            question_difficulties,
            topic_type="main",
            min_responses=3
        )
        
        sub_topic_abilities_dict = estimator.estimate_topic_abilities(
            user_responses,
            question_topic_map,
            question_difficulties,
            topic_type="sub",
            min_responses=3
        )
        
        main_topic_abilities = [
            TopicAbility(
                topic_id=topic_id,
                ability=ability_val,
                confidence=conf,
                num_responses=num_resp
            )
            for topic_id, (ability_val, conf, num_resp) in main_topic_abilities_dict.items()
        ]
        
        sub_topic_abilities = [
            TopicAbility(
                topic_id=topic_id,
                ability=ability_val,
                confidence=conf,
                num_responses=num_resp
            )
            for topic_id, (ability_val, conf, num_resp) in sub_topic_abilities_dict.items()
        ]
        
        return UserAbilityResponse(
            user_id=request.user_id,
            overall_ability=ability,
            confidence=confidence,
            num_responses=len(user_responses),
            main_topic_abilities=main_topic_abilities,
            sub_topic_abilities=sub_topic_abilities,
            message="Ability estimated successfully"
        )
    
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tính ability: {str(e)}")


@router.post("/estimate-abilities-batch",
             response_model=EstimateAbilitiesBatchResponse,
             summary="Tính toán năng lực (ability) của nhiều user cùng lúc")
async def estimate_abilities_batch(
    request: EstimateAbilitiesBatchRequest,
    estimator: AbilityEstimatorService = Depends(get_ability_estimator)
):
    """
    Tính toán năng lực (ability) của nhiều user cùng lúc
    
    API này sẽ:
    1. Load lịch sử trả lời của tất cả user trong danh sách
    2. Tính toán ability cho từng user
    3. Trả về kết quả cho tất cả user (bao gồm cả những user không có dữ liệu)
    
    **Giới hạn:** Tối đa 100 user mỗi lần request
    
    Args:
        request: Request chứa danh sách user_ids
    
    Returns:
        EstimateAbilitiesBatchResponse với kết quả cho tất cả user
    """
    try:
        progress_data = load_progress_data()
        _, question_difficulties = load_questions_and_difficulties()
        question_topic_map = get_question_topic_map()
        
        users_responses_map = UserResponseLoaderService.load_multiple_users_responses(
            progress_data,
            request.user_ids
        )
        
        results = []
        successful_count = 0
        failed_count = 0
        
        for user_id in request.user_ids:
            user_responses = users_responses_map.get(str(user_id), [])
            
            if not user_responses:
                results.append(BatchUserAbilityResponse(
                    user_id=str(user_id),
                    overall_ability=None,
                    confidence=None,
                    num_responses=0,
                    main_topic_abilities=None,
                    sub_topic_abilities=None,
                    error="Không tìm thấy dữ liệu trả lời"
                ))
                failed_count += 1
            else:
                try:
                    ability, confidence = estimator.estimate_ability(
                        user_responses,
                        question_difficulties
                    )
                    
                    main_topic_abilities_dict = estimator.estimate_topic_abilities(
                        user_responses,
                        question_topic_map,
                        question_difficulties,
                        topic_type="main",
                        min_responses=3
                    )
                    
                    sub_topic_abilities_dict = estimator.estimate_topic_abilities(
                        user_responses,
                        question_topic_map,
                        question_difficulties,
                        topic_type="sub",
                        min_responses=3
                    )
                    
                    main_topic_abilities = [
                        TopicAbility(
                            topic_id=topic_id,
                            ability=ability_val,
                            confidence=conf,
                            num_responses=num_resp
                        )
                        for topic_id, (ability_val, conf, num_resp) in main_topic_abilities_dict.items()
                    ]
                    
                    sub_topic_abilities = [
                        TopicAbility(
                            topic_id=topic_id,
                            ability=ability_val,
                            confidence=conf,
                            num_responses=num_resp
                        )
                        for topic_id, (ability_val, conf, num_resp) in sub_topic_abilities_dict.items()
                    ]
                    
                    results.append(BatchUserAbilityResponse(
                        user_id=str(user_id),
                        overall_ability=ability,
                        confidence=confidence,
                        num_responses=len(user_responses),
                        main_topic_abilities=main_topic_abilities if main_topic_abilities else None,
                        sub_topic_abilities=sub_topic_abilities if sub_topic_abilities else None,
                        error=None
                    ))
                    successful_count += 1
                except Exception as e:
                    results.append(BatchUserAbilityResponse(
                        user_id=str(user_id),
                        overall_ability=None,
                        confidence=None,
                        num_responses=len(user_responses),
                        main_topic_abilities=None,
                        sub_topic_abilities=None,
                        error=f"Lỗi khi tính ability: {str(e)}"
                    ))
                    failed_count += 1
        
        return EstimateAbilitiesBatchResponse(
            results=results,
            total_users=len(request.user_ids),
            successful_count=successful_count,
            failed_count=failed_count
        )
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tính ability batch: {str(e)}")

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

@router.post("/passing-probability", response_model=PassingProbabilityResponse)
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
            user_responses: List[UserResponse] = [
                UserResponse(
                    question_id=ans.question_id,
                    is_correct=ans.is_correct,
                    response_time=30.0,
                    timestamp=0,
                    choice_selected=-1,
                )
                for ans in request.user_responses
            ]
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
        
        passing_prob, confidence_score, expected_score, exam_info = \
            passing_prob_service.calculate_passing_probability(
                user_id=request.user_id,
                exam_questions=exam_questions,
                passing_threshold=request.exam_structure.passing_threshold,
                user_responses=user_responses,
                question_difficulties=question_difficulties,
                total_score=request.exam_structure.total_score
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

