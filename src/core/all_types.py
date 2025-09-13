"""
纯数据类型定义模块
作用：定义系统中所有的数据结构，不包含任何业务逻辑
原则：只定义数据，不定义行为
"""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime

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
    return_description: Dict[str, Any]  # 详细的返回值描述，包含schema和字段说明

    # 可选属性 - 有默认值的字段必须在后面
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

@dataclass
class AgentConfig:
    """Agent配置信息"""
    name: str
    description: str
    available_tools: List[str]
    max_iterations: int = 10
    timeout: float = 30.0