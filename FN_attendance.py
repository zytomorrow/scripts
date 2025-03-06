# -*- coding: utf-8 -*-

"""
飞牛站点签到脚本

new Env('飞牛签到');
0 */1 * * * FN_attendance.py
"""


import os
import re
import json
import time
import logging
from typing import Dict, Optional
import requests
from requests.exceptions import RequestException

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

JSON_FILE_NAME = 'FN_attendance.json'
BASIC_URL = 'https://club.fnnas.com/plugin.php?id=zqlj_sign'
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

class RetryDecorator:
    """重试装饰器类"""
    def __init__(self, max_retries=3, delay=1):
        self.max_retries = max_retries
        self.delay = delay

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < self.max_retries:
                try:
                    logger.info(f'Attempt {retries+1}/{self.max_retries}')
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f'Operation failed: {str(e)}')
                    retries += 1
                    time.sleep(self.delay)
            raise Exception(f"Operation failed after {self.max_retries} attempts")
        return wrapper

class FNClient:
    """飞牛论坛签到客户端"""
    def __init__(self, cookie: str):
        if not cookie:
            raise ValueError("Cookie cannot be empty")
        
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.headers.update({'Cookie': cookie})
        self.sign: Optional[str] = None

    @RetryDecorator(max_retries=3)
    def fetch_sign(self) -> None:
        """获取签到签名"""
        response = self.session.get(BASIC_URL)
        response.raise_for_status()
        
        if match := re.search(r'sign=([A-Za-z0-9]+)', response.text):
            self.sign = match.group(1)
            logger.info(f'Sign acquired: {self.sign}')
        else:
            raise ValueError("Sign parameter not found in response")

    @RetryDecorator(max_retries=3)
    def perform_attendance(self) -> Dict:
        """执行签到操作"""
        if not self.sign:
            raise ValueError("Sign not initialized")

        sign_url = f'{BASIC_URL}&sign={self.sign}'
        logger.debug(f'Sign URL: {sign_url}')
        
        # 执行签到请求
        response = self.session.get(sign_url)
        response.raise_for_status()

        # 验证签到结果
        verify_response = self.session.get(BASIC_URL)
        verify_response.raise_for_status()

        if '今日已打卡' not in verify_response.text:
            raise ValueError("Attendance verification failed")

        return self._parse_attendance_details(verify_response.text)

    @staticmethod
    def _parse_attendance_details(html: str) -> Dict:
        """解析签到详情"""
        patterns = {
            'recently_attendance': r'最近打卡：(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            'month_attendance_times': r'本月打卡：(\d+)',
            'continue_attendance_times': r'连续打卡：(\d+)',
            'total_attendance_times': r'累计打卡：(\d+)',
            'total_reward': r'累计奖励：(\d+)',
            'recently_reward': r'最近奖励：(\d+)',
            'level': r'当前打卡等级：(.+?)</li>'
        }

        details = {}
        for key, pattern in patterns.items():
            if match := re.search(pattern, html):
                details[key] = match.group(1)
        return details

class AttendanceManager:
    """签到状态管理器"""
    @staticmethod
    def init_data_file() -> Dict:
        """初始化数据文件"""
        default_data = {
            'last_attendance': '0000-00-00',
            'info': {
                'recently_attendance': None,
                'month_attention_times': 0,
                'continue_attention_times': 0,
                'total_attention_times': 0,
                'total_reward': 0,
                'recently_reward': 0,
                'level': 'L0'
            }
        }

        try:
            if not os.path.exists(JSON_FILE_NAME):
                with open(JSON_FILE_NAME, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, indent=2)
            return default_data
        except IOError as e:
            logger.error(f"File operation failed: {str(e)}")
            return default_data

    @staticmethod
    def update_record(details: Dict) -> None:
        """更新签到记录"""
        try:
            with open(JSON_FILE_NAME, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data['last_attendance'] = time.strftime('%Y-%m-%d')
                data['info'].update(details)
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to update record: {str(e)}")

def main():
    """主执行流程"""
    AttendanceManager.init_data_file()
    
    try:
        with open(JSON_FILE_NAME, 'r', encoding='utf-8') as f:
            record = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load records: {str(e)}")
        return

    if record['last_attendance'] == time.strftime('%Y-%m-%d'):
        logger.info("今日已签到，无需重复操作")
        return

    cookie = os.getenv('PV_COOKIE')
    if not cookie:
        logger.error("未找到环境变量 PV_COOKIE")
        return

    try:
        client = FNClient(cookie)
        client.fetch_sign()
        details = client.perform_attendance()
        AttendanceManager.update_record(details)
        
        report = (
            "<h1>签到成功</h1><hr>"
            f"打卡时间：{details['recently_attendance']}<br>"
            f"本月打卡：{details['month_attendance_times']}天<br>"
            f"连续打卡：{details['continue_attendance_times']}天<br>"
            f"累计打卡：{details['total_attendance_times']}天<br>"
            f"累计奖励：{details['total_reward']}飞牛币<br>"
            f"最近奖励：{details['recently_reward']}飞牛币<br>"
            f"当前等级：{details['level']}"
        )
        
        QLAPI.notify("飞牛论坛签到报告", report)
        logger.info(report.replace('<br>', '\n'))

    except Exception as e:
        logger.error(f"签到流程失败: {str(e)}")

if __name__ == "__main__":
    main()