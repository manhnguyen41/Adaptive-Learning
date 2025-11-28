import requests
import json
import sys
import os
import argparse
from typing import List, Dict

def fetch_user_question_progress(app_id: str, limit: int = 1000, offset: int = 0) -> List[Dict]:
    """
    Lấy dữ liệu user question progress từ API
    
    Args:
        app_id: ID của app
        limit: Số lượng bản ghi mỗi lần (tối đa có thể là 1000)
        offset: Vị trí bắt đầu
        
    Returns:
        Danh sách các bản ghi
    """
    url = "https://test-api-cms-v2-dot-micro-enigma-235001.uc.r.appspot.com/api/tools/get-user-question-progress-by-app-id"
    params = {
        "appId": app_id,
        "limit": limit,
        "offset": offset
    }
    
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gọi API: {e}")
        return []

def fetch_all_data(app_id: str, total_limit: int = 100000) -> List[Dict]:
    """
    Lấy tất cả dữ liệu với pagination
    
    Args:
        app_id: ID của app
        total_limit: Tổng số bản ghi muốn lấy
        
    Returns:
        Danh sách tất cả các bản ghi
    """
    all_data = []
    offset = 0
    batch_size = 1000  # Lấy 1000 bản ghi mỗi lần
    
    print(f"Bắt đầu lấy dữ liệu (tối đa {total_limit} bản ghi)...")
    
    while len(all_data) < total_limit:
        remaining = total_limit - len(all_data)
        current_limit = min(batch_size, remaining)
        
        print(f"Đang lấy bản ghi {offset + 1} đến {offset + current_limit}...")
        
        batch_data = fetch_user_question_progress(app_id, limit=current_limit, offset=offset)
        
        if not batch_data:
            print("Không còn dữ liệu hoặc có lỗi xảy ra.")
            break
            
        all_data.extend(batch_data)
        print(f"Đã lấy được {len(all_data)} bản ghi")
        
        # Nếu số bản ghi trả về ít hơn limit, có thể đã hết dữ liệu
        if len(batch_data) < current_limit:
            print("Đã lấy hết dữ liệu có sẵn.")
            break
            
        offset += len(batch_data)
        
        # Nếu đã đủ số lượng yêu cầu, dừng lại
        if len(all_data) >= total_limit:
            break
    
    return all_data[:total_limit]  # Đảm bảo không vượt quá total_limit

def main():
    parser = argparse.ArgumentParser(description='Lấy dữ liệu user question progress từ API')
    parser.add_argument('--app-id', type=str, default='5074526257807360', 
                        help='ID của app (mặc định: 5074526257807360)')
    parser.add_argument('--limit', type=int, default=100000, 
                        help='Tổng số bản ghi muốn lấy (mặc định: 100000)')
    parser.add_argument('--output', type=str, default=None,
                        help='Tên file output (mặc định: user_question_progress_{limit}.json)')
    
    args = parser.parse_args()
    
    app_id = args.app_id
    total_records = args.limit
    
    # Lấy tất cả dữ liệu
    all_data = fetch_all_data(app_id, total_limit=total_records)
    
    # Tạo tên file output
    if args.output:
        output_file = args.output
    else:
        output_file = f"user_question_progress_{total_records}.json"
    
    print(f"\nĐang lưu {len(all_data)} bản ghi vào file {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Đã lưu thành công {len(all_data)} bản ghi vào file {output_file}")
    
    # Tính kích thước file
    file_size = os.path.getsize(output_file) / (1024*1024)
    print(f"📊 Kích thước file: {file_size:.2f} MB")

if __name__ == "__main__":
    main()

