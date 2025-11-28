"""
Analysis Service - Phân tích và thống kê câu hỏi
"""

from typing import Dict, List
from collections import defaultdict
import numpy as np
from models.question import Question

class AnalysisService:
    """
    Service để phân tích và thống kê câu hỏi
    """
    
    @staticmethod
    def analyze_questions(questions: List[Question], 
                         question_difficulties: Dict[str, float]) -> Dict:
        """
        Phân tích và thống kê các câu hỏi
        
        Args:
            questions: Danh sách câu hỏi
            question_difficulties: Dict mapping question_id -> difficulty
        
        Returns:
            Dict chứa các thống kê và phân tích
        """
        if not questions:
            return {
                "total_questions": 0,
                "statistics": {
                    "difficulty": {
                        "min": 0.0,
                        "max": 0.0,
                        "mean": 0.0,
                        "median": 0.0,
                        "std": 0.0
                    },
                    "discrimination": {
                        "min": 1.0,
                        "max": 1.0,
                        "mean": 1.0,
                        "median": 1.0
                    }
                },
                "distributions": {
                    "difficulty": {
                        "easy": 0,
                        "medium": 0,
                        "hard": 0
                    },
                    "topics": {
                        "by_main_topic": {},
                        "by_sub_topic": {},
                        "total_main_topics": 0,
                        "total_sub_topics": 0,
                        "top_5_main_topics": []
                    }
                }
            }
        
        difficulties = []
        for q in questions:
            diff = question_difficulties.get(q.question_id, q.difficulty)
            difficulties.append(diff)
        
        difficulties = np.array(difficulties)
        
        difficulty_stats = {
            "min": float(np.min(difficulties)),
            "max": float(np.max(difficulties)),
            "mean": float(np.mean(difficulties)),
            "median": float(np.median(difficulties)),
            "std": float(np.std(difficulties))
        }
        
        easy_count = np.sum((difficulties >= -3) & (difficulties < -1))
        medium_count = np.sum((difficulties >= -1) & (difficulties <= 1))
        hard_count = np.sum((difficulties > 1) & (difficulties <= 3))
        
        difficulty_distribution = {
            "easy": int(easy_count),  
            "medium": int(medium_count), 
            "hard": int(hard_count) 
        }
        
        main_topic_count = defaultdict(int)
        for q in questions:
            main_topic_id = q.main_topic_id if q.main_topic_id else "unknown"
            main_topic_count[main_topic_id] += 1
        
        topic_distribution = {
            "by_main_topic": dict(main_topic_count),
            "total_main_topics": len(main_topic_count)
        }
        
        sub_topic_count = defaultdict(int)
        for q in questions:
            sub_topic_id = q.sub_topic_id if q.sub_topic_id else "unknown"
            sub_topic_count[sub_topic_id] += 1
        
        topic_distribution["by_sub_topic"] = dict(sub_topic_count)
        topic_distribution["total_sub_topics"] = len(sub_topic_count)
        
        discriminations = [q.discrimination for q in questions]
        discrimination_stats = {
            "min": float(min(discriminations)),
            "max": float(max(discriminations)),
            "mean": float(np.mean(discriminations)),
            "median": float(np.median(discriminations))
        }
        
        sorted_main_topics = sorted(
            main_topic_count.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        top_topics = [
            {"topic_id": topic_id, "question_count": count}
            for topic_id, count in sorted_main_topics
        ]
        
        topic_distribution["top_5_main_topics"] = top_topics
        
        return {
            "total_questions": len(questions),
            "statistics": {
                "difficulty": difficulty_stats,
                "discrimination": discrimination_stats
            },
            "distributions": {
                "difficulty": difficulty_distribution,
                "topics": topic_distribution
            }
        }

