"""
Next Action API endpoints
API để tính toán năng lực (ability) của user
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
import json
from api.schemas import (
    EstimateAbilityRequest,
    UserAbilityResponse,
    TopicAbility,
    EstimateAbilitiesBatchRequest,
    EstimateAbilitiesBatchResponse,
    BatchUserAbilityResponse,
)
from api.shared import (
    load_questions_and_difficulties,
    load_progress_data,
    get_ability_estimator,
    get_question_topic_map,
    load_all_responses,
)
from services.user_response_loader_service import UserResponseLoaderService
from services.ability_estimator_service import AbilityEstimatorService
from models.user_response import UserResponse

router = APIRouter(prefix="/api/next-action", tags=["Next Action"])


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
    1. Load lịch sử trả lời của user từ dữ liệu hoặc sử dụng user_responses từ request
    2. Tính toán ability sử dụng IRT model (MLE)
    3. Trả về ability và độ tin cậy
    
    **Ability được tính trong thang Standard Normal:**
    - Giá trị âm: Năng lực dưới trung bình
    - Giá trị dương: Năng lực trên trung bình
    - Giá trị 0: Năng lực trung bình
    
    **Lịch sử trả lời:**
    - Nếu truyền user_responses trong request, API sẽ sử dụng dữ liệu đó thay vì load từ file
    - Nếu không truyền user_responses, API sẽ load từ dữ liệu đã lưu
    
    Args:
        request: Request chứa user_id và optional user_responses
    
    Returns:
        UserAbilityResponse với overall_ability, confidence và số câu đã trả lời
    """
    try:
        progress_data = load_progress_data()
        _, question_difficulties = load_questions_and_difficulties()
        
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
                    f"Không tìm thấy dữ liệu trả lời cho user {request.user_id} "
                    "(truyền user_responses hoặc đảm bảo có dữ liệu đã lưu)."
                )
            )
        
        all_responses = load_all_responses()
        
        ability, confidence = estimator.estimate_ability(
            user_responses,
            question_difficulties,
            all_responses_for_expected_time=all_responses
        )
        
        question_topic_map = get_question_topic_map()
        
        main_topic_abilities_dict = estimator.estimate_topic_abilities(
            user_responses,
            question_topic_map,
            question_difficulties,
            topic_type="main",
            min_responses=1,
            all_responses_for_expected_time=all_responses
        )
        
        sub_topic_abilities_dict = estimator.estimate_topic_abilities(
            user_responses,
            question_topic_map,
            question_difficulties,
            topic_type="sub",
            min_responses=1,
            all_responses_for_expected_time=all_responses
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
        
        all_responses = load_all_responses()
        
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
                        question_difficulties,
                        all_responses_for_expected_time=all_responses
                    )
                    
                    main_topic_abilities_dict = estimator.estimate_topic_abilities(
                        user_responses,
                        question_topic_map,
                        question_difficulties,
                        topic_type="main",
                        min_responses=1,
                        all_responses_for_expected_time=all_responses
                    )
                    
                    sub_topic_abilities_dict = estimator.estimate_topic_abilities(
                        user_responses,
                        question_topic_map,
                        question_difficulties,
                        topic_type="sub",
                        min_responses=1,
                        all_responses_for_expected_time=all_responses
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
