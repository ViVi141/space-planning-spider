#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索线程模块
处理后台搜索和爬取任务，避免界面卡死
"""

from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime
from space_planning.core import database as db
from space_planning.core.logger_config import get_logger

logger = get_logger(__name__)


class SearchThread(QThread):
    """搜索线程，避免界面卡死"""
    progress_signal = pyqtSignal(str)  # 进度信号
    result_signal = pyqtSignal(list)   # 初始数据库结果
    single_policy_signal = pyqtSignal(object)  # 新增单条政策
    finished_signal = pyqtSignal()     # 完成信号
    error_signal = pyqtSignal(str)     # 错误信号
    data_count_signal = pyqtSignal(int)  # 数据量信号
    
    def __init__(self, level, keywords, need_crawl=True, start_date=None, end_date=None, 
                 enable_anti_crawler=True, speed_mode="正常速度", spider=None, 
                 main_window=None, use_multithread=False, thread_count=4):
        super().__init__()
        self.level = level
        self.keywords = keywords
        self.need_crawl = need_crawl
        self.start_date = start_date
        self.end_date = end_date
        self.enable_anti_crawler = enable_anti_crawler
        self.speed_mode = speed_mode
        self.spider = spider
        self.main_window = main_window
        self.stop_flag = False  # 确保初始化为 False
        self.use_multithread = use_multithread
        self.thread_count = thread_count
        
        logger.info(f"SearchThread 初始化: level={level}, keywords={keywords}, need_crawl={need_crawl}, stop_flag={self.stop_flag}")
    
    def run(self):
        try:
            # 第一步：查询数据库现有数据
            self.progress_signal.emit("正在查询数据库...")
            db_results = db.search_policies(self.level, self.keywords, self.start_date, self.end_date)
            self.result_signal.emit(db_results)
            
            if not self.need_crawl:
                logger.info("不需要爬取新数据，直接返回数据库结果")
                self.finished_signal.emit()
                return
            
            # 第二步：判断是否需要爬取新数据
            # 即使没有关键词，也可以爬取（获取所有政策）
            if not self.keywords:
                logger.info("没有设置关键词，将爬取所有符合条件的政策")
                self.progress_signal.emit("未设置关键词，将爬取所有政策...")
            
            # 第三步：执行爬取
            logger.info(f"准备开始爬取，level={self.level}, keywords={self.keywords}, need_crawl={self.need_crawl}, stop_flag={self.stop_flag}")
            self.progress_signal.emit("正在爬取新数据...")
            
            # 根据use_multithread选择爬虫
            if self.use_multithread and self.main_window:
                # 使用多线程爬虫
                if self.level == "住房和城乡建设部":
                    crawler = self.main_window.national_multithread_spider
                elif self.level == "广东省人民政府":
                    crawler = self.main_window.guangdong_multithread_spider
                elif self.level == "自然资源部":
                    crawler = self.main_window.mnr_multithread_spider
                else:
                    crawler = self.spider
                
                if crawler:
                    # 多线程爬取
                    def stop_callback():
                        return self.stop_flag
                    
                    def callback(msg):
                        if not self.stop_flag:
                            self.progress_signal.emit(msg)
                    
                    def policy_callback(policy):
                        if not self.stop_flag:
                            self.single_policy_signal.emit(policy)
                    
                    results = crawler.crawl_policies(
                        keywords=self.keywords,
                        start_date=self.start_date,
                        end_date=self.end_date,
                        callback=callback,
                        stop_callback=stop_callback,
                        policy_callback=policy_callback,
                        max_workers=self.thread_count
                    )
                else:
                    logger.warning(f"未找到多线程爬虫实例: {self.level}")
                    self.finished_signal.emit()
                    return
            else:
                # 使用单线程爬虫
                # 优先使用传入的spider，如果没有则从main_window获取
                crawler = self.spider
                if not crawler and self.main_window:
                    # 根据level从main_window获取对应的爬虫实例
                    if self.level == "住房和城乡建设部":
                        crawler = self.main_window.national_spider
                    elif self.level == "广东省人民政府":
                        crawler = self.main_window.guangdong_spider
                    elif self.level == "自然资源部":
                        crawler = self.main_window.mnr_spider
                    else:
                        # 默认使用国家级爬虫
                        crawler = self.main_window.national_spider
                
                if crawler:
                    logger.info(f"使用单线程爬虫: {type(crawler).__name__}, level: {self.level}")
                    logger.info(f"爬取参数: keywords={self.keywords}, start_date={self.start_date}, end_date={self.end_date}, stop_flag={self.stop_flag}")
                    
                    def stop_callback():
                        stop = self.stop_flag
                        if stop:
                            logger.debug(f"stop_callback 返回 True (stop_flag={self.stop_flag})")
                        return stop
                    
                    def callback(msg):
                        if not self.stop_flag:
                            logger.debug(f"进度回调: {msg}")
                            self.progress_signal.emit(msg)
                        else:
                            logger.debug(f"已停止，忽略进度回调: {msg}")
                    
                    def policy_callback(policy):
                        if not self.stop_flag:
                            self.single_policy_signal.emit(policy)
                        else:
                            logger.debug("已停止，忽略政策回调")
                    
                    # 检查爬虫是否支持 policy_callback 参数
                    import inspect
                    sig = inspect.signature(crawler.crawl_policies)
                    supports_policy_callback = 'policy_callback' in sig.parameters
                    
                    logger.info(f"爬虫 {type(crawler).__name__} 支持 policy_callback: {supports_policy_callback}")
                    
                    # 构建参数
                    crawl_kwargs = {
                        'keywords': self.keywords,
                        'start_date': self.start_date,
                        'end_date': self.end_date,
                        'callback': callback,
                        'stop_callback': stop_callback,
                        'disable_speed_limit': not self.enable_anti_crawler,
                        'speed_mode': self.speed_mode
                    }
                    
                    # 如果支持 policy_callback，添加它
                    if supports_policy_callback:
                        crawl_kwargs['policy_callback'] = policy_callback
                        logger.info("使用 policy_callback 进行实时返回")
                    else:
                        logger.info("爬虫不支持 policy_callback，将在爬取完成后批量返回结果")
                    
                    # 再次检查 stop_flag，确保没有被意外设置
                    if self.stop_flag:
                        logger.warning(f"警告: 在开始爬取前 stop_flag 已被设置为 True，将立即停止")
                        self.error_signal.emit("爬取已停止（stop_flag=True）")
                        return
                    
                    logger.info(f"开始调用 crawl_policies，参数: keywords={self.keywords}, start_date={self.start_date}, end_date={self.end_date}, stop_flag={self.stop_flag}")
                    try:
                        results = crawler.crawl_policies(**crawl_kwargs)
                        logger.info(f"爬取完成，返回 {len(results) if results else 0} 条结果")
                    except Exception as crawl_error:
                        logger.error(f"爬取过程中出错: {crawl_error}", exc_info=True)
                        raise
                    
                    # 如果爬虫不支持 policy_callback，在爬取完成后批量发送结果
                    if not supports_policy_callback and results:
                        logger.info(f"批量发送 {len(results)} 条政策结果")
                        logger.info(f"结果类型: {type(results)}, 第一条数据类型: {type(results[0]) if results else 'N/A'}")
                        if results and len(results) > 0:
                            first_policy = results[0]
                            logger.info(f"第一条政策示例: type={type(first_policy)}, keys={list(first_policy.keys()) if isinstance(first_policy, dict) else 'N/A'}")
                        
                        sent_count = 0
                        for idx, policy in enumerate(results):
                            if self.stop_flag:
                                logger.info(f"检测到停止信号，已发送 {sent_count} 条，剩余 {len(results) - idx} 条未发送")
                                break
                            try:
                                logger.info(f"正在发送第 {idx+1}/{len(results)} 条政策")
                                self.single_policy_signal.emit(policy)
                                sent_count += 1
                                # 每10条记录一次，避免日志过多
                                if sent_count % 10 == 0:
                                    logger.info(f"已发送 {sent_count}/{len(results)} 条政策")
                            except Exception as emit_error:
                                logger.error(f"发送第 {idx+1} 条政策信号失败: {emit_error}", exc_info=True)
                        
                        logger.info(f"批量发送完成，共发送 {sent_count}/{len(results)} 条政策")
                    elif not supports_policy_callback:
                        logger.warning(f"爬虫返回空结果或None: results={results}, type={type(results)}")
                else:
                    logger.error(f"未找到爬虫实例: level={self.level}, spider={self.spider}, main_window={self.main_window}")
                    self.error_signal.emit(f"未找到爬虫实例，请检查机构选择是否正确")
                    return
            
            self.finished_signal.emit()
            
        except Exception as e:
            logger.error(f"搜索线程执行失败: {e}", exc_info=True)
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"搜索线程详细错误:\n{error_detail}")
            self.error_signal.emit(f"搜索失败: {str(e)}\n\n详情请查看日志文件")
    
    def stop(self):
        """停止搜索"""
        logger.info(f"收到停止信号，设置 stop_flag=True (之前为 {self.stop_flag})")
        self.stop_flag = True

