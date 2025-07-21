#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多线程基础爬虫
"""

import threading
import queue
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Callable
from datetime import datetime
import logging
import os

from .proxy_pool import ProxyManager, initialize_proxy_pool, get_shared_proxy, report_shared_proxy_result, is_global_proxy_enabled

logger = logging.getLogger(__name__)


class MultiThreadBaseCrawler:
    """多线程基础爬虫类"""
    
    def __init__(self, max_workers=4, enable_proxy=True):
        self.max_workers = max_workers
        self.enable_proxy = enable_proxy
        
        # 线程管理
        self.thread_sessions = {}  # 线程专用会话
        self.thread_locks = {}     # 线程锁
        self.thread_proxies = {}   # 线程专用代理
        
        # 任务管理
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.error_queue = queue.Queue()
        
        # 统计管理
        self.stats_lock = threading.Lock()
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_threads': 0,
            'total_crawled': 0,
            'total_saved': 0,
            'start_time': None,
            'end_time': None
        }
        
        # 去重管理
        self.seen_items = set()
        self.seen_lock = threading.Lock()
        
        # 停止管理
        self.stop_flag = False
        self.stop_lock = threading.Lock()
        
        # 代理管理 - 使用共享代理系统
        if enable_proxy:
            try:
                # 检查全局代理是否启用
                if is_global_proxy_enabled():
                    logger.info("多线程爬虫使用共享代理系统")
                else:
                    logger.info("全局代理已禁用，多线程爬虫将不使用代理")
                    self.enable_proxy = False
            except Exception as e:
                logger.error(f"初始化代理管理器失败: {e}")
                self.enable_proxy = False
        else:
            logger.info("代理已禁用")
        
        logger.info(f"初始化多线程爬虫，最大线程数: {max_workers}, 代理启用: {self.enable_proxy}")
    
    def set_stop_flag(self, stop_callback: Optional[Callable] = None):
        """设置停止标志"""
        with self.stop_lock:
            self.stop_flag = True
            self.stop_callback = stop_callback
    
    def check_stop(self) -> bool:
        """检查是否需要停止"""
        with self.stop_lock:
            if self.stop_flag:
                return True
            if hasattr(self, 'stop_callback') and self.stop_callback:
                return self.stop_callback()
            return False
    
    def _get_thread_session(self):
        """获取线程专用会话和代理"""
        thread_id = threading.current_thread().ident
        
        if thread_id not in self.thread_sessions:
            # 创建新的会话
            import requests
            session = requests.Session()
            
            # 设置共享代理
            if self.enable_proxy:
                shared_proxy = get_shared_proxy()
                if shared_proxy:
                    session.proxies.update(shared_proxy)
                    logger.info(f"线程 {threading.current_thread().name} 使用共享代理")
                else:
                    logger.warning(f"线程 {threading.current_thread().name} 无法获取共享代理")
            
            # 创建线程锁
            lock = threading.Lock()
            
            self.thread_sessions[thread_id] = session
            self.thread_locks[thread_id] = lock
        
        return self.thread_sessions[thread_id], self.thread_locks[thread_id]
    
    def _rotate_thread_proxy(self) -> bool:
        """轮换线程代理 - 使用共享代理系统"""
        if not self.enable_proxy:
            return False
        
        try:
            # 报告当前代理失败
            report_shared_proxy_result(False)
            
            # 获取新的共享代理
            new_proxy = get_shared_proxy()
            if new_proxy:
                thread_id = threading.current_thread().ident
                if thread_id in self.thread_sessions:
                    self.thread_sessions[thread_id].proxies.update(new_proxy)
                    logger.info(f"线程 {threading.current_thread().name} 已轮换共享代理")
                    return True
            else:
                logger.warning(f"线程 {threading.current_thread().name} 无法获取新代理")
                return False
        except Exception as e:
            logger.error(f"轮换代理失败: {e}")
            return False
    
    def _generate_item_hash(self, item: Dict) -> str:
        """生成项目哈希值用于去重"""
        # 只使用标题作为去重依据，避免过于严格
        title = item.get('title', '').strip()
        
        # 生成哈希值
        import hashlib
        hash_string = f"{title}"
        return hashlib.md5(hash_string.encode('utf-8')).hexdigest()
    
    def _is_duplicate_item(self, item_hash: str) -> bool:
        """检查是否为重复项"""
        with self.seen_lock:
            if item_hash in self.seen_items:
                return True
            self.seen_items.add(item_hash)
            return False
    
    def _process_single_task(self, task_data: Dict, callback: Optional[Callable] = None) -> List[Dict]:
        """处理单个任务（线程安全）"""
        thread_name = threading.current_thread().name
        thread_id = threading.current_thread().ident
        task_id = task_data.get('task_id', 'unknown')
        
        # 更新活跃线程数
        with self.stats_lock:
            self.stats['active_threads'] += 1
        
        try:
            logger.info(f"线程 {thread_name} 开始处理任务: {task_id}")
            if callback:
                callback(f"线程 {thread_name} 开始处理任务")
            
            # 检查是否需要停止
            if self.check_stop():
                logger.info(f"线程 {thread_name} 检测到停止信号，退出任务")
                if callback:
                    callback(f"线程 {thread_name} 已停止")
                return []
            
            # 获取线程专用会话
            session, lock = self._get_thread_session()
            
            # 执行具体的爬取任务（由子类实现）
            results = self._execute_task(task_data, session, lock, callback)
            
            # 更新统计
            with self.stats_lock:
                self.stats['completed_tasks'] += 1
                self.stats['total_crawled'] += len(results)
                self.stats['total_saved'] += len(results)
                self.stats['active_threads'] -= 1
            
            logger.info(f"线程 {thread_name} 完成任务，获取 {len(results)} 条数据")
            if callback:
                callback(f"线程 {thread_name} 完成任务，获取 {len(results)} 条数据")
            
            return results
            
        except Exception as e:
            logger.error(f"线程 {thread_name} 处理任务失败: {e}")
            
            # 尝试轮换代理
            if self._rotate_thread_proxy():
                logger.info(f"线程 {thread_name} 已轮换代理，可重试")
            
            # 更新失败统计
            with self.stats_lock:
                self.stats['failed_tasks'] += 1
                self.stats['active_threads'] -= 1
            
            # 记录错误
            self.error_queue.put((task_id, str(e)))
            
            if callback:
                callback(f"线程 {thread_name} 处理失败: {e}")
            
            return []
    
    def _execute_task(self, task_data: Dict, session, lock, callback: Optional[Callable] = None) -> List[Dict]:
        """执行具体任务（由子类重写）"""
        raise NotImplementedError("子类必须实现 _execute_task 方法")
    
    def _prepare_tasks(self) -> List[Dict]:
        """准备任务列表（由子类重写）"""
        raise NotImplementedError("子类必须实现 _prepare_tasks 方法")
    
    def crawl_multithread(self, callback: Optional[Callable] = None, 
                         stop_callback: Optional[Callable] = None,
                         max_workers: Optional[int] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> List[Dict]:
        """多线程爬取主方法"""
        if max_workers is None:
            max_workers = self.max_workers
        
        # 重置停止标志
        with self.stop_lock:
            self.stop_flag = False
            self.stop_callback = stop_callback
        
        # 保存时间范围参数
        if start_date and end_date:
            self.user_start_date = start_date
            self.user_end_date = end_date
            logger.info(f"设置用户时间范围: {start_date} 至 {end_date}")
        else:
            self.user_start_date = None
            self.user_end_date = None
            logger.info("未指定时间范围，使用默认范围")
        
        logger.info(f"开始多线程爬取，线程数: {max_workers}")
        
        # 重置统计信息
        with self.stats_lock:
            self.stats = {
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'active_threads': 0,
                'total_crawled': 0,
                'total_saved': 0,
                'start_time': datetime.now(),
                'end_time': None
            }
        
        # 清空去重集合
        with self.seen_lock:
            self.seen_items.clear()
        
        # 准备任务列表
        tasks = self._prepare_tasks()
        with self.stats_lock:
            self.stats['total_tasks'] = len(tasks)
        
        if callback:
            callback(f"准备完成，共 {len(tasks)} 个任务，使用 {max_workers} 个线程")
        
        all_results = []
        start_time = time.time()
        
        # 使用线程池执行任务
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            for task_data in tasks:
                if self.check_stop():
                    logger.info("用户已停止爬取")
                    break
                
                future = executor.submit(
                    self._process_single_task,
                    task_data,
                    callback
                )
                future_to_task[future] = task_data.get('task_id', 'unknown')
            
            # 收集结果
            for future in as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    task_results = future.result()
                    all_results.extend(task_results)
                    
                    # 实时显示进度
                    with self.stats_lock:
                        completed = self.stats['completed_tasks']
                        failed = self.stats['failed_tasks']
                        total = self.stats['total_tasks']
                        active = self.stats['active_threads']
                    
                    if callback:
                        callback(f"任务 {task_id} 完成，当前进度: {completed}/{total} 完成, {failed} 失败, {active} 活跃线程")
                    
                    # 检查是否需要停止
                    if self.check_stop():
                        logger.info("用户已停止爬取，等待剩余任务完成")
                        if callback:
                            callback("用户已停止爬取，等待剩余任务完成")
                        break
                    
                except Exception as e:
                    logger.error(f"任务 {task_id} 执行异常: {e}")
                    if callback:
                        callback(f"任务 {task_id} 执行失败: {e}")
        
        # 最终统计
        with self.stats_lock:
            self.stats['end_time'] = datetime.now()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 检查是否被停止
        was_stopped = self.check_stop()
        
        logger.info(f"多线程爬取完成统计:")
        logger.info(f"  总耗时: {elapsed_time:.2f} 秒")
        logger.info(f"  总任务数: {self.stats['total_tasks']} 个")
        logger.info(f"  完成任务数: {self.stats['completed_tasks']} 个")
        logger.info(f"  失败任务数: {self.stats['failed_tasks']} 个")
        logger.info(f"  总爬取数量: {self.stats['total_crawled']} 条")
        logger.info(f"  最终保存数量: {self.stats['total_saved']} 条")
        if was_stopped:
            logger.info("  爬取被用户停止")
        
        if callback:
            if was_stopped:
                callback(f"多线程爬取已停止！总耗时: {elapsed_time:.2f}秒，最终保存: {self.stats['total_saved']} 条")
            else:
                callback(f"多线程爬取完成！总耗时: {elapsed_time:.2f}秒，最终保存: {self.stats['total_saved']} 条")
        
        return all_results
    
    def get_multithread_stats(self) -> Dict:
        """获取多线程爬取统计信息"""
        with self.stats_lock:
            stats = self.stats.copy()
            if stats['start_time'] and stats['end_time']:
                stats['elapsed_time'] = (stats['end_time'] - stats['start_time']).total_seconds()
            return stats
    
    def get_error_summary(self) -> List[tuple]:
        """获取错误摘要"""
        errors = []
        while not self.error_queue.empty():
            try:
                task_id, error_msg = self.error_queue.get_nowait()
                errors.append((task_id, error_msg))
            except queue.Empty:
                break
        return errors
    
    def get_proxy_stats(self) -> Dict:
        """获取代理统计信息"""
        # 代理统计信息现在由共享代理系统提供
        return {} 