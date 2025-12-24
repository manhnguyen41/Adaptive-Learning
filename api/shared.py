"""
Shared utilities và data loaders cho tất cả API routes
"""

from typing import Dict, List
import json
import os
import csv
from services.data_loader_service import DataLoaderService
from services.question_selector_service import QuestionSelectorService
from services.ability_estimator_service import AbilityEstimatorService
from models.irt_model import IRTModel

# Cache variables
_questions_cache = None
_difficulties_cache = None
_progress_data_cache = None
_topic_meta_cache = None
_question_topic_map_cache = None
_all_responses_cache = None

# Config
PROGRESS_FILE = "user_question_progress_1000000.json"
TOPIC_FILE = "topic_questions_asvab.csv"


def load_questions_and_difficulties():
    """Load câu hỏi và độ khó (có cache)"""
    global _questions_cache, _difficulties_cache
    
    if _questions_cache is not None and _difficulties_cache is not None:
        return _questions_cache, _difficulties_cache
    
    if not os.path.exists(PROGRESS_FILE):
        raise FileNotFoundError(f"File không tồn tại: {PROGRESS_FILE}")
    
    with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
        progress_data = json.load(f)
    
    topic_data = _load_topic_data()
    
    valid_question_ids = {str(row.get('question_id', '')) for row in topic_data if row.get('question_id')}
    
    questions = DataLoaderService.load_questions_from_data(progress_data, topic_data)
    difficulties = DataLoaderService.calculate_question_difficulties(progress_data, valid_question_ids)
    
    _questions_cache = questions
    _difficulties_cache = difficulties
    
    return questions, difficulties


def load_progress_data():
    """Load progress data (có cache)"""
    global _progress_data_cache
    
    if _progress_data_cache is not None:
        return _progress_data_cache
    
    if not os.path.exists(PROGRESS_FILE):
        raise FileNotFoundError(f"File không tồn tại: {PROGRESS_FILE}")
    
    with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
        _progress_data_cache = json.load(f)
    
    return _progress_data_cache


def _load_topic_data() -> List[Dict]:
    """Load topic data từ CSV file"""
    topic_data = []
    if os.path.exists(TOPIC_FILE):
        with open(TOPIC_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            first_field = reader.fieldnames[0]
            
            if '|' in first_field:
                columns = first_field.split('|')
                for row in reader:
                    values = row[first_field].split('|')
                    if len(values) == len(columns):
                        topic_data.append(dict(zip(columns, values)))
            else:
                topic_data = list(reader)
    return topic_data


def get_topic_meta_map() -> Dict[str, Dict[str, str]]:
    """Tạo mapping topic_id -> {name, type} từ file topic"""
    global _topic_meta_cache
    if _topic_meta_cache is not None:
        return _topic_meta_cache

    meta_map: Dict[str, Dict[str, str]] = {}

    if os.path.exists(TOPIC_FILE):
        with open(TOPIC_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            first_field = reader.fieldnames[0]

            if '|' in first_field:
                columns = first_field.split('|')
                for row in reader:
                    values = row[first_field].split('|')
                    if len(values) != len(columns):
                        continue
                    row = dict(zip(columns, values))
                    main_id = row.get("main_topic_id", "")
                    main_name = row.get("main_topic_name", "")
                    sub_id = row.get("sub_topic_id", "")
                    sub_name = row.get("sub_topic_name", "")
                    if main_id:
                        meta_map[str(main_id)] = {"name": main_name, "type": "main"}
                    if sub_id:
                        meta_map[str(sub_id)] = {"name": sub_name, "type": "sub"}
            else:
                for row in reader:
                    main_id = row.get("main_topic_id", "")
                    main_name = row.get("main_topic_name", "")
                    sub_id = row.get("sub_topic_id", "")
                    sub_name = row.get("sub_topic_name", "")
                    if main_id:
                        meta_map[str(main_id)] = {"name": main_name, "type": "main"}
                    if sub_id:
                        meta_map[str(sub_id)] = {"name": sub_name, "type": "sub"}

    _topic_meta_cache = meta_map
    return meta_map


def get_question_topic_map() -> Dict[str, Dict[str, str]]:
    """Tạo mapping question_id -> topic info từ questions cache"""
    global _question_topic_map_cache
    
    if _question_topic_map_cache is not None:
        return _question_topic_map_cache
    
    all_questions, _ = load_questions_and_difficulties()
    
    question_topic_map = {}
    for q in all_questions:
        question_topic_map[q.question_id] = {
            "main_topic_id": q.main_topic_id,
            "sub_topic_id": q.sub_topic_id
        }
    
    _question_topic_map_cache = question_topic_map
    return question_topic_map


def get_question_selector() -> QuestionSelectorService:
    """Dependency để tạo QuestionSelectorService"""
    irt_model = IRTModel(guessing_param=0.25)
    return QuestionSelectorService(irt_model)


def get_ability_estimator() -> AbilityEstimatorService:
    """Dependency để tạo AbilityEstimatorService"""
    irt_model = IRTModel(guessing_param=0.25)
    return AbilityEstimatorService(irt_model)


def load_all_responses():
    """Load tất cả responses từ progress_data (có cache)"""
    global _all_responses_cache
    
    if _all_responses_cache is not None:
        return _all_responses_cache
    
    from services.user_response_loader_service import UserResponseLoaderService
    progress_data = load_progress_data()
    _all_responses_cache = UserResponseLoaderService.load_all_responses(progress_data)
    
    return _all_responses_cache


def clear_cache():
    """Clear tất cả cache - dùng cho testing hoặc reload data"""
    global _questions_cache, _difficulties_cache, _progress_data_cache
    global _topic_meta_cache, _question_topic_map_cache, _all_responses_cache
    
    _questions_cache = None
    _difficulties_cache = None
    _progress_data_cache = None
    _topic_meta_cache = None
    _question_topic_map_cache = None
    _all_responses_cache = None

