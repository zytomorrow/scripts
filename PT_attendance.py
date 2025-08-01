# -*- coding: utf-8 -*-

"""
PT站点签到脚本

## 20250730
    新增站点：
    1. btschool.club

## 20250528
    新增站点：
    1. ptskit.com

## 20250328
    新增站点:
    1. lemonhd.net

## 20250306
    优化内容：
    1. 增强正则匹配健壮性
    2. 优化JSON文件初始化逻辑
    3. 增加请求超时和异常处理
    4. 修复cookie获取逻辑
    5. 优化结果拼接效率
    6. 改进跨平台文件创建

new Env('PT签到');
0 */1 * * * PT_attendance.py
"""

import os
import re
import requests
import time
import json
from functools import wraps


PT = {
    'ICC2022': {
        'env': 'icc2022_cookie',
        'attendance_url': 'https://www.icc2022.com/attendance.php',
        'index_url': "https://www.icc2022.com/index.php"
    },
    'HDTIME': {
        'env': 'HDTIME_cookie',
        'attendance_url': 'https://hdtime.org/attendance.php',
        'index_url': "https://hdtime.org/index.php"
    },
    'HDVIDEO': {
        'env': 'HDVIDEO_cookie',
        'attendance_url': 'https://hdvideo.one/attendance.php',
        'index_url': "https://hdvideo.one/index.php"
    },
    'CARPTS': {
        'env': 'CARPTS_cookie',
        'attendance_url': 'https://carpt.net/attendance.php',
        'index_url': "https://carpt.net/index.php"
    },
    'ULTRAHD': {
        'env': 'ULTRAHD_cookie',
        'attendance_url': 'https://ultrahd.net/attendance.php',
        'index_url': "https://ultrahd.net/index.php"
    },
    'AFUN': {
        'env': 'AFUN_cookie',
        'attendance_url': 'https://www.ptlover.cc/attendance.php',
        'index_url': "https://www.ptlover.cc/index.php"
    },
    'LEMONHD': {
        'env': 'LEMONHD_cookie',
        'attendance_url': 'https://lemonhd.net/attendance.php',
        'index_url': "https://lemonhd.net/index.php"
    },
    'PTSKIT': {
        'env': 'PTSKIT_cookie',
        'attendance_url': 'https://www.ptskit.com/attendance.php',
        'index_url': "https://www.ptskit.com/index.php"
    },
    'BTSCHOOL': {
        'env': 'BTSCHOOL_cookie',
        'attendance_url': 'https://pt.btschool.club/index.php?action=addbonus',
        'index_url': 'https://pt.btschool.club/index.php',
    }
}


def retry(max_retries=3, delay=1, exceptions=(Exception,)):
    """装饰器：重试失败的函数调用"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    print(f"异常捕获: {e.__class__.__name__}: {e}. 重试中...")
                    retries += 1
                    time.sleep(delay)
            raise Exception(f"重试{max_retries}次后失败")
        return wrapper
    return decorator


class PTClient:
    """PT站点客户端"""
    
    def __init__(self, cookie, attendance_url, index_url):
        self.cookie = cookie
        self.attendance_url = attendance_url
        self.index_url = index_url
        self.headers = self._init_headers()
        self.timeout = 10  # 请求超时时间

    def _init_headers(self):
        """初始化请求头"""
        return {
            'accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/avif,image/webp,image/apng,*/*;q=0.8,'
                      'application/signed-exchange;v=b3;q=0.7'),
            'cookie': self.cookie,
            'referer': self.index_url,
            'user-agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/132.0.0.0 Safari/537.36')
        }

    @retry(max_retries=3, delay=1)
    def attendance(self):
        """获取签到信息"""
        try:
            response = requests.get(
                self.attendance_url, 
                headers=self.headers, 
                timeout=self.timeout
            )
            response.raise_for_status()
            
            attendance_detail = {'status': False}
            if '欢迎回来' in response.text:
                attendance_detail.update({
                    'status': True,
                    'times': self._safe_re_search(
                        r'这是您的第.*?(\d+)', response.text
                    ),
                    'continue': self._safe_re_search(
                        r'已连续签到.*?(\d+)', response.text
                    ),
                    'reward': self._safe_re_search(
                        r'本次签到获得.*?(\d+)', response.text
                    ),
                    'retroactive_cards': self._safe_re_search(
                        r'目前拥有补签卡.*?(\d+)', response.text
                    ),
                    'today_rank': self._safe_re_rank(response.text),
                })
            return attendance_detail
        except requests.RequestException as e:
            print(f"请求异常: {str(e)}")
            return {'status': False}

    @retry(max_retries=3, delay=1)
    def index_info(self):
        """获取首页信息"""
        try:
            response = requests.get(
                self.index_url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            basic_info = {'status': False}
            if '欢迎回来' in response.text:
                basic_info.update({
                    'status': True,
                    'share_ratio': self._safe_re_search(
                        r'分享率.*?(\d+\.\d+)', response.text
                    ),
                    'upload_count': self._safe_re_search(
                        r'上传量:</font>(.*?)<', response.text, cleanup=True
                    ),
                    'download_count': self._safe_re_search(
                        r'下载量:</font>(.*?)<', response.text, cleanup=True
                    ),
                    'ml_count': self._safe_re_search(
                        r'使用</a>]:(.*?)<', response.text, cleanup=True
                    ),
                    'mails': self._safe_re_search(
                        r'(\d+) 新', response.text
                    ),
                    'notices': re.findall(
                        r'(\d{4}\.\d{2}\.\d{2}) - <b>(.*?)</b>', response.text
                    )
                })
            return basic_info
        except requests.RequestException as e:
            print(f"请求异常: {str(e)}")
            return {'status': False}

    @staticmethod
    def _safe_re_search(pattern, text, group=0, cleanup=False):
        """安全的正则搜索，防止异常"""
        match = re.findall(pattern, text)
        if match:
            result = match[0] if isinstance(match, list) else match
            return result.replace(' ', '') if cleanup else result
        return 'N/A'

    @staticmethod
    def _safe_re_rank(text):
        """获取排名信息"""
        match = re.search(r'今日签到排名：<b>(\d+)</b> / <b>(\d+)</b>', text)
        return '/'.join(match.groups()) if match else 'N/A/N/A'


def init_json_file():
    """初始化JSON文件"""
    default_data = {
        'total': len(PT),
        'enables': [
            pt_name for pt_name, details in PT.items() 
            if os.getenv(details['env'])
        ],
    }
    
    for pt_name in PT:
        default_data.setdefault(pt_name, {
            'last_attendance': '0000-00-00',
            'info': {
                'times': 0,
                'continue': 0,
                'reward': 0,
                'retroactive_cards': 0,
                'today_rank': '0/0',
                'share_ratio': 0,
                'upload_count': 0,
                'download_count': 0,
                'ml_count': 0,
                'mails': 0,
                'notices': []
            }
        })
    
    if not os.path.exists('PT_attendance.json'):
        with open('PT_attendance.json', 'w') as f:
            json.dump(default_data, f, indent=4)
    
    return default_data


def generate_report(detail):
    """生成报告内容"""
    today = time.strftime('%Y-%m-%d')
    completed_sites = [pt for pt in detail['enables'] 
                      if detail[pt]['last_attendance'] == today]
    
    report = [
        "<h1>PT详情：</h1>",
        f"支持站点数量：{detail['total']}个<br>",
        f"启用站点数量：{len(detail['enables'])}个<br>",
        f"已完成签到站点：{len(completed_sites)}个<br><hr>"
    ]
    return ''.join(report)


def update_total_and_enables(detail, pt_name, cookie):
    """更新总数和启用站点列表"""
    # 更新启用站点列表
    if pt_name not in detail['enables'] and cookie:
        detail['enables'].append(pt_name)

    # 更新总数
    detail['total'] = len(PT)


def init_station_data(detail, pt_name):
    """初始化站点数据"""
    if pt_name not in detail:
        detail[pt_name] = {
            'last_attendance': '0000-00-00',
            'info': {
                'times': 0,
                'continue': 0,
                'reward': 0,
                'retroactive_cards': 0,
                'today_rank': '0/0',
                'share_ratio': 0,
                'upload_count': 0,
                'download_count': 0,
                'ml_count': 0,
                'mails': 0,
                'notices': []
            }
        }


def update_station_info(detail, pt_name, attendance_detail, basic_info):
    """更新站点信息"""
    detail[pt_name]['last_attendance'] = time.strftime('%Y-%m-%d')
    detail[pt_name]['info'].update({
        'times': attendance_detail.get('times', 0),
        'continue': attendance_detail.get('continue', 0),
        'reward': attendance_detail.get('reward', 0),
        'retroactive_cards': attendance_detail.get('retroactive_cards', 0),
        'today_rank': attendance_detail.get('today_rank', '0/0'),
        'share_ratio': basic_info.get('share_ratio', 0),
        'upload_count': basic_info.get('upload_count', 0),
        'download_count': basic_info.get('download_count', 0),
        'ml_count': basic_info.get('ml_count', 0),
        'mails': basic_info.get('mails', 0),
        'notices': basic_info.get('notices', [])
    })


def generate_station_report(pt_name, attendance_detail, basic_info):
    """生成站点报告"""
    report = []
    report.append(
        f'<h2>{pt_name} 这是第{attendance_detail["times"]}次签到'
        f'（已连续签到{attendance_detail["continue"]}天）</h2>'
    )
    report.extend([
        f'• 今日获得魔力：{attendance_detail["reward"]}<br>',
        f'• 补签卡：{attendance_detail["retroactive_cards"]}张<br>',
        f'• 今日排名：{attendance_detail["today_rank"]}<br>',
        f'• 分享率：{basic_info["share_ratio"]}<br>',
        f'• 上传量：{basic_info["upload_count"]}<br>',
        f'• 下载量：{basic_info["download_count"]}<br>',
        f'• 魔力值：{basic_info["ml_count"]}<br>',
        f'• 新消息：{basic_info["mails"]}条<br>',
    ])
    
    # 添加公告
    notices_html = ''.join([
        f'<li>{date} - {content}</li>' 
        for date, content in basic_info["notices"]
    ])
    report.append(f'• 公告：<ul>{notices_html}</ul><hr>')
    
    return report


def run():
    """主函数"""
    # 初始化JSON文件
    if not os.path.exists('PT_attendance.json'):
        init_json_file()
    
    with open('PT_attendance.json', 'r+') as f:
        detail = json.load(f)
        detail.setdefault('enables', [])
        f.seek(0)
        json.dump(detail, f, indent=4)
        f.truncate()

    result = []
    need_push = False
    today = time.strftime('%Y-%m-%d')

    # 处理每个站点
    for pt_name in PT.keys():
        pt_config = PT.get(pt_name, {})
        if not pt_config:
            continue

        cookie = os.getenv(pt_config['env'])
        if not cookie:
            print(f'{pt_name}: 未找到环境变量 {pt_config["env"]}')
            continue
            
        try:
            if detail[pt_name]['last_attendance'] == today:
                print(f'{pt_name}: 今日已签到，跳过...')
                continue
        except KeyError:
            print(f'站点{pt_name}为新增站点，执行...')

        need_push = True
        print(f'{pt_name}: 开始签到...')
        
        client = PTClient(
            cookie=cookie,
            attendance_url=pt_config['attendance_url'],
            index_url=pt_config['index_url']
        )

        # 获取签到信息和站点基本信息
        attendance_detail = client.attendance()
        basic_info = client.index_info()

        if attendance_detail['status'] and basic_info['status']:
            # 更新总数和启用站点列表
            update_total_and_enables(detail, pt_name, cookie)
            
            # 初始化站点数据
            init_station_data(detail, pt_name)
            
            # 更新站点信息
            update_station_info(detail, pt_name, attendance_detail, basic_info)
            
            # 生成站点报告
            result.extend(generate_station_report(
                pt_name, attendance_detail, basic_info
            ))
        else:
            result.append(f'<h2 style="color:red">{pt_name} 签到异常</h2><hr>')
    
    # 添加总体报告
    result.insert(0, generate_report(detail))
    
    # 更新JSON文件
    with open('PT_attendance.json', 'w', encoding='utf8') as f:
        json.dump(detail, f, indent=4)

    # 推送通知
    if need_push:
        final_report = ''.join(result)
        try:
            QLAPI.notify("PT签到报告", final_report)
        except ImportError:
            print("未找到青龙通知模块，跳过通知推送")


if __name__ == "__main__":
    run()
