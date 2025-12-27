"""
Difficulty Estimator Service
"""

import numpy as np
from typing import List
from models.user_response import UserResponse
from models.difficulty_scale_converter import DifficultyScaleConverter

class DifficultyEstimatorService:
    """
    Service để ước tính độ khó câu hỏi dựa trên lịch sử làm bài
    Kết hợp tỷ lệ trả lời đúng và thời gian trả lời trung bình
    
    Độ khó được trả về trong thang Standard Normal Distribution:
    - Trung bình = 0
    - Độ lệch chuẩn = 1
    - Phạm vi: [-3, +3] (99.7% dữ liệu nằm trong khoảng này)
    """
    
    @staticmethod
    def estimate_difficulty(responses: List[UserResponse], 
                           avg_time_all_questions: float = None,
                           accuracy_weight: float = 0.5,
                           time_weight: float = 0.5) -> float:
        """
        Tính độ khó câu hỏi dựa trên cả tỷ lệ trả lời đúng và thời gian trả lời trung bình
        
        Args:
            responses: Danh sách phản hồi của tất cả người dùng về câu hỏi này
            avg_time_all_questions: Thời gian trung bình của tất cả câu hỏi
            accuracy_weight: Trọng số cho tỷ lệ trả lời đúng (mặc định: 0.6)
            time_weight: Trọng số cho thời gian trả lời (mặc định: 0.4)
        
        Returns:
            Độ khó trong thang Standard Normal [-3, +3]
        """
        if not responses:
            return 0.0 
        
        correct_count = sum(1 for r in responses if r.is_correct)
        accuracy = correct_count / len(responses)
        difficulty_from_accuracy = 1.0 - accuracy
        
        response_times = [r.response_time for r in responses]
        avg_time = np.mean(response_times)
        
        if avg_time_all_questions is None:
            avg_time_all_questions = avg_time
        
        min_time = 5.0
        max_time = 70.0
        
        normalized_time = (avg_time - min_time) / (max_time - min_time)
        normalized_time = max(0.0, min(1.0, normalized_time))
        difficulty_from_time = normalized_time
        
        final_difficulty_0_1 = (accuracy_weight * difficulty_from_accuracy + 
                               time_weight * difficulty_from_time)
        final_difficulty_0_1 = max(0.0, min(1.0, final_difficulty_0_1))
        
        final_difficulty_std = DifficultyScaleConverter.to_standard_normal(final_difficulty_0_1) + 1.2
        
        return final_difficulty_std

