"""
UserAbility Model
"""

from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class UserAbility:
    """Năng lực người học"""
    overall_ability: float = 0.0 
    topic_abilities: Optional[Dict[str, float]] = None  
    confidence: float = 0.0  
    
    def __post_init__(self):
        if self.topic_abilities is None:
            self.topic_abilities = {}

