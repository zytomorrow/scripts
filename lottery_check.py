# -*- coding: utf-8 -*-

"""
检查彩票中奖情况

new Env('彩票检查');
0 9,12,18 * * * lottery_check.py
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Union
import requests
from datetime import datetime
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 常量定义
JSON_FILE_NAME = 'lottery_data.json'
LOTTERY_APIS = {
    'ssq': {
        'url': ('http://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/'
                'findDrawNotice'),
        'params': {'name': 'ssq', 'pageNo': '1', 'pageSize': '1'},
        'env_key': 'LOTTERY_SSQ',
        'draw_days': [2, 4, 7]  # 周二、四、日开奖
    },
    '3d': {
        'url': ('http://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/'
                'findDrawNotice'),
        'params': {'name': '3d', 'pageNo': '1', 'pageSize': '1'},
        'env_key': 'LOTTERY_3D',
        'draw_days': list(range(1, 8))  # 每天开奖
    },
    'kl8': {
        'url': ('http://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/'
                'findDrawNotice'),
        'params': {'name': 'kl8', 'pageNo': '1', 'pageSize': '1'},
        'env_key': 'LOTTERY_KL8',
        'draw_days': list(range(1, 8))  # 每天开奖
    }
}


class LotteryChecker:
    def __init__(self):
        self.data = self.init_data_file()
    
    @staticmethod
    def init_data_file() -> Dict:
        """初始化数据文件"""
        default_data = {
            'types': {
                'ssq': {
                    'history': {'lottery_numbers': [], 'rewards': {}},
                    'total_rewards': 0,
                    'max_reward': {'date': '', 'level': '', 'money': 0},
                    'last_draw_date': '0000-00-00',
                    'last_check_date': '0000-00-00',
                    'date_info': {'last_push_date': '0000-00-00'}
                },
                '3d': {
                    'history': {'lottery_numbers': [], 'rewards': {}},
                    'total_rewards': 0,
                    'max_reward': {'date': '', 'level': '', 'money': 0},
                    'last_draw_date': '0000-00-00',
                    'last_check_date': '0000-00-00',
                    'date_info': {'last_push_date': '0000-00-00'}
                },
                'kl8': {
                    'history': {'lottery_numbers': [], 'rewards': {}},
                    'total_rewards': 0,
                    'max_reward': {'date': '', 'level': '', 'money': 0},
                    'last_draw_date': '0000-00-00',
                    'last_check_date': '0000-00-00',
                    'date_info': {'last_push_date': '0000-00-00'}
                }
            }
        }

        try:
            if not os.path.exists(JSON_FILE_NAME):
                with open(JSON_FILE_NAME, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, indent=2)
            with open(JSON_FILE_NAME, 'r', encoding='utf-8') as f:
                return json.load(f)
        except IOError as e:
            logger.error(f"文件操作失败: {str(e)}")
            return default_data

    def should_check_lottery(self, lottery_type: str, draw_date: str) -> bool:
        """检查是否需要检查彩票"""
        # 如果没有开奖日期，不检查
        if not draw_date:
            return False

        logger.info(f"检查彩票类型: {lottery_type}, 开奖日期: {draw_date}")

        logger.info(f"原始开奖日期: {draw_date}")
        
        # 使用正则表达式去除非日期字符
        draw_date = re.sub(r'[^\d-]', '', draw_date)
        logger.info(f"解析后的开奖日期: {draw_date}")
        
        # 获取上次检查的开奖日期
        last_check_date = self.data['types'][lottery_type]['last_check_date']
        last_check_date = last_check_date.split(' ')[0]  # 只保留日期部分
        logger.info(f"上次检查的开奖日期: {last_check_date}")
        
        # 如果开奖日期比上次检查的开奖日期新，需要检查
        if draw_date > last_check_date:
            logger.info("开奖日期比上次检查的日期新，继续检查...")
            # 检查是否是开奖日
            draw_date_obj = datetime.strptime(draw_date, '%Y-%m-%d')
            weekday = draw_date_obj.isoweekday()  # 1-7 表示周一到周日
            logger.info(f"开奖日期的星期: {weekday}")
            
            # 如果不是开奖日，不检查
            if weekday not in LOTTERY_APIS[lottery_type]['draw_days']:
                logger.info("不是开奖日，跳过检查")
                return False
            
            logger.info("是开奖日，进行检查")
            return True
        
        logger.info("开奖日期不新，无需检查")
        return False

    def get_lottery_numbers(self, lottery_type: str) -> Optional[List[str]]:
        """从环境变量获取彩票号码，并根据彩票类型进行格式化"""
        env_key = LOTTERY_APIS[lottery_type]['env_key']
        numbers = os.getenv(env_key)
        if not numbers:
            return None
        
        try:
            if lottery_type == '3d':
                # 3D彩票去掉前导零
                return [str(int(num)) for num in numbers.split(',')]
            else:
                # 其他彩票补全为两位数格式
                return [f"{int(num):02}" for num in numbers.split(',')]
        except Exception as e:
            logger.error(
                f"解析{lottery_type}彩票号码失败: {numbers}, 错误: {str(e)}"
            )
            return None

    def get_latest_lottery_info(self, lottery_type: str) -> Optional[Dict]:
        """获取最新开奖信息"""
        api_info = LOTTERY_APIS[lottery_type]
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36')
        }
        
        try:
            response = requests.get(
                api_info['url'],
                headers=headers,
                params=api_info['params']
            )
            response.raise_for_status()
            data = response.json()
            
            return data['result'][0]
        except Exception as e:
            logger.error(
                f"获取{lottery_type}开奖信息失败: {str(e)}"
            )
            return None

    def check_ssq(self, my_numbers: List[str]) -> Dict:
        """检查双色球中奖"""
        latest_info = self.get_latest_lottery_info('ssq')
        if not latest_info or len(my_numbers) != 7:
            return None

        winning_numbers = latest_info['red'].split(',') + [latest_info['blue']]
        my_red_numbers = my_numbers[:-1]
        my_blue_number = my_numbers[-1]

        red_matches = len(set(my_red_numbers) & set(winning_numbers[:-1]))
        blue_matches = my_blue_number == winning_numbers[-1]

        prize_level = self._calculate_ssq_prize(red_matches, blue_matches)
        
        return {
            'date': latest_info['date'],
            'winning_numbers': winning_numbers,
            'my_numbers': my_numbers,
            'prize_level': prize_level,
            'prize_amount': self._get_prize_amount(prize_level, latest_info)
        }

    def check_3d(self, my_numbers: List[str]) -> Dict:
        """检查福彩3D中奖"""
        latest_info = self.get_latest_lottery_info('3d')
        if not latest_info or len(my_numbers) != 3:
            return None

        winning_numbers = latest_info['red'].split(',')
        matches = sum(1 for my, win in zip(my_numbers, winning_numbers)
                      if my == win)
        
        prize_level = self._calculate_3d_prize(matches)
        
        return {
            'date': latest_info['date'],
            'winning_numbers': winning_numbers,
            'my_numbers': my_numbers,
            'prize_level': prize_level,
            'prize_amount': 1040 if prize_level == "中奖" else 0
        }

    def check_kl8(self, my_numbers: List[str], play_type: int) -> Dict:
        """检查快乐8中奖，支持从选一到选十的不同玩法"""
        logger.info(f"检查快乐8彩票，用户号码: {my_numbers}, 玩法: 选{play_type}")
        
        latest_info = self.get_latest_lottery_info('kl8')
        if not latest_info:
            logger.error("未能获取快乐8的最新开奖信息")
            return None
        if len(my_numbers) != play_type:
            logger.error(f"快乐8号码数量不正确，应为{play_type}个")
            return None

        winning_numbers = latest_info['red'].split(',')
        logger.info(f"快乐8中奖号码: {winning_numbers}")

        matches = len(set(my_numbers) & set(winning_numbers))
        logger.info(f"匹配的号码数量: {matches}")

        prize_level = f'x{play_type}z{matches}'
        
        prize_info = next(
            (item for item in latest_info.get('prizegrades', [])
             if item['type'] == prize_level),
            None
        )
        if prize_info:

            return {
                'date': latest_info['date'],
                'winning_numbers': winning_numbers,
                'my_numbers': my_numbers,
                'prize_level': prize_level,
                'prize_amount': prize_info['typemoney']
            }
        return {
            'date': latest_info['date'],
            'winning_numbers': winning_numbers,
            'my_numbers': my_numbers,
            'prize_level': prize_level,
            'prize_amount': 0
        }

    @staticmethod
    def _calculate_ssq_prize(red_matches: int, blue_matches: bool) -> str:
        """计算双色球中奖等级"""
        if red_matches == 6 and blue_matches:
            return "一等奖"
        elif red_matches == 6:
            return "二等奖"
        elif red_matches == 5 and blue_matches:
            return "三等奖"
        elif red_matches == 5 or (red_matches == 4 and blue_matches):
            return "四等奖"
        elif red_matches == 4 or (red_matches == 3 and blue_matches):
            return "五等奖"
        elif blue_matches:
            return "六等奖"
        return "未中奖"

    @staticmethod
    def _calculate_3d_prize(matches: int) -> str:
        """计算福彩3D中奖等级"""
        if matches == 3:
            return "中奖"
        else:
            return "未中奖"

    @staticmethod
    def _calculate_kl8_prize(matches: int, play_type: int, prizegrades: List[Dict]) -> Dict[str, str]:
        """计算快乐8中奖结果，返回匹配的号码数量和类型"""
        prize_type = f"x{matches}z{play_type}"
        prize_info = next(
            (item for item in prizegrades if item['type'] == prize_type),
            None
        )
        if prize_info:
            return {"type": prize_type, "typemoney": prize_info['typemoney']}
        return {"type": prize_type, "typemoney": "0"}

    def _get_prize_amount(self, prize_level: str, lottery_info: Dict) -> float:
        """获取奖金金额"""
        if prize_level == "未中奖":
            return 0
        # 替换中文数字为阿拉伯数字
        prize_level = prize_level.replace(
            "一", "1"
        ).replace("二", "2").replace("三", "3").replace(
            "四", "4"
        ).replace("五", "5").replace("六", "6")[0]

        try:
            prize_info = next(
                (item for item in lottery_info.get('prizegrades', [])
                 if item['type'] == int(prize_level)),
                None
            )
            return prize_info['typemoney'] if prize_info else 0
        except Exception as e:
            logger.error(f"获取奖金金额失败: {str(e)}")
            return 0

    def _update_history(self, lottery_type: str, result: Dict) -> None:
        """更新中奖历史记录"""
        try:
            with open(JSON_FILE_NAME, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                lottery_data = data['types'][lottery_type]
                
                # 更新最后检查日期
                lottery_data['last_check_date'] = time.strftime('%Y-%m-%d')
                
                # 添加到历史记录
                if result['prize_level'] != "未中奖":
                    lottery_data['history']['lottery_numbers'].append(
                        result['my_numbers']
                    )
                    lottery_data['history']['rewards'][result['date']] = {
                        'level': result['prize_level'],
                        'amount': result['prize_amount']
                    }
                    
                    # 更新总奖金
                    lottery_data['total_rewards'] += int(result['prize_amount'])
                    
                    # 更新最高奖金记录
                    if int(result['prize_amount']) > \
                            lottery_data['max_reward']['money']:
                        lottery_data['max_reward'] = {
                            'date': result['date'],
                            'level': result['prize_level'],
                            'money': result['prize_amount']
                        }
                
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            logger.error(f"更新历史记录失败: {str(e)}")

    def _update_last_draw_date(self, lottery_type: str, draw_date: str) -> None:
        """更新最后检查的开奖日期"""
        try:
            # 去除日期中的星期格式
            draw_date = draw_date[:len(draw_date)-3]
            with open(JSON_FILE_NAME, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data['types'][lottery_type]['last_draw_date'] = draw_date
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            logger.error(f"更新最后检查开奖日期失败: {str(e)}")

    def _update_last_check_date(self, lottery_type: str, check_date: str) -> None:
        """更新最后检查的日期"""
        try:
            # 去除日期中的星期格式
            check_date = check_date[:len(check_date)-3]
            with open(JSON_FILE_NAME, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data['types'][lottery_type]['last_check_date'] = check_date
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            logger.error(f"更新最后检查日期失败: {str(e)}")

    @staticmethod
    def _write_json_data(file_path: str, data: Dict) -> None:
        """将数据写入JSON文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


def check_lottery(lottery_type: str, numbers: List[str], checker: LotteryChecker, play_type: int = 10) -> Union[Dict, None]:
    """检查指定类型彩票"""
    check_functions = {
        'ssq': checker.check_ssq,
        '3d': checker.check_3d,
        'kl8': checker.check_kl8
    }
    
    if lottery_type == 'kl8':
        result = check_functions[lottery_type](numbers, play_type=play_type)
    else:
        result = check_functions[lottery_type](numbers)

    if result:
        draw_date = result['date'].split(' ')[0]  # 提取日期部分
        if checker.should_check_lottery(lottery_type, draw_date):
            print(f"\n{lottery_type.upper()}检查结果:")
            print(f"开奖日期: {result['date']}")
            print(f"中奖号码: {', '.join(result['winning_numbers'])}")
            print(f"您的号码: {', '.join(result['my_numbers'])}")
            print(f"中奖结果: {result['prize_level']}")
            print(f"中奖金额: {result['prize_amount']}元")
            checker._update_history(lottery_type, result)
            checker._update_last_draw_date(lottery_type, draw_date)
            checker._update_last_check_date(lottery_type, draw_date)
        else:
            logger.info(f"{lottery_type.upper()}没有新的开奖结果需要检查")
    else:
        logger.error(f"{lottery_type.upper()}检查失败")

    return result


def generate_html_report(results):
    html_content = []

    for result in results:
        html_content.extend([
            f"<h2 style='color: #4CAF50; text-align: center;'>{result['lottery_type'].upper()} 检查结果</h2>",
            f"• 开奖日期: {result['date']}<br>",
            f"• 中奖号码: {', '.join(result['winning_numbers'])}<br>",
            f"• 用户号码: {', '.join(result['my_numbers'])}<br>",
            f"• 中奖结果: {result['prize_level']}<br>",
            f"• 中奖金额: {result['prize_amount']}元<br>",
            "<hr>"
        ])

    return ''.join(html_content)

def run():
    """主函数"""
    checker = LotteryChecker()
    results = []
        
    # 检查各类彩票
    for lottery_type in ['ssq', '3d', 'kl8']:
        numbers = checker.get_lottery_numbers(lottery_type)
        if numbers:
            result = check_lottery(lottery_type, numbers, checker)
            if result:
                results.append({
                    'lottery_type': lottery_type,
                    'date': result['date'],
                    'winning_numbers': result['winning_numbers'],
                    'my_numbers': result['my_numbers'],
                    'prize_level': result['prize_level'],
                    'prize_amount': result['prize_amount']
                })
        else:
            logger.info(f"未配置{lottery_type.upper()}彩票号码，跳过检查")

    # 生成HTML报告
    html_report = generate_html_report(results)

    # 检查是否已经推送
    current_date = datetime.now().strftime('%Y-%m-%d')

    # 在成功推送后更新最后推送日期
    try:
        with open(JSON_FILE_NAME, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            # 确保 `date_info` 存在
            if 'date_info' not in data:
                data['date_info'] = {'last_push_date': '0000-00-00'}
            last_push_date = data['date_info'].get('last_push_date', '0000-00-00')

            if last_push_date == current_date:
                logger.info("今天已经推送过彩票检查报告，不再重复推送。")
                return

            QLAPI.notify("彩票检查报告", html_report)
            # 更新最后推送日期
            data['date_info']['last_push_date'] = current_date
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
    except Exception as e:
        logger.error(f"发送彩票检查报告失败: {str(e)}")


if __name__ == "__main__":
    run() 
    
