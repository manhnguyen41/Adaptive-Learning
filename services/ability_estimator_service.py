"""
Ability Estimator Service
"""

import math
from typing import Dict, Tuple, List, Optional
from collections import defaultdict

from models.user_response import UserResponse
from models.irt_model import IRTModel


def compute_prior_sigma(
    num_responses: int,
    sigma_min: float = 0.5,
    sigma_max: float = 2.0,
    k: float = 5.0,
) -> float:
    """
    Tính sigma_prior(n) = sigma_min + (sigma_max - sigma_min) * (1 - exp(-n / k)).

    - num_responses: số câu đã trả lời (len(responses))
    - sigma_min: prior rất chặt khi n nhỏ
    - sigma_max: prior rất lỏng khi n lớn
    - k: điều chỉnh tốc độ “nới lỏng” prior theo n
    """
    if num_responses <= 0:
        return sigma_min
    factor = 1.0 - math.exp(-num_responses / k)
    return sigma_min + (sigma_max - sigma_min) * factor


class AbilityEstimatorService:
    """
    Service để ước tính năng lực người học dựa trên lịch sử trả lời
    Tích hợp thời gian trả lời vào tính toán (Time-Weighted Information)
    """
    
    def __init__(self, irt_model: IRTModel, use_time_weighting: bool = False, time_scale: float = 20.0):
        """
        Args:
            irt_model: IRT model để tính probability và information
            use_time_weighting: Có sử dụng trọng số thời gian không (mặc định: True)
            time_scale: Tham số điều chỉnh độ nhạy của time weight (mặc định: 20.0 giây)
        """
        self.irt_model = irt_model
        self.use_time_weighting = use_time_weighting
        self.time_scale = time_scale
    
    def _calculate_expected_times(self, responses: List[UserResponse]) -> Dict[str, float]:
        """
        Tính thời gian trung bình (expected_time) cho mỗi câu hỏi từ responses
        
        Args:
            responses: Danh sách responses để tính expected_time
            
        Returns:
            Dict mapping question_id -> expected_time (giây)
        """
        question_times = defaultdict(list)
        
        for response in responses:
            if response.response_time > 0:  
                question_times[response.question_id].append(response.response_time)
        
        expected_times = {}
        for question_id, times in question_times.items():
            if times:
                expected_times[question_id] = sum(times) / len(times)
            else:
                expected_times[question_id] = 30.0 
        
        return expected_times
    
    def _calculate_time_weight(self, response_time: float, expected_time: float) -> float:
        """
        Tính trọng số thời gian dựa trên response_time và expected_time
        
        Args:
            response_time: Thời gian trả lời thực tế (giây)
            expected_time: Thời gian trung bình cho câu hỏi này (giây)
            
        Returns:
            Time weight (0.0 - 2.0)
        """
        if not self.use_time_weighting:
            return 1.0
        
        if expected_time <= 0:
            return 1.0
        
        time_ratio = response_time / expected_time
        
        if time_ratio <= 0.5:
            return 1.2
        elif time_ratio <= 0.8:
            return 1.1
        elif time_ratio <= 1.0:
            return 1.0
        elif time_ratio <= 1.5:
            return 0.9
        elif time_ratio <= 2.0:
            return 0.7
        else:
            return 0.5
    
    def _calculate_time_weight_sigmoid(self, response_time: float, expected_time: float) -> float:
        """
        Tính trọng số thời gian sử dụng sigmoid function (phương án thay thế)
        
        Args:
            response_time: Thời gian trả lời thực tế (giây)
            expected_time: Thời gian trung bình cho câu hỏi này (giây)
            
        Returns:
            Time weight (0.0 - 2.0)
        """
        if not self.use_time_weighting:
            return 1.0
        
        if expected_time <= 0:
            return 1.0
        
        time_diff = response_time - expected_time
        sigmoid_input = -time_diff / self.time_scale
        
        weight = 1.0 / (1.0 + math.exp(sigmoid_input))
        
        return max(0.3, min(1.5, 0.7 + 0.6 * weight))
    
    def estimate_ability(
        self,
        responses: List[UserResponse],
        question_difficulties: Dict[str, float],
        initial_ability: float = 0.0,
        max_iterations: int = 10,
        tolerance: float = 0.001,
        all_responses_for_expected_time: Optional[List[UserResponse]] = None,
        use_map: bool = True,
        sigma_min: float = 0.5,
        sigma_max: float = 2.0,
        k_prior: float = 5.0,
    ) -> Tuple[float, float]:
        """
        Ước tính năng lực sử dụng Maximum Likelihood Estimation (MLE)
        hoặc Maximum A Posteriori (MAP) với prior Gaussian cho ability.
        
        Args:
            responses: Lịch sử trả lời của người học
            question_difficulties: Dict mapping question_id -> difficulty (Standard Normal)
            initial_ability: Giá trị khởi tạo
            max_iterations: Số lần lặp tối đa
            tolerance: Ngưỡng dừng khi thay đổi ability < tolerance
            all_responses_for_expected_time: Tất cả responses để tính expected_time 
                                            (nếu None, dùng responses hiện tại)
            use_map: True => dùng MAP với prior Gaussian; False => MLE thuần
            sigma_min, sigma_max, k_prior: tham số cho sigma_prior(n)
        
        Returns:
            Tuple (ability, confidence) - ability trong thang Standard Normal
        """
        if not responses:
            return initial_ability, 0.0
        
        ability = initial_ability
        c = self.irt_model.guessing_param
        
        if self.use_time_weighting:
            responses_for_expected = (
                all_responses_for_expected_time
                if all_responses_for_expected_time
                else responses
            )
            expected_times = self._calculate_expected_times(responses_for_expected)
        else:
            expected_times = {}

        num_responses = len(responses)
        
        for _ in range(max_iterations):
            likelihood_derivative = 0.0
            information = 0.0
            
            for response in responses:
                a = 1.0
                difficulty = question_difficulties.get(response.question_id, 0.0)
                prob = self.irt_model.probability_correct(ability, difficulty)
                
                if prob <= c + 1e-9 or prob >= 1.0 - 1e-9:
                    continue

                u = 1.0 if response.is_correct else 0.0
                
                weight = (prob - c) / (prob * (1 - c))
                score = a * (u - prob) * weight
                likelihood_derivative += score

                info = self.irt_model.information(ability, difficulty)
                
                if self.use_time_weighting:
                    expected_time = expected_times.get(response.question_id, 30.0)
                    time_weight = self._calculate_time_weight(
                        response.response_time, expected_time
                    )
                    info = info * time_weight
                
                information += info

            if use_map:
                prior_sigma = compute_prior_sigma(
                    num_responses=num_responses,
                    sigma_min=sigma_min,
                    sigma_max=sigma_max,
                    k=k_prior,
                )
                prior_var = prior_sigma ** 2

                prior_derivative = -ability / prior_var          # d/dθ log p(θ)
                prior_information = 1.0 / prior_var              # -d²/dθ² log p(θ)

                total_derivative = likelihood_derivative + prior_derivative
                total_information = information + prior_information
            else:
                total_derivative = likelihood_derivative
                total_information = information
            
            if total_information <= 1e-9:
                break
            
            change = total_derivative / total_information

            change = max(-2.0, min(2.0, change))

            ability += change
            
            if abs(change) < tolerance:
                break
        
        ability = max(-3.0, min(3.0, ability))

        if use_map and "total_information" in locals() and total_information > 1e-9:
            info_for_conf = total_information
        else:
            info_for_conf = information if information > 1e-9 else 1.0

        se = 1.0 / math.sqrt(info_for_conf)
        confidence = 1.0 / (1.0 + se)
        
        return ability, confidence
    
    def estimate_topic_abilities(self, 
                                 responses: List[UserResponse],
                                 question_topic_map: Dict[str, Dict[str, str]],
                                 question_difficulties: Dict[str, float],
                                 topic_type: str = "main",
                                 min_responses: int = 1,
                                 all_responses_for_expected_time: Optional[List[UserResponse]] = None) -> Dict[str, Tuple[float, float, int]]:
        """
        Ước tính năng lực theo từng topic
        
        Args:
            responses: Lịch sử trả lời của người học
            question_topic_map: Dict mapping question_id -> {main_topic_id, sub_topic_id}
            question_difficulties: Dict mapping question_id -> difficulty (Standard Normal)
            topic_type: "main" hoặc "sub" để tính theo main topic hay sub topic
            min_responses: Số lượng responses tối thiểu để tính ability (mặc định: 3)
        
        Returns:
            Dict mapping topic_id -> (ability, confidence, num_responses)
        """
        if not responses:
            return {}
        
        from collections import defaultdict
        topic_responses = defaultdict(list)
        
        topic_key = "main_topic_id" if topic_type == "main" else "sub_topic_id"
        
        for response in responses:
            topic_info = question_topic_map.get(response.question_id, {})
            topic_id = topic_info.get(topic_key, "")
            
            if topic_id:
                topic_responses[topic_id].append(response)
        
        topic_abilities = {}
        for topic_id, topic_resp in topic_responses.items():
            num_resp = len(topic_resp)
            if num_resp < min_responses:  # Cần ít nhất min_responses câu để tính ability đáng tin cậy
                continue
            
            ability, confidence = self.estimate_ability(
                topic_resp,
                question_difficulties,
                all_responses_for_expected_time=all_responses_for_expected_time
            )
            topic_abilities[topic_id] = (ability, confidence, num_resp)
        
        return topic_abilities

