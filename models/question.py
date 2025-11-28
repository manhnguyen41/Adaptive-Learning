"""
Question Model
"""

from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class Question:
    """Thông tin câu hỏi"""
    question_id: str
    main_topic_id: str
    sub_topic_id: str
    difficulty: float = 0.0  
    discrimination: float = 1.0
    topic_weights: Optional[Dict[str, float]] = None  
    
    def __post_init__(self):
        """
        Độ khó được đo bằng Standard Normal Distribution:
        - Trung bình = 0
        - Độ lệch chuẩn = 1
        - Phạm vi thực tế: [-3, +3] 
        - difficulty < 0: Câu hỏi dễ hơn trung bình
        - difficulty > 0: Câu hỏi khó hơn trung bình
        """
        if self.difficulty < -3:
            self.difficulty = -3.0
        elif self.difficulty > 3:
            self.difficulty = 3.0
        
        if self.topic_weights is None:
            self.topic_weights = {}

