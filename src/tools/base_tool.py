from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time
import logging
import sys
import os


@dataclass # Python会自动帮你完成变量初始化，对应这个class你就不用手动写__init__的函数了。对于纯数据对象很好用。
class ToolMetadata:
    """
    工具元数据类 - 存储工具的基本信息
    
    作用：
    1. 让Agent能够理解工具的功能和用法
    2. 提供工具的参数定义和返回值类型
    3. 支持工具的自动发现和分类
    4. 提供工具的版本管理和标签分类
    5. 详细描述工具的返回值结构
    """
    # 必需属性 - 每个工具都必须提供（无默认值的字段必须在前面）
    name: str                           # 工具唯一标识名称，如 "paper_extractor"
    description: str                    # 工具功能的详细描述
    parameters: Dict[str, Any]          # 参数定义：{"param_name": {"type": "str", "required": True, "description": "..."}}
    return_type: str                   # 返回值类型描述，如 "dict", "list", "str"
    category: str                      # 工具分类，如 "extraction", "audio", "file", "analysis"
    
    # 可选属性 - 有默认值的字段必须在后面
    return_description: Dict[str, Any] = None  # 详细的返回值描述，包含schema和字段说明
    tags: List[str] = None             # 工具标签列表，用于更细粒度的分类和搜索
    version: str = "1.0.0"             # 工具版本号，用于版本管理和兼容性检查
    
    def __post_init__(self):
        """
        初始化后处理 - 为可选属性设置默认值
        
        作用：
        1. 确保tags属性始终是一个列表
        2. 为return_description提供基本结构
        3. 验证必需属性的有效性
        """
        # 确保tags是一个列表
        if self.tags is None:
            self.tags = []
        
        # 为return_description提供基本结构
        if self.return_description is None:
            self.return_description = {
                "description": f"返回{self.return_type}类型的结果",
                "schema": {}
            }
    

@dataclass
class ToolResult:
    """
    工具执行结果类 - 标准化所有工具的返回格式
    
    作用：
    1. 统一所有工具的返回格式，便于Agent处理
    2. 提供详细的执行信息，便于调试和监控
    3. 支持错误处理和异常情况的标准化处理
    """
    success: bool                    # 执行是否成功
    data: Any                       # 实际返回的数据（成功时）
    error_message: Optional[str]    # 错误信息（失败时）
    execution_time: float           # 执行耗时（秒）
    metadata: Dict[str, Any]        # 额外的元数据信息
    tool_name: str                  # 执行的工具名称
    timestamp: float                # 执行时间戳


class BaseTool(ABC): # ABC是abstract Base Class表示一个抽象基类，所有继承了这个基类的子类都要遵守这个基类的规则。
    """
    工具基类 - 所有具体工具都必须继承此类
    
    作用：
    1. 定义所有工具的标准接口
    2. 提供通用的功能（参数验证、错误处理、日志等）
    3. 确保所有工具都有一致的行为模式
    """
    
    def __init__(self, log_queue=None):
        """
        初始化工具基类
        
        参数:
            log_queue: 日志队列，用于向主进程发送日志信息
        """
        self.log_queue = log_queue
        self.logger = logging.getLogger(self.__class__.__name__) # 括号里面表示的是自身这个class的name，这个logger这个class自己的日志，可以通过它分析class的行为。
    
    @abstractmethod # 这个表示每个子对象都必须实现的function，根据自己的情况实现，不然会报错。
    def get_metadata(self) -> ToolMetadata:
        """
        获取工具元数据 - 每个工具必须实现
        
        作用：
        1. 返回工具的详细信息
        2. 让Agent了解如何使用这个工具
        3. 支持工具的自动注册和发现
        
        返回:
            ToolMetadata: 工具的元数据信息
        """
        pass
    
    @abstractmethod # 这个表示每个子对象都必须实现的function，根据自己的情况实现，不然会报错。
    def _execute_impl(self, **kwargs) -> Any:
        """
        工具的核心执行逻辑 - 每个工具必须实现
        
        作用：
        1. 实现工具的具体功能
        2. 处理输入参数并返回结果
        3. 只关注业务逻辑，不处理通用逻辑
        
        参数:
            **kwargs: 工具执行所需的参数
            
        返回:
            Any: 工具执行的原始结果
        """
        pass
    
    def execute(self, **kwargs) -> ToolResult:
        """
        统一的工具执行入口 - Agent调用的标准接口
        
        作用：
        1. 提供统一的工具调用接口
        2. 处理参数验证、错误捕获、日志记录
        3. 返回标准化的执行结果
        
        实现逻辑：
        1. 记录开始时间
        2. 验证输入参数
        3. 调用 _execute_impl() 执行具体逻辑
        4. 捕获和处理异常
        5. 记录执行时间和日志
        6. 返回标准化的 ToolResult
        
        参数:
            **kwargs: 传递给具体工具实现的参数
            
        返回:
            ToolResult: 标准化的工具执行结果
        """
        
        # 1. 记录开始时间，用于计算执行耗时
        start_time = time.time()
        
        # 获取工具名称用于日志和结果记录
        tool_name = self.__class__.__name__
        
        # 记录工具执行开始的日志
        self.log(f"开始执行工具: {tool_name}", "info")
        if kwargs:
            # 记录输入参数（注意：敏感信息应该被过滤）
            safe_kwargs = self._sanitize_log_params(kwargs)
            self.log(f"输入参数: {safe_kwargs}", "debug")
        
        # 初始化返回结果对象
        result = ToolResult(
            success=False,
            data=None,
            error_message=None,
            execution_time=0.0,
            metadata={},
            tool_name=tool_name,
            timestamp=start_time
        )
        
        try:
            # 2. 验证输入参数
            self.log("开始参数验证", "debug")
            
            if not self.validate_parameters(**kwargs):
                # 参数验证失败
                error_msg = "输入参数验证失败"
                result.error_message = error_msg
                self.log(f"错误: {error_msg}", "error")
                return result
            
            self.log("参数验证通过", "debug")
            
            # 4. 调用具体的工具实现逻辑
            self.log("开始执行核心逻辑", "debug")
            
            # 调用子类实现的核心逻辑
            execution_result = self._execute_impl(**kwargs)
            
            # 5. 处理执行结果
            result.success = True
            result.data = execution_result
            
            # 添加执行元数据
            result.metadata = {
                "tool_version": getattr(self, 'version', '1.0.0'),
                "execution_context": {
                    "input_params_count": len(kwargs),
                    "has_log_queue": self.log_queue is not None
                }
            }
            
            self.log("工具执行成功完成", "info")
            
        except ValueError as e:
            # 参数值错误（通常是业务逻辑层面的参数问题）
            error_msg = f"参数值错误: {str(e)}"
            result.error_message = error_msg
            self.log(f"错误: {error_msg}", "error")
            
        except TypeError as e:
            # 类型错误（通常是参数类型不匹配）
            error_msg = f"参数类型错误: {str(e)}"
            result.error_message = error_msg
            self.log(f"错误: {error_msg}", "error")
            
        except NotImplementedError as e:
            # 功能未实现错误（子类未正确实现抽象方法）
            error_msg = f"功能未实现: {str(e)}"
            result.error_message = error_msg
            self.log(f"错误: {error_msg}", "error")
            
        except Exception as e:
            # 捕获所有其他异常
            error_msg = f"执行过程中发生未预期的错误: {str(e)}"
            result.error_message = error_msg
            self.log(f"错误: {error_msg}", "error")
            
            # 记录详细的异常信息用于调试
            import traceback
            detailed_error = traceback.format_exc()
            self.log(f"详细错误信息: {detailed_error}", "debug")
            
        finally:
            # 6. 计算并记录执行时间
            end_time = time.time()
            execution_time = end_time - start_time
            result.execution_time = execution_time
            
            # 记录执行完成的日志
            status = "成功" if result.success else "失败"
            self.log(f"工具执行{status}，耗时: {execution_time:.3f}秒", "info")
            
            # 如果执行失败，记录错误摘要
            if not result.success and result.error_message:
                self.log(f"执行失败原因: {result.error_message}", "warning")
        
        # 7. 返回标准化的执行结果
        return result
    
    def _sanitize_log_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        过滤日志参数中的敏感信息
        
        作用：
        1. 移除或脱敏敏感参数（如密码、API密钥等）
        2. 限制参数值的长度，避免日志过长
        3. 保护用户隐私和系统安全
        
        参数:
            params: 原始参数字典
            
        返回:
            Dict[str, Any]: 过滤后的安全参数字典
        """
        
        # 定义敏感参数的关键词（不区分大小写）
        sensitive_keywords = {
            'password', 'passwd', 'pwd', 'secret', 'key', 'token', 
            'api_key', 'apikey', 'access_token', 'auth', 'credential',
            'private', 'confidential', 'sensitive'
        }
        
        # 创建安全的参数副本
        safe_params = {}
        
        for key, value in params.items():
            # 检查参数名是否包含敏感关键词
            key_lower = key.lower()
            is_sensitive = any(keyword in key_lower for keyword in sensitive_keywords)
            
            if is_sensitive:
                # 敏感参数：只显示类型和长度信息
                if isinstance(value, str):
                    safe_params[key] = f"<{type(value).__name__}:length={len(value)}>"
                else:
                    safe_params[key] = f"<{type(value).__name__}:hidden>"
            else:
                # 非敏感参数：限制显示长度
                if isinstance(value, str) and len(value) > 100:
                    # 长字符串截断显示
                    safe_params[key] = f"{value[:50]}...<truncated:total_length={len(value)}>"
                elif isinstance(value, (list, dict)) and len(str(value)) > 200:
                    # 长列表或字典显示摘要信息
                    safe_params[key] = f"<{type(value).__name__}:length={len(value)}>"
                else:
                    # 普通参数直接显示
                    safe_params[key] = value
        
        return safe_params
    
    @abstractmethod
    def validate_parameters(self, **kwargs) -> bool:
        """
        验证输入参数是否符合要求
        
        作用：
        1. 检查必需参数是否存在
        2. 验证参数类型是否正确
        3. 检查参数值是否在有效范围内
        
        实现逻辑：
        1. 获取工具的参数定义
        2. 检查必需参数
        3. 验证参数类型
        4. 检查参数约束条件
        """
        # TODO: 实现参数验证逻辑
        # 1. 获取元数据中的参数定义
        # 2. 检查必需参数是否存在
        # 3. 验证参数类型
        # 4. 检查参数值的有效性
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        检查工具是否可用
        
        作用：
        1. 检查工具的依赖是否满足
        2. 验证必要的资源是否可用
        3. 确保工具能够正常执行
        
        实现逻辑：
        1. 检查Python包依赖
        2. 检查文件系统资源
        3. 检查网络连接（如果需要）
        4. 检查API密钥等配置
        """
        # TODO: 实现可用性检查
        # 1. 检查依赖包是否安装
        # 2. 检查必要的文件和目录
        # 3. 检查网络连接
        # 4. 检查配置和密钥
        pass
    
    def get_usage_example(self) -> Dict[str, Any]:
        """
        获取工具的使用示例
        
        作用：
        1. 为Agent提供工具使用的具体示例
        2. 帮助Agent学习如何正确调用工具
        3. 支持工具的自动测试
        
        返回格式：
        {
            "input_example": {"param1": "value1", "param2": "value2"},
            "expected_output": {"description": "预期输出的描述"},
            "use_cases": ["使用场景1", "使用场景2"]
        }
        """
        # TODO: 实现使用示例生成
        # 1. 提供典型的输入参数示例
        # 2. 描述预期的输出格式
        # 3. 列出常见的使用场景
        pass
    
    def cleanup(self):
        """
        清理工具使用的资源
        
        作用：
        1. 释放工具占用的系统资源
        2. 清理临时文件和缓存
        3. 关闭网络连接和文件句柄
        
        实现逻辑：
        1. 删除临时文件
        2. 关闭打开的文件句柄
        3. 释放内存资源
        4. 断开网络连接
        """
        # TODO: 实现资源清理逻辑
        # 1. 清理临时文件
        # 2. 关闭文件句柄
        # 3. 释放内存
        # 4. 断开连接
        pass
    
    def log(self, message: str, level: str = "info"):
        """
        记录日志信息
        
        作用：
        1. 统一的日志记录接口
        2. 支持多进程环境下的日志传递
        3. 便于调试和监控工具执行
        """
        # TODO: 实现日志记录
        # 1. 格式化日志消息
        # 2. 通过log_queue发送到主进程
        # 3. 同时记录到本地日志
        pass


class ToolRegistry:
    """
    工具注册中心 - 管理所有可用的工具
    
    作用：
    1. 统一管理所有工具的注册和发现
    2. 提供工具的查询和分类功能
    3. 支持工具的动态加载和卸载
    """
    
    def __init__(self):
        """
        初始化工具注册中心
        """
        self._tools: Dict[str, BaseTool] = {}  # 存储所有注册的工具
        self._categories: Dict[str, List[str]] = {}  # 按分类存储工具名称
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def register_tool(self, tool: BaseTool) -> None:
        """
        注册一个新工具到工具注册表中
        
        作用：
        1. 将工具添加到注册表中，使Agent能够发现和使用该工具
        2. 按分类组织工具，便于Agent根据任务类型查找合适的工具
        3. 验证工具的有效性，确保只有可用的工具被注册
        4. 维护工具的元数据信息，支持工具的自动发现和调用
        
        参数:
            tool (BaseTool): 要注册的工具实例，必须继承自BaseTool基类
        
        抛出异常:
            TypeError: 如果传入的不是BaseTool实例
            ValueError: 如果工具名称已存在或工具不可用
            RuntimeError: 如果工具元数据获取失败
        
        实现逻辑：
        1. 验证输入参数的类型和有效性
        2. 获取工具的元数据信息（名称、描述、分类等）
        3. 检查工具名称是否与已注册的工具冲突
        4. 验证工具是否在当前环境中可用
        5. 将工具添加到主工具字典中
        6. 更新分类索引，便于按类别查找工具
        7. 记录注册成功的日志信息
        """
        
        try:
            # 2. 获取工具的元数据
            # 调用工具的get_metadata()方法获取工具的基本信息
            # 这包括工具名称、描述、参数定义、返回类型、分类等
            metadata = tool.get_metadata()
            
            # 验证元数据是否有效
            # 使用更灵活的类型检查，避免模块导入问题
            if not (hasattr(metadata, '__class__') and metadata.__class__.__name__ == 'ToolMetadata'):
                error_msg = f"工具元数据必须是ToolMetadata实例，当前类型: {type(metadata).__name__}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 验证ToolMetadata必需的属性是否存在
            required_attrs = ['name', 'description', 'parameters', 'return_type', 'category']
            for attr in required_attrs:
                if not hasattr(metadata, attr):
                    error_msg = f"工具元数据缺少必需属性: {attr}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)
            
            # 验证工具名称是否存在
            if not metadata.name or not isinstance(metadata.name, str):
                error_msg = "工具名称不能为空且必须是字符串类型"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            tool_name = metadata.name.strip()
            if not tool_name:
                error_msg = "工具名称不能为空字符串"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
        except Exception as e:
            error_msg = f"获取工具元数据失败: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        
        # 3. 检查工具名称是否已存在（避免重复注册）
        if tool_name in self._tools:
            error_msg = f"工具名称 '{tool_name}' 已存在，无法重复注册"
            self.logger.warning(error_msg)
            raise ValueError(error_msg)
        
        # 4. 验证工具是否在当前环境中可用
        # 调用工具的is_available()方法检查依赖项、权限等
        try:
            if not tool.is_available():
                error_msg = f"工具 '{tool_name}' 在当前环境中不可用，请检查依赖项和配置"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"检查工具 '{tool_name}' 可用性时发生错误: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        # 5. 将工具添加到主工具字典中
        # _tools字典的结构: {"tool_name": tool_instance}
        self._tools[tool_name] = tool
        
        # 6. 更新分类索引
        # 获取工具的分类信息，如果没有指定分类则使用默认分类
        category = getattr(metadata, 'category', 'general')
        if not category or not isinstance(category, str):
            category = 'general'  # 默认分类
        
        category = category.strip().lower()  # 标准化分类名称
        
        # 如果该分类还不存在，创建新的分类列表
        if category not in self._categories:
            self._categories[category] = []
        
        # 将工具名称添加到对应分类的列表中
        # _categories字典的结构: {"category_name": ["tool1", "tool2", ...]}
        if tool_name not in self._categories[category]:
            self._categories[category].append(tool_name)
        
        # 7. 记录成功注册的日志
        self.logger.info(f"工具 '{tool_name}' 注册成功，分类: '{category}'")
        
        # 可选：记录详细的调试信息
        self.logger.debug(f"工具详细信息 - 名称: {tool_name}, 描述: {metadata.description[:100]}..., 版本: {getattr(metadata, 'version', 'unknown')}")
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        注销一个工具
        
        作用：
        1. 从注册表中移除工具
        2. 清理相关的分类信息
        3. 释放工具占用的资源
        """
        # TODO: 实现工具注销逻辑
        # 1. 检查工具是否存在
        # 2. 调用工具的cleanup方法
        # 3. 从注册表中移除
        # 4. 更新分类索引
        pass
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        根据名称获取工具实例
        
        作用：
        1. 为Agent提供工具查询接口
        2. 支持工具的动态获取
        3. 处理工具不存在的情况
        """
        # TODO: 实现工具获取逻辑
        # 1. 检查工具是否存在
        # 2. 验证工具是否可用
        # 3. 返回工具实例或None
        pass
    
    def list_available_tools(self) -> List[ToolMetadata]:
        """
        列出所有可用工具的元数据
        
        作用：
        1. 为Agent提供工具发现功能
        2. 支持工具的批量查询
        3. 过滤不可用的工具
        """
        # TODO: 实现工具列表生成
        # 1. 遍历所有注册的工具
        # 2. 检查工具可用性
        # 3. 收集工具元数据
        # 4. 返回元数据列表
        pass
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """
        按分类获取工具列表
        
        作用：
        1. 支持按功能分类查找工具
        2. 便于Agent选择合适的工具
        3. 提高工具发现的效率
        """
        # TODO: 实现分类查询逻辑
        # 1. 检查分类是否存在
        # 2. 获取该分类下的工具名称
        # 3. 返回工具实例列表
        pass
    
    def search_tools(self, keyword: str) -> List[ToolMetadata]:
        """
        根据关键词搜索工具
        
        作用：
        1. 支持模糊搜索工具
        2. 基于工具名称和描述进行匹配
        3. 提高工具发现的灵活性
        """
        # TODO: 实现工具搜索逻辑
        # 1. 遍历所有工具的元数据
        # 2. 在名称和描述中搜索关键词
        # 3. 返回匹配的工具元数据
        pass
    
    def get_categories(self) -> List[str]:
        """
        获取所有可用的工具分类列表
        
        作用：
        1. 为Agent提供分类浏览功能
        2. 支持按分类组织工具展示
        3. 便于了解系统中有哪些类型的工具
        
        返回:
            List[str]: 所有分类名称的列表
        """
        # TODO: 实现分类列表获取
        # 1. 返回_categories字典的所有键
        # 2. 过滤掉空分类
        # 3. 按字母顺序排序
        pass
    
    def get_tool_count(self) -> Dict[str, int]:
        """
        获取工具数量统计信息
        
        作用：
        1. 提供系统工具的统计概览
        2. 支持监控和管理功能
        3. 便于了解各分类下的工具分布
        
        返回:
            Dict[str, int]: 包含总数和各分类数量的统计信息
            格式: {
                "total": 总工具数,
                "available": 可用工具数,
                "categories": {
                    "分类名": 该分类工具数,
                    ...
                }
            }
        """
        # TODO: 实现工具数量统计
        # 1. 统计总工具数
        # 2. 统计可用工具数
        # 3. 统计各分类的工具数量
        # 4. 返回结构化的统计信息
        pass
    
    def is_tool_registered(self, tool_name: str) -> bool:
        """
        检查指定工具是否已注册
        
        作用：
        1. 避免重复注册同名工具
        2. 支持工具存在性检查
        3. 便于条件性工具操作
        
        参数:
            tool_name: 要检查的工具名称
            
        返回:
            bool: True表示工具已注册，False表示未注册
        """
        # TODO: 实现工具注册检查
        # 1. 检查工具名称是否在_tools字典中
        # 2. 返回布尔结果
        pass
    
    def refresh_tools(self) -> Dict[str, bool]:
        """
        刷新所有工具的可用性状态
        
        作用：
        1. 重新检查所有工具的可用性
        2. 更新工具状态信息
        3. 识别因环境变化而不可用的工具
        
        返回:
            Dict[str, bool]: 各工具的可用性状态
            格式: {"工具名": True/False, ...}
        """
        # TODO: 实现工具可用性刷新
        # 1. 遍历所有注册的工具
        # 2. 调用每个工具的is_available()方法
        # 3. 收集并返回可用性状态
        # 4. 可选：记录状态变化的日志
        pass


def tool(name: str, description: str, category: str = "general", version: str = "1.0.0"):
    """
    工具装饰器 - 简化工具的定义和注册
    
    作用：
    1. 通过装饰器简化工具类的定义
    2. 自动生成部分元数据信息
    3. 支持声明式的工具开发
    
    使用示例：
    @tool(name="my_tool", description="我的工具", category="custom")
    class MyTool(BaseTool):
        # 工具实现
        pass
    """
    def decorator(cls):
        # TODO: 实现装饰器逻辑
        # 1. 验证类是否继承自BaseTool
        # 2. 为类添加元数据属性
        # 3. 可选：自动注册到全局注册表
        return cls
    return decorator


def validate_tool_result(result: ToolResult) -> bool:
    """
    验证工具结果的格式是否正确
    
    作用：
    1. 确保工具返回结果的一致性
    2. 验证必需字段是否存在
    3. 检查数据类型是否正确
    """
    # TODO: 实现结果验证逻辑
    # 1. 检查必需字段
    # 2. 验证字段类型
    # 3. 检查数据的合理性
    pass


# 全局工具注册表实例
default_registry = ToolRegistry()


def get_default_registry() -> ToolRegistry:
    """
    获取默认的工具注册表实例
    
    作用：
    1. 提供全局统一的工具注册表
    2. 简化工具的注册和使用
    3. 支持单例模式的工具管理
    """
    return default_registry