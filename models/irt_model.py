"""
IRT Model - Item Response Theory 3-PL
"""

import math

class IRTModel:
    """
    Mô hình Item Response Theory (3-PL: 3 Parameters Logistic)
    
    P(θ) = c + (1-c) / (1 + exp(-a*(θ - b)))
    
    Trong đó:
    - θ (theta): Năng lực người học (Standard Normal)
    - a: Độ phân biệt của câu hỏi (discrimination)
    - b: Độ khó của câu hỏi (difficulty) - Standard Normal
    - c: Xác suất đoán đúng (guessing parameter)
    """
    
    def __init__(self, guessing_param: float = 0.25):
        """
        Args:
            guessing_param: Xác suất đoán đúng (thường là 1/số_phương_án)
        """
        self.guessing_param = guessing_param
    
    def probability_correct(self, ability: float, difficulty: float, 
                          discrimination: float = 1.0) -> float:
        """
        Tính xác suất trả lời đúng câu hỏi
        
        Args:
            ability: Năng lực người học (theta) - Standard Normal
            difficulty: Độ khó câu hỏi (b) - Standard Normal
            discrimination: Độ phân biệt (a)
        
        Returns:
            Xác suất trả lời đúng (0-1)
        """
        exponent = -discrimination * (ability - difficulty)
        prob = self.guessing_param + (1 - self.guessing_param) / (1 + math.exp(exponent))
        return max(0.0, min(1.0, prob))
    
    def information(self, ability: float, difficulty: float, 
                   discrimination: float = 1.0) -> float:
        """
        Tính thông tin (information) mà câu hỏi cung cấp về năng lực
        
        Câu hỏi cung cấp nhiều thông tin nhất khi độ khó ≈ năng lực
        
        Công thức Fisher Information đúng cho IRT 3-PL:
        I(θ) = a² * (P-c)² * (1-P) / [(1-c)² * P]
        
        Args:
            ability: Năng lực người học (Standard Normal)
            difficulty: Độ khó câu hỏi (Standard Normal)
            discrimination: Độ phân biệt
        
        Returns:
            Giá trị thông tin (càng cao càng tốt)
        """
        prob = self.probability_correct(ability, difficulty, discrimination)
        
        if prob <= self.guessing_param or prob >= 1.0:
            return 0.0
        
        numerator = (discrimination ** 2) * (prob - self.guessing_param) ** 2 * (1 - prob)
        denominator = ((1 - self.guessing_param) ** 2) * prob
        
        info = numerator / denominator if denominator > 0 else 0.0
        
        return max(0.0, info)

