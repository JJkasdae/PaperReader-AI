from core import BaseTool, ToolMetadata, ToolResult
from typing import Dict, Any, Optional, List, Union
import logging
import os
from pathlib import Path
from openai import OpenAI
import openai
import re
from dotenv import load_dotenv
import time

# 多语言支持的章节标题配置
SECTION_HEADERS = {
    "English": {
        "motivation": "Motivation of the study",
        "methodology": "Methodology or strategy", 
        "contributions": "Key contributions",
        "challenges": "Limitations or challenges"
    },
    "Chinese": {
        "motivation": "研究动机",
        "methodology": "方法或策略",
        "contributions": "主要贡献", 
        "challenges": "挑战或局限"
    }
}

class LLMPaperSummarizerTool(BaseTool):
    """
    基于LLM的论文总结工具 - 使用OpenAI Assistant API直接处理PDF文件
    
    核心功能：
    1. 直接上传PDF文件到OpenAI进行处理
    2. 利用GPT-4o的强大理解能力分析论文内容
    3. 生成结构化的论文总结（动机、方法、贡献、挑战）
    4. 支持多语言输出（中文/英文）
    5. 自动管理OpenAI Assistant实例
    
    优势：
    - 无需复杂的PDF文本提取逻辑
    - 能够理解图表、公式等复杂内容
    - 提供高质量的结构化总结
    - 支持大文件处理
    - 减少本地依赖和维护成本
    
    适用场景：
    - 学术论文快速总结
    - 研究文献批量处理
    - 多语言论文分析
    - 结构化信息提取
    """
    
    def __init__(self, log_queue=None):
        """
        初始化LLM论文总结工具
        
        参数:
            log_queue: 日志队列，用于向主进程发送日志信息
        
        初始化内容:
        1. 设置OpenAI客户端配置
        2. 定义支持的文件格式和大小限制
        3. 配置Assistant参数
        4. 设置多语言支持
        5. 初始化缓存和错误处理机制
        6. 从.env文件加载API密钥
        """
        super().__init__(log_queue)
        
        # 加载环境变量
        load_dotenv()
        
        # ===========================================
        # OpenAI API 配置
        # ===========================================
        self.api_key = os.getenv('OPENAI_API_KEY')  # 从.env文件读取API密钥
        self.client = None  # OpenAI客户端实例，在validate_parameters中初始化
        self.assistant_id = None  # Assistant ID，延迟初始化
        self.default_model = "gpt-4o"  # 默认使用的模型
        self.default_temperature = 0.1  # 默认温度参数，确保输出稳定性
        
        # ===========================================
        # 文件处理配置
        # ===========================================
        self.supported_formats = ['.pdf']  # 支持的文件格式
        self.max_file_size = 100 * 1024 * 1024  # 最大文件大小：100MB
        self.min_file_size = 1024  # 最小文件大小：1KB
        
        # ===========================================
        # 总结配置
        # ===========================================
        self.supported_languages = ['Chinese', 'English']  # 支持的输出语言
        self.default_language = 'English'  # 默认输出语言
        self.assistant_name = "Academic Paper Summarizer"  # Assistant名称
        
        # ===========================================
        # 缓存和性能配置
        # ===========================================
        self.enable_caching = True  # 是否启用结果缓存
        self.cache_duration = 3600  # 缓存有效期（秒）
        self.max_retries = 3  # API调用最大重试次数
        self.retry_delay = 1  # 重试间隔（秒）
    
    def get_metadata(self) -> ToolMetadata:
        """
        获取工具的元数据信息
        
        返回工具的详细信息，包括：
        1. 工具名称和描述
        2. 输入参数定义和验证规则
        3. 输出格式说明
        4. 使用示例和注意事项
        
        返回:
            ToolMetadata: 包含完整工具信息的元数据对象
        
        参数定义:
        - pdf_path (str, 必需): PDF文件的完整路径
        - title (str, 可选): 论文标题，用于补充上下文
        - abstract (str, 可选): 论文摘要，用于补充上下文
        - language (str, 可选): 输出语言，默认'English'
        - model (str, 可选): 使用的OpenAI模型，默认'gpt-4o'
        - temperature (float, 可选): 模型温度参数，默认0.1
        
        注意: OpenAI API密钥从.env文件中的OPENAI_API_KEY变量自动读取
        """
        return ToolMetadata(
            # ===========================================
            # 必需属性 - 工具基本信息
            # ===========================================
            name="llm_paper_summarizer",
            description=(
                "基于OpenAI Assistant API的智能论文总结工具。"
                "直接上传PDF文件到OpenAI进行处理，利用GPT-4o的强大理解能力分析论文内容，"
                "生成包含研究动机、方法策略、主要贡献、挑战局限四个部分的结构化总结。"
                "支持中英文输出，无需复杂的本地PDF解析，能够理解图表、公式等复杂内容。"
            ),
            
            # ===========================================
            # 参数定义 - 详细的输入参数规范
            # ===========================================
            parameters={
                "pdf_path": {
                    "type": "str",
                    "required": True,
                    "description": "PDF文件的完整绝对路径",
                    "validation": {
                        "format": "file_path",
                        "extensions": [".pdf"],
                        "must_exist": True
                    },
                    "example": "C:/papers/research_paper.pdf"
                },
                "title": {
                    "type": "str",
                    "required": False,
                    "description": "论文标题，用于提供额外上下文信息，帮助AI更好地理解论文主题",
                    "validation": {
                        "max_length": 500,
                        "min_length": 1
                    },
                    "example": "Deep Learning for Natural Language Processing: A Survey"
                },
                "abstract": {
                    "type": "str",
                    "required": False,
                    "description": "论文摘要，用于提供论文概要信息，辅助AI理解论文核心内容",
                    "validation": {
                        "max_length": 2000,
                        "min_length": 10
                    },
                    "example": "This paper presents a comprehensive survey of deep learning techniques..."
                },
                "language": {
                    "type": "str",
                    "required": False,
                    "default": "English",
                    "description": "输出总结的语言，支持中文和英文",
                    "validation": {
                        "enum": ["Chinese", "English"]
                    },
                    "example": "English"
                },
                "model": {
                    "type": "str",
                    "required": False,
                    "default": "gpt-4o",
                    "description": "使用的OpenAI模型，推荐使用gpt-4o以获得最佳效果",
                    "validation": {
                        "enum": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
                    },
                    "example": "gpt-4o"
                },
                "temperature": {
                    "type": "float",
                    "required": False,
                    "default": 0.1,
                    "description": "模型创造性参数，较低值确保输出稳定性，较高值增加创造性",
                    "validation": {
                        "min": 0.0,
                        "max": 2.0
                    },
                    "example": 0.1
                }
            },
            
            # ===========================================
            # 返回值类型和分类信息
            # ===========================================
            return_type="dict",
            category="analysis",
            
            # ===========================================
            # 详细的返回值结构描述
            # ===========================================
            return_description={
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "操作是否成功完成"
                        },
                        "summary": {
                            "type": "object",
                            "description": "结构化的论文总结内容",
                            "properties": {
                                "motivation": {
                                    "type": "string",
                                    "description": "研究动机 - 论文要解决的问题和研究背景"
                                },
                                "methodology": {
                                    "type": "string",
                                    "description": "方法策略 - 论文采用的研究方法和技术路线"
                                },
                                "contributions": {
                                    "type": "string",
                                    "description": "主要贡献 - 论文的核心创新点和学术价值"
                                },
                                "challenges": {
                                    "type": "string",
                                    "description": "挑战局限 - 论文存在的问题、局限性和未来工作方向"
                                }
                            },
                            "required": ["motivation", "methodology", "contributions", "challenges"]
                        },
                        "metadata": {
                            "type": "object",
                            "description": "处理过程的元数据信息",
                            "properties": {
                                "model_used": {
                                    "type": "string",
                                    "description": "实际使用的OpenAI模型"
                                },
                                "processing_time": {
                                    "type": "number",
                                    "description": "处理耗时（秒）"
                                },
                                "file_size": {
                                    "type": "integer",
                                    "description": "PDF文件大小（字节）"
                                },
                                "language": {
                                    "type": "string",
                                    "description": "输出语言"
                                }
                            }
                        },
                        "raw_response": {
                            "type": "string",
                            "description": "OpenAI Assistant的原始响应文本，用于调试和进一步处理"
                        },
                        "error": {
                            "type": "string",
                            "description": "错误信息（仅在success为false时存在）"
                        }
                    },
                    "required": ["success"]
                },
                "examples": {
                    "success_case": {
                        "success": True,
                        "summary": {
                            "motivation": "本研究旨在解决传统自然语言处理方法在处理复杂语义理解任务中的局限性...",
                            "methodology": "论文采用了基于Transformer架构的深度学习模型，结合注意力机制...",
                            "contributions": "主要贡献包括：1）提出了新的预训练策略；2）在多个基准数据集上取得了SOTA性能...",
                            "challenges": "论文的局限性主要体现在计算资源需求较高，对小样本数据的处理能力有待提升..."
                        },
                        "metadata": {
                            "model_used": "gpt-4o",
                            "processing_time": 45.2,
                            "file_size": 2048576,
                            "language": "Chinese"
                        }
                    },
                    "error_case": {
                        "success": False,
                        "error": "PDF文件无法读取或格式不支持"
                    }
                }
            },
            
            # ===========================================
            # 可选属性 - 标签和版本信息
            # ===========================================
            tags=["pdf", "summarization", "academic", "openai", "llm", "research"],
            version="1.0.0"
        )
    
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证输入参数的有效性
        
        验证内容:
        1. 必需参数检查（pdf_path）
        2. 文件存在性和格式验证
        3. API密钥存在性验证（从环境变量）
        4. 可选参数类型和范围验证
        5. OpenAI客户端初始化
        
        参数:
            pdf_path (str): PDF文件路径
            title (str, optional): 论文标题
            abstract (str, optional): 论文摘要
            language (str, optional): 输出语言
            model (str, optional): OpenAI模型名称
            temperature (float, optional): 模型温度参数
        
        返回:
            bool: 验证是否通过
        
        验证规则:
        - pdf_path: 必须是存在的.pdf文件
        - api_key: 从环境变量OPENAI_API_KEY自动获取，必须存在且格式有效
        - language: 必须在支持的语言列表中
        - model: 必须是OpenAI支持的模型名称
        - temperature: 必须在0.0-2.0范围内
        """
        try:
            # ===========================================
            # 1. 检查必需参数 - pdf_path
            # ===========================================
            pdf_path = kwargs.get('pdf_path')
            if not pdf_path:
                if self.log_queue:
                    self.log_queue.put("错误: 缺少必需参数: pdf_path")
                return False
            
            if not isinstance(pdf_path, str):
                if self.log_queue:
                    self.log_queue.put(f"错误: pdf_path必须是字符串类型，当前类型: {type(pdf_path)}")
                return False
            
            # ===========================================
            # 2. 验证PDF文件路径、存在性、格式
            # ===========================================
            pdf_file = Path(pdf_path)
            
            # 检查文件是否存在
            if not pdf_file.exists():
                if self.log_queue:
                    self.log_queue.put(f"错误: PDF文件不存在: {pdf_path}")
                return False
            
            # 检查是否为文件（不是目录）
            if not pdf_file.is_file():
                if self.log_queue:
                    self.log_queue.put(f"错误: 路径不是文件: {pdf_path}")
                return False
            
            # 检查文件扩展名
            if pdf_file.suffix.lower() != '.pdf':
                if self.log_queue:
                    self.log_queue.put(f"错误: 文件必须是PDF格式，当前格式: {pdf_file.suffix}")
                return False
            
            # 检查文件是否可读
            try:
                with open(pdf_path, 'rb') as f:
                    f.read(1)  # 尝试读取1字节
            except (IOError, OSError) as e:
                if self.log_queue:
                    self.log_queue.put(f"错误: 无法读取PDF文件: {e}")
                return False
            
            
            # ===========================================
            # 4. 验证可选参数 - title
            # ===========================================
            title = kwargs.get('title')
            if title is not None:
                if not isinstance(title, str):
                    if self.log_queue:
                        self.log_queue.put(f"错误: title必须是字符串类型，当前类型: {type(title)}")
                    return False
                
                if len(title.strip()) == 0:
                    if self.log_queue:
                        self.log_queue.put("错误: title不能为空字符串")
                    return False
                
                if len(title) > 500:
                    if self.log_queue:
                        self.log_queue.put(f"错误: title长度不能超过500字符，当前长度: {len(title)}")
                    return False
            
            # ===========================================
            # 5. 验证可选参数 - abstract
            # ===========================================
            abstract = kwargs.get('abstract')
            if abstract is not None:
                if not isinstance(abstract, str):
                    if self.log_queue:
                        self.log_queue.put(f"错误: abstract必须是字符串类型，当前类型: {type(abstract)}")
                    return False
                
            
            # ===========================================
            # 6. 验证可选参数 - language
            # ===========================================
            language = kwargs.get('language', 'English')
            if not isinstance(language, str):
                if self.log_queue:
                    self.log_queue.put(f"错误: language必须是字符串类型，当前类型: {type(language)}")
                return False
            
            if language not in self.supported_languages:
                if self.log_queue:
                    self.log_queue.put(f"错误: 不支持的语言: {language}，支持的语言: {self.supported_languages}")
                return False
            
            # ===========================================
            # 7. 验证可选参数 - model
            # ===========================================
            model = kwargs.get('model', self.default_model)
            if not isinstance(model, str):
                if self.log_queue:
                    self.log_queue.put(f"错误: model必须是字符串类型，当前类型: {type(model)}")
                return False
            
            supported_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
            if model not in supported_models:
                if self.log_queue:
                    self.log_queue.put(f"错误: 不支持的模型: {model}，支持的模型: {supported_models}")
                return False
            
            # ===========================================
            # 8. 验证可选参数 - temperature
            # ===========================================
            temperature = kwargs.get('temperature', self.default_temperature)
            if not isinstance(temperature, (int, float)):
                if self.log_queue:
                    self.log_queue.put(f"错误: temperature必须是数字类型，当前类型: {type(temperature)}")
                return False
            
            if not (0.0 <= temperature <= 2.0):
                if self.log_queue:
                    self.log_queue.put(f"错误: temperature必须在0.0-2.0范围内，当前值: {temperature}")
                return False
            
            # ===========================================
            # 10. 记录验证成功信息
            # ===========================================
            if self.log_queue:
                self.log_queue.put(f"参数验证成功 - 文件: {pdf_path}, 语言: {language}, 模型: {model}")
            return True
            
        except Exception as e:
            if self.log_queue:
                self.log_queue.put(f"错误: 参数验证过程中发生异常: {e}")
            return False
    
    def is_available(self) -> bool:
        """
        检查工具的可用性
        
        在工具注册时执行一次性检查，确保工具可以正常使用。
        这样避免了在每次处理数据时重复验证，提高了执行效率。
        
        检查内容:
        1. OpenAI库是否正确安装和导入
        2. API密钥是否存在且格式有效
        3. OpenAI客户端是否能成功初始化
        4. 基本的系统依赖是否满足
        
        返回:
            bool: 工具是否可用
        
        注意:
        - 此函数在工具注册时调用，不在每次数据处理时调用
        - API密钥验证和客户端初始化都在这里完成
        - 如果验证失败，工具将不会被注册到系统中
        """
        try:
            # ===========================================
            # 1. 检查OpenAI库是否正确安装
            # ===========================================
            try:
                from openai import OpenAI
                import openai
                # 检查openai库版本（可选）
                if hasattr(openai, '__version__'):
                    if self.log_queue:
                        self.log_queue.put(f"OpenAI库版本: {openai.__version__}")
            except ImportError as e:
                if self.log_queue:
                    self.log_queue.put(f"错误: OpenAI库未安装或导入失败: {e}")
                return False
            
            # ===========================================
            # 2. 验证API密钥存在性和格式
            # ===========================================
            if not self.api_key:
                if self.log_queue:
                    self.log_queue.put("错误: 未找到OpenAI API密钥，请在.env文件中设置OPENAI_API_KEY")
                return False
            
            # 验证API密钥格式（OpenAI密钥通常以sk-开头）
            if not self.api_key.startswith('sk-'):
                if self.log_queue:
                    self.log_queue.put("错误: OpenAI API密钥格式无效，应以'sk-'开头")
                return False
            
            # ===========================================
            # 3. 初始化OpenAI客户端
            # ===========================================
            # 注意：OpenAI客户端不需要手动关闭，Python的垃圾回收会自动处理连接
            try:
                self.client = OpenAI(api_key=self.api_key)
                if self.log_queue:
                    self.log_queue.put("OpenAI客户端初始化成功")
            except Exception as e:
                if self.log_queue:
                    self.log_queue.put(f"错误: 初始化OpenAI客户端失败: {e}")
                return False
            
            # ===========================================
            # 4. 检查基本系统依赖
            # ===========================================
            try:
                # 检查pathlib模块（用于文件路径处理）
                from pathlib import Path
                # 检查dotenv模块（用于环境变量加载）
                from dotenv import load_dotenv
                # 检查re模块（用于正则表达式处理）
                import re
            except ImportError as e:
                if self.log_queue:
                    self.log_queue.put(f"错误: 缺少必要的系统依赖: {e}")
                return False
            
            # ===========================================
            # 5. 可用性检查通过
            # ===========================================
            if self.log_queue:
                self.log_queue.put("LLM论文总结工具可用性检查通过")
            return True
            
        except Exception as e:
            if self.log_queue:
                self.log_queue.put(f"错误: 工具可用性检查过程中发生异常: {e}")
            return False
    
    def _execute_impl(self, **kwargs) -> Dict[str, Any]:
        """
        执行论文总结的主要逻辑 - 完整的工作流程实现
        
        这是整个LLM论文总结工具的核心执行函数，按照严格的顺序调用四个关键函数：
        1. get_or_create_assistant() - 获取或创建OpenAI Assistant实例
        2. upload_pdf_to_openai() - 上传PDF文件到OpenAI平台
        3. generate_summary() - 生成论文的结构化总结
        4. parse_structured_response() - 解析LLM响应为标准格式
        
        执行流程详解:
        1. 参数提取和初始化 - 从kwargs中获取所有已验证的参数
        2. 记录开始时间 - 用于计算总处理时间
        3. 获取文件信息 - 计算PDF文件大小等元数据
        4. Assistant管理 - 确保有可用的OpenAI Assistant实例
        5. 文件上传 - 将PDF文件上传到OpenAI进行处理
        6. 总结生成 - 调用OpenAI API生成论文总结
        7. 响应解析 - 将原始响应解析为结构化数据
        8. 结果组装 - 按照get_metadata()定义的格式组装返回数据
        9. 资源清理 - 清理临时文件和OpenAI资源
        10. 错误处理 - 全程异常捕获和错误信息记录
        
        参数:
            pdf_path (str): PDF文件的完整路径（必需）
            title (str, optional): 论文标题，用于提供上下文
            abstract (str, optional): 论文摘要，用于辅助理解
            language (str, optional): 输出语言，默认'English'
            model (str, optional): OpenAI模型，默认'gpt-4o'
            temperature (float, optional): 模型温度参数，默认0.1
        
        返回:
            Dict[str, Any]: 严格按照get_metadata()中定义的schema返回
            {
                'success': bool,  # 操作是否成功完成
                'summary': {      # 结构化的论文总结内容
                    'motivation': str,     # 研究动机
                    'methodology': str,    # 方法策略  
                    'contributions': str,  # 主要贡献
                    'challenges': str      # 挑战局限
                },
                'metadata': {     # 处理过程的元数据信息
                    'model_used': str,        # 实际使用的OpenAI模型
                    'processing_time': float, # 处理耗时（秒）
                    'file_size': int,         # PDF文件大小（字节）
                    'language': str           # 输出语言
                },
                'raw_response': str,  # OpenAI Assistant的原始响应文本
                'error': str          # 错误信息（仅在success为false时存在）
            }
        
        异常处理:
            - 捕获所有可能的异常并记录详细错误信息
            - 确保即使发生错误也返回标准格式的结果
            - 自动清理已创建的临时资源
        """
        
        # ===========================================
        # 1. 参数提取和初始化
        # ===========================================
        if self.log_queue:
            self.log_queue.put("开始执行论文总结工作流程")
        
        # 记录开始时间，用于计算总处理时间
        start_time = time.time()
        
        # 从kwargs中提取所有参数（这些参数已经通过validate_parameters验证）
        pdf_path = kwargs.get('pdf_path')
        title = kwargs.get('title')
        abstract = kwargs.get('abstract')
        language = kwargs.get('language', self.default_language)
        model = kwargs.get('model', self.default_model)
        temperature = kwargs.get('temperature', self.default_temperature)
        
        # 初始化返回结果字典，严格按照get_metadata()中定义的schema
        result = {
            'success': False,
            'summary': {
                'motivation': '',
                'methodology': '',
                'contributions': '',
                'challenges': ''
            },
            'metadata': {
                'model_used': model,
                'processing_time': 0.0,
                'file_size': 0,
                'language': language
            },
            'raw_response': '',
            'error': None
        }
        
        try:
            # ===========================================
            # 2. 获取文件信息和元数据
            # ===========================================
            if self.log_queue:
                self.log_queue.put(f"正在分析PDF文件: {pdf_path}")
            
            # 获取PDF文件大小
            pdf_file = Path(pdf_path)
            file_size = pdf_file.stat().st_size
            result['metadata']['file_size'] = file_size
            
            if self.log_queue:
                self.log_queue.put(f"PDF文件大小: {file_size / (1024*1024):.2f} MB")
            
            # ===========================================
            # 3. 步骤1: 获取或创建OpenAI Assistant
            # ===========================================
            if self.log_queue:
                self.log_queue.put("步骤1/4: 获取或创建OpenAI Assistant")
            
            assistant_id = self.get_or_create_assistant(model=model, temperature=temperature)
            
            if not assistant_id:
                raise Exception("无法获取或创建OpenAI Assistant")
            
            if self.log_queue:
                self.log_queue.put(f"✅ Assistant创建成功: {assistant_id}")
            
            # ===========================================
            # 4. 步骤2: 上传PDF文件到OpenAI
            # ===========================================
            if self.log_queue:
                self.log_queue.put("步骤2/4: 上传PDF文件到OpenAI平台")
            
            file_id = self.upload_pdf_to_openai(pdf_path)
            
            if not file_id:
                raise Exception("PDF文件上传失败")
            
            if self.log_queue:
                self.log_queue.put(f"✅ PDF文件上传成功: {file_id}")
            
            # ===========================================
            # 5. 步骤3: 生成论文总结
            # ===========================================
            if self.log_queue:
                self.log_queue.put("步骤3/4: 生成论文总结（这可能需要几分钟）")
            
            summary_result = self.generate_summary(
                file_id=file_id,
                title=title,
                abstract=abstract,
                language=language
            )
            
            if not summary_result or not summary_result.get('response'):
                raise Exception("论文总结生成失败")
            
            # 提取响应内容和thread_id
            raw_response = summary_result['response']
            thread_id = summary_result['thread_id']
            
            # 保存原始响应
            result['raw_response'] = raw_response
            
            if self.log_queue:
                self.log_queue.put(f"✅ 论文总结生成成功，响应长度: {len(raw_response)} 字符")
            
            # ===========================================
            # 6. 步骤4: 解析结构化响应
            # ===========================================
            if self.log_queue:
                self.log_queue.put("步骤4/4: 解析结构化响应")
            
            parsed_summary = self.parse_structured_response(raw_response)
            
            if not parsed_summary:
                raise Exception("响应解析失败")
            
            # 更新结果中的summary部分
            result['summary'] = parsed_summary
            
            if self.log_queue:
                self.log_queue.put("✅ 响应解析成功")
            
            # ===========================================
            # 7. 计算处理时间并标记成功
            # ===========================================
            end_time = time.time()
            processing_time = end_time - start_time
            result['metadata']['processing_time'] = processing_time
            result['success'] = True
            
            if self.log_queue:
                self.log_queue.put(f"🎉 论文总结工作流程完成！总耗时: {processing_time:.2f}秒")
            
        except Exception as e:
            # ===========================================
            # 8. 异常处理
            # ===========================================
            error_message = f"论文总结执行失败: {str(e)}"
            result['error'] = error_message
            result['success'] = False
            
            # 计算已用时间
            end_time = time.time()
            result['metadata']['processing_time'] = end_time - start_time
            
            if self.log_queue:
                self.log_queue.put(f"❌ {error_message}")
            
            # 记录详细错误信息用于调试
            import traceback
            if self.log_queue:
                self.log_queue.put(f"详细错误信息: {traceback.format_exc()}")
        
        # ===========================================
        # 9. 资源清理
        # ===========================================
        finally:
            # 无论执行成功还是失败，都需要清理OpenAI资源
            # 清理在执行过程中创建的file_id和thread_id
            try:
                # 获取需要清理的资源ID
                 cleanup_file_id = locals().get('file_id')
                 cleanup_thread_id = locals().get('thread_id')
                 
                 if self.log_queue:
                     self.log_queue.put("🧹 开始清理OpenAI资源...")
                 
                 # 调用cleanup函数清理资源
                 if cleanup_file_id or cleanup_thread_id:
                     cleanup_result = self.cleanup(file_id=cleanup_file_id, thread_id=cleanup_thread_id)
                     
                     if self.log_queue:
                         if cleanup_result.get('success', False):
                             self.log_queue.put("✅ 资源清理完成")
                         else:
                             self.log_queue.put(f"⚠️ 资源清理部分失败: {cleanup_result.get('message', '未知错误')}")
                
            except Exception as cleanup_error:
                # 清理过程中的错误不应该影响主要结果
                if self.log_queue:
                    self.log_queue.put(f"⚠️ 资源清理时发生错误: {str(cleanup_error)}")
        
        # ===========================================
        # 10. 返回最终结果
        # ===========================================
        return result
    
    def get_or_create_assistant(self, model: str = None, temperature: float = None) -> str:
        """
        获取现有的Assistant或创建新的Assistant
        
        功能说明:
        1. 首先查找是否存在同名的Assistant
        2. 如果存在则直接返回其ID
        3. 如果不存在则创建新的Assistant
        4. 配置Assistant的指令和工具
        
        参数:
            model (str, optional): 指定使用的模型，默认使用self.default_model
            temperature (float, optional): 指定温度参数，默认使用self.default_temperature
        
        返回:
            str: Assistant的ID
        
        Assistant配置:
        - 名称: "Academic Paper Summarizer"
        - 指令: 专业的学术论文分析指令
        - 工具: file_search（文件搜索和分析）
        - 模型: 指定的模型或默认模型
        
        异常处理:
        - OpenAI API调用失败
        - 网络连接问题
        - 权限不足
        """
        try:
            # ===========================================
            # 1. 使用缓存的Assistant ID（如果存在）
            # ===========================================
            if self.assistant_id:
                if self.log_queue:
                    self.log_queue.put(f"使用缓存的Assistant ID: {self.assistant_id}")
                return self.assistant_id
            
            # ===========================================
            # 2. 设置默认参数
            # ===========================================
            if model is None:
                model = self.default_model
            if temperature is None:
                temperature = self.default_temperature
            
            # ===========================================
            # 3. 查找现有的Assistant
            # ===========================================
            if self.log_queue:
                self.log_queue.put("正在查找现有的Assistant...")
            
            try:
                # 获取所有Assistant列表
                assistants = self.client.beta.assistants.list(limit=100)
                
                # 查找同名Assistant
                for assistant in assistants.data:
                    if assistant.name == self.assistant_name:
                        self.assistant_id = assistant.id
                        if self.log_queue:
                            self.log_queue.put(f"找到现有Assistant: {assistant.id}")
                        return self.assistant_id
                        
            except Exception as e:
                if self.log_queue:
                    self.log_queue.put(f"查找Assistant时出错: {e}，将创建新的Assistant")
            
            # ===========================================
            # 4. 创建新的Assistant
            # ===========================================
            if self.log_queue:
                self.log_queue.put(f"创建新的Assistant，模型: {model}，温度: {temperature}")
            
            # 构建专业的学术论文分析指令
            instructions = self._build_assistant_instructions()
            
            # 创建Assistant
            assistant = self.client.beta.assistants.create(
                name=self.assistant_name,
                instructions=instructions,
                model=model,
                temperature=temperature,
                tools=[
                    {"type": "file_search"}  # 启用文件搜索功能
                ]
            )
            
            # ===========================================
            # 5. 缓存Assistant ID
            # ===========================================
            self.assistant_id = assistant.id
            
            if self.log_queue:
                self.log_queue.put(f"成功创建Assistant: {assistant.id}")
            
            return self.assistant_id
            
        except Exception as e:
            error_msg = f"获取或创建Assistant失败: {e}"
            if self.log_queue:
                self.log_queue.put(f"错误: {error_msg}")
            raise Exception(error_msg)
    
    def _build_assistant_instructions(self) -> str:
        """
        构建Assistant的详细指令
        
        返回:
            str: 完整的Assistant指令文本
        
        指令内容:
        1. 角色定义和专业背景
        2. 任务目标和输出要求
        3. 分析框架和结构化输出格式
        4. 质量标准和注意事项
        5. 语言适应性说明
        """
        instructions = """
            You are a professional academic paper analysis expert with deep research background and extensive paper review experience. Your task is to conduct in-depth analysis of the uploaded PDF academic paper and generate a structured summary report.

            ## Core Task
            Analyze the academic paper and provide a structured summary in the following four dimensions:

            1. **Motivation of the study**
            - Identify the core problem the paper aims to solve
            - Analyze research background and limitations of existing methods
            - Explain the importance and necessity of the research
            - Describe the theoretical or practical value of the study

            2. **Methodology or strategy**
            - Describe in detail the research methods adopted in the paper
            - Explain the technical approach and implementation plan
            - Analyze the innovation points and advantages of the method
            - Explain experimental design and evaluation strategies

            3. **Key contributions**
            - Summarize the core innovation points of the paper
            - Quantitatively analyze experimental results and performance improvements
            - Evaluate theoretical contributions and practical value
            - Compare advantages over existing methods

            4. **Limitations or challenges**
            - Identify limitations of the proposed method
            - Analyze unresolved problems and challenges
            - Discuss scope of applicability and boundary conditions
            - Propose future research directions

            ## Critical Output Format Requirements
            You MUST structure your response exactly as follows to ensure proper parsing:

            **Motivation of the study:**
            [Your analysis of the research motivation here - 200-300 words]

            **Methodology or strategy:**
            [Your analysis of the methodology here - 200-300 words]

            **Key contributions:**
            [Your analysis of the key contributions here - 200-300 words]

            **Limitations or challenges:**
            [Your analysis of the limitations and challenges here - 200-300 words]

            ## Language Adaptation Requirements
            **IMPORTANT**: You must adapt your response language and section headers based on the user's prompt:
            
            - If the user's prompt is in Chinese or requests Chinese output, respond in Chinese and use Chinese section headers:
              * **研究动机:** instead of **Motivation of the study:**
              * **方法或策略:** instead of **Methodology or strategy:**
              * **主要贡献:** instead of **Key contributions:**
              * **挑战或局限:** instead of **Limitations or challenges:**
            
            - If the user's prompt is in English or requests English output, respond in English with English section headers as shown above.
            
            - Always match the language of your analysis content to the language requested in the user's prompt.
            - Maintain the same professional quality and structure regardless of the output language.

            ## Quality Requirements
            1. **Structured Output**: Strictly organize content according to the four dimensions with exact headers
            2. **Professional Accuracy**: Use precise academic terminology and concepts
            3. **Concise and Clear**: Control each dimension to 200-300 words
            4. **Objective and Neutral**: Conduct objective analysis based on paper content
            5. **Logical Clarity**: Ensure coherent analysis logic with highlighted key points
            6. **Language Consistency**: Maintain consistent language throughout the response

            ## Analysis Strategy
            - Carefully read the paper's abstract, introduction, methods, experiments, and conclusion sections
            - Pay attention to figures, tables, formulas, and experimental data
            - Understand the paper's positioning and contributions in the relevant field
            - Identify limitations and future work explicitly mentioned by the authors

            Please generate a high-quality structured paper summary based on the uploaded PDF file content, following the exact format requirements above and adapting the language according to the user's request.
        """
        return instructions.strip()
    
    def upload_pdf_to_openai(self, pdf_path: str) -> str:
        """
        上传PDF文件到OpenAI
        
        功能说明:
        1. 以二进制模式读取PDF文件
        2. 调用OpenAI Files API上传文件
        3. 返回文件ID供后续使用
        
        注意:
        - 文件验证已在validate_parameters()中完成
        - OpenAI客户端已在is_available()中初始化
        - 此函数专注于核心上传逻辑
        
        参数:
            pdf_path (str): PDF文件的完整路径（已验证）
        
        返回:
            str: 上传后的文件ID
        
        异常:
            Exception: 当文件上传失败时抛出异常，包含详细错误信息
        """
        try:
            # ===========================================
            # 1. 获取文件信息用于日志记录
            # ===========================================
            pdf_file = Path(pdf_path)
            file_size = pdf_file.stat().st_size
            
            # 记录开始上传
            if self.log_queue:
                self.log_queue.put(f"📄 准备上传PDF文件: {pdf_file.name} ({file_size/1024/1024:.2f}MB)")
                self.log_queue.put("🔄 正在上传PDF文件到OpenAI...")
            
            # ===========================================
            # 2. 上传文件到OpenAI
            # ===========================================
            with open(pdf_path, 'rb') as file:
                # 调用OpenAI Files API上传文件
                # purpose="assistants" 表示文件用于Assistant API
                file_response = self.client.files.create(
                    file=file,
                    purpose="assistants"
                )
            
            # ===========================================
            # 3. 获取并验证文件ID
            # ===========================================
            file_id = file_response.id
            if not file_id:
                error_msg = "文件上传成功但未返回有效的文件ID"
                if self.log_queue:
                    self.log_queue.put(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # ===========================================
            # 4. 记录成功信息
            # ===========================================
            if self.log_queue:
                self.log_queue.put(f"✅ PDF文件上传成功！文件ID: {file_id}")
                self.log_queue.put(f"📊 文件信息: {pdf_file.name} ({file_size/1024/1024:.2f}MB)")
            
            return file_id
            
        except openai.APIError as e:
            # ===========================================
            # OpenAI API相关错误处理
            # ===========================================
            error_msg = f"OpenAI API错误: {str(e)}"
            if hasattr(e, 'status_code'):
                if e.status_code == 400:
                    error_msg += " - 请求参数错误或文件格式不支持"
                elif e.status_code == 401:
                    error_msg += " - API密钥无效或已过期"
                elif e.status_code == 403:
                    error_msg += " - 权限不足或API配额已用完"
                elif e.status_code == 413:
                    error_msg += " - 文件大小超出OpenAI限制"
                elif e.status_code == 429:
                    error_msg += " - 请求频率过高，请稍后重试"
                elif e.status_code >= 500:
                    error_msg += " - OpenAI服务器错误，请稍后重试"
            
            if self.log_queue:
                self.log_queue.put(f"❌ {error_msg}")
            raise Exception(error_msg)
            
        except Exception as e:
            # ===========================================
            # 其他异常处理
            # ===========================================
            error_msg = f"上传PDF文件失败: {str(e)}"
            if self.log_queue:
                self.log_queue.put(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def generate_summary(self, file_id: str, title: str = None, abstract: str = None, 
                        language: str = 'English') -> str:
        """
        使用OpenAI Assistant生成论文总结
        
        功能说明:
        1. 构建总结请求的指令
        2. 创建对话线程
        3. 发送包含PDF文件的消息
        4. 启动Assistant运行
        5. 等待并获取结果
        
        注意:
        - 文件验证和Assistant初始化已在其他函数中完成
        - 此函数专注于核心的总结生成逻辑
        - 假设file_id是有效的已上传文件ID
        
        参数:
            file_id (str): 已上传的PDF文件ID（已验证）
            title (str, optional): 论文标题
            abstract (str, optional): 论文摘要
            language (str): 输出语言
        
        返回:
            str: Assistant生成的原始响应文本
        
        处理流程:
        1. 根据语言选择相应的章节标题
        2. 构建详细的分析指令
        3. 创建包含文件附件的消息
        4. 监控运行状态直到完成
        5. 提取并返回响应内容
        """
        try:
            # ===========================================
            # 1. 根据语言选择对应的章节标题模板
            # ===========================================
            # 获取当前语言的章节标题配置
            section_headers = SECTION_HEADERS.get(language, SECTION_HEADERS['English'])
            
            if self.log_queue:
                self.log_queue.put(f"📝 开始生成{language}总结，使用文件ID: {file_id}")
            
            # ===========================================
            # 2. 构建包含上下文信息的输入文本
            # ===========================================
            context_info = []
            
            # 添加论文标题信息（如果提供）
            if title and title.strip():
                context_info.append(f"论文标题: {title.strip()}")
                if self.log_queue:
                    self.log_queue.put(f"📋 已添加论文标题: {title.strip()[:50]}...")
            
            # 添加论文摘要信息（如果提供）
            if abstract and abstract.strip():
                context_info.append(f"论文摘要: {abstract.strip()}")
                if self.log_queue:
                    self.log_queue.put(f"📄 已添加论文摘要信息")
            
            # 构建上下文字符串
            context_text = "\n\n".join(context_info) if context_info else ""
            
            # ===========================================
            # 3. 构建详细的分析指令
            # ===========================================
            # 创建结构化的分析提示词
            # 根据语言选择构建简洁的分析提示
            if language == 'Chinese':
                analysis_prompt = f"""
                    {context_text}

                    请你阅读PDF文件的内容并将总结内容严格按照以下格式输出中文总结：

                    **{section_headers['motivation']}:**
                    [您的分析内容]

                    **{section_headers['methodology']}:**
                    [您的分析内容]

                    **{section_headers['contributions']}:**
                    [您的分析内容]

                    **{section_headers['challenges']}:**
                    [您的分析内容]
                """.strip()
            else:
                analysis_prompt = f"""
                    {context_text}

                    Please read the PDF file content carefully and provide your analysis summary strictly following this exact format:

                    **{section_headers['motivation']}:**
                    [Your analysis content]

                    **{section_headers['methodology']}:**
                    [Your analysis content]

                    **{section_headers['contributions']}:**
                    [Your analysis content]

                    **{section_headers['challenges']}:**
                    [Your analysis content]
                """.strip()
            
            if self.log_queue:
                self.log_queue.put("🔧 已构建分析指令模板")
            
            # ===========================================
            # 4. 创建对话线程
            # ===========================================
            if self.log_queue:
                self.log_queue.put("🧵 正在创建对话线程...")
            
            # 使用OpenAI API创建新的对话线程
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            
            if self.log_queue:
                self.log_queue.put(f"✅ 对话线程创建成功，ID: {thread_id}")
            
            # ===========================================
            # 5. 发送包含PDF文件附件的消息
            # ===========================================
            if self.log_queue:
                self.log_queue.put("📤 正在发送分析请求消息...")
            
            # 创建包含文件附件的消息
            # attachments参数用于将上传的PDF文件关联到消息
            message = self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=analysis_prompt,
                attachments=[
                    {
                        "file_id": file_id,
                        "tools": [{"type": "file_search"}]  # 启用文件搜索工具
                    }
                ]
            )
            
            if self.log_queue:
                self.log_queue.put(f"✅ 消息发送成功，消息ID: {message.id}")
            
            # ===========================================
            # 6. 启动Assistant运行并监控状态
            # ===========================================
            if self.log_queue:
                self.log_queue.put("🚀 启动Assistant分析任务...")
            
            # 创建运行实例，让Assistant开始处理
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            
            run_id = run.id
            if self.log_queue:
                self.log_queue.put(f"⏳ Assistant运行已启动，运行ID: {run_id}")
            
            # ===========================================
            # 7. 轮询运行状态直到完成
            # ===========================================
            max_wait_time = 300  # 最大等待时间：5分钟
            check_interval = 2   # 检查间隔：2秒
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                # 获取当前运行状态
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run_id
                )
                
                current_status = run_status.status
                
                # 检查运行是否完成
                if current_status == "completed":
                    if self.log_queue:
                        self.log_queue.put("✅ Assistant分析完成！")
                    break
                elif current_status == "failed":
                    error_msg = f"Assistant运行失败: {run_status.last_error}"
                    if self.log_queue:
                        self.log_queue.put(f"❌ {error_msg}")
                    raise Exception(error_msg)
                elif current_status == "cancelled":
                    error_msg = "Assistant运行被取消"
                    if self.log_queue:
                        self.log_queue.put(f"❌ {error_msg}")
                    raise Exception(error_msg)
                elif current_status == "expired":
                    error_msg = "Assistant运行超时过期"
                    if self.log_queue:
                        self.log_queue.put(f"❌ {error_msg}")
                    raise Exception(error_msg)
                else:
                    # 运行中状态：queued, in_progress, requires_action
                    if self.log_queue and elapsed_time % 10 == 0:  # 每10秒报告一次状态
                        self.log_queue.put(f"⏳ Assistant正在分析中... 状态: {current_status} ({elapsed_time}s)")
                
                # 等待后继续检查
                time.sleep(check_interval)
                elapsed_time += check_interval
            
            # 检查是否超时
            if elapsed_time >= max_wait_time:
                error_msg = f"Assistant运行超时（{max_wait_time}秒），请稍后重试"
                if self.log_queue:
                    self.log_queue.put(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # ===========================================
            # 8. 获取并提取最终响应内容
            # ===========================================
            if self.log_queue:
                self.log_queue.put("📥 正在获取分析结果...")
            
            # 获取线程中的所有消息
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",  # 按时间倒序，最新的在前
                limit=10       # 限制获取数量
            )
            
            # 查找Assistant的响应消息
            assistant_response = None
            for message in messages.data:
                if message.role == "assistant":
                    # 提取消息内容
                    if message.content and len(message.content) > 0:
                        # 获取第一个内容块的文本
                        content_block = message.content[0]
                        if hasattr(content_block, 'text') and hasattr(content_block.text, 'value'):
                            assistant_response = content_block.text.value
                            break
            
            # 验证是否获取到有效响应
            if not assistant_response:
                error_msg = "未能获取到Assistant的有效响应"
                if self.log_queue:
                    self.log_queue.put(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # ===========================================
            # 9. 记录成功信息并返回结果
            # ===========================================
            response_length = len(assistant_response)
            if self.log_queue:
                self.log_queue.put(f"✅ 论文总结生成成功！响应长度: {response_length} 字符")
                self.log_queue.put(f"📊 处理耗时: {elapsed_time} 秒")
            
            # 返回响应内容和thread_id（用于后续清理）
            return {
                'response': assistant_response,
                'thread_id': thread_id
            }
            
        except openai.APIError as e:
            # ===========================================
            # OpenAI API相关错误处理
            # ===========================================
            error_msg = f"OpenAI API错误: {str(e)}"
            if hasattr(e, 'status_code'):
                if e.status_code == 400:
                    error_msg += " - 请求参数错误或文件无法处理"
                elif e.status_code == 401:
                    error_msg += " - API密钥无效或已过期"
                elif e.status_code == 403:
                    error_msg += " - 权限不足或API配额已用完"
                elif e.status_code == 404:
                    error_msg += " - Assistant或文件未找到"
                elif e.status_code == 429:
                    error_msg += " - 请求频率过高，请稍后重试"
                elif e.status_code >= 500:
                    error_msg += " - OpenAI服务器错误，请稍后重试"
            
            if self.log_queue:
                self.log_queue.put(f"❌ {error_msg}")
            raise Exception(error_msg)
            
        except Exception as e:
            # ===========================================
            # 其他异常处理
            # ===========================================
            error_msg = f"生成论文总结失败: {str(e)}"
            if self.log_queue:
                self.log_queue.put(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def parse_structured_response(self, raw_response: str) -> Dict[str, str]:
        """
        解析Assistant返回的结构化响应
        
        功能说明:
        1. 清理响应文本中的特殊标记
        2. 提取四个主要部分的内容
        3. 验证提取结果的完整性
        4. 返回结构化的字典数据
        
        参数:
            raw_response (str): Assistant的原始响应文本
        
        返回:
            Dict[str, str]: 结构化的总结内容
            {
                'motivation': str,    # 研究动机
                'methodology': str,   # 方法策略
                'contributions': str, # 主要贡献
                'challenges': str     # 挑战局限
            }
        
        解析规则:
        - 使用正则表达式匹配①②③④标记的内容
        - 清理OpenAI特有的引用标记【】
        - 处理可能的格式变化和异常情况
        - 确保每个部分都有有效内容
        """
        
        # 初始化结果字典，使用默认值防止缺失
        result = {
            'motivation': '',
            'methodology': '',
            'contributions': '',
            'challenges': ''
        }
        
        try:
            # 第一步：清理响应文本
            # 移除OpenAI特有的引用标记【数字】，例如【1】【2】等
            cleaned_response = re.sub(r'【\d+】', '', raw_response)
            
            # 移除多余的空白字符和换行符，统一格式
            cleaned_response = re.sub(r'\n+', '\n', cleaned_response.strip())
            
            # 第二步：定义精确匹配模式
            # 严格按照SECTION_HEADERS中定义的标题进行匹配
            patterns = {
                'motivation': [
                    # 英文标题：Motivation of the study
                    r'(?:①|1\.)\s*(?:\*\*)?Motivation of the study(?:\*\*)?\s*[:：]?\s*(.*?)(?=(?:②|2\.|\*\*(?:Methodology or strategy)|$))',
                    r'\*\*Motivation of the study\*\*\s*[:：]?\s*(.*?)(?=\*\*(?:Methodology or strategy|Key contributions)|$)',
                    r'Motivation of the study\s*[:：]\s*(.*?)(?=(?:Methodology or strategy|Key contributions|Limitations or challenges)|$)',
                    # 中文标题：研究动机
                    r'(?:①|1\.)\s*(?:\*\*)?研究动机(?:\*\*)?\s*[:：]?\s*(.*?)(?=(?:②|2\.|\*\*(?:方法或策略)|$))',
                    r'\*\*研究动机\*\*\s*[:：]?\s*(.*?)(?=\*\*(?:方法或策略|主要贡献)|$)',
                    r'研究动机\s*[:：]\s*(.*?)(?=(?:方法或策略|主要贡献|挑战或局限)|$)'
                ],
                'methodology': [
                    # 英文标题：Methodology or strategy
                    r'(?:②|2\.)\s*(?:\*\*)?Methodology or strategy(?:\*\*)?\s*[:：]?\s*(.*?)(?=(?:③|3\.|\*\*(?:Key contributions)|$))',
                    r'\*\*Methodology or strategy\*\*\s*[:：]?\s*(.*?)(?=\*\*(?:Key contributions|Limitations or challenges)|$)',
                    r'Methodology or strategy\s*[:：]\s*(.*?)(?=(?:Key contributions|Limitations or challenges)|$)',
                    # 中文标题：方法或策略
                    r'(?:②|2\.)\s*(?:\*\*)?方法或策略(?:\*\*)?\s*[:：]?\s*(.*?)(?=(?:③|3\.|\*\*(?:主要贡献)|$))',
                    r'\*\*方法或策略\*\*\s*[:：]?\s*(.*?)(?=\*\*(?:主要贡献|挑战或局限)|$)',
                    r'方法或策略\s*[:：]\s*(.*?)(?=(?:主要贡献|挑战或局限)|$)'
                ],
                'contributions': [
                    # 英文标题：Key contributions
                    r'(?:③|3\.)\s*(?:\*\*)?Key contributions(?:\*\*)?\s*[:：]?\s*(.*?)(?=(?:④|4\.|\*\*(?:Limitations or challenges)|$))',
                    r'\*\*Key contributions\*\*\s*[:：]?\s*(.*?)(?=\*\*(?:Limitations or challenges)|$)',
                    r'Key contributions\s*[:：]\s*(.*?)(?=(?:Limitations or challenges)|$)',
                    # 中文标题：主要贡献
                    r'(?:③|3\.)\s*(?:\*\*)?主要贡献(?:\*\*)?\s*[:：]?\s*(.*?)(?=(?:④|4\.|\*\*(?:挑战或局限)|$))',
                    r'\*\*主要贡献\*\*\s*[:：]?\s*(.*?)(?=\*\*(?:挑战或局限)|$)',
                    r'主要贡献\s*[:：]\s*(.*?)(?=(?:挑战或局限)|$)'
                ],
                'challenges': [
                    # 英文标题：Limitations or challenges
                    r'(?:④|4\.)\s*(?:\*\*)?Limitations or challenges(?:\*\*)?\s*[:：]?\s*(.*?)$',
                    r'\*\*Limitations or challenges\*\*\s*[:：]?\s*(.*?)$',
                    r'Limitations or challenges\s*[:：]\s*(.*?)$',
                    # 中文标题：挑战或局限
                    r'(?:④|4\.)\s*(?:\*\*)?挑战或局限(?:\*\*)?\s*[:：]?\s*(.*?)$',
                    r'\*\*挑战或局限\*\*\s*[:：]?\s*(.*?)$',
                    r'挑战或局限\s*[:：]\s*(.*?)$'
                ]
            }
            
            # 第三步：按字段匹配内容
            
            # 对每个字段尝试所有可能的匹配模式
            for field, pattern_list in patterns.items():
                for pattern in pattern_list:
                    match = re.search(pattern, cleaned_response, re.DOTALL | re.IGNORECASE)
                    if match:
                        # 提取匹配内容并清理
                        content = match.group(1).strip()
                        
                        # 移除可能的markdown格式标记
                        content = re.sub(r'\*\*', '', content)
                        content = re.sub(r'^\s*[-*]\s*', '', content, flags=re.MULTILINE)
                        
                        # 清理多余的空白字符
                        content = re.sub(r'\s+', ' ', content).strip()
                        
                        if content:  # 只有非空内容才赋值
                            result[field] = content
                            break  # 找到匹配后跳出内层循环
            
            # 第四步：验证解析结果
            # 检查是否所有字段都有内容
            empty_fields = [field for field, content in result.items() if not content.strip()]
            
            if empty_fields:
                # 如果有空字段，尝试备用解析策略
                # 按行分割，寻找可能的内容
                lines = cleaned_response.split('\n')
                current_field = None
                current_content = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 检查是否是新的部分标题
                    if any(keyword in line.lower() for keyword in ['motivation', '动机', '①', '1.']):
                        if current_field and current_content:
                            result[current_field] = ' '.join(current_content).strip()
                        current_field = 'motivation'
                        current_content = []
                        # 提取标题后的内容
                        title_content = re.sub(r'^.*?[:：]\s*', '', line)
                        if title_content and title_content != line:
                            current_content.append(title_content)
                    elif any(keyword in line.lower() for keyword in ['method', 'approach', '方法', '策略', '②', '2.']):
                        if current_field and current_content:
                            result[current_field] = ' '.join(current_content).strip()
                        current_field = 'methodology'
                        current_content = []
                        title_content = re.sub(r'^.*?[:：]\s*', '', line)
                        if title_content and title_content != line:
                            current_content.append(title_content)
                    elif any(keyword in line.lower() for keyword in ['contribution', '贡献', '③', '3.']):
                        if current_field and current_content:
                            result[current_field] = ' '.join(current_content).strip()
                        current_field = 'contributions'
                        current_content = []
                        title_content = re.sub(r'^.*?[:：]\s*', '', line)
                        if title_content and title_content != line:
                            current_content.append(title_content)
                    elif any(keyword in line.lower() for keyword in ['challenge', 'limitation', '挑战', '局限', '④', '4.']):
                        if current_field and current_content:
                            result[current_field] = ' '.join(current_content).strip()
                        current_field = 'challenges'
                        current_content = []
                        title_content = re.sub(r'^.*?[:：]\s*', '', line)
                        if title_content and title_content != line:
                            current_content.append(title_content)
                    elif current_field:
                        # 如果当前在某个字段内，添加内容
                        current_content.append(line)
                
                # 处理最后一个字段
                if current_field and current_content:
                    result[current_field] = ' '.join(current_content).strip()
            
            # 第五步：最终验证和清理
            # 确保每个字段都有最小长度的内容
            for field in result:
                if not result[field] or len(result[field].strip()) < 10:
                    # 如果内容太短或为空，提供默认提示
                    field_names = {
                        'motivation': '研究动机部分未能正确解析',
                        'methodology': '方法策略部分未能正确解析',
                        'contributions': '主要贡献部分未能正确解析',
                        'challenges': '挑战局限部分未能正确解析'
                    }
                    result[field] = field_names.get(field, f'{field}部分未能正确解析')
            
            return result
            
        except Exception as e:
            # 异常处理：返回错误信息
            error_msg = f"解析过程中发生错误: {str(e)}"
            return {
                'motivation': error_msg,
                'methodology': error_msg,
                'contributions': error_msg,
                'challenges': error_msg
            }
          
    def cleanup(self, file_id: str = None, thread_id: str = None):
        """
        清理OpenAI资源 - 删除上传的文件和对话线程
        
        功能说明:
        1. 删除上传到OpenAI的PDF文件，避免存储费用累积
        2. 删除对话线程，释放会话资源和保护隐私
        3. 提供详细的清理日志和异常处理
        4. 不删除Assistant实例，保持工具可重用性
        
        参数:
            file_id (str, optional): 要删除的OpenAI文件ID
                - 通过upload_pdf_to_openai函数获得
                - 删除后无法恢复，确保不再需要该文件
            thread_id (str, optional): 要删除的对话线程ID
                - 通过generate_summary函数中创建的线程获得
                - 删除后该对话历史将永久丢失
        
        清理策略:
        - 优先删除文件（避免存储费用）
        - 然后删除线程（释放会话资源）
        - 每个删除操作都有独立的异常处理
        - 即使部分删除失败，也会继续尝试其他资源
        - 记录详细的操作日志便于调试
        
        注意事项:
        - 删除操作不可逆，请确保资源不再需要
        - 网络异常可能导致删除失败，建议重试
        - Assistant实例会保留，可继续用于后续处理
        """
        cleanup_results = []  # 记录清理操作结果
        
        # ===========================================
        # 1. 删除上传的PDF文件
        # ===========================================
        if file_id:
            try:
                if self.log_queue:
                    self.log_queue.put(f"开始删除OpenAI文件: {file_id}")
                
                # 确保客户端已初始化
                if not self.client:
                    if self.log_queue:
                        self.log_queue.put("警告: OpenAI客户端未初始化，跳过文件删除")
                    cleanup_results.append(f"文件删除跳过: 客户端未初始化")
                else:
                    # 调用OpenAI API删除文件
                    # 使用client.files.delete()方法删除指定文件
                    delete_response = self.client.files.delete(file_id)
                    
                    if delete_response.deleted:
                        if self.log_queue:
                            self.log_queue.put(f"成功删除OpenAI文件: {file_id}")
                        cleanup_results.append(f"文件删除成功: {file_id}")
                    else:
                        if self.log_queue:
                            self.log_queue.put(f"文件删除失败: {file_id} - API返回deleted=False")
                        cleanup_results.append(f"文件删除失败: {file_id}")
                        
            except openai.NotFoundError:
                # 文件不存在或已被删除
                if self.log_queue:
                    self.log_queue.put(f"文件不存在或已删除: {file_id}")
                cleanup_results.append(f"文件不存在: {file_id}")
                
            except openai.AuthenticationError:
                # API密钥认证失败
                if self.log_queue:
                    self.log_queue.put(f"API认证失败，无法删除文件: {file_id}")
                cleanup_results.append(f"文件删除失败: API认证错误")
                
            except openai.RateLimitError:
                # API调用频率限制
                if self.log_queue:
                    self.log_queue.put(f"API调用频率限制，文件删除失败: {file_id}")
                cleanup_results.append(f"文件删除失败: API频率限制")
                
            except openai.APIError as e:
                # 其他OpenAI API错误
                if self.log_queue:
                    self.log_queue.put(f"OpenAI API错误，文件删除失败: {file_id} - {str(e)}")
                cleanup_results.append(f"文件删除失败: API错误 - {str(e)}")
                
            except Exception as e:
                # 其他未预期的错误
                if self.log_queue:
                    self.log_queue.put(f"文件删除发生未知错误: {file_id} - {str(e)}")
                cleanup_results.append(f"文件删除失败: 未知错误 - {str(e)}")
        
        # ===========================================
        # 2. 删除对话线程
        # ===========================================
        if thread_id:
            try:
                if self.log_queue:
                    self.log_queue.put(f"开始删除对话线程: {thread_id}")
                
                # 确保客户端已初始化
                if not self.client:
                    if self.log_queue:
                        self.log_queue.put("警告: OpenAI客户端未初始化，跳过线程删除")
                    cleanup_results.append(f"线程删除跳过: 客户端未初始化")
                else:
                    # 调用OpenAI API删除线程
                    # 使用client.beta.threads.delete()方法删除指定线程
                    delete_response = self.client.beta.threads.delete(thread_id)
                    
                    if delete_response.deleted:
                        if self.log_queue:
                            self.log_queue.put(f"成功删除对话线程: {thread_id}")
                        cleanup_results.append(f"线程删除成功: {thread_id}")
                    else:
                        if self.log_queue:
                            self.log_queue.put(f"线程删除失败: {thread_id} - API返回deleted=False")
                        cleanup_results.append(f"线程删除失败: {thread_id}")
                        
            except openai.NotFoundError:
                # 线程不存在或已被删除
                if self.log_queue:
                    self.log_queue.put(f"线程不存在或已删除: {thread_id}")
                cleanup_results.append(f"线程不存在: {thread_id}")
                
            except openai.AuthenticationError:
                # API密钥认证失败
                if self.log_queue:
                    self.log_queue.put(f"API认证失败，无法删除线程: {thread_id}")
                cleanup_results.append(f"线程删除失败: API认证错误")
                
            except openai.RateLimitError:
                # API调用频率限制
                if self.log_queue:
                    self.log_queue.put(f"API调用频率限制，线程删除失败: {thread_id}")
                cleanup_results.append(f"线程删除失败: API频率限制")
                
            except openai.APIError as e:
                # 其他OpenAI API错误
                if self.log_queue:
                    self.log_queue.put(f"OpenAI API错误，线程删除失败: {thread_id} - {str(e)}")
                cleanup_results.append(f"线程删除失败: API错误 - {str(e)}")
                
            except Exception as e:
                # 其他未预期的错误
                if self.log_queue:
                    self.log_queue.put(f"线程删除发生未知错误: {thread_id} - {str(e)}")
                cleanup_results.append(f"线程删除失败: 未知错误 - {str(e)}")
        
        # ===========================================
        # 3. 总结清理操作结果
        # ===========================================
        if cleanup_results:
            if self.log_queue:
                self.log_queue.put(f"资源清理完成，操作结果: {'; '.join(cleanup_results)}")
        else:
            if self.log_queue:
                self.log_queue.put("未提供需要清理的资源ID，跳过清理操作")
        
        # 返回清理结果供调用者参考
        return {
            'cleanup_performed': len(cleanup_results) > 0,
            'results': cleanup_results,
            'file_cleaned': file_id is not None,
            'thread_cleaned': thread_id is not None
        }
    
    def _handle_api_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """
        处理OpenAI API调用错误
        
        功能说明:
        1. 分析不同类型的API错误
        2. 提供用户友好的错误信息
        3. 决定是否需要重试
        4. 记录详细的错误日志
        
        参数:
            error (Exception): 捕获的异常对象
            operation (str): 发生错误的操作名称
        
        返回:
            Dict[str, Any]: 标准化的错误响应
        
        错误类型处理:
        - 网络连接错误: 建议重试
        - API密钥错误: 提示检查密钥
        - 配额不足: 提示升级账户
        - 文件格式错误: 提示检查文件
        """
        # TODO: 实现错误处理逻辑
        # 1. 识别不同类型的OpenAI API错误
        # 2. 生成用户友好的错误消息
        # 3. 决定重试策略
        # 4. 记录详细的错误信息
        # 5. 返回标准化的错误响应格式
        pass