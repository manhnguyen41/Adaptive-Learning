"""
Question Selector Service
"""

import numpy as np
from typing import Dict, List, Optional
from models.question import Question
from models.user_response import UserResponse
from models.user_ability import UserAbility
from models.irt_model import IRTModel
from services.ability_estimator_service import AbilityEstimatorService

class QuestionSelectorService:
    """
    Service để chọn câu hỏi cho Diagnostic Test dựa trên mô hình xác suất
    """
    
    def __init__(self, irt_model: IRTModel = None):
        self.irt_model = irt_model or IRTModel()
        self.ability_estimator = AbilityEstimatorService(self.irt_model)
    
    def select_next_question(self,
                            candidate_questions: List[Question],
                            user_responses: List[UserResponse],
                            question_difficulties: Dict[str, float],
                            user_ability: Optional[UserAbility] = None) -> Question:
        """
        Chọn câu hỏi tiếp theo để đánh giá năng lực
        
        Chiến lược: Maximize Information (tối đa hóa thông tin)
        
        Args:
            candidate_questions: Danh sách câu hỏi có thể chọn
            user_responses: Lịch sử trả lời của người học
            question_difficulties: Độ khó của các câu hỏi (Standard Normal)
            user_ability: Năng lực hiện tại (nếu None sẽ ước tính)
        
        Returns:
            Câu hỏi được chọn
        """
        if user_ability is None:
            estimated_ability, confidence = self.ability_estimator.estimate_ability(
                user_responses, question_difficulties
            )
            user_ability = UserAbility(
                overall_ability=estimated_ability,
                confidence=confidence
            )
        
        answered_question_ids = {r.question_id for r in user_responses}
        available_questions = [
            q for q in candidate_questions 
            if q.question_id not in answered_question_ids
        ]
        
        if not available_questions:
            raise ValueError("Không còn câu hỏi nào để chọn")
        
        best_question = None
        best_score = -float('inf')
        
        for question in available_questions:
            difficulty = question_difficulties.get(
                question.question_id, 
                question.difficulty
            )
            
            information = self.irt_model.information(
                user_ability.overall_ability,
                difficulty,
                question.discrimination
            )
            
            score = information
            
            if score > best_score:
                best_score = score
                best_question = question
        
        return best_question
    
    def select_initial_question_set(self,
                                   all_questions: List[Question],
                                   question_difficulties: Dict[str, float],
                                   num_questions: int = 20,
                                   coverage_topics: List[str] = None) -> List[Question]:
        """
        Chọn bộ câu hỏi ban đầu cho Diagnostic Test
        
        Chiến lược:
        - Chọn câu hỏi có độ khó trung bình trước
        - Đảm bảo bao phủ các topic quan trọng
        - Đa dạng về độ khó
        
        Args:
            all_questions: Tất cả câu hỏi có sẵn
            question_difficulties: Độ khó của các câu hỏi (Standard Normal)
            num_questions: Số lượng câu hỏi cần chọn
            coverage_topics: Danh sách topic cần bao phủ
        
        Returns:
            Danh sách câu hỏi được chọn
        """
        candidate_questions = all_questions
        if coverage_topics:
            candidate_questions = [
                q for q in all_questions 
                if q.main_topic_id in coverage_topics or q.sub_topic_id in coverage_topics
            ]
        
        sorted_questions = sorted(
            candidate_questions,
            key=lambda q: question_difficulties.get(q.question_id, q.difficulty)
        )
        
        selected = []
        num_bins = min(num_questions, 5)  
        questions_per_bin = num_questions // num_bins
        
        for i in range(num_bins):
            start_idx = i * len(sorted_questions) // num_bins
            end_idx = (i + 1) * len(sorted_questions) // num_bins
            bin_questions = sorted_questions[start_idx:end_idx]
            
            if bin_questions:
                selected_in_bin = np.random.choice(
                    bin_questions,
                    size=min(questions_per_bin, len(bin_questions)),
                    replace=False
                ).tolist()
                selected.extend(selected_in_bin)
        
        remaining = num_questions - len(selected)
        if remaining > 0:
            available = [q for q in candidate_questions if q not in selected]
            selected.extend(available[:remaining])
        
        return selected[:num_questions]

