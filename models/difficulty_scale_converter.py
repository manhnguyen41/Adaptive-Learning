"""
Difficulty Scale Converter
"""

class DifficultyScaleConverter:
    """
    Chuyển đổi giữa các thang đo độ khó
    """
    
    @staticmethod
    def to_standard_normal(difficulty_0_1: float) -> float:
        """
        Chuyển đổi từ thang [0, 1] sang Standard Normal [-3, +3]
        
        Args:
            difficulty_0_1: Độ khó trong thang [0, 1] (0 = dễ, 1 = khó)
        
        Returns:
            Độ khó trong thang Standard Normal (trung bình = 0, SD = 1)
        """
        difficulty_std = (difficulty_0_1 - 0.5) * 6.0
        return max(-3.0, min(3.0, difficulty_std))
    
    @staticmethod
    def from_standard_normal(difficulty_std: float) -> float:
        """
        Chuyển đổi từ Standard Normal [-3, +3] sang thang [0, 1]
        
        Args:
            difficulty_std: Độ khó trong thang Standard Normal
        
        Returns:
            Độ khó trong thang [0, 1]
        """
        difficulty_0_1 = (difficulty_std / 6.0) + 0.5
        return max(0.0, min(1.0, difficulty_0_1))

