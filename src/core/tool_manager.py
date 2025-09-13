from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import time
from .all_types import ToolMetadata, ToolResult
from .interfaces import BaseTool
from .exceptions import ToolRegistrationError

class ToolManager:
    """
    工具管理中心 - 管理所有可用的工具
    
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
            
            # 更简洁、更Pythonic的方式
            if not isinstance(metadata, ToolMetadata):
                error_msg = f"工具元数据必须是ToolMetadata实例，当前类型: {type(metadata).__name__}"
                self.logger.error(error_msg)
                raise ToolRegistrationError(error_msg)  # 使用专门的异常类型
            
            # 验证工具名称
            if not metadata.name or not isinstance(metadata.name, str):
                error_msg = "工具名称不能为空且必须是字符串类型"
                self.logger.error(error_msg)
                raise ToolRegistrationError(error_msg)
            
            tool_name = metadata.name.strip()
            if not tool_name:
                error_msg = "工具名称不能为空字符串"
                self.logger.error(error_msg)
                raise ToolRegistrationError(error_msg)
            
        except Exception as e:
            error_msg = f"获取工具元数据失败: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        
        # 3. 检查工具名称是否已存在（避免重复注册）
        if tool_name in self._tools:
            error_msg = f"工具名称 '{tool_name}' 已存在，无法重复注册"
            self.logger.warning(error_msg)
            raise ToolRegistrationError(error_msg)
        
        # 4. 验证工具是否在当前环境中可用
        # 调用工具的is_available()方法检查依赖项、权限等
        try:
            if not tool.is_available():
                error_msg = f"工具 '{tool_name}' 在当前环境中不可用，请检查依赖项和配置"
                self.logger.warning(error_msg)
                raise ToolRegistrationError(error_msg)
        except Exception as e:
            error_msg = f"检查工具 '{tool_name}' 可用性时发生错误: {str(e)}"
            self.logger.error(error_msg)
            raise ToolRegistrationError(error_msg) from e
        
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
        
        参数:
            tool_name (str): 要注销的工具名称
            
        返回:
            bool: True表示注销成功，False表示工具不存在
            
        抛出异常:
            ValueError: 如果工具名称为空或无效
            RuntimeError: 如果工具清理过程中发生错误
            
        实现逻辑：
        1. 验证输入参数的有效性
        2. 检查工具是否存在于注册表中
        3. 调用工具的cleanup方法释放资源
        4. 从主工具字典中移除工具
        5. 从分类索引中清理工具引用
        6. 清理空的分类
        7. 记录注销成功的日志信息
        """
        
        # 1. 验证输入参数的有效性
        if not tool_name or not isinstance(tool_name, str):
            error_msg = "工具名称不能为空且必须是字符串类型"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        tool_name = tool_name.strip()
        if not tool_name:
            error_msg = "工具名称不能为空字符串"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 2. 检查工具是否存在于注册表中
        if tool_name not in self._tools:
            self.logger.warning(f"工具 '{tool_name}' 不存在，无法注销")
            return False
        
        # 获取要注销的工具实例
        tool_instance = self._tools[tool_name]
        
        try:
            # 3. 调用工具的cleanup方法释放资源
            # 检查工具是否有cleanup方法，如果有则调用
            if hasattr(tool_instance, 'cleanup') and callable(getattr(tool_instance, 'cleanup')):
                try:
                    tool_instance.cleanup()
                    self.logger.debug(f"工具 '{tool_name}' 清理方法执行成功")
                except Exception as cleanup_error:
                    # 清理失败不应该阻止注销过程，但需要记录警告
                    self.logger.warning(f"工具 '{tool_name}' 清理方法执行失败: {str(cleanup_error)}")
            
            # 4. 从主工具字典中移除工具
            del self._tools[tool_name]
            
            # 5. 从分类索引中清理工具引用
            # 遍历所有分类，找到包含该工具的分类并移除
            categories_to_clean = []  # 记录需要清理的空分类
            
            for category, tool_list in self._categories.items():
                if tool_name in tool_list:
                    # 从分类列表中移除工具名称
                    tool_list.remove(tool_name)
                    self.logger.debug(f"从分类 '{category}' 中移除工具 '{tool_name}'")
                    
                    # 6. 标记空分类以便后续清理
                    if not tool_list:  # 如果分类变为空
                        categories_to_clean.append(category)
            
            # 清理空的分类
            for empty_category in categories_to_clean:
                del self._categories[empty_category]
                self.logger.debug(f"清理空分类: '{empty_category}'")
            
            # 7. 记录注销成功的日志信息
            self.logger.info(f"工具 '{tool_name}' 注销成功")
            
            # 可选：记录详细的调试信息
            remaining_tools = len(self._tools)
            remaining_categories = len(self._categories)
            self.logger.debug(f"注销后统计 - 剩余工具数: {remaining_tools}, 剩余分类数: {remaining_categories}")
            
            return True
            
        except Exception as e:
            # 如果注销过程中发生错误，记录错误并重新抛出
            error_msg = f"注销工具 '{tool_name}' 时发生错误: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        根据名称获取工具实例
        
        作用：
        1. 为Agent提供工具查询接口
        2. 支持工具的动态获取
        3. 处理工具不存在的情况
        
        参数:
            tool_name (str): 要获取的工具名称
            
        返回:
            Optional[BaseTool]: 工具实例，如果工具不存在或不可用则返回None
            
        抛出异常:
            ValueError: 如果工具名称为空或无效
            
        实现逻辑：
        1. 验证输入参数的有效性
        2. 检查工具是否存在于注册表中
        3. 验证工具是否在当前环境中可用
        4. 返回工具实例或None
        5. 记录获取操作的日志信息
        
        使用场景：
        - Agent需要根据名称获取特定工具时
        - 在执行任务前检查工具是否可用
        - 动态工具调用和管理
        """
        
        # 1. 验证输入参数的有效性
        if not tool_name or not isinstance(tool_name, str):
            error_msg = "工具名称不能为空且必须是字符串类型"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        tool_name = tool_name.strip()
        if not tool_name:
            error_msg = "工具名称不能为空字符串"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 2. 检查工具是否存在于注册表中
        if tool_name not in self._tools:
            self.logger.debug(f"工具 '{tool_name}' 不存在于注册表中")
            return None
        
        # 获取工具实例
        tool_instance = self._tools[tool_name]
        
        try:
            # 3. 验证工具是否在当前环境中可用
            # 调用工具的is_available()方法检查依赖项、权限等
            # 这确保返回的工具在当前环境中是可以正常使用的
            if not tool_instance.is_available():
                self.logger.warning(f"工具 '{tool_name}' 存在但当前不可用，请检查依赖项和配置")
                return None
            
            # 4. 记录成功获取的日志信息
            self.logger.debug(f"成功获取工具: '{tool_name}'")
            
            # 5. 返回可用的工具实例
            return tool_instance
            
        except Exception as e:
            # 如果检查可用性时发生错误，记录错误并返回None
            # 这里不抛出异常，而是返回None，因为这是一个查询操作
            # Agent可以根据返回值判断工具是否可用
            error_msg = f"检查工具 '{tool_name}' 可用性时发生错误: {str(e)}"
            self.logger.error(error_msg)
            return None
    
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
