"""
Passing Probability Service - Tính xác suất đậu bài thi thật
"""

import math
from typing import Dict, List, Tuple
import numpy as np

from models.irt_model import IRTModel
from models.user_response import UserResponse
from services.ability_estimator_service import AbilityEstimatorService

class PassingProbabilityService:
    """
    Service để tính xác suất đậu bài thi thật của người học
    Sử dụng IRT model để dự đoán xác suất trả lời đúng từng câu hỏi
    """
    
    def __init__(self, irt_model: IRTModel, ability_estimator: AbilityEstimatorService):
        self.irt_model = irt_model
        self.ability_estimator = ability_estimator
    
    def calculate_passing_probability(
        self,
        user_id: str,
        exam_questions: List[Dict],
        passing_threshold: float,
        user_responses: List[UserResponse],
        question_difficulties: Dict[str, float],
        question_topic_map: Dict[str, Dict[str, str]] = None,
        total_score: int = None,
        all_responses_for_expected_time: List[UserResponse] = None
    ) -> Tuple[float, float, str, float, Dict]:
        """
        Tính xác suất đậu bài thi thật
        
        Args:
            user_id: ID của user
            exam_questions: Danh sách câu hỏi trong đề thi [{"question_id": str, "difficulty": float, "discrimination": float}]
            passing_threshold: Ngưỡng đậu (0-1, ví dụ: 0.7 = 70%)
            user_responses: Lịch sử trả lời của user (để tính ability)
            question_difficulties: Dict mapping question_id -> difficulty (Standard Normal)
            question_topic_map: Dict mapping question_id -> {main_topic_id, sub_topic_id}
            total_score: Tổng điểm của đề thi. Nếu None, dùng số lượng câu hỏi
        
        Returns:
            Tuple (passing_probability, confidence_score, confidence_level, expected_score, exam_info)
            - passing_probability: Xác suất đậu (0-100%)
            - confidence_score: Điểm tin cậy (0-1)
            - confidence_level: Mức độ tin cậy ("high", "medium", "low")
            - expected_score: Điểm số dự kiến (0-100%)
            - exam_info: Thông tin về đề thi
        """
        if not exam_questions:
            return 0.0, 0.0, "low", 0.0, {}
        
        overall_ability, overall_ability_confidence = self.ability_estimator.estimate_ability(
            user_responses,
            question_difficulties,
            all_responses_for_expected_time=all_responses_for_expected_time
        )
        
        main_topic_abilities = {}
        if question_topic_map:
            main_topic_abilities_dict = self.ability_estimator.estimate_topic_abilities(
                user_responses,
                question_topic_map,
                question_difficulties,
                topic_type="main",
                min_responses=1,
                all_responses_for_expected_time=all_responses_for_expected_time
            )
            main_topic_abilities = {
                topic_id: ability_val
                for topic_id, (ability_val, _, _) in main_topic_abilities_dict.items()
            }
        
        question_probs = []
        total_difficulty = 0.0
        
        for q in exam_questions:
            question_id = q.get("question_id", "")
            difficulty = q.get("difficulty")
            discrimination = q.get("discrimination", 1.0)
            
            if difficulty is None:
                difficulty = question_difficulties.get(question_id, 0.0)
            
            ability_to_use = overall_ability
            if question_topic_map:
                topic_info = question_topic_map.get(question_id, {})
                main_topic_id = str(topic_info.get("main_topic_id", ""))
                if main_topic_id and main_topic_id in main_topic_abilities:
                    ability_to_use = main_topic_abilities[main_topic_id]
            
            prob = self.irt_model.probability_correct(
                ability=ability_to_use,
                difficulty=difficulty,
                discrimination=discrimination
            )
            
            question_probs.append(prob)
            total_difficulty += difficulty
        
        num_questions = len(exam_questions)
        avg_difficulty = total_difficulty / num_questions if num_questions > 0 else 0.0
        
        expected_correct = sum(question_probs)
        expected_score = (expected_correct / num_questions) * 100.0 if num_questions > 0 else 0.0
        
        min_correct = math.ceil(passing_threshold * num_questions)
        
        passing_prob = 0.0
        
        if num_questions > 0:
            # Sử dụng xấp xỉ chuẩn nếu số câu hỏi lớn (>30)
            if num_questions > 30:
                mean = expected_correct
                variance = sum(p * (1 - p) for p in question_probs)
                std = math.sqrt(variance) if variance > 0 else 1.0
                
                z_score = (min_correct - 0.5 - mean) / std if std > 0 else 0.0
                passing_prob = 1.0 - (0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0))))
            else:
                # Tính chính xác bằng phân phối nhị thức Poisson
                for k in range(min_correct, num_questions + 1):
                    prob_k = self._binomial_probability(question_probs, k, num_questions)
                    passing_prob += prob_k
        
        passing_prob = max(0.0, min(100.0, passing_prob * 100.0))
        
        ability_conf = overall_ability_confidence
        
        num_questions_conf = min(1.0, num_questions / 50.0) 
        
        if len(question_probs) > 1:
            prob_variance = np.var(question_probs)
            variance_conf = min(1.0, prob_variance * 4.0)  
        else:
            variance_conf = 0.5
        
        confidence_score = (ability_conf * 0.5 + num_questions_conf * 0.3 + variance_conf * 0.2)
        confidence_score = max(0.0, min(1.0, confidence_score))
        
        topic_statistics = {}
        if question_topic_map and user_responses:
            from collections import defaultdict
            topic_total = defaultdict(int)
            topic_correct = defaultdict(int)
            
            for response in user_responses:
                topic_info = question_topic_map.get(response.question_id, {})
                main_topic_id = str(topic_info.get("main_topic_id", ""))
                
                if main_topic_id:
                    topic_total[main_topic_id] += 1
                    if response.is_correct:
                        topic_correct[main_topic_id] += 1
            
            for topic_id in topic_total:
                total = topic_total[topic_id]
                correct = topic_correct[topic_id]
                accuracy = (correct / total * 100.0) if total > 0 else 0.0
                
                topic_statistics[topic_id] = {
                    "total": total,
                    "correct": correct,
                    "accuracy": round(accuracy, 2)
                }
        
        exam_info = {
            "total_questions": num_questions,
            "average_difficulty": round(avg_difficulty, 2),
            "min_correct_needed": min_correct,
            "overall_ability": round(overall_ability, 2),
            "ability_confidence": round(overall_ability_confidence, 2),
            "main_topic_abilities": {
                topic_id: round(ability_val, 2)
                for topic_id, ability_val in main_topic_abilities.items()
            } if main_topic_abilities else {},
            "topic_statistics": topic_statistics
        }
        
        return passing_prob, confidence_score, expected_score, exam_info
    
    def _binomial_probability(self, probs: List[float], k: int, n: int) -> float:
        """
        Tính xác suất đúng đúng k câu trong n câu
        Sử dụng dynamic programming để tính hiệu quả
        
        Args:
            probs: Danh sách xác suất đúng của từng câu
            k: Số câu đúng cần tính
            n: Tổng số câu
        
        Returns:
            Xác suất đúng đúng k câu
        """
        if k > n or k < 0:
            return 0.0
        if k == 0:
            return math.prod(1.0 - p for p in probs)
        if k == n:
            return math.prod(probs)
        
        # Dynamic programming: dp[i][j] = xác suất đúng j câu trong i câu đầu
        dp_prev = [0.0] * (k + 1)
        dp_prev[0] = 1.0
        
        for i in range(n):
            dp_curr = [0.0] * (k + 1)
            p = probs[i]
            
            max_j = min(i + 1, k)
            for j in range(max_j + 1):
                if j == 0:
                    dp_curr[j] = dp_prev[j] * (1.0 - p)
                else:
                    dp_curr[j] = dp_prev[j] * (1.0 - p) + dp_prev[j - 1] * p
            
            dp_prev = dp_curr
        
        return dp_prev[k] if k < len(dp_prev) else 0.0



