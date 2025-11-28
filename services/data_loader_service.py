"""
Data Loader Service
"""

import json
import csv
import numpy as np
from typing import Dict, List
from collections import defaultdict
from models.question import Question
from models.user_response import UserResponse
from services.difficulty_estimator_service import DifficultyEstimatorService

class DataLoaderService:
    """
    Service để tải và xử lý dữ liệu
    """
    
    @staticmethod
    def load_questions_from_data(progress_data: List[Dict], 
                                topic_data: List[Dict]) -> List[Question]:
        """
        Tải câu hỏi từ dữ liệu có sẵn
        
        Args:
            progress_data: Dữ liệu từ user_question_progress
            topic_data: Dữ liệu từ topic_questions_asvab.csv
        
        Returns:
            Danh sách Question objects
        """
        question_topic_map = {}
        for topic_row in topic_data:
            question_id = topic_row.get('question_id', '')
            if question_id:
                question_topic_map[question_id] = {
                    'main_topic_id': topic_row.get('main_topic_id', ''),
                    'sub_topic_id': topic_row.get('sub_topic_id', ''),
                }
        
        questions = []
        question_ids_seen = set()
        
        for progress_row in progress_data:
            question_id = str(progress_row.get('questionId', ''))
            
            if not question_id or question_id in question_ids_seen:
                continue
            
            topic_info = question_topic_map.get(question_id, {})
            
            question = Question(
                question_id=question_id,
                main_topic_id=topic_info.get('main_topic_id', ''),
                sub_topic_id=topic_info.get('sub_topic_id', ''),
                difficulty=0.0  
            )
            
            questions.append(question)
            question_ids_seen.add(question_id)
        
        return questions
    
    @staticmethod
    def calculate_question_difficulties(progress_data: List[Dict]) -> Dict[str, float]:
        """
        Tính độ khó của các câu hỏi từ dữ liệu lịch sử
        
        Args:
            progress_data: Dữ liệu từ user_question_progress
        
        Returns:
            Dict mapping question_id -> difficulty (trong thang Standard Normal [-3, +3])
        """
        question_responses = defaultdict(list)
        
        for row in progress_data:
            question_id = str(row.get('questionId', ''))
            choices_selected = row.get('choicesSelected', [])
            
            played_times_str = row.get('playedTimes', '[]')
            try:
                played_times = json.loads(played_times_str) if played_times_str else []
                if played_times: 
                    start_time = played_times[-1].get('startTime', 0)
                    end_time = played_times[-1].get('endTime', 0)
                    response_time = (end_time - start_time) / 1000.0  
                else:
                    response_time = 30.0  
            except:
                response_time = 30.0
            
            histories = row.get('histories', [])
            if not isinstance(histories, list) or len(histories) == 0:
                is_correct = False
            else:
                is_correct = (histories[-1] == 1)
            
            if question_id:
                if not isinstance(choices_selected, list) or len(choices_selected) == 0:
                    choice_selected = -1
                else:
                    choice_selected = choices_selected[0]
                
                response = UserResponse(
                    question_id=question_id,
                    is_correct=is_correct,
                    response_time=response_time,
                    timestamp=row.get('lastUpdate', 0),
                    choice_selected=choice_selected
                )
                question_responses[question_id].append(response)
        
        difficulties = {}
        estimator = DifficultyEstimatorService()
        
        all_response_times = []
        for responses in question_responses.values():
            all_response_times.extend([r.response_time for r in responses])
        avg_time_all = np.mean(all_response_times) if all_response_times else 30.0
        
        for question_id, responses in question_responses.items():
            difficulty = estimator.estimate_difficulty(
                responses,
                avg_time_all_questions=avg_time_all,
                accuracy_weight=0.6,
                time_weight=0.4
            )
            difficulties[question_id] = difficulty
        
        return difficulties

