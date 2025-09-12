from base_tool import BaseTool, ToolMetadata, ToolResult
import requests
from bs4 import BeautifulSoup
import tempfile
import os
from typing import Dict, Any
import re
from urllib.parse import urljoin, urlparse
import time
from datetime import datetime
import sys

class SinglePaperExtractionTool(BaseTool):
    """
    单篇论文提取工具 - 从单个论文URL提取摘要、标题和PDF文件
    
    作用：
    1. 作为最基础的论文提取工具，为其他工具提供核心功能
    2. 从HuggingFace Papers或类似网站提取单篇论文的详细信息
    3. 下载并保存论文PDF到临时目录
    4. 提供标准化的论文数据格式
    """
    
    def __init__(self, log_queue=None):
        """
        初始化单篇论文提取工具
        
        参数:
            log_queue: 日志队列，用于向主进程发送日志信息
        """
        super().__init__(log_queue)
        
        # 网络请求配置：这段代码是创建了一个“假装自己是 Chrome 浏览器”的网络请求对象 self.session，用于模拟真实用户访问网页，便于爬虫、接口调用等。
        self.session = requests.Session() # 创建了一个浏览器对话请求
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 超时和重试配置
        self.request_timeout = 30  # 请求超时时间（秒）
        self.max_retries = 3       # 最大重试次数
        self.retry_delay = 2       # 重试间隔（秒）
        
        # PDF下载配置
        self.temp_pdf_dir = "temp_pdf"
        self.max_pdf_size = 50 * 1024 * 1024   # 最大PDF文件大小（50MB） 1024bit * 1024kb * 50mb
        
        # BeautifulSoup解析器配置
        self.parser = 'html.parser'  # 默认解析器
        
        # 支持的论文网站配置
        self.supported_domains = {
            'huggingface.co': {
                'title_selector': 'h1',
                'abstract_selector': '.pb-8 p',
                'pdf_link_selector': 'a[href$=".pdf"]'
            },
            'arxiv.org': {
                'title_selector': 'h1.title',
                'abstract_selector': 'blockquote.abstract',
                'pdf_link_selector': 'a[href*="/pdf/"]'
            }
        }
        
        # 创建临时PDF目录
        os.makedirs(self.temp_pdf_dir, exist_ok=True)
        
        # 日志记录
        if self.log_queue:
            self.log_queue.put("SinglePaperExtractionTool initialized successfully")
    
    def get_metadata(self) -> ToolMetadata:
        """
        获取工具元数据
        
        作用：
        1. 定义工具的基本信息和参数规范
        2. 让Agent了解如何正确调用这个工具
        3. 支持工具的自动发现和分类
        
        返回:
            ToolMetadata: 包含工具名称、描述、参数定义等信息
        """
        return ToolMetadata(
            name="single_paper_extractor",
            description="从单个论文URL提取摘要、标题和PDF文件，支持HuggingFace Papers和arXiv等主流论文网站",
            parameters={
                "paper_url": {
                    "type": "str",
                    "required": True,
                    "description": "论文页面的完整URL地址，支持HuggingFace Papers、arXiv等网站",
                    "example": "https://huggingface.co/papers/2301.07041"
                },
                "download_pdf": {
                    "type": "bool",
                    "required": False,
                    "default": True,
                    "description": "是否下载PDF文件到本地，默认为True"
                },
                "custom_filename": {
                    "type": "str",
                    "required": False,
                    "description": "自定义PDF文件名（不包含扩展名），如果不提供则使用论文标题"
                }
            },
            return_type="dict",
            return_description={
                "description": "包含论文信息的字典",
                "schema": {
                    "title": "论文标题",
                    "abstract": "论文摘要",
                    "pdf_path": "PDF文件本地路径（如果下载成功）",
                    "pdf_url": "PDF文件的原始URL",
                    "url": "论文页面URL",
                    "extraction_time": "提取时间戳",
                    "success": "提取是否成功",
                    "error_message": "错误信息（如果失败）"
                }
            },
            category="extraction",
            tags=["paper", "pdf", "academic", "research"],
            version="1.0.0"
        )
    
    def _execute_impl(self, **kwargs) -> Dict[str, Any]:
        """
        核心执行逻辑 - 提取单篇论文信息
        
        作用：
        1. 实现论文信息提取的核心业务逻辑
        2. 从网页中解析标题、摘要和PDF链接
        3. 下载PDF文件到临时目录
        4. 返回结构化的论文数据
        
        参数:
            paper_url (str): 论文页面的URL地址
            download_pdf (bool, optional): 是否下载PDF文件，默认为True
            custom_filename (str, optional): 自定义PDF文件名
            
        返回:
            Dict[str, Any]: 包含论文信息的完整字典
        """
        
        # 1. 获取并验证输入参数
        paper_url = kwargs.get('paper_url')
        download_pdf = kwargs.get('download_pdf', True)  # 默认下载PDF
        custom_filename = kwargs.get('custom_filename', None)  # 自定义文件名
        
        # 初始化返回结果字典
        result = {
            "title": None,
            "abstract": None,
            "pdf_path": None,
            "pdf_url": None,
            "url": paper_url,
            "extraction_time": datetime.now().isoformat(),
            "success": False,
            "error_message": None
        }
        
        try:
            # 2. 发送HTTP请求获取网页内容
            if self.log_queue:
                self.log_queue.put(f"开始提取论文信息: {paper_url}")
            
            # 使用配置的session发送请求，包含重试机制
            response = None
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(paper_url, timeout=self.request_timeout) # 会返回一个 requests.Response 对象，它代表了一次完整的 HTTP 响应，里面包含了你从网页上拿到的所有数据和元信息。
                    response.raise_for_status()  # 检查HTTP状态码
                    break  # 请求成功，跳出重试循环
                except requests.RequestException as e:
                    if attempt < self.max_retries - 1:  # 不是最后一次尝试
                        if self.log_queue:
                            self.log_queue.put(f"请求失败，{self.retry_delay}秒后重试 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                        time.sleep(self.retry_delay)  # 等待后重试
                    else:
                        raise  # 最后一次尝试失败，抛出异常
            
            # 3. 使用BeautifulSoup解析HTML内容; soup 是一个结构化 HTML 对象树（Document Object Model），米可以用.find(), .find_all()等方法去访问你需要的元素。
            soup = BeautifulSoup(response.text, self.parser) # response.text 是一个字符串，它包含了从网页上获取的所有原始HTML内容。
            
            # 4. 提取论文标题
            title = self._extract_title_from_soup(soup)
            result["title"] = title
            
            if self.log_queue:
                self.log_queue.put(f"提取到标题: {title}")
            
            # 5. 提取论文摘要
            abstract = self._extract_abstract_from_soup(soup)
            result["abstract"] = abstract
            
            if self.log_queue:
                self.log_queue.put(f"提取到摘要: {abstract[:100]}..." if abstract and len(abstract) > 100 else f"提取到摘要: {abstract}")
            
            # 6. 查找并处理PDF下载链接
            if download_pdf:
                pdf_info = self._find_and_download_pdf(soup, paper_url, custom_filename, title)
                result["pdf_path"] = pdf_info.get("pdf_path")
                result["pdf_url"] = pdf_info.get("pdf_url")
                
                if pdf_info.get("pdf_path"):
                    if self.log_queue:
                        self.log_queue.put(f"PDF下载成功: {pdf_info.get('pdf_path')}")
                else:
                    if self.log_queue:
                        self.log_queue.put("未找到有效的PDF下载链接")
            
            # 7. 标记提取成功
            result["success"] = True
            
            if self.log_queue:
                self.log_queue.put(f"论文信息提取完成: {title}")
            
        except requests.RequestException as e:
            # 网络请求相关错误
            error_msg = f"网络请求失败: {str(e)}"
            result["error_message"] = error_msg
            if self.log_queue:
                self.log_queue.put(f"错误: {error_msg}")
                
        except Exception as e:
            # 其他所有错误
            error_msg = f"提取过程中发生错误: {str(e)}"
            result["error_message"] = error_msg
            if self.log_queue:
                self.log_queue.put(f"错误: {error_msg}")
        
        # 8. 返回完整的结果字典
        return result
    
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证输入参数（此函数还未被调用，这个函数可能会在_execute_impl运行之前或者在开头调用，以此知道输入参数是否合规。）
        
        作用：
        1. 检查paper_url参数是否存在且为字符串类型
        2. 验证URL格式是否正确
        3. 检查URL是否可访问
        4. 确保参数符合工具的要求
        
        实现逻辑：
        1. 检查paper_url是否存在
        2. 验证paper_url是否为字符串
        3. 使用正则表达式或urlparse验证URL格式
        4. 可选：发送HEAD请求检查URL可访问性
        
        返回:
            bool: 参数验证是否通过
        """
        
        # 1. 检查必需参数paper_url是否存在
        if 'paper_url' not in kwargs:
            if self.log_queue:
                self.log_queue.put("错误: 缺少必需参数 'paper_url'")
            return False
        
        paper_url = kwargs.get('paper_url')
        
        # 2. 验证paper_url是否为字符串类型
        if not isinstance(paper_url, str):
            if self.log_queue:
                self.log_queue.put(f"错误: paper_url必须是字符串类型，当前类型: {type(paper_url).__name__}")
            return False
        
        # 3. 检查URL是否为空或只包含空白字符
        if not paper_url.strip():
            if self.log_queue:
                self.log_queue.put("错误: paper_url不能为空")
            return False
        
        # 4. 使用urlparse验证URL格式的基本有效性
        try:
            parsed_url = urlparse(paper_url)
            # 检查URL是否包含scheme（协议）和netloc（域名）
            if not parsed_url.scheme or not parsed_url.netloc:
                if self.log_queue:
                    self.log_queue.put(f"错误: URL格式无效，缺少协议或域名: {paper_url}")
                return False
            
            # 检查协议是否为http或https
            if parsed_url.scheme.lower() not in ['http', 'https']:
                if self.log_queue:
                    self.log_queue.put(f"错误: 不支持的URL协议 '{parsed_url.scheme}'，仅支持http和https")
                return False
                
        except Exception as e:
            # urlparse解析失败
            if self.log_queue:
                self.log_queue.put(f"错误: URL解析失败: {str(e)}")
            return False
        
        # 5. 验证可选参数download_pdf的类型（如果提供）
        download_pdf = kwargs.get('download_pdf')
        if download_pdf is not None and not isinstance(download_pdf, bool):
            if self.log_queue:
                self.log_queue.put(f"错误: download_pdf必须是布尔类型，当前类型: {type(download_pdf).__name__}")
            return False
        
        # 6. 验证可选参数custom_filename的类型（如果提供）
        custom_filename = kwargs.get('custom_filename')
        if custom_filename is not None:
            # 检查是否为字符串类型
            if not isinstance(custom_filename, str):
                if self.log_queue:
                    self.log_queue.put(f"错误: custom_filename必须是字符串类型，当前类型: {type(custom_filename).__name__}")
                return False
            
            # 检查文件名是否包含非法字符（Windows和Linux通用的非法字符）
            illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
            if any(char in custom_filename for char in illegal_chars):
                if self.log_queue:
                    self.log_queue.put(f"错误: custom_filename包含非法字符: {custom_filename}")
                return False
            
            # 检查文件名长度是否合理（避免过长的文件名）
            if len(custom_filename.strip()) == 0:
                if self.log_queue:
                    self.log_queue.put("错误: custom_filename不能为空字符串")
                return False
            
            if len(custom_filename) > 200:
                if self.log_queue:
                    self.log_queue.put(f"错误: custom_filename过长（{len(custom_filename)}字符），最大允许200字符")
                return False
        
        # 7. 可选：检查URL的可访问性（发送HEAD请求）
        # 注意：这个检查比较耗时，在生产环境中可能需要根据需求决定是否启用
        try:
            # 发送HEAD请求检查URL是否可访问，设置较短的超时时间
            head_response = self.session.head(paper_url, timeout=10, allow_redirects=True)
            
            # 检查HTTP状态码是否表示成功或重定向
            if head_response.status_code >= 400:
                if self.log_queue:
                    self.log_queue.put(f"警告: URL返回HTTP状态码 {head_response.status_code}，可能无法访问: {paper_url}")
                # 注意：这里返回True而不是False，因为有些网站可能阻止HEAD请求但允许GET请求
                # 实际的可访问性检查会在_execute_impl中的GET请求时进行
            
        except requests.RequestException as e:
            # 网络请求失败，记录警告但不阻止验证通过
            if self.log_queue:
                self.log_queue.put(f"警告: 无法验证URL可访问性: {str(e)}")
            # 同样返回True，因为网络问题可能是临时的
        
        # 8. 所有验证通过
        if self.log_queue:
            self.log_queue.put(f"参数验证通过: {paper_url}")
        
        return True
    
    def is_available(self) -> bool:
        """
        检查工具是否可用
        
        作用：
        1. 验证必要的Python包是否已安装
        2. 检查网络连接是否正常
        3. 确认临时目录是否可写
        4. 验证工具的运行环境
        
        实现逻辑：
        1. 检查requests包是否可导入
        2. 检查BeautifulSoup包是否可导入
        3. 测试网络连接（可选）
        4. 检查临时目录的读写权限
        
        返回:
            bool: 工具是否可用
        """
        
        # 1. 检查必要的Python包是否可用
        try:
            # 尝试创建一个Session对象来验证requests功能
            test_session = requests.Session()
            if self.log_queue:
                self.log_queue.put("✓ requests包检查通过")
                
        except ImportError as e:
            # requests包未安装或导入失败
            if self.log_queue:
                self.log_queue.put(f"✗ requests包不可用: {str(e)}")
            return False
        except Exception as e:
            # requests包导入成功但创建Session失败
            if self.log_queue:
                self.log_queue.put(f"✗ requests包功能异常: {str(e)}")
            return False
        
        try:
            # 尝试创建一个简单的BeautifulSoup对象来验证功能
            test_soup = BeautifulSoup("<html><body><h1>test</h1></body></html>", 'html.parser')
            # 验证基本解析功能
            if test_soup.find('h1') is None:
                raise Exception("BeautifulSoup解析功能异常")
            if self.log_queue:
                self.log_queue.put("✓ BeautifulSoup包检查通过")
                
        except ImportError as e:
            # BeautifulSoup包未安装或导入失败
            if self.log_queue:
                self.log_queue.put(f"✗ BeautifulSoup包不可用: {str(e)}")
            return False
        except Exception as e:
            # BeautifulSoup包导入成功但功能异常
            if self.log_queue:
                self.log_queue.put(f"✗ BeautifulSoup包功能异常: {str(e)}")
            return False
        
        # 2. 检查临时PDF目录的读写权限
        try:
            # 确保临时目录存在
            os.makedirs(self.temp_pdf_dir, exist_ok=True)
            
            # 创建测试文件来验证写权限
            test_file_path = os.path.join(self.temp_pdf_dir, "test_write_permission.tmp")
            
            # 尝试写入测试文件
            with open(test_file_path, 'w', encoding='utf-8') as test_file:
                test_file.write("test content for write permission")
            
            # 尝试读取测试文件验证读权限
            with open(test_file_path, 'r', encoding='utf-8') as test_file:
                content = test_file.read()
                if content != "test content for write permission":
                    raise Exception("文件读取内容不匹配")
            
            # 清理测试文件
            os.remove(test_file_path)
            
            if self.log_queue:
                self.log_queue.put(f"✓ 临时目录读写权限检查通过: {self.temp_pdf_dir}")
                
        except PermissionError as e:
            # 权限不足，无法创建目录或文件
            if self.log_queue:
                self.log_queue.put(f"✗ 临时目录权限不足: {str(e)}")
            return False
        except OSError as e:
            # 操作系统相关错误（磁盘空间不足、路径无效等）
            if self.log_queue:
                self.log_queue.put(f"✗ 临时目录操作系统错误: {str(e)}")
            return False
        except Exception as e:
            # 其他文件系统相关错误
            if self.log_queue:
                self.log_queue.put(f"✗ 临时目录访问异常: {str(e)}")
            return False
        
        # 3. 检查网络连接可用性（可选，使用轻量级测试）
        try:
            # 使用HEAD请求测试网络连接，选择可靠的测试URL
            test_urls = [
                "https://www.google.com",  # 全球可访问
                "https://httpbin.org/status/200",  # HTTP测试服务
                "https://www.baidu.com"  # 中国大陆可访问
            ]
            
            network_available = False
            for test_url in test_urls:
                try:
                    # 发送HEAD请求，设置短超时时间
                    response = self.session.head(test_url, timeout=5)
                    if response.status_code < 400:
                        network_available = True
                        if self.log_queue:
                            self.log_queue.put(f"✓ 网络连接检查通过: {test_url}")
                        break
                except:
                    # 单个URL失败，继续尝试下一个
                    continue
            
            if not network_available:
                # 所有测试URL都失败，但这不一定意味着工具不可用
                # 因为目标网站可能仍然可访问
                if self.log_queue:
                    self.log_queue.put("⚠ 网络连接测试失败，但不影响工具可用性判断")
            
        except Exception as e:
            # 网络测试异常，记录警告但不影响工具可用性
            if self.log_queue:
                self.log_queue.put(f"⚠ 网络连接测试异常: {str(e)}")
        
        # 4. 检查其他系统依赖
        try:
            # 验证正则表达式模块
            test_pattern = re.compile(r'test')
            if not test_pattern.match('test'):
                raise Exception("正则表达式功能异常")
            
            # 验证URL解析模块
            test_parsed = urlparse('https://example.com/test')
            if not test_parsed.scheme or not test_parsed.netloc:
                raise Exception("URL解析功能异常")
            
            # 验证时间处理模块
            from datetime import datetime
            test_time = datetime.now()
            if not test_time:
                raise Exception("时间处理功能异常")
            
            if self.log_queue:
                self.log_queue.put("✓ 系统依赖模块检查通过")
                
        except ImportError as e:
            # 系统模块导入失败（这种情况很少见）
            if self.log_queue:
                self.log_queue.put(f"✗ 系统模块不可用: {str(e)}")
            return False
        except Exception as e:
            # 系统模块功能异常
            if self.log_queue:
                self.log_queue.put(f"✗ 系统模块功能异常: {str(e)}")
            return False
        
        # 5. 验证工具自身的配置
        try:
            # 检查session对象是否正确初始化
            if not hasattr(self, 'session') or self.session is None:
                raise Exception("网络会话对象未初始化")
            
            # 检查关键配置参数
            if not hasattr(self, 'temp_pdf_dir') or not self.temp_pdf_dir:
                raise Exception("临时目录配置缺失")
            
            if not hasattr(self, 'request_timeout') or self.request_timeout <= 0:
                raise Exception("请求超时配置无效")
            
            if not hasattr(self, 'max_retries') or self.max_retries < 0:
                raise Exception("重试次数配置无效")
            
            if self.log_queue:
                self.log_queue.put("✓ 工具配置检查通过")
                
        except Exception as e:
            # 工具配置异常
            if self.log_queue:
                self.log_queue.put(f"✗ 工具配置异常: {str(e)}")
            return False
        
        # 6. 所有检查通过，工具可用
        if self.log_queue:
            self.log_queue.put("✅ SinglePaperExtractionTool 可用性检查全部通过")
        
        return True
    
    def get_usage_example(self) -> Dict[str, Any]:
        """
        获取工具使用示例
        
        作用：
        1. 为Agent提供具体的使用示例
        2. 展示正确的参数格式和类型
        3. 说明预期的输出格式和字段
        4. 帮助Agent学习如何使用这个工具
        5. 提供不同场景下的参数配置示例
        
        返回:
            Dict[str, Any]: 包含完整使用示例的字典
        """
        return {
            # 基本输入示例
            "input_examples": {
                "basic": {
                    "paper_url": "https://arxiv.org/abs/2301.00001",
                    "description": "最基本的使用方式，只提供论文URL"
                },
                "with_pdf_download": {
                    "paper_url": "https://arxiv.org/abs/2301.00001",
                    "download_pdf": True,
                    "description": "启用PDF下载功能"
                },
                "with_custom_filename": {
                    "paper_url": "https://arxiv.org/abs/2301.00001",
                    "download_pdf": True,
                    "custom_filename": "my_research_paper",
                    "description": "使用自定义文件名保存PDF"
                },
                "minimal_extraction": {
                    "paper_url": "https://arxiv.org/abs/2301.00001",
                    "download_pdf": False,
                    "description": "仅提取标题和摘要，不下载PDF"
                }
            },
            
            # 支持的URL类型示例
            "supported_urls": [
                "https://arxiv.org/abs/2301.00001",
                "https://huggingface.co/papers/9999.99999",
                "https://ieeexplore.ieee.org/document/9999999",
                "https://dl.acm.org/doi/10.1145/3999999.3999999",
                "https://papers.nips.cc/paper/2023/hash/abcd1234"
            ],
            
            # 预期输出格式
             "expected_output": {
                 "success_case": {
                     "title": "Attention Is All You Need",
                     "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
                     "pdf_path": "d:\\temp_pdf\\attention_is_all_you_need.pdf",
                     "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                     "url": "https://arxiv.org/abs/1706.03762",
                     "extraction_time": "2024-01-15T14:30:25.123456",
                     "success": True,
                     "error_message": None
                 },
                 "error_case": {
                     "title": None,
                     "abstract": None,
                     "pdf_path": None,
                     "pdf_url": None,
                     "url": "https://invalid-url.com",
                     "extraction_time": "2024-01-15T14:30:25.123456",
                     "success": False,
                     "error_message": "网络请求失败: HTTPSConnectionPool(host='invalid-url.com', port=443)"
                 }
             },
            
            # 参数说明
            "parameter_details": {
                "paper_url": {
                    "type": "str",
                    "required": True,
                    "description": "论文页面URL，支持主流学术网站",
                    "validation": "必须是有效的HTTP/HTTPS URL"
                },
                "download_pdf": {
                    "type": "bool",
                    "required": False,
                    "default": True,
                    "description": "是否下载PDF文件到本地"
                },
                "custom_filename": {
                    "type": "str",
                    "required": False,
                    "default": "auto-generated from title",
                    "description": "自定义PDF文件名（不含扩展名）",
                    "validation": "长度1-100字符，不含特殊字符"
                }
            },
            
            # 使用场景
            "use_cases": [
                "从arXiv提取最新研究论文信息",
                "从Hugging Face上获取daily papers"
                "批量收集特定领域的论文摘要",
                "为文献综述准备论文资料",
                "构建论文数据库的基础数据",
                "学术研究中的论文预处理"
            ],
            
            # 注意事项
            "notes": [
                "确保网络连接正常，某些学术网站可能需要访问权限",
                "PDF下载可能较慢，取决于文件大小和网络速度",
                "部分网站可能有反爬虫机制，建议适当延时",
                "自定义文件名会自动过滤不安全字符"
            ]
        }
    
    def cleanup(self):
        """
        清理工具资源
        
        作用：
        1. 清理临时下载的PDF文件
        2. 释放网络连接资源
        3. 清理缓存数据
        4. 确保工具使用后不留下垃圾文件
        
        实现逻辑：
        1. 遍历临时PDF目录，删除所有PDF文件
        2. 清理空的临时目录
        3. 关闭网络Session连接
        4. 重置工具状态
        """
        
        # 1. 清理临时PDF目录中的所有文件
        try:
            if os.path.exists(self.temp_pdf_dir):
                # 遍历临时目录中的所有文件
                for filename in os.listdir(self.temp_pdf_dir):
                    file_path = os.path.join(self.temp_pdf_dir, filename)
                    
                    # 只删除文件，不删除子目录
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                            if self.log_queue:
                                self.log_queue.put(f"🧹 已删除临时文件: {file_path}")
                        except Exception as e:
                            if self.log_queue:
                                self.log_queue.put(f"⚠️ 删除文件失败 {file_path}: {str(e)}")
                
                # 尝试删除空的临时目录（如果目录为空）
                try:
                    if not os.listdir(self.temp_pdf_dir):  # 检查目录是否为空
                        os.rmdir(self.temp_pdf_dir)
                        if self.log_queue:
                            self.log_queue.put(f"🧹 已删除空的临时目录: {self.temp_pdf_dir}")
                except OSError:
                    # 目录不为空或删除失败，这是正常情况
                    pass
                    
        except Exception as e:
            if self.log_queue:
                self.log_queue.put(f"⚠️ 清理临时目录时发生错误: {str(e)}")
        
        # 2. 关闭网络Session连接
        try:
            if hasattr(self, 'session') and self.session:
                self.session.close()
                if self.log_queue:
                    self.log_queue.put("🔌 已关闭网络Session连接")
        except Exception as e:
            if self.log_queue:
                self.log_queue.put(f"⚠️ 关闭网络连接时发生错误: {str(e)}")
        
        # 3. 记录清理完成
        if self.log_queue:
            self.log_queue.put("✅ SinglePaperExtractionTool 资源清理完成")
    
    def delete_specific_pdf(self, pdf_path):
        """
        删除指定的PDF文件
        
        作用：
        1. 提供单个文件删除功能
        2. 支持精确的文件清理
        3. 复用Extraction.py中的删除逻辑
        
        参数:
            pdf_path (str): 要删除的PDF文件路径
            
        返回:
            bool: 删除是否成功
        """
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                if self.log_queue:
                    self.log_queue.put(f"🧹 已删除PDF文件: {pdf_path}")
                return True
            except Exception as e:
                if self.log_queue:
                    self.log_queue.put(f"⚠️ 删除PDF文件失败 {pdf_path}: {str(e)}")
                return False
        else:
            if self.log_queue:
                self.log_queue.put(f"⚠️ PDF文件不存在或路径无效: {pdf_path}")
            return False
    
    def _extract_title_from_soup(self, soup):
        """
        从BeautifulSoup对象中提取论文标题
        
        作用：
        1. 提供标题提取的专门方法
        2. 处理不同网站的标题格式
        3. 提高代码的可维护性
        
        参数:
            soup: BeautifulSoup解析对象
            
        返回:
            str: 提取到的论文标题，如果未找到则返回默认值
        """
        title = None
        
        # 1. 尝试从h1标签提取标题（最常见的标题标签）
        h1_tag = soup.find("h1")
        if h1_tag:
            title = h1_tag.get_text(strip=True)  # 获取文本并去除首尾空白
            if self.log_queue:
                self.log_queue.put(f"从h1标签提取到标题: {title}")
        
        # 2. 如果h1没有找到，尝试从h3标签提取（HuggingFace Papers常用格式）
        if not title:
            h3_tag = soup.find("h3")
            if h3_tag:
                title = h3_tag.get_text(strip=True)
                if self.log_queue:
                    self.log_queue.put(f"从h3标签提取到标题: {title}")
        
        # 3. 尝试从特定class的元素提取（针对特殊网站格式）
        if not title:
            # 查找可能包含标题的其他元素
            title_selectors = [
                "h2.title",  # arXiv格式
                ".paper-title",  # 通用论文标题class
                "[data-testid='paper-title']",  # 测试ID格式
                "h1.title",  # 带class的h1标题
            ]
            
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    if self.log_queue:
                        self.log_queue.put(f"从选择器 {selector} 提取到标题: {title}")
                    break
        
        # 4. 清理和验证标题文本
        if title:
            # 移除多余的空白字符和换行符
            title = re.sub(r'\s+', ' ', title).strip()
            # 限制标题长度，避免过长的标题
            if len(title) > 200:
                title = title[:200] + "..."
        else:
            # 如果所有方法都失败，返回默认标题
            title = "未找到论文标题"
            if self.log_queue:
                self.log_queue.put("警告: 未能提取到论文标题")
        
        return title
    
    def _extract_abstract_from_soup(self, soup):
        """
        从BeautifulSoup对象中提取论文摘要
        
        作用：
        1. 提供摘要提取的专门方法
        2. 处理不同的摘要格式和布局
        3. 清理和格式化摘要文本
        
        参数:
            soup: BeautifulSoup解析对象
            
        返回:
            str: 提取到的论文摘要，如果未找到则返回默认值
        """
        abstract_text = None
        
        # 1. 方法一：查找"Abstract"标题的h2标签（HuggingFace Papers格式）
        abstract_header = soup.find("h2", string="Abstract")
        if abstract_header:
            if self.log_queue:
                self.log_queue.put("找到Abstract标题，开始提取摘要内容")
            
            # 查找Abstract标题后的兄弟元素（包含摘要内容的div）
            abstract_container = abstract_header.find_next_sibling("div")
            if abstract_container:
                # 只提取特定class的p标签内容（HuggingFace格式）
                p_tags = abstract_container.find_all("p", class_="text-gray-600")
                if p_tags:
                    # 合并所有p标签的文本内容
                    abstract_text = "\n".join(p.get_text(strip=True) for p in p_tags)
                    if self.log_queue:
                        self.log_queue.put(f"从text-gray-600类提取到摘要: {len(abstract_text)}字符")
                
                # 如果特定class没找到，尝试提取所有p标签
                if not abstract_text:
                    p_tags = abstract_container.find_all("p")
                    if p_tags:
                        abstract_text = "\n".join(p.get_text(strip=True) for p in p_tags)
                        if self.log_queue:
                            self.log_queue.put(f"从通用p标签提取到摘要: {len(abstract_text)}字符")
        
        # 2. 方法二：查找arXiv格式的摘要（blockquote.abstract）
        if not abstract_text:
            abstract_block = soup.find("blockquote", class_="abstract")
            if abstract_block:
                abstract_text = abstract_block.get_text(strip=True)
                # 移除"Abstract:"前缀（如果存在）
                if abstract_text.startswith("Abstract:"):
                    abstract_text = abstract_text[9:].strip()
                if self.log_queue:
                    self.log_queue.put(f"从arXiv格式提取到摘要: {len(abstract_text)}字符")
        
        # 3. 方法三：查找其他可能的摘要格式
        if not abstract_text:
            # 尝试多种可能的摘要选择器
            abstract_selectors = [
                ".abstract",  # 通用摘要class
                "#abstract",  # 摘要ID
                "[data-testid='abstract']",  # 测试ID格式
                ".paper-abstract",  # 论文摘要class
                ".summary",  # 摘要/总结class
            ]
            
            for selector in abstract_selectors:
                element = soup.select_one(selector)
                if element:
                    abstract_text = element.get_text(strip=True)
                    if self.log_queue:
                        self.log_queue.put(f"从选择器 {selector} 提取到摘要: {len(abstract_text)}字符")
                    break
        
        # 4. 方法四：通过文本内容查找Abstract关键词
        if not abstract_text:
            # 查找包含"Abstract"文本的元素
            abstract_elements = soup.find_all(text=re.compile(r"Abstract", re.IGNORECASE))
            for element in abstract_elements:
                parent = element.parent
                if parent:
                    # 查找父元素的下一个兄弟元素或子元素
                    next_element = parent.find_next_sibling()
                    if next_element:
                        potential_abstract = next_element.get_text(strip=True)
                        # 验证是否像摘要（长度合理且不是导航文本）
                        if 50 < len(potential_abstract) < 2000:
                            abstract_text = potential_abstract
                            if self.log_queue:
                                self.log_queue.put(f"通过Abstract关键词查找到摘要: {len(abstract_text)}字符")
                            break
        
        # 5. 清理和验证摘要文本
        if abstract_text:
            # 移除多余的空白字符和换行符
            abstract_text = re.sub(r'\s+', ' ', abstract_text).strip()
            
            # 验证摘要长度的合理性
            if len(abstract_text) < 20:
                abstract_text = "摘要内容过短，可能提取不完整"
                if self.log_queue:
                    self.log_queue.put("警告: 提取的摘要内容过短")
            elif len(abstract_text) > 3000:
                # 截断过长的摘要
                abstract_text = abstract_text[:3000] + "..."
                if self.log_queue:
                    self.log_queue.put("警告: 摘要内容过长，已截断")
        else:
            # 如果所有方法都失败，返回默认值
            abstract_text = "未找到论文摘要"
            if self.log_queue:
                self.log_queue.put("警告: 未能提取到论文摘要")
        
        return abstract_text
    
    def _find_and_download_pdf(self, soup, base_url, custom_filename=None, title=None):
        """
        查找并下载PDF文件
        
        作用：
        1. 从网页中查找PDF下载链接
        2. 验证PDF链接的有效性
        3. 下载PDF到临时目录
        4. 返回本地PDF文件路径和原始URL
        
        参数:
            soup: BeautifulSoup解析对象
            base_url: 基础URL，用于构建完整的PDF链接
            custom_filename: 自定义文件名（可选）
            title: 论文标题，用于生成文件名（可选）
            
        返回:
            dict: 包含pdf_path和pdf_url的字典
        """
        
        result = {
            "pdf_path": None,
            "pdf_url": None
        }
        
        pdf_link = None
        
        # 1. 方法一：查找HuggingFace Papers格式的PDF链接
        # 查找特定class的a标签，包含PDF下载链接
        pdf_buttons = soup.find_all("a", class_="btn inline-flex h-9 items-center", href=True)
        for a in pdf_buttons:
            href = a["href"]
            # 检查链接是否指向PDF文件
            if href.lower().endswith(".pdf") or "/pdf/" in href.lower():
                pdf_link = href
                if self.log_queue:
                    self.log_queue.put(f"从HuggingFace格式找到PDF链接: {href}")
                break
        
        # 2. 方法二：查找通用的PDF链接
        if not pdf_link:
            # 查找所有包含PDF的链接
            all_links = soup.find_all("a", href=True)
            for link in all_links:
                href = link["href"]
                # 检查多种PDF链接格式
                if (href.lower().endswith(".pdf") or 
                    "/pdf/" in href.lower() or 
                    "download" in href.lower() and "pdf" in href.lower()):
                    pdf_link = href
                    if self.log_queue:
                        self.log_queue.put(f"从通用格式找到PDF链接: {href}")
                    break
        
        # 3. 方法三：查找arXiv格式的PDF链接
        if not pdf_link:
            # arXiv通常有特定的PDF链接格式
            arxiv_pdf_links = soup.find_all("a", href=re.compile(r"/pdf/\d+\.\d+"))
            if arxiv_pdf_links:
                pdf_link = arxiv_pdf_links[0]["href"]
                if self.log_queue:
                    self.log_queue.put(f"从arXiv格式找到PDF链接: {pdf_link}")
        
        # 4. 如果找到PDF链接，进行下载处理
        if pdf_link:
            try:
                # 构建完整的PDF URL
                if pdf_link.startswith("http"):
                    full_pdf_url = pdf_link  # 已经是完整URL
                else:
                    # 相对URL，需要与base_url合并
                    full_pdf_url = urljoin(base_url, pdf_link)
                
                result["pdf_url"] = full_pdf_url
                
                if self.log_queue:
                    self.log_queue.put(f"开始验证PDF链接: {full_pdf_url}")
                
                # 5. 发送HEAD请求验证PDF文件
                head_response = self.session.head(full_pdf_url, allow_redirects=True, timeout=self.request_timeout)
                
                # 检查响应状态和内容类型
                if head_response.status_code == 200:
                    content_type = head_response.headers.get("Content-Type", "").lower()
                    content_length = head_response.headers.get("Content-Length")
                    
                    # 验证是否为PDF文件
                    if "pdf" in content_type or pdf_link.lower().endswith(".pdf"):
                        # 检查文件大小限制
                        if content_length:
                            file_size = int(content_length)
                            if file_size > self.max_pdf_size:
                                if self.log_queue:
                                    self.log_queue.put(f"PDF文件过大 ({file_size} bytes)，跳过下载")
                                return result
                        
                        if self.log_queue:
                            self.log_queue.put(f"PDF验证成功，开始下载 (大小: {content_length or '未知'} bytes)")
                        
                        # 6. 下载PDF文件
                        pdf_response = self.session.get(full_pdf_url, stream=True, timeout=self.request_timeout)
                        pdf_response.raise_for_status()
                        
                        # 7. 生成文件名
                        if custom_filename:
                            filename = f"{custom_filename}.pdf"
                        elif title:
                            # 使用论文标题生成文件名，清理非法字符
                            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]  # 限制长度并替换非法字符
                            filename = f"{safe_title}.pdf"
                        else:
                            # 使用时间戳生成默认文件名
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"paper_{timestamp}.pdf"
                        
                        # 8. 创建临时文件并写入PDF内容
                        temp_file = tempfile.NamedTemporaryFile(
                            delete=False, 
                            suffix=".pdf", 
                            dir=self.temp_pdf_dir,
                            prefix=filename.replace(".pdf", "_")
                        )
                        
                        try:
                            # 分块写入文件，避免内存占用过大
                            total_size = 0
                            with open(temp_file.name, "wb") as f:
                                for chunk in pdf_response.iter_content(chunk_size=8192):
                                    if chunk:  # 过滤掉keep-alive的空块
                                        f.write(chunk)
                                        total_size += len(chunk)
                                        
                                        # 检查文件大小限制
                                        if total_size > self.max_pdf_size:
                                            if self.log_queue:
                                                self.log_queue.put(f"下载过程中文件超过大小限制，停止下载")
                                            os.remove(temp_file.name)  # 删除不完整的文件
                                            return result
                            
                            result["pdf_path"] = temp_file.name
                            
                            if self.log_queue:
                                self.log_queue.put(f"PDF下载完成: {temp_file.name} (大小: {total_size} bytes)")
                                
                        except Exception as e:
                            # 下载过程中出错，清理临时文件
                            if os.path.exists(temp_file.name):
                                os.remove(temp_file.name)
                            if self.log_queue:
                                self.log_queue.put(f"PDF下载失败: {str(e)}")
                            
                    else:
                        if self.log_queue:
                            self.log_queue.put(f"链接不是有效的PDF文件 (Content-Type: {content_type})")
                else:
                    if self.log_queue:
                        self.log_queue.put(f"PDF链接验证失败 (状态码: {head_response.status_code})")
                        
            except requests.RequestException as e:
                if self.log_queue:
                    self.log_queue.put(f"PDF下载请求失败: {str(e)}")
            except Exception as e:
                if self.log_queue:
                    self.log_queue.put(f"PDF处理过程中发生错误: {str(e)}")
        else:
            if self.log_queue:
                self.log_queue.put("未找到有效的PDF下载链接")
        
        return result
        
class DailyPapersCollectorTool(BaseTool):
    """
    每日论文收集工具 - 批量收集每日论文列表
    
    作用：
    1. 从HuggingFace Papers等网站批量收集每日论文
    2. 内部使用SinglePaperExtractionTool处理单篇论文提取
    3. 支持限制收集数量和自定义数据源
    4. 提供批量处理的进度反馈和错误处理
    """
    
    def __init__(self, log_queue=None):
        """
        初始化每日论文收集工具
        
        参数:
            log_queue: 日志队列，用于向主进程发送日志信息
        """
        super().__init__(log_queue)
        
        # 单篇论文提取工具实例
        self.single_extractor = SinglePaperExtractionTool(log_queue)
        
        # 网络请求配置
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.request_timeout = 30  # 请求超时时间（秒）
        self.max_retries = 3       # 最大重试次数
        self.retry_delay = 2       # 重试间隔（秒）
        
        # 批量处理配置
        self.default_max_count = 10    # 默认最大收集数量，与get_metadata保持一致
        self.batch_delay = 1           # 批量请求间隔（秒）
        self.concurrent_limit = 5      # 并发处理限制
        self.min_delay_between_requests = 0.5  # 最小请求间隔
        
        # 数据源配置
        self.default_source_url = "https://huggingface.co/papers"
        self.supported_sources = {
            'huggingface': {
                'base_url': 'https://huggingface.co/papers',
                'paper_list_selector': 'article h3 a',
                'title_selector': 'h3 a',
                'pagination_selector': '.pagination a',
                'paper_url_prefix': 'https://huggingface.co'
            },
            'arxiv': {
                'base_url': 'https://arxiv.org/list/cs.AI/recent',
                'paper_list_selector': 'dt a[title="Abstract"]',
                'title_selector': 'div.list-title',
                'pagination_selector': 'a[accesskey]',
                'paper_url_prefix': 'https://arxiv.org'
            }
        }
        
        # 批量处理状态跟踪
        self.failed_papers = []     # 失败的论文列表
        self.success_count = 0      # 成功处理数量
        self.total_count = 0        # 总处理数量
        self.processed_urls = set() # 已处理的URL集合（去重）
        
        # BeautifulSoup解析器配置
        self.parser = 'html.parser'
        
        # 日志记录
        if self.log_queue:
            self.log_queue.put("DailyPapersCollectorTool initialized successfully")
    
    def get_metadata(self) -> ToolMetadata:
        """
        获取工具元数据
        
        作用：
        1. 定义批量收集工具的参数和功能
        2. 让Agent了解如何配置批量收集任务
        3. 支持灵活的数据源和数量控制
        
        返回:
            ToolMetadata: 包含工具名称、描述、参数定义等信息
        """
        return ToolMetadata(
            name="daily_papers_collector",
            description="批量收集每日论文列表，从指定数据源（如HuggingFace Papers、arXiv等）获取多篇论文的摘要、标题和PDF文件",
            parameters={
                "source_url": {
                    "type": "str",
                    "required": False,
                    "description": "论文数据源URL，如果不提供则使用默认的HuggingFace Papers每日列表",
                    "example": "https://huggingface.co/papers"
                },
                "max_papers": {
                    "type": "int",
                    "required": False,
                    "default": 10,
                    "description": "要收集的最大论文数量，默认为10篇，范围1-50",
                    "minimum": 1,
                    "maximum": 50
                },
                "download_pdfs": {
                    "type": "bool",
                    "required": False,
                    "default": True,
                    "description": "是否下载所有论文的PDF文件到本地，默认为True"
                },
                "filter_keywords": {
                    "type": "list",
                    "required": False,
                    "description": "关键词过滤列表，只收集标题或摘要包含这些关键词的论文",
                    "example": ["machine learning", "AI", "neural network"]
                }
            },
            return_type="dict",
            return_description={
                "description": "包含批量论文收集结果的字典",
                "schema": {
                    "papers": "论文信息列表，每个元素包含title、abstract、pdf_path、pdf_url、url等字段",
                    "total_found": "找到的论文总数",
                    "total_collected": "成功收集的论文数量",
                    "total_downloaded": "成功下载PDF的论文数量",
                    "failed_papers": "收集失败的论文URL列表",
                    "source_url": "使用的数据源URL",
                    "collection_time": "收集完成时间戳",
                    "success": "整体收集是否成功",
                    "error_message": "错误信息（如果失败）"
                }
            },
            category="extraction",
            tags=["paper", "pdf", "academic", "research", "batch", "daily"],
            version="1.0.0"
        )
    
    def _execute_impl(self, **kwargs) -> list[Dict[str, Any]]:
        """
        核心执行逻辑 - 批量收集论文信息
        
        作用：
        1. 实现批量论文收集的核心业务逻辑
        2. 解析论文列表页面，获取所有论文链接
        3. 使用SinglePaperExtractionTool处理每篇论文
        4. 提供进度反馈和错误处理
        
        参数:
            source_url (str, optional): 论文列表页面URL
            max_count (int, optional): 最大收集数量
            include_pdf (bool, optional): 是否下载PDF文件
            
        返回:
            List[Dict[str, Any]]: 论文信息列表，每个元素包含：
            {
                "title": "论文标题",
                "abstract": "论文摘要",
                "pdf_path": "PDF文件路径（如果下载）",
                "url": "论文页面URL",
                "extraction_status": "success/failed",
                "error_message": "错误信息（如果失败）"
            }
        
        实现逻辑：
        1. 获取并验证输入参数
        2. 发送HTTP请求获取论文列表页面
        3. 解析HTML，提取所有论文链接
        4. 根据max_count限制论文数量
        5. 循环调用SinglePaperExtractionTool处理每篇论文
        6. 记录处理进度和错误信息
        7. 返回完整的论文信息列表
        """
        # 1. 获取并验证输入参数
        source_url = kwargs.get('source_url', self.default_source_url)
        max_papers = kwargs.get('max_papers', self.default_max_count)  # 与get_metadata中的默认值保持一致
        download_pdfs = kwargs.get('download_pdfs', True)
        filter_keywords = kwargs.get('filter_keywords', [])
        
        # 初始化返回结果
        result = {
            "papers": [],
            "total_found": 0,
            "total_collected": 0,
            "total_downloaded": 0,
            "failed_papers": [],
            "source_url": source_url,
            "collection_time": datetime.now().isoformat(),
            "success": False,
            "error_message": None
        }
        
        try:
            if self.log_queue:
                self.log_queue.put(f"开始批量收集论文，数据源: {source_url}，最大数量: {max_papers}")
            
            # 2. 发送HTTP请求获取论文列表页面
            response = None
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(source_url, timeout=self.request_timeout)
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    if attempt < self.max_retries - 1:
                        if self.log_queue:
                            self.log_queue.put(f"请求失败，{self.retry_delay}秒后重试 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                        time.sleep(self.retry_delay)
                    else:
                        raise
            
            # 3. 解析HTML，提取所有论文链接
            soup = BeautifulSoup(response.text, self.parser)
            paper_links = self._parse_paper_links_from_soup(soup, source_url)
            
            result["total_found"] = len(paper_links)
            
            if self.log_queue:
                self.log_queue.put(f"找到 {len(paper_links)} 篇论文")
            
            # 4. 应用关键词过滤
            if filter_keywords:
                filtered_links = []
                for paper in paper_links:
                    title_lower = paper["title"].lower()
                    if any(keyword.lower() in title_lower for keyword in filter_keywords):
                        filtered_links.append(paper)
                paper_links = filtered_links
                
                if self.log_queue:
                    self.log_queue.put(f"关键词过滤后剩余 {len(paper_links)} 篇论文")
            
            # 5. 根据max_papers限制处理数量
            paper_links = paper_links[:max_papers]
            
            # 6. 循环处理每篇论文
            for i, paper_info in enumerate(paper_links, 1):
                try:
                    if self.log_queue:
                        self.log_queue.put(f"正在处理第 {i}/{len(paper_links)} 篇论文: {paper_info['title']}")
                    
                    # 调用SinglePaperExtractionTool处理单篇论文
                    paper_result = self.single_extractor.execute(
                        paper_url=paper_info["url"],
                        download_pdf=download_pdfs
                    )
                    
                    if paper_result.success:
                        result["papers"].append(paper_result.data)
                        result["total_collected"] += 1
                        
                        # 统计PDF下载成功数量
                        if paper_result.data.get("pdf_path"):
                            result["total_downloaded"] += 1
                        
                        if self.log_queue:
                            self.log_queue.put(f"✓ 成功处理: {paper_info['title']}")
                    else:
                        # 处理失败的论文
                        result["failed_papers"].append({
                            "url": paper_info["url"],
                            "title": paper_info["title"],
                            "error": paper_result.error_message
                        })
                        
                        if self.log_queue:
                            self.log_queue.put(f"✗ 处理失败: {paper_info['title']} - {paper_result.error_message}")
                
                except Exception as e:
                    # 单篇论文处理异常
                    error_msg = f"处理论文时发生异常: {str(e)}"
                    result["failed_papers"].append({
                        "url": paper_info["url"],
                        "title": paper_info["title"],
                        "error": error_msg
                    })
                    
                    if self.log_queue:
                        self.log_queue.put(f"✗ 异常: {paper_info['title']} - {error_msg}")
                
                # 添加延时避免请求过快
                if i < len(paper_links):  # 不是最后一篇
                    time.sleep(self.request_interval)
            
            # 7. 设置成功状态
            result["success"] = True
            
            if self.log_queue:
                self.log_queue.put(f"批量收集完成: 成功 {result['total_collected']} 篇，失败 {len(result['failed_papers'])} 篇")
        
        except requests.RequestException as e:
            # 网络请求相关错误
            error_msg = f"网络请求失败: {str(e)}"
            result["error_message"] = error_msg
            if self.log_queue:
                self.log_queue.put(f"错误: {error_msg}")
        
        except Exception as e:
            # 其他所有错误
            error_msg = f"批量收集过程中发生错误: {str(e)}"
            result["error_message"] = error_msg
            if self.log_queue:
                self.log_queue.put(f"错误: {error_msg}")
        
        return result
    
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证输入参数
        
        作用：
        1. 验证source_url格式（如果提供）
        2. 检查max_papers是否为正整数且在有效范围内
        3. 验证download_pdfs是否为布尔值
        4. 检查filter_keywords是否为列表格式
        5. 确保参数组合的合理性
        
        实现逻辑：
        1. 检查source_url格式（可选参数，必须是有效URL）
        2. 验证max_papers范围（可选参数，必须在1-50之间）
        3. 验证download_pdfs类型（可选参数，必须是布尔值）
        4. 检查filter_keywords格式（可选参数，必须是字符串列表）
        5. 记录验证过程和结果
        
        参数:
            **kwargs: 待验证的参数字典
                - source_url (str, optional): 论文数据源URL
                - max_papers (int, optional): 最大收集论文数量，范围1-50
                - download_pdfs (bool, optional): 是否下载PDF文件
                - filter_keywords (list, optional): 关键词过滤列表
        
        返回:
            bool: 参数验证是否通过
        """
        try:
            # 1. 验证source_url参数（可选）
            if 'source_url' in kwargs:
                source_url = kwargs['source_url']
                
                # 检查是否为字符串类型
                if not isinstance(source_url, str):
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: source_url必须是字符串类型，当前类型: {type(source_url)}")
                    return False
                
                # 检查URL格式是否有效
                parsed_url = urlparse(source_url)
                if not parsed_url.scheme or not parsed_url.netloc:
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: source_url格式无效: {source_url}")
                    return False
                
                # 检查协议是否为http或https
                if parsed_url.scheme not in ['http', 'https']:
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: source_url必须使用http或https协议: {source_url}")
                    return False
                
                if self.log_queue:
                    self.log_queue.put(f"✓ source_url验证通过: {source_url}")
            
            # 2. 验证max_papers参数（可选）
            if 'max_papers' in kwargs:
                max_papers = kwargs['max_papers']
                
                # 检查是否为整数类型
                if not isinstance(max_papers, int):
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: max_papers必须是整数类型，当前类型: {type(max_papers)}")
                    return False
                
                # 检查数值范围（根据get_metadata中的定义：1-50）
                if max_papers < 1 or max_papers > 50:
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: max_papers必须在1-50范围内，当前值: {max_papers}")
                    return False
                
                if self.log_queue:
                    self.log_queue.put(f"✓ max_papers验证通过: {max_papers}")
            
            # 3. 验证download_pdfs参数（可选）
            if 'download_pdfs' in kwargs:
                download_pdfs = kwargs['download_pdfs']
                
                # 检查是否为布尔类型
                if not isinstance(download_pdfs, bool):
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: download_pdfs必须是布尔类型，当前类型: {type(download_pdfs)}")
                    return False
                
                if self.log_queue:
                    self.log_queue.put(f"✓ download_pdfs验证通过: {download_pdfs}")
            
            # 4. 验证filter_keywords参数（可选）
            if 'filter_keywords' in kwargs:
                filter_keywords = kwargs['filter_keywords']
                
                # 检查是否为列表类型
                if not isinstance(filter_keywords, list):
                    if self.log_queue:
                        self.log_queue.put(f"参数验证失败: filter_keywords必须是列表类型，当前类型: {type(filter_keywords)}")
                    return False
                
                # 检查列表中的每个元素是否为字符串
                for i, keyword in enumerate(filter_keywords):
                    if not isinstance(keyword, str):
                        if self.log_queue:
                            self.log_queue.put(f"参数验证失败: filter_keywords[{i}]必须是字符串，当前类型: {type(keyword)}")
                        return False
                    
                    # 检查关键词是否为空字符串
                    if not keyword.strip():
                        if self.log_queue:
                            self.log_queue.put(f"参数验证失败: filter_keywords[{i}]不能为空字符串")
                        return False
                
                if self.log_queue:
                    self.log_queue.put(f"✓ filter_keywords验证通过: {len(filter_keywords)}个关键词")
            
            # 5. 检查参数组合的合理性
            # 如果设置了filter_keywords但max_papers很小，给出警告
            if 'filter_keywords' in kwargs and 'max_papers' in kwargs:
                if len(kwargs['filter_keywords']) > 0 and kwargs['max_papers'] < 5:
                    if self.log_queue:
                        self.log_queue.put(f"警告: 设置了关键词过滤但max_papers较小({kwargs['max_papers']})，可能导致收集结果很少")
            
            # 6. 记录验证成功
            if self.log_queue:
                validated_params = [key for key in ['source_url', 'max_papers', 'download_pdfs', 'filter_keywords'] if key in kwargs]
                self.log_queue.put(f"✓ 参数验证全部通过，已验证参数: {validated_params}")
            
            return True
            
        except Exception as e:
            # 捕获验证过程中的任何异常
            error_msg = f"参数验证过程中发生异常: {str(e)}"
            if self.log_queue:
                self.log_queue.put(f"参数验证失败: {error_msg}")
            return False
    
    def is_available(self) -> bool:
        """
        检查工具是否可用
        
        作用：
        1. 检查SinglePaperExtractionTool是否可用（包含所有基础依赖检查）
        2. 验证工具自身配置的完整性
        3. 测试批量处理相关的功能模块
        
        实现逻辑：
        1. 调用self.single_extractor.is_available()检查基础功能和依赖
        2. 检查工具配置参数的有效性
        3. 测试批量处理相关的功能模块
        
        返回:
            bool: 工具是否可用
        """
        try:
            # 1. 检查SinglePaperExtractionTool的可用性
            # SinglePaperExtractionTool.is_available()已经包含了所有基础依赖检查：
            # - requests和BeautifulSoup包的功能验证
            # - 临时PDF目录的读写权限检查
            # - 网络连接可用性测试（可选）
            # - 系统依赖检查
            # 因此我们只需要调用它，无需重复检查
            if not hasattr(self, 'single_extractor') or self.single_extractor is None:
                if self.log_queue:
                    self.log_queue.put("✗ SinglePaperExtractionTool未初始化")
                return False
            
            # 调用单篇提取工具的可用性检查（包含所有基础依赖验证）
            if not self.single_extractor.is_available():
                if self.log_queue:
                    self.log_queue.put("✗ SinglePaperExtractionTool不可用")
                return False
            
            if self.log_queue:
                self.log_queue.put("✓ SinglePaperExtractionTool可用性检查通过（包含所有基础依赖）")
            
            # 2. 验证工具自身配置的完整性
            try:
                # 检查默认配置参数
                if not hasattr(self, 'default_max_count') or self.default_max_count <= 0:
                    raise Exception("default_max_count配置无效")
                
                if not hasattr(self, 'batch_delay') or self.batch_delay < 0:
                    raise Exception("batch_delay配置无效")
                
                if not hasattr(self, 'max_retries') or self.max_retries < 0:
                    raise Exception("max_retries配置无效")
                
                # 检查日志队列配置（可选）
                if hasattr(self, 'log_queue') and self.log_queue is not None:
                    # 测试日志队列是否可用
                    try:
                        self.log_queue.put("测试日志队列功能")
                    except Exception as e:
                        if self.log_queue:
                            self.log_queue.put(f"⚠ 日志队列功能异常: {str(e)}")
                
                if self.log_queue:
                    self.log_queue.put("✓ 工具配置检查通过")
                    
            except Exception as e:
                if self.log_queue:
                    self.log_queue.put(f"✗ 工具配置异常: {str(e)}")
                return False
            
            # 3. 测试批量处理相关的功能模块
            try:
                # 验证正则表达式模块（用于解析论文链接）
                test_pattern = re.compile(r'test')
                if not test_pattern.match('test'):
                    raise Exception("正则表达式功能异常")
                
                # 验证URL解析模块（用于处理相对链接）
                test_parsed = urlparse('https://example.com/test')
                if not test_parsed.scheme or not test_parsed.netloc:
                    raise Exception("URL解析功能异常")
                
                test_joined = urljoin('https://example.com/', 'test.html')
                if test_joined != 'https://example.com/test.html':
                    raise Exception("URL拼接功能异常")
                
                # 验证时间处理模块（用于记录处理时间）
                test_time = datetime.now()
                if not test_time:
                    raise Exception("时间处理功能异常")
                
                if self.log_queue:
                    self.log_queue.put("✓ 批量处理功能模块检查通过")
                    
            except ImportError as e:
                if self.log_queue:
                    self.log_queue.put(f"✗ 批量处理依赖模块不可用: {str(e)}")
                return False
            except Exception as e:
                if self.log_queue:
                    self.log_queue.put(f"✗ 批量处理功能模块异常: {str(e)}")
                return False
            
            # 4. 所有检查通过，工具可用
            if self.log_queue:
                self.log_queue.put("✅ DailyPapersCollectorTool 可用性检查全部通过")
            
            return True
            
        except Exception as e:
            # 捕获检查过程中的任何未预期异常
            error_msg = f"可用性检查过程中发生异常: {str(e)}"
            if self.log_queue:
                self.log_queue.put(f"✗ {error_msg}")
            return False
    
    def get_usage_example(self) -> Dict[str, Any]:
        """
        获取工具使用示例
        
        作用：
        1. 为Agent提供批量收集的使用示例
        2. 展示不同参数组合的效果
        3. 说明批量处理的预期输出格式
        4. 确保参数名称与_execute_impl函数保持一致
        
        返回:
            Dict[str, Any]: 包含使用示例的字典
        """
        return {
            "input_examples": {
                "basic_collection": {
                    "description": "基本批量收集（使用默认设置）",
                    "params": {
                        "max_papers": 10,
                        "download_pdfs": True
                    }
                },
                "custom_source": {
                    "description": "从自定义数据源收集论文",
                    "params": {
                        "source_url": "https://huggingface.co/papers",
                        "max_papers": 5,
                        "download_pdfs": True
                    }
                },
                "metadata_only": {
                    "description": "仅收集论文元数据（不下载PDF）",
                    "params": {
                        "max_papers": 20,
                        "download_pdfs": False
                    }
                },
                "filtered_collection": {
                    "description": "使用关键词过滤收集特定主题论文",
                    "params": {
                        "max_papers": 15,
                        "download_pdfs": True,
                        "filter_keywords": ["machine learning", "neural network", "AI"]
                    }
                }
            },
            "expected_output": {
                "description": "返回包含批量收集结果的完整字典",
                "structure": {
                    "papers": "论文信息列表，每个元素包含SinglePaperExtractionTool的完整输出",
                    "total_found": "在数据源中找到的论文总数",
                    "total_collected": "成功收集的论文数量",
                    "total_downloaded": "成功下载PDF的论文数量",
                    "failed_papers": "收集失败的论文信息列表",
                    "source_url": "实际使用的数据源URL",
                    "collection_time": "收集完成的时间戳",
                    "success": "整体收集任务是否成功",
                    "error_message": "错误信息（如果失败）"
                },
                "example": {
                    "papers": [
                        {
                            "title": "Attention Is All You Need",
                            "abstract": "The dominant sequence transduction models...",
                            "pdf_path": "temp_pdf/attention_is_all_you_need.pdf",
                            "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                            "url": "https://huggingface.co/papers/1706.03762",
                            "extraction_time": "2024-01-15T10:30:00",
                            "success": True
                        }
                    ],
                    "total_found": 25,
                    "total_collected": 10,
                    "total_downloaded": 8,
                    "failed_papers": [
                        {
                            "url": "https://huggingface.co/papers/failed_paper",
                            "title": "Failed Paper Title",
                            "error": "PDF下载失败: 文件大小超过限制"
                        }
                    ],
                    "source_url": "https://huggingface.co/papers",
                    "collection_time": "2024-01-15T10:35:00",
                    "success": True,
                    "error_message": None
                }
            },
            "use_cases": [
                "每日自动收集最新AI论文",
                "批量构建特定领域的论文数据库",
                "为研究团队提供论文摘要和PDF汇总",
                "定期监控顶级会议的新发表论文",
                "基于关键词筛选相关研究论文"
            ],
            "parameter_notes": {
                "source_url": "支持HuggingFace Papers、arXiv等主流论文网站",
                "max_papers": "建议设置在1-50之间，过大可能导致处理时间过长",
                "download_pdfs": "设置为False可显著提高收集速度",
                "filter_keywords": "支持多个关键词，使用OR逻辑进行匹配"
            }
        }
    
    def cleanup(self):
        """
        清理工具资源
        
        作用：
        1. 清理SinglePaperExtractionTool的资源
        2. 清理批量处理过程中的临时数据
        3. 释放网络连接和内存资源
        
        实现逻辑：
        1. 调用self.single_extractor.cleanup()
        2. 清理批量处理的临时数据
        3. 释放其他资源
        """
        # TODO: 实现资源清理
        # 1. 清理SinglePaperExtractionTool资源
        # 2. 清理批量处理临时数据
        # 3. 释放其他资源
        pass
    
    def _parse_paper_links_from_soup(self, soup, source_url):
        """
        从BeautifulSoup对象中解析论文链接列表
        
        作用：
        1. 提供论文链接提取的专门方法
        2. 处理不同网站的链接格式
        3. 过滤和验证链接的有效性
        
        参数:
            soup (BeautifulSoup): 已解析的HTML对象
            source_url (str): 数据源URL，用于确定解析策略
        
        实现逻辑：
        1. 根据数据源类型选择不同的解析策略
        2. 提取每个论文的链接和基本信息
        3. 构建完整的URL
        4. 返回论文链接列表
        
        返回:
            List[Dict[str, str]]: 论文链接列表，每个元素包含title和url字段
        """
        paper_links = []
        
        try:
            # 根据数据源类型选择不同的解析策略
            if 'huggingface.co' in source_url:
                # HuggingFace Papers页面解析
                for card in soup.select("article"):
                    title_tag = card.select_one("h3")
                    if not title_tag:
                        continue
                    
                    title = title_tag.text.strip()
                    link_tag = card.find("a", href=True)
                    if link_tag:
                        paper_url = "https://huggingface.co" + link_tag['href']
                        paper_links.append({
                            "title": title,
                            "url": paper_url
                        })
            
            elif 'arxiv.org' in source_url:
                # arXiv页面解析（如果需要支持）
                # 这里可以添加arXiv的解析逻辑
                if self.log_queue:
                    self.log_queue.put("arXiv解析逻辑待实现")
                pass
            
            else:
                # 通用解析策略
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if any(domain in href for domain in ['huggingface.co/papers', 'arxiv.org/abs']):
                        title = link.get_text(strip=True)
                        if title and len(title) > 10:  # 过滤掉太短的标题
                            paper_links.append({
                                "title": title,
                                "url": href if href.startswith('http') else urljoin(source_url, href)
                            })
            
            if self.log_queue:
                self.log_queue.put(f"从HTML中解析出 {len(paper_links)} 个论文链接")
                
        except Exception as e:
            error_msg = f"解析论文链接时发生错误: {str(e)}"
            if self.log_queue:
                self.log_queue.put(f"✗ {error_msg}")
            # 返回空列表而不是抛出异常，让调用方处理
            
        return paper_links
    
    def get_progress_callback(self):
        """
        获取进度回调函数
        
        作用：
        1. 为Agent提供批量处理的进度信息
        2. 支持实时监控和用户反馈
        3. 便于调试和性能优化
        
        返回:
            callable: 进度回调函数，接收进度信息参数
        """
        def progress_callback(current, total, current_paper=None, status="processing", error_message=None):
            """
            进度回调函数
            
            参数:
                current (int): 当前处理的论文序号（从1开始）
                total (int): 总论文数量
                current_paper (dict, optional): 当前处理的论文信息，包含title和url
                status (str): 当前状态 - "processing", "success", "failed", "completed"
                error_message (str, optional): 错误信息（当status为"failed"时）
            """
            try:
                # 计算进度百分比
                progress_percent = (current / total * 100) if total > 0 else 0
                
                # 构建进度信息
                if status == "processing":
                    if current_paper:
                        message = f"📄 正在处理第 {current}/{total} 篇论文 ({progress_percent:.1f}%): {current_paper.get('title', '未知标题')}"
                    else:
                        message = f"📄 正在处理第 {current}/{total} 篇论文 ({progress_percent:.1f}%)"
                        
                elif status == "success":
                    if current_paper:
                        message = f"✅ 成功处理第 {current}/{total} 篇论文: {current_paper.get('title', '未知标题')}"
                    else:
                        message = f"✅ 成功处理第 {current}/{total} 篇论文"
                        
                elif status == "failed":
                    if current_paper:
                        message = f"❌ 处理失败第 {current}/{total} 篇论文: {current_paper.get('title', '未知标题')}"
                        if error_message:
                            message += f" - {error_message}"
                    else:
                        message = f"❌ 处理失败第 {current}/{total} 篇论文"
                        if error_message:
                            message += f" - {error_message}"
                            
                elif status == "completed":
                    message = f"🎉 批量处理完成！成功处理 {current}/{total} 篇论文 (100%)"
                    
                else:
                    message = f"📊 进度更新: {current}/{total} ({progress_percent:.1f}%) - {status}"
                
                # 通过日志队列发送进度信息
                if self.log_queue:
                    self.log_queue.put(message)
                    
                # 可选：返回进度信息字典供调用方使用
                return {
                    "current": current,
                    "total": total,
                    "progress_percent": progress_percent,
                    "status": status,
                    "current_paper": current_paper,
                    "error_message": error_message,
                    "message": message
                }
                
            except Exception as e:
                # 进度回调本身不应该影响主流程，记录错误但不抛出异常
                if self.log_queue:
                    self.log_queue.put(f"⚠️ 进度回调函数发生错误: {str(e)}")
                return None
        
        return progress_callback


class PaperDataManagerTool(BaseTool):
    """
    论文数据管理工具 - 管理论文数据的存储、检索和组织
    
    作用：
    1. 提供论文数据的持久化存储（JSON、数据库等）
    2. 支持论文数据的查询、过滤和排序
    3. 管理论文文件的组织结构和元数据
    4. 提供数据导入导出和备份功能
    """
    
    def __init__(self, log_queue=None, storage_path="./data/papers"):
        """
        初始化论文数据管理工具
        
        参数:
            log_queue: 日志队列，用于向主进程发送日志信息
            storage_path: 数据存储路径，默认为./data/papers
        """
        super().__init__(log_queue)
        self.storage_path = storage_path
        self.metadata_file = f"{storage_path}/metadata.json"
        self.papers_index = {}
        self.supported_formats = ["json", "csv", "sqlite"]
    
    def get_metadata(self) -> ToolMetadata:
        """
        获取工具元数据
        
        作用：
        1. 定义数据管理工具的参数和功能
        2. 让Agent了解如何进行数据操作
        3. 支持多种数据操作类型（存储、查询、导出等）
        
        返回:
            ToolMetadata: 包含工具名称、描述、参数定义等信息
        """
        # TODO: 实现元数据定义
        # 返回 ToolMetadata 对象，包含：
        # - name: "paper_data_manager"
        # - description: "管理论文数据的存储、检索和组织"
        # - parameters: {
        #     "action": {"type": "str", "required": True, "description": "操作类型：save/load/query/export/import/delete"},
        #     "data": {"type": "dict", "required": False, "description": "要保存的论文数据（action=save时必需）"},
        #     "query_params": {"type": "dict", "required": False, "description": "查询参数（action=query时使用）"},
        #     "export_format": {"type": "str", "required": False, "description": "导出格式：json/csv/sqlite"},
        #     "file_path": {"type": "str", "required": False, "description": "文件路径（导入导出时使用）"}
        #   }
        # - return_type: "dict"
        # - category: "data_management"
        pass
    
    def _execute_impl(self, **kwargs) -> Dict[str, Any]:
        """
        核心执行逻辑 - 根据action执行不同的数据管理操作
        
        作用：
        1. 实现数据管理的核心业务逻辑
        2. 根据action参数分发到具体的操作方法
        3. 提供统一的错误处理和结果格式
        4. 支持批量操作和事务处理
        
        参数:
            action (str): 操作类型 - save/load/query/export/import/delete
            data (dict, optional): 论文数据（保存时使用）
            query_params (dict, optional): 查询参数
            export_format (str, optional): 导出格式
            file_path (str, optional): 文件路径
            
        返回:
            Dict[str, Any]: 操作结果，格式：
            {
                "success": True/False,
                "action": "执行的操作类型",
                "result": "具体结果数据",
                "message": "操作说明",
                "count": "影响的记录数（如果适用）"
            }
        
        实现逻辑：
        1. 获取并验证action参数
        2. 根据action分发到对应的私有方法：
           - save -> _save_paper_data()
           - load -> _load_paper_data()
           - query -> _query_papers()
           - export -> _export_data()
           - import -> _import_data()
           - delete -> _delete_paper_data()
        3. 统一处理异常和返回结果
        4. 更新索引和元数据
        """
        # TODO: 实现数据管理逻辑
        # 1. 获取action参数
        # 2. 根据action分发到具体方法
        # 3. 处理异常和返回统一格式结果
        pass
    
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证输入参数
        
        作用：
        1. 验证action参数的有效性
        2. 检查必需参数是否提供
        3. 验证数据格式和文件路径
        4. 确保参数组合的合理性
        
        实现逻辑：
        1. 检查action是否在支持的操作列表中
        2. 根据action验证对应的必需参数
        3. 验证数据格式和文件路径的有效性
        4. 检查参数之间的逻辑关系
        
        返回:
            bool: 参数验证是否通过
        """
        # TODO: 实现参数验证
        # 1. 验证action参数
        # 2. 检查必需参数
        # 3. 验证数据格式
        # 4. 检查参数逻辑关系
        pass
    
    def is_available(self) -> bool:
        """
        检查工具是否可用
        
        作用：
        1. 检查存储路径是否可访问
        2. 验证必要的依赖包
        3. 确认数据库连接（如果使用）
        4. 检查磁盘空间和权限
        
        实现逻辑：
        1. 检查存储路径的读写权限
        2. 验证JSON、CSV等处理库
        3. 测试数据库连接（如果配置）
        4. 检查磁盘空间
        
        返回:
            bool: 工具是否可用
        """
        # TODO: 实现可用性检查
        # 1. 检查存储路径权限
        # 2. 验证依赖包
        # 3. 测试数据库连接
        # 4. 检查系统资源
        pass
    
    def get_usage_example(self) -> Dict[str, Any]:
        """
        获取工具使用示例
        
        作用：
        1. 为Agent提供数据管理的使用示例
        2. 展示不同操作类型的参数格式
        3. 说明预期的输入输出格式
        
        返回:
            Dict[str, Any]: 包含使用示例的字典
        """
        return {
            "input_examples": [
                {
                    "description": "保存单篇论文数据",
                    "params": {
                        "action": "save",
                        "data": {
                            "title": "论文标题",
                            "abstract": "论文摘要",
                            "pdf_path": "/path/to/paper.pdf",
                            "url": "https://example.com/paper",
                            "timestamp": "2024-01-01T00:00:00Z"
                        }
                    }
                },
                {
                    "description": "查询包含特定关键词的论文",
                    "params": {
                        "action": "query",
                        "query_params": {
                            "title_contains": "machine learning",
                            "limit": 10,
                            "sort_by": "timestamp",
                            "order": "desc"
                        }
                    }
                },
                {
                    "description": "导出所有论文数据为CSV格式",
                    "params": {
                        "action": "export",
                        "export_format": "csv",
                        "file_path": "./exports/papers.csv"
                    }
                },
                {
                    "description": "从JSON文件导入论文数据",
                    "params": {
                        "action": "import",
                        "file_path": "./imports/papers.json"
                    }
                }
            ],
            "expected_output": {
                "description": "返回操作结果，包含成功状态和具体数据",
                "example": {
                    "success": True,
                    "action": "query",
                    "result": [
                        {
                            "id": "paper_001",
                            "title": "机器学习论文标题",
                            "abstract": "论文摘要...",
                            "timestamp": "2024-01-01T00:00:00Z"
                        }
                    ],
                    "message": "查询完成，找到1篇论文",
                    "count": 1
                }
            },
            "use_cases": [
                "构建论文数据库",
                "论文数据备份和恢复",
                "论文信息检索和过滤",
                "数据分析和统计",
                "与其他系统的数据交换"
            ]
        }
    
    def cleanup(self):
        """
        清理工具资源
        
        作用：
        1. 保存未提交的数据变更
        2. 关闭数据库连接
        3. 清理临时文件和缓存
        4. 释放内存资源
        
        实现逻辑：
        1. 保存papers_index到磁盘
        2. 关闭数据库连接
        3. 清理临时文件
        4. 释放内存
        """
        # TODO: 实现资源清理
        # 1. 保存索引数据
        # 2. 关闭数据库连接
        # 3. 清理临时文件
        # 4. 释放内存资源
        pass
    
    def _save_paper_data(self, data):
        """
        保存论文数据到存储系统
        
        作用：
        1. 将论文数据持久化存储
        2. 生成唯一ID和时间戳
        3. 更新索引和元数据
        4. 处理重复数据检查
        
        实现逻辑：
        1. 生成论文唯一ID
        2. 添加时间戳和元数据
        3. 保存到JSON文件或数据库
        4. 更新索引
        """
        # TODO: 实现数据保存逻辑
        pass
    
    def _load_paper_data(self, paper_id=None):
        """
        加载论文数据
        
        作用：
        1. 从存储系统加载论文数据
        2. 支持加载单篇或所有论文
        3. 处理数据格式转换
        4. 提供缓存机制
        
        实现逻辑：
        1. 根据paper_id加载特定论文或所有论文
        2. 从JSON文件或数据库读取
        3. 格式化返回数据
        """
        # TODO: 实现数据加载逻辑
        pass
    
    def _query_papers(self, query_params):
        """
        查询论文数据
        
        作用：
        1. 根据查询条件过滤论文
        2. 支持多种查询条件组合
        3. 提供排序和分页功能
        4. 优化查询性能
        
        实现逻辑：
        1. 解析查询参数
        2. 应用过滤条件
        3. 排序和分页
        4. 返回查询结果
        """
        # TODO: 实现查询逻辑
        pass
    
    def _export_data(self, export_format, file_path=None):
        """
        导出论文数据
        
        作用：
        1. 将论文数据导出为指定格式
        2. 支持JSON、CSV、SQLite等格式
        3. 处理大数据量的分批导出
        4. 提供导出进度反馈
        
        实现逻辑：
        1. 验证导出格式
        2. 准备导出数据
        3. 根据格式调用对应的导出方法
        4. 保存到指定路径
        """
        # TODO: 实现数据导出逻辑
        pass
    
    def _import_data(self, file_path):
        """
        导入论文数据
        
        作用：
        1. 从外部文件导入论文数据
        2. 支持多种文件格式
        3. 处理数据验证和去重
        4. 提供导入进度反馈
        
        实现逻辑：
        1. 检查文件格式和存在性
        2. 读取和解析文件数据
        3. 验证数据格式
        4. 批量保存到存储系统
        """
        # TODO: 实现数据导入逻辑
        pass
    
    def _delete_paper_data(self, paper_id):
        """
        删除论文数据
        
        作用：
        1. 从存储系统删除指定论文
        2. 清理相关的文件和索引
        3. 提供软删除和硬删除选项
        4. 记录删除操作日志
        
        实现逻辑：
        1. 验证论文ID存在性
        2. 删除论文数据记录
        3. 清理相关文件
        4. 更新索引
        """
        # TODO: 实现数据删除逻辑
        pass
    
    def get_statistics(self):
        """
        获取论文数据统计信息
        
        作用：
        1. 提供论文数量、存储大小等统计
        2. 分析论文来源和时间分布
        3. 生成数据质量报告
        4. 支持Agent的决策制定
        
        返回:
            Dict[str, Any]: 统计信息字典
        """
        # TODO: 实现统计信息生成
        pass
    
    def create_backup(self, backup_path=None):
        """
        创建数据备份
        
        作用：
        1. 创建完整的数据备份
        2. 支持增量备份和全量备份
        3. 压缩备份文件节省空间
        4. 验证备份完整性
        
        实现逻辑：
        1. 确定备份路径和文件名
        2. 收集所有需要备份的数据
        3. 创建压缩备份文件
        4. 验证备份完整性
        """
        # TODO: 实现备份创建逻辑
        pass
    
    def restore_from_backup(self, backup_path):
        """
        从备份恢复数据
        
        作用：
        1. 从备份文件恢复论文数据
        2. 验证备份文件完整性
        3. 处理数据冲突和合并
        4. 提供恢复进度反馈
        
        实现逻辑：
        1. 验证备份文件
        2. 解压和读取备份数据
        3. 处理数据冲突
        4. 恢复到存储系统
        """
        # TODO: 实现备份恢复逻辑
        pass

# 测试代码 - 用于验证SinglePaperExtractionTool的功能
if __name__ == "__main__":
    # 创建测试实例
    print("开始测试SinglePaperExtractionTool...")
    
    # 创建一个简单的日志队列模拟器
    class SimpleLogQueue:
        def put(self, message):
            print(f"[LOG] {message}")
    
    # 初始化工具
    log_queue = SimpleLogQueue()
    extractor = SinglePaperExtractionTool(log_queue)
    
    # 测试用的论文URL（HuggingFace Papers示例）
    test_url = "https://huggingface.co/papers/2509.07980"  # 可以替换为其他有效的论文URL
    
    print(f"\n测试URL: {test_url}")
    print("="*50)
    
    try:
        # 调用_execute_impl函数进行测试
        result = extractor._execute_impl(
            paper_url=test_url,
            download_pdf=True,  # 设置为True测试PDF下载
            custom_filename="test_paper"  # 自定义文件名
        )
        
        print("\n测试结果:")
        print("="*30)
        print(f"成功状态: {result.get('success')}")
        print(f"论文标题: {result.get('title')}")
        print(f"摘要长度: {len(result.get('abstract', '')) if result.get('abstract') else 0} 字符")
        print(f"PDF路径: {result.get('pdf_path')}")
        print(f"PDF URL: {result.get('pdf_url')}")
        print(f"提取时间: {result.get('extraction_time')}")
        
        if result.get('error_message'):
            print(f"错误信息: {result.get('error_message')}")
        
        # 显示摘要的前200个字符
        if result.get('abstract'):
            abstract_preview = result.get('abstract')[:200] + "..." if len(result.get('abstract', '')) > 200 else result.get('abstract')
            print(f"\n摘要预览:\n{abstract_preview}")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成!")