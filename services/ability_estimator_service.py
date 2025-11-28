"""
Ability Estimator Service
"""

import math
from typing import Dict, Tuple, List

from models.user_response import UserResponse
from models.irt_model import IRTModel

class AbilityEstimatorService:
    """
    Service để ước tính năng lực người học dựa trên lịch sử trả lời
    """
    
    def __init__(self, irt_model: IRTModel):
        self.irt_model = irt_model
    
    def estimate_ability(self, responses: List[UserResponse], 
                        question_difficulties: Dict[str, float],
                        initial_ability: float = 0.0,
                        max_iterations: int = 10,
                        tolerance: float = 0.001) -> Tuple[float, float]:
        """
        Ước tính năng lực sử dụng Maximum Likelihood Estimation (MLE)
        
        Args:
            responses: Lịch sử trả lời của người học
            question_difficulties: Dict mapping question_id -> difficulty (Standard Normal)
            initial_ability: Giá trị khởi tạo
            max_iterations: Số lần lặp tối đa
        
        Returns:
            Tuple (ability, confidence) - ability trong thang Standard Normal
        """
        if not responses:
            return initial_ability, 0.0
        
        ability = initial_ability

        c = self.irt_model.guessing_param
        
        for _ in range(max_iterations):
            likelihood_derivative = 0.0
            information = 0.0
            
            for response in responses:
                a = 1
                difficulty = question_difficulties.get(response.question_id, 0.0)
                prob = self.irt_model.probability_correct(ability, difficulty)
                
                if prob <= c + 1e-9 or prob >= 1.0 - 1e-9:
                    continue

                u = 1.0 if response.is_correct else 0.0
                
                weight = (prob - c) / (prob * (1 - c))
                score = a * (u - prob) * weight
                likelihood_derivative += score

                info = self.irt_model.information(ability, difficulty)
                information += info
            
            if information <= 1e-9:
                break
            
            change = likelihood_derivative / information

            change = max(-2.0, min(2.0, change))

            ability += change
            
            if abs(change) < tolerance:
                break
        
        ability = max(-3.0, min(3.0, ability))

        se = 1.0 / math.sqrt(information) if information > 1e-9 else 1.0
        confidence = 1.0 / (1.0 + se)
        
        return ability, confidence
    
    def estimate_topic_abilities(self, 
                                 responses: List[UserResponse],
                                 question_topic_map: Dict[str, Dict[str, str]],
                                 question_difficulties: Dict[str, float],
                                 topic_type: str = "main",
                                 min_responses: int = 3) -> Dict[str, Tuple[float, float, int]]:
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
                question_difficulties
            )
            topic_abilities[topic_id] = (ability, confidence, num_resp)
        
        return topic_abilities

