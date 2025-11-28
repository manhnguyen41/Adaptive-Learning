# Adaptive Learning Diagnostic Test API

API hệ thống Adaptive Learning sử dụng Item Response Theory (IRT) để đánh giá năng lực người học và dự đoán xác suất đậu bài thi thật.

## 📋 Mục lục

1. [Giới thiệu](#giới-thiệu)
2. [Cài đặt và Chạy Server](#cài-đặt-và-chạy-server)
3. [Giải thích Thuật toán](#giải-thích-thuật-toán)
   - [Cách tính Độ khó (Difficulty)](#cách-tính-độ-khó-difficulty)
   - [Cách tính Ability (Năng lực)](#cách-tính-ability-năng-lực)
   - [Cách tính Passing Probability](#cách-tính-passing-probability)
4. [API Endpoints](#api-endpoints)
5. [Ví dụ sử dụng](#ví-dụ-sử-dụng)

---

## Giới thiệu

Hệ thống sử dụng **Item Response Theory (IRT)** - một mô hình đánh giá năng lực người học dựa trên:

- **Độ khó câu hỏi** (Difficulty): Được tính từ tỷ lệ trả lời đúng và thời gian trả lời
- **Năng lực người học** (Ability): Được ước tính từ lịch sử trả lời câu hỏi
- **Xác suất đậu** (Passing Probability): Dự đoán khả năng vượt qua bài thi thật

---

## Cài đặt và Chạy Server

### Yêu cầu

- Python 3.8+
- pip

### Các bước cài đặt

1. **Tạo virtual environment (nếu chưa có):**

```bash
python -m venv venv
```

2. **Kích hoạt virtual environment:**

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

3. **Cài đặt dependencies:**

```bash
pip install -r requirements.txt
```

4. **Kiểm tra file dữ liệu:**

Đảm bảo có các file sau trong thư mục gốc:
- `user_question_progress_100000.json`: Dữ liệu lịch sử làm bài của người học
- `topic_questions_asvab.csv`: Dữ liệu mapping câu hỏi với topic

### Chạy Server

**Cách 1: Sử dụng script `run_api.py`**

```bash
python run_api.py
```

**Cách 2: Sử dụng uvicorn trực tiếp**

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Cách 3: Sử dụng FastAPI CLI**

```bash
fastapi dev api/main.py
```

Server sẽ chạy tại: **http://localhost:8000**

### Truy cập API Documentation

Sau khi server chạy, truy cập:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Giải thích Thuật toán

### Cách tính Độ khó (Difficulty)

Độ khó của một câu hỏi được tính dựa trên **2 yếu tố chính**:

#### 1. Tỷ lệ trả lời đúng (Accuracy)

```
accuracy = số_câu_trả_lời_đúng / tổng_số_lần_làm
difficulty_from_accuracy = 1.0 - accuracy
```

- Accuracy cao → Câu hỏi dễ
- Accuracy thấp → Câu hỏi khó

#### 2. Thời gian trả lời trung bình (Response Time)

```
time_ratio = thời_gian_trung_bình_câu_hỏi / thời_gian_trung_bình_tất_cả_câu
difficulty_from_time = 0.5 * (1 + (time_ratio - 1) * 0.5)
```

- Thời gian trả lời dài → Câu hỏi khó hơn
- Thời gian trả lời ngắn → Câu hỏi dễ hơn

#### 3. Kết hợp hai yếu tố

```
final_difficulty_0_1 = (accuracy_weight * difficulty_from_accuracy + 
                        time_weight * difficulty_from_time)

Trong đó:
- accuracy_weight = 0.6 (trọng số 60%)
- time_weight = 0.4 (trọng số 40%)
```

#### 4. Chuyển đổi sang Standard Normal Distribution

Độ khó cuối cùng được chuyển đổi từ thang [0, 1] sang **Standard Normal Distribution** [-3, +3]:

```
difficulty_std = (difficulty_0_1 - 0.5) * 6.0
```

**Ý nghĩa:**
- **difficulty < 0**: Câu hỏi dễ hơn trung bình
- **difficulty = 0**: Câu hỏi ở mức trung bình
- **difficulty > 0**: Câu hỏi khó hơn trung bình
- **Phạm vi**: [-3, +3]

---

### Cách tính Ability (Năng lực)

Ability (năng lực) của người học được ước tính bằng **Maximum Likelihood Estimation (MLE)** sử dụng phương pháp **Newton-Raphson**.

#### 1. Mô hình IRT 3-PL

Xác suất trả lời đúng một câu hỏi được tính theo công thức:

```
P(θ) = c + (1-c) / (1 + exp(-a*(θ - b)))
```

Trong đó:
- **θ (theta)**: Năng lực người học (Standard Normal, cần tìm)
- **a**: Độ phân biệt câu hỏi (discrimination), mặc định = 1.0
- **b**: Độ khó câu hỏi (difficulty, Standard Normal)
- **c**: Xác suất đoán đúng (guessing parameter), mặc định = 0.25

#### 2. Likelihood Function

Xác suất người học trả lời đúng/sai các câu hỏi:

```
L(θ) = ∏ [P(θ)]^u * [1 - P(θ)]^(1-u)

Trong đó:
- u = 1 nếu trả lời đúng, u = 0 nếu trả lời sai
```

#### 3. Maximum Likelihood Estimation

Tìm θ để **L(θ) đạt cực đại** bằng cách giải:

```
d(log L(θ)) / dθ = 0
```

Đạo hàm bậc nhất (likelihood derivative):

```
d(log L(θ)) / dθ = Σ [a * (u - P(θ)) * (P(θ) - c) / (P(θ) * (1 - c))]
```

Đạo hàm bậc hai (Fisher Information):

```
I(θ) = Σ [a² * (P(θ) - c)² * (1 - P(θ)) / ((1 - c)² * P(θ))]
```

#### 4. Phương pháp Newton-Raphson

Lặp lại để tìm θ:

```
θ_new = θ_old + (likelihood_derivative / I(θ_old))
```

Dừng khi:
- Số lần lặp đạt max (mặc định: 10)
- Thay đổi < tolerance (mặc định: 0.001)

#### 5. Confidence (Độ tin cậy)

```
SE(θ) = 1 / √I(θ)  (Standard Error)
confidence = 1 / (1 + SE(θ))
```

- Confidence cao → Ước tính ability đáng tin cậy
- Confidence thấp → Cần thêm dữ liệu

#### 6. Phạm vi Ability

Ability được giới hạn trong khoảng **[-3, +3]** (Standard Normal Distribution).

---

### Cách tính Passing Probability

Xác suất đậu bài thi thật được tính dựa trên:

#### 1. Ước tính Ability

Tính ability của người học từ lịch sử trả lời (như mục trên).

#### 2. Tính xác suất đúng cho từng câu hỏi

Với mỗi câu hỏi trong đề thi, tính xác suất đúng bằng IRT:

```
P_i = c + (1-c) / (1 + exp(-a*(θ - b_i)))

Trong đó:
- P_i: Xác suất đúng câu hỏi thứ i
- θ: Ability của người học
- b_i: Độ khó câu hỏi thứ i
```

#### 3. Expected Score (Điểm dự kiến)

```
expected_correct = Σ P_i  (tổng xác suất đúng tất cả câu hỏi)
expected_score = (expected_correct / số_câu_hỏi) * 100%
```

#### 4. Tính xác suất đậu

**Bước 1:** Tính số câu đúng tối thiểu để đậu:

```
min_correct = ceil(passing_threshold * số_câu_hỏi)

Ví dụ: passing_threshold = 0.7, số_câu_hỏi = 50
→ min_correct = ceil(0.7 * 50) = 35 câu
```

**Bước 2:** Tính xác suất đậu bằng phân phối nhị thức:

**Trường hợp 1: Số câu hỏi ≤ 30** → Tính chính xác bằng Dynamic Programming

```
P(đậu) = P(X ≥ min_correct)

Trong đó X là biến ngẫu nhiên số câu đúng, phân phối nhị thức:
- P(X = k) được tính bằng DP từ danh sách P_i
```

**Trường hợp 2: Số câu hỏi > 30** → Xấp xỉ chuẩn

```
mean = Σ P_i
variance = Σ [P_i * (1 - P_i)]
std = √variance

z_score = (min_correct - 0.5 - mean) / std
P(đậu) = 1 - Φ(z_score)  (với Φ là CDF của phân phối chuẩn)
```

#### 5. Confidence Score

Confidence được tính dựa trên:

```
confidence = (ability_confidence * 0.5) + 
             (num_questions_confidence * 0.3) + 
             (variance_confidence * 0.2)

Trong đó:
- ability_confidence: Độ tin cậy của ước tính ability
- num_questions_confidence: min(1.0, số_câu_hỏi / 50.0)
- variance_confidence: Độ phân tán của xác suất (variance)
```

---

## API Endpoints

### 1. Tạo bộ câu hỏi Diagnostic Test

**POST** `/api/diagnostic/generate-question-set`

Tạo bộ câu hỏi ban đầu để đánh giá năng lực người học.

**Request:**
```json
{
  "num_questions": 20,
  "coverage_topics": ["5878262490202112"],
  "app_id": "5074526257807360"
}
```

**Response:**
```json
{
  "questions": [
    {
      "question_id": "4515379877511168",
      "main_topic_id": "5878262490202112",
      "sub_topic_id": "6140467079020544",
      "difficulty": 0.5,
      "discrimination": 1.0
    }
  ],
  "total_questions": 20,
  "message": "Successfully generated diagnostic question set"
}
```

---

### 2. Lấy tất cả câu hỏi kèm phân tích

**GET** `/api/diagnostic/questions?limit=100`

Lấy danh sách tất cả câu hỏi kèm thống kê và phân tích.

**Query Parameters:**
- `limit` (optional): Giới hạn số câu hỏi trả về

**Response:**
```json
{
  "questions": [...],
  "total_questions": 1500,
  "statistics": {
    "difficulty": {
      "min": -2.5,
      "max": 2.8,
      "mean": 0.1,
      "median": 0.0,
      "std": 1.2
    },
    "discrimination": {...}
  },
  "distributions": {...}
}
```

---

### 3. Tính Ability của một user

**POST** `/api/diagnostic/estimate-ability`

Tính năng lực tổng thể và theo từng topic của một user.

**Request:**
```json
{
  "user_id": "2004alexiamacias@gmail.com"
}
```

**Response:**
```json
{
  "user_id": "2004alexiamacias@gmail.com",
  "overall_ability": 0.5,
  "confidence": 0.85,
  "num_responses": 20,
  "main_topic_abilities": [
    {
      "topic_id": "5878262490202112",
      "ability": 0.6,
      "confidence": 0.8,
      "num_responses": 5
    }
  ],
  "sub_topic_abilities": [...],
  "message": "Ability estimated successfully"
}
```

---

### 4. Tính Ability của nhiều user (Batch)

**POST** `/api/diagnostic/estimate-abilities-batch`

Tính ability cho nhiều user cùng lúc.

**Request:**
```json
{
  "user_ids": [
    "2004alexiamacias@gmail.com"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "user_id": "2004alexiamacias@gmail.com",
      "overall_ability": 0.5,
      "confidence": 0.85,
      "num_responses": 20,
      "main_topic_abilities": [...],
      "sub_topic_abilities": [...],
      "error": null
    }
  ],
  "total_users": 3,
  "successful_count": 3,
  "failed_count": 0
}
```

---

### 5. Tính Passing Probability

**POST** `/api/diagnostic/passing-probability`

Dự đoán xác suất đậu bài thi thật của người học.

**Request:**
```json
{
  "user_id": "2004alexiamacias@gmail.com",
  "exam_structure": {
    "questions": [
      {
        "question_id": "4515379877511168",
        "difficulty": 0.5,
        "discrimination": 1.0
      }
    ],
    "passing_threshold": 0.7,
    "total_score": 100
  }
}
```

**Response:**
```json
{
  "user_id": "2004alexiamacias@gmail.com",
  "passing_probability": 75.5,
  "confidence_score": 0.85,
  "expected_score": 78.2,
  "passing_threshold": 70.0,
  "exam_info": {
    "total_questions": 50,
    "average_difficulty": 0.3,
    "min_correct_needed": 35,
    "user_ability": 0.5,
    "ability_confidence": 0.85
  },
  "message": "Passing probability calculated successfully"
}
```

---

## Ví dụ sử dụng

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Tính ability của một user
response = requests.post(
    f"{BASE_URL}/api/diagnostic/estimate-ability",
    json={"user_id": "2004alexiamacias@gmail.com"}
)
print(response.json())

# 2. Tính passing probability
response = requests.post(
    f"{BASE_URL}/api/diagnostic/passing-probability",
    json={
        "user_id": "2004alexiamacias@gmail.com",
        "exam_structure": {
            "questions": [
                {"question_id": "4515379877511168", "difficulty": 0.5, "discrimination": 1.0},
                {"question_id": "5515379877511169", "difficulty": 0.8, "discrimination": 1.0}
            ],
            "passing_threshold": 0.7
        }
    }
)
print(response.json())
```

### cURL

```bash
# Tính ability
curl -X POST "http://localhost:8000/api/diagnostic/estimate-ability" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "2004alexiamacias@gmail.com"}'

# Tính passing probability
curl -X POST "http://localhost:8000/api/diagnostic/passing-probability" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "2004alexiamacias@gmail.com",
    "exam_structure": {
      "questions": [
        {"question_id": "4515379877511168", "difficulty": 0.5}
      ],
      "passing_threshold": 0.7
    }
  }'
```