"""
User Response Loader Service - Load user responses từ dữ liệu
"""

import json
from typing import Dict, List, Optional
from collections import defaultdict
from models.user_response import UserResponse

class UserResponseLoaderService:
    """
    Service để load user responses từ dữ liệu progress
    """
    
    @staticmethod
    def load_user_responses(progress_data: List[Dict], 
                           user_id: str) -> List[UserResponse]:
        """
        Load tất cả responses của một user cụ thể
        
        Args:
            progress_data: Dữ liệu từ user_question_progress
            user_id: ID của user cần load
        
        Returns:
            Danh sách UserResponse của user đó
        """
        responses = []
        
        for row in progress_data:
            row_user_id = str(row.get('userId', ''))
            if row_user_id != str(user_id):
                continue
            
            question_id = str(row.get('questionId', ''))
            if not question_id:
                continue
            
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
            responses.append(response)
        
        return responses
    
    @staticmethod
    def load_multiple_users_responses(progress_data: List[Dict], 
                                     user_ids: List[str]) -> Dict[str, List[UserResponse]]:
        """
        Load responses của nhiều user cùng lúc
        
        Args:
            progress_data: Dữ liệu từ user_question_progress
            user_ids: Danh sách ID của các user cần load
        
        Returns:
            Dict mapping user_id -> List[UserResponse]
        """
        user_ids_set = {str(uid) for uid in user_ids}
        user_responses_map = defaultdict(list)
        
        for row in progress_data:
            row_user_id = str(row.get('userId', ''))
            if row_user_id not in user_ids_set:
                continue
            
            question_id = str(row.get('questionId', ''))
            if not question_id:
                continue
            
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
            user_responses_map[row_user_id].append(response)
        
        return dict(user_responses_map)

