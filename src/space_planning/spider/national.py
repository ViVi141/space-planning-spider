import requests
from datetime import datetime
import time
import random
import logging
from typing import Dict, Optional

from ..core import database as db
from .anti_crawler import AntiCrawlerManager
from .monitor import CrawlerMonitor
from .spider_config import SpiderConfig
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# 机构名称常量
LEVEL_NAME = "住房和城乡建设部"

class NationalSpider:
    def __init__(self):
        # 从配置获取参数
        config = SpiderConfig.get_national_config()
        
        self.api_url = config['api_url']
        self.level = config['level']
        self.base_url = config['base_url']
        self.base_params = config['base_params'].copy()
        self.speed_mode = config['default_speed_mode']
        
        # 初始化防反爬虫管理器
        self.anti_crawler = AntiCrawlerManager()
        self.monitor = CrawlerMonitor()
        
        # 设置特定的请求头（住建部网站需要）
        self.special_headers = config['headers'].copy()
        self.special_headers.update({
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-KL-SaaS-Ajax-Request': 'Ajax_Request',
            'X-Requested-With': 'XMLHttpRequest'
        })
    
    def _ensure_proxy_initialized(self):
        """确保代理系统已初始化（在每次请求前调用）"""
        try:
            from .proxy_pool import initialize_proxy_pool, is_global_proxy_enabled, get_proxy_stats
            import os
            
            # 检查代理状态
            if not is_global_proxy_enabled():
                return False
            
            # 检查代理池是否已初始化
            try:
                stats = get_proxy_stats()
                if stats and stats.get('running', False):
                    # 代理池已运行
                    return True
            except Exception:
                pass
            
            # 初始化代理池
            config_file = os.path.join(os.path.dirname(__file__), '..', 'gui', 'proxy_config.json')
            if os.path.exists(config_file):
                if initialize_proxy_pool(config_file):
                    logger.info("NationalSpider: 代理池已初始化")
                    return True
                else:
                    logger.warning("NationalSpider: 代理池初始化失败（可能配置未启用）")
            else:
                logger.debug(f"NationalSpider: 代理配置文件不存在: {config_file}")
        except Exception as e:
            logger.error(f"NationalSpider: 代理初始化失败: {e}", exc_info=True)
        
        return False

    def crawl_policies(self, keywords=None, callback=None, start_date=None, end_date=None, speed_mode="正常速度", disable_speed_limit=False, stop_callback=None, policy_callback=None):
        """
        通过API获取住建部政策文件，基于时间区间过滤
        Args:
            keywords: 关键词列表，None表示不限制
            callback: 进度回调函数，用于GUI显示进度
            start_date: 起始日期（yyyy-MM-dd）
            end_date: 结束日期（yyyy-MM-dd）
            speed_mode: 速度模式（"快速模式"、"正常速度"、"慢速模式"）
            disable_speed_limit: 是否禁用速度限制
            stop_callback: 停止回调函数
            policy_callback: 政策数据回调函数，每解析到一条政策时调用
        """
        logger.info(f"NationalSpider.crawl_policies 开始执行: keywords={keywords}, start_date={start_date}, end_date={end_date}, speed_mode={speed_mode}")
        
        # 设置速度模式并应用统一配置
        self.speed_mode = speed_mode
        self.anti_crawler.configure_speed_mode(speed_mode, disable_speed_limit)
        
        policies = []
        # 从通用配置获取页面大小
        common_config = SpiderConfig.get_common_config()
        page_size = common_config['page_size']
        
        page_no = 1
        total_processed = 0
        
        # 时间区间状态跟踪
        dt_start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        dt_end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        # 从通用配置获取参数
        common_config = SpiderConfig.get_common_config()
        max_consecutive_out_of_range = common_config['max_consecutive_out_of_range']
        
        in_target_range = False  # 是否已进入目标时间区间
        consecutive_out_of_range = 0  # 连续超出范围的页数
        
        while True:
            # 检查是否停止
            if stop_callback and stop_callback():
                logger.info("用户已停止爬取")
                break
                
            logger.debug(f"正在检索第 {page_no} 页...")
            if callback:
                callback(f"正在检索第 {page_no} 页...")
            
            try:
                # 确保代理已初始化（在每次请求前检查）
                self._ensure_proxy_initialized()
                
                # 检查请求频率限制
                # self.rate_limiter.wait_if_needed() # Removed as per edit hint
                
                import json
                param_json = {
                    "pageNo": page_no,
                    "pageSize": page_size,
                    "loadEnabled": True,
                    "search": "{}"
                }
                params = self.base_params.copy()
                params['paramJson'] = json.dumps(param_json)
                
                # 合并请求头
                headers = self.special_headers.copy()
                
                # 使用防反爬虫管理器发送请求（已集成代理支持）
                try:
                    logger.debug(f"正在请求第 {page_no} 页: {self.api_url}")
                    resp = self.anti_crawler.make_request(
                        self.api_url, 
                        method='GET',
                        params=params, 
                        headers=headers
                    )
                    logger.debug(f"第 {page_no} 页请求成功，状态码: {resp.status_code}")
                    data = resp.json()
                    logger.debug(f"第 {page_no} 页响应数据: data键存在={('data' in data)}, data类型={type(data.get('data'))}")
                    self.monitor.record_request(self.api_url, success=True)
                except Exception as e:
                    logger.error(f"第 {page_no} 页请求失败: {e}", exc_info=True)
                    self.monitor.record_request(self.api_url, success=False, error_type=str(e))
                    raise
                
                html_content = data.get('data', {}).get('html', '')
                if not html_content:
                    logger.warning(f"第 {page_no} 页无HTML内容，响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    logger.warning(f"第 {page_no} 页 data['data'] 内容: {data.get('data')}")
                    logger.info(f"第 {page_no} 页无HTML内容，停止检索，已获取 {len(policies)} 条政策")
                    return policies
                
                soup = BeautifulSoup(html_content, 'html.parser')
                table = soup.find('table')
                if not isinstance(table, Tag):
                    logger.warning(f"第 {page_no} 页未找到表格，HTML长度: {len(html_content)}, 停止检索")
                    logger.debug(f"第 {page_no} 页HTML前500字符: {html_content[:500]}")
                    return policies
                tbody = table.find('tbody')
                if not isinstance(tbody, Tag):
                    logger.warning(f"第 {page_no} 页未找到tbody，停止检索")
                    return policies
                rows = tbody.find_all('tr')
                logger.debug(f"第 {page_no} 页找到 {len(rows)} 条政策")
                page_policies = []
                page_dates = []
                
                for row in rows:
                    if not isinstance(row, Tag):
                        continue
                    # 检查是否停止
                    if stop_callback and stop_callback():
                        logger.info("用户已停止爬取")
                        break
                        
                    cells = row.find_all('td') if hasattr(row, 'find_all') else []
                    if len(cells) >= 4:
                        # 将ResultSet转换为列表，避免索引问题
                        cells_list = list(cells)
                        title_cell = cells_list[1] if len(cells_list) > 1 else None
                        title_link = None
                        if isinstance(title_cell, Tag):
                            title_link = title_cell.find('a')
                            if title_link and isinstance(title_link, Tag):
                                title = title_link.get('title', '') or title_link.get_text(strip=True)
                                url = title_link.get('href', '')
                            else:
                                title = ''
                                url = ''
                            
                            # 验证标题和URL有效性
                            if not title or not title.strip() or len(title.strip()) < 3:
                                continue
                            if not url or not isinstance(url, str) or not url.strip():
                                continue
                            
                            url = url.strip()
                            # 过滤明显无效的URL
                            if url == '表格没有内容' or url == '无' or url.lower() == 'none' or len(url) < 5:
                                logger.debug(f"跳过无效URL: {url} (标题: {title[:30]})")
                                continue
                            
                            doc_number = cells_list[2].get_text(strip=True) if len(cells_list) > 2 and isinstance(cells_list[2], Tag) else ''
                            pub_date = cells_list[3].get_text(strip=True) if len(cells_list) > 3 and isinstance(cells_list[3], Tag) else ''
                            
                            # 确保URL是完整的HTTP/HTTPS链接
                            if not url.startswith('http://') and not url.startswith('https://'):
                                if url.startswith('/'):
                                    url = self.base_url + url
                                elif url.startswith('javascript:') or url.startswith('#'):
                                    logger.debug(f"跳过JavaScript链接或锚点: {url}")
                                    continue
                                else:
                                    # 尝试拼接base_url
                                    url = self.base_url + '/' + url if not url.startswith('/') else self.base_url + url
                            
                            # 解析日期
                            try:
                                dt_pub = datetime.strptime(pub_date, '%Y-%m-%d')
                                page_dates.append(dt_pub)
                            except Exception:
                                continue
                            
                            # 时间区间过滤
                            if dt_start and dt_pub < dt_start:
                                continue
                            if dt_end and dt_pub > dt_end:
                                continue
                            
                            # 关键词过滤
                            if keywords and keywords != [''] and not any(kw in title for kw in keywords):
                                continue
                            
                            logger.debug(f"处理政策: {title}")
                            if callback:
                                callback(f"正在处理: {title[:30]}...")
                            
                            # 根据速度设置决定是否添加延迟
                            if not disable_speed_limit:
                                time.sleep(random.uniform(0.5, 2.0))
                            content = self.get_policy_detail(url, stop_callback)
                            policy_data = {
                                'level': '住房和城乡建设部',
                                'title': title,
                                'pub_date': pub_date,
                                'doc_number': doc_number,
                                'source': url,  # 确保source字段存在
                                'url': url,  # 兼容字段
                                'link': url,  # 兼容字段
                                'content': content,
                                'category': '',  # 添加category字段（住建部没有分类）
                                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            page_policies.append(policy_data)
                            
                            # 调用 policy_callback 实时返回政策数据
                            if policy_callback:
                                try:
                                    policy_callback(policy_data)
                                except Exception as cb_error:
                                    logger.warning(f"调用 policy_callback 失败: {cb_error}")
                            
                            # 立即发送单条政策数据到界面
                            if callback:
                                callback(f"已获取: {title[:30]}...")
                                # 发送政策数据信号 - 发送完整内容
                                callback(f"POLICY_DATA:{title}|{pub_date}|{url}|{content}")
                
                logger.debug(f"第 {page_no} 页：找到 {len(rows)} 条，保留 {len(page_policies)} 条")
                total_processed += len(page_policies)
                policies.extend(page_policies)
                
                # 时间区间状态检查 - 优化版本
                if dt_start and dt_end and page_dates:
                    # 更精确的时间区间判断
                    if not in_target_range:
                        # 检查是否有任何数据在目标时间范围内
                        has_target_data = any(dt_start <= d <= dt_end for d in page_dates)
                        if has_target_data:
                            in_target_range = True
                            consecutive_out_of_range = 0
                            logger.info(f"第 {page_no} 页：进入目标时间区间 [{start_date} - {end_date}]")
                    
                    elif in_target_range:
                        # 检查是否所有数据都在目标范围外
                        all_out_of_range = all(d < dt_start or d > dt_end for d in page_dates)
                        if all_out_of_range:
                            consecutive_out_of_range += 1
                            logger.debug(f"第 {page_no} 页：脱离目标时间区间，连续 {consecutive_out_of_range} 页")
                            
                            # 如果连续多页都脱离范围，停止检索
                            if consecutive_out_of_range >= max_consecutive_out_of_range:
                                logger.info(f"连续 {max_consecutive_out_of_range} 页脱离目标时间区间，停止检索")
                                return policies
                        else:
                            consecutive_out_of_range = 0
                
                # 更新进度
                if page_policies:
                    if callback:
                        callback(f"在第 {page_no} 页找到 {len(page_policies)} 条政策")
                else:
                    if callback:
                        callback(f"第 {page_no} 页无匹配政策")
                
                page_no += 1
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"检索第 {page_no} 页超时: {e}")
                if callback:
                    callback(f"检索第 {page_no} 页超时，尝试继续下一页...")
                page_no += 1
                continue
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"检索第 {page_no} 页连接错误: {e}")
                if callback:
                    callback(f"检索第 {page_no} 页连接错误，尝试继续下一页...")
                page_no += 1
                continue
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
                logger.error(f"检索第 {page_no} 页HTTP错误: {e} (状态码: {status_code})")
                if callback:
                    callback(f"检索第 {page_no} 页HTTP错误 (状态码: {status_code})")
                # HTTP错误通常是可恢复的，继续下一页
                page_no += 1
                continue
            except (ValueError, KeyError) as e:
                # JSON解析错误或数据结构错误
                logger.warning(f"检索第 {page_no} 页数据解析错误: {e}")
                if callback:
                    callback(f"检索第 {page_no} 页数据解析错误，尝试继续下一页...")
                page_no += 1
                continue
            except Exception as e:
                logger.error(f"检索第 {page_no} 页时出现未知错误: {e}", exc_info=True)
                if callback:
                    callback(f"检索第 {page_no} 页时出错: {e}")
                # 对于未知错误，根据错误信息判断是否继续
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['timeout', 'connection', 'network', 'dns']):
                    logger.info("检测到网络相关错误，尝试继续下一页...")
                    page_no += 1
                    continue
                else:
                    logger.error("遇到严重错误，停止爬取")
                    break
        
        logger.info(f"爬取完成，共获取 {len(policies)} 条政策")
        if callback:
            callback(f"爬取完成，共获取 {len(policies)} 条政策")
        
        return policies

    def get_crawler_status(self):
        """获取爬虫状态"""
        return {
            'speed_mode': self.speed_mode,
            'monitor_stats': self.monitor.get_stats(),
            # Removed rate_limiter_stats as per edit hint
        }

    def _parse_policy_item(self, item: Dict) -> Optional[Dict]:
        """解析单个政策项（与多线程版本保持一致）"""
        try:
            title = item.get('title', '').strip()
            if not title:
                return None
            
            pub_date = item.get('pub_date', '')
            doc_number = item.get('doc_number', '')
            url = item.get('source', '')
            
            # 获取政策详情内容
            content = self.get_policy_detail(url) if url else ''
            
            return {
                'level': self.level,
                'title': title,
                'pub_date': pub_date,
                'doc_number': doc_number,
                'source': url,  # 确保source字段存在
                'url': url,  # 兼容字段
                'link': url,  # 兼容字段
                'content': content,
                'category': '',  # 添加category字段（住建部没有分类）
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"解析政策项失败: {e}", exc_info=True)
            return None

    def get_policy_detail(self, url, stop_callback=None):
        """获取政策详情内容"""
        try:
            # 检查是否停止
            if stop_callback and stop_callback():
                return ""
            
            # 验证 URL 有效性
            if not url or not isinstance(url, str):
                logger.warning(f"无效的URL: {url}")
                return ""
            
            url = url.strip()
            if not url or url == '表格没有内容' or len(url) < 10:  # 过滤明显无效的URL
                logger.warning(f"跳过无效URL: {url}")
                return ""
            
            # 确保URL是完整的HTTP/HTTPS链接
            if not url.startswith('http://') and not url.startswith('https://'):
                if url.startswith('/'):
                    url = self.base_url + url
                elif not url.startswith('http'):
                    logger.warning(f"URL格式不正确，跳过: {url}")
                    return ""
            
            # 使用防反爬虫管理器发送请求
            headers = self.special_headers.copy()
            try:
                resp = self.anti_crawler.make_request(url, headers=headers)
            except requests.exceptions.RequestException as e:
                # 网络请求异常，记录但不中断流程
                self.monitor.record_request(url, success=False, error_type=f"网络请求异常: {str(e)}")
                logger.debug(f"获取政策详情网络请求失败: {url}, 错误: {e}")
                return ""
            except Exception as e:
                # 其他异常，记录但不中断流程
                self.monitor.record_request(url, success=False, error_type=str(e))
                logger.debug(f"获取政策详情请求失败: {url}, 错误: {e}")
                return ""
            
            # 检查响应是否有效
            if not resp or not hasattr(resp, 'content'):
                logger.warning(f"无效的响应: {url}")
                return ""
            
            # 记录成功的详情页面请求
            self.monitor.record_request(url, success=True)
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 提取正文内容
            content_div = soup.find('div', class_='content')
            if content_div:
                content = content_div.get_text(strip=True)
                if content and len(content) > 50:  # 确保内容足够长
                    return content
            
            # 备用方案：尝试其他常见的内容容器
            for selector in ['div.article-content', 'div.text', 'div.main-content', 'div.detail']:
                content_div = soup.select_one(selector)
                if content_div:
                    content = content_div.get_text(strip=True)
                    if content and len(content) > 50:
                        return content
            
            # 最后的兜底方案：返回整个页面的文本
            return soup.get_text(strip=True)
            
        except Exception as e:
            # 记录失败的详情页面请求，但不抛出异常
            url_str = str(url) if url else "未知URL"
            self.monitor.record_request(url_str, success=False, error_type=str(e))
            logger.debug(f"获取政策详情失败: {url_str}, 错误: {e}")
            return ""  # 返回空字符串而不是抛出异常

    def save_to_db(self, policies):
        """保存政策到数据库"""
        for policy in policies:
            # 检查policy是字典还是其他格式
            if isinstance(policy, dict):
                db.insert_policy(
                    policy['level'],
                    policy['title'],
                    policy['pub_date'],
                    policy['source'],
                    policy['content'],
                    policy['crawl_time']
                )
            elif isinstance(policy, (list, tuple)) and len(policy) >= 6:
                # 如果是元组格式：(id, level, title, pub_date, source, content)
                db.insert_policy(
                    policy[1],  # level
                    policy[2],  # title
                    policy[3],  # pub_date
                    policy[4],  # source
                    policy[5],  # content
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # crawl_time
                )

# 为兼容性添加别名类
class NationalPolicyCrawler(NationalSpider):
    """国家级政策爬虫类（NationalSpider的别名）"""
    pass

if __name__ == "__main__":
    spider = NationalSpider()
    policies = spider.crawl_policies(['规划', '空间', '用地'])
    spider.save_to_db(policies)
    logger.info(f"爬取到 {len(policies)} 条国家住建部政策") 