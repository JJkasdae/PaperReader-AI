from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import time
from .all_types import ToolMetadata, ToolResult

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


class BaseAgent(ABC):
    """Agent基类 - 所有Agent的抽象接口"""
    
    @abstractmethod
    def execute_task(self, task: str) -> Dict[str, Any]:
        """执行任务"""
        pass
    
    @abstractmethod
    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        pass