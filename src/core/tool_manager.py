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
        
        # 3. 记录成功获取的日志信息并返回工具实例
        # 由于工具在注册时已经验证过可用性，这里直接返回
        self.logger.debug(f"成功获取工具: '{tool_name}'")
        return tool_instance
    
    def list_available_tools(self) -> List[ToolMetadata]:
        """
        列出所有已注册工具的元数据
        
        作用：
        1. 为Agent提供工具发现功能 - Agent可以通过此方法了解系统中有哪些工具可用
        2. 支持工具的批量查询 - 一次性获取所有工具信息，避免多次单独查询
        3. 提供完整的工具元数据 - 包括工具名称、描述、参数定义等详细信息
        4. 返回所有已注册的工具 - 由于工具在注册时已验证可用性，无需重复检查
        
        返回:
            List[ToolMetadata]: 所有已注册工具的元数据列表
            每个元数据包含工具的完整信息，如名称、描述、参数、分类等
            
        实现逻辑：
        1. 遍历所有已注册的工具实例
        2. 收集工具的元数据信息
        3. 验证元数据的有效性和完整性
        4. 按工具名称排序并返回列表
        5. 记录操作日志便于调试和监控
        
        使用场景：
        - Agent启动时发现可用工具
        - 动态展示工具列表给用户
        - 工具管理和监控界面
        - 系统健康检查和诊断
        """
        
        available_tools = []  # 存储可用工具的元数据列表
        
        # 1. 遍历所有已注册的工具实例
        # _tools字典结构: {"tool_name": tool_instance}
        # 由于工具在注册时已经验证过可用性，这里直接收集元数据
        for tool_name, tool_instance in self._tools.items():
            try:
                # 2. 收集工具的元数据信息
                # 调用工具的get_metadata()方法获取完整的工具信息
                metadata = tool_instance.get_metadata()
                
                # 验证元数据的有效性
                if not isinstance(metadata, ToolMetadata):
                    self.logger.warning(f"工具 '{tool_name}' 的元数据类型无效，跳过")
                    continue
                
                # 验证元数据的完整性
                if not metadata.name or not isinstance(metadata.name, str):
                    self.logger.warning(f"工具 '{tool_name}' 的元数据名称无效，跳过")
                    continue
                
                # 将有效的元数据添加到结果列表中
                available_tools.append(metadata)
                self.logger.debug(f"成功收集工具元数据: '{tool_name}'")
                
            except Exception as e:
                # 处理单个工具元数据获取过程中的异常
                # 记录错误但不中断整个列表生成过程
                self.logger.error(f"获取工具 '{tool_name}' 元数据时发生错误: {str(e)}")
                continue
        
        # 4. 按工具名称排序并返回列表
        # 使用工具名称进行字母排序，提供一致的工具顺序
        try:
            available_tools.sort(key=lambda metadata: metadata.name.lower())
        except Exception as e:
            # 排序失败时记录警告，但仍返回未排序的列表
            self.logger.warning(f"工具列表排序失败: {str(e)}")
        
        # 4. 记录操作日志便于调试和监控
        total_registered = len(self._tools)
        total_collected = len(available_tools)
        self.logger.info(f"工具列表生成完成 - 已注册: {total_registered}, 成功收集: {total_collected}")
        
        # 可选：记录详细的调试信息
        if available_tools:
            tool_names = [metadata.name for metadata in available_tools]
            self.logger.debug(f"已注册工具列表: {', '.join(tool_names)}")
        else:
            self.logger.warning("当前没有已注册的工具")
        
        return available_tools
    
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
    
    def get_tool_count(self) -> Dict[str, Any]:
        """
        获取工具数量统计信息
        
        作用：
        1. 提供系统工具的统计概览 - 让Agent和用户了解当前系统中工具的整体情况
        2. 支持监控和管理功能 - 便于系统管理员监控工具注册状态和分布情况
        3. 便于了解各分类下的工具分布 - 帮助分析工具生态的完整性和平衡性
        4. 支持系统诊断和调试 - 通过统计信息快速识别潜在问题
        
        返回:
            Dict[str, Any]: 包含总数和各分类数量的统计信息
            格式: {
                "total": 总工具数 (int),
                "categories": {
                    "分类名": 该分类工具数 (int),
                    ...
                },
                "category_count": 分类总数 (int)
            }
            
        实现逻辑：
        1. 统计已注册工具的总数
        2. 统计各分类下的工具数量
        3. 计算分类总数
        4. 构建并返回结构化的统计信息
        5. 记录统计操作的日志信息
        
        使用场景：
        - 系统启动时的状态检查
        - 管理界面的统计展示
        - 系统健康监控和报告
        - 工具生态分析和优化
        """
        
        try:
            # 1. 统计已注册工具的总数
            # _tools字典包含所有已注册的工具实例
            total_tools = len(self._tools)
            
            # 2. 统计各分类下的工具数量
            # _categories字典结构: {"category_name": ["tool1", "tool2", ...]}
            category_stats = {}
            
            # 遍历所有分类，统计每个分类下的工具数量
            for category_name, tool_list in self._categories.items():
                # 确保分类名称有效
                if category_name and isinstance(tool_list, list):
                    category_stats[category_name] = len(tool_list)
                    self.logger.debug(f"分类 '{category_name}' 包含 {len(tool_list)} 个工具")
                else:
                    # 处理无效分类数据
                    self.logger.warning(f"发现无效分类数据: {category_name}")
                    continue
            
            # 3. 计算分类总数
            total_categories = len(category_stats)
            
            # 4. 构建并返回结构化的统计信息
            statistics = {
                "total": total_tools,
                "categories": category_stats,
                "category_count": total_categories
            }
            
            # 5. 记录统计操作的日志信息
            self.logger.info(f"工具统计完成 - 总工具数: {total_tools}, 分类数: {total_categories}")
            
            # 可选：记录详细的调试信息
            if category_stats:
                category_summary = ", ".join([f"{cat}: {count}" for cat, count in category_stats.items()])
                self.logger.debug(f"分类详情: {category_summary}")
            else:
                self.logger.debug("当前没有工具分类")
            
            # 数据一致性验证
            # 验证分类中的工具总数是否与注册表中的工具总数一致
            category_tool_sum = sum(category_stats.values())
            if category_tool_sum != total_tools:
                self.logger.warning(
                    f"数据一致性警告: 分类中工具总数({category_tool_sum}) "
                    f"与注册表工具总数({total_tools})不一致"
                )
            
            return statistics
            
        except Exception as e:
            # 处理统计过程中的异常
            error_msg = f"获取工具统计信息时发生错误: {str(e)}"
            self.logger.error(error_msg)
            
            # 返回基本的错误状态统计
            # 即使发生错误，也尽量提供一些基本信息
            try:
                basic_stats = {
                    "total": len(self._tools) if hasattr(self, '_tools') else 0,
                    "categories": {},
                    "category_count": 0,
                    "error": str(e)
                }
                return basic_stats
            except:
                # 如果连基本统计都无法获取，返回空统计
                return {
                    "total": 0,
                    "categories": {},
                    "category_count": 0,
                    "error": "无法获取工具统计信息"
                }
    
    def is_tool_registered(self, tool_name: str) -> bool:
        """
        检查指定工具是否已注册
        
        作用：
        1. 避免重复注册同名工具 - 在注册新工具前检查是否已存在同名工具
        2. 支持工具存在性检查 - 为Agent提供工具可用性的快速查询接口
        3. 便于条件性工具操作 - 支持基于工具存在性的条件逻辑处理
        4. 提供轻量级查询 - 相比get_tool方法，这是更轻量的存在性检查
        
        参数:
            tool_name (str): 要检查的工具名称，必须是非空字符串
            
        返回:
            bool: True表示工具已注册，False表示未注册或工具名称无效
            
        抛出异常:
            ValueError: 如果工具名称为空或不是字符串类型
            
        实现逻辑：
        1. 验证输入参数的有效性（类型和内容检查）
        2. 标准化工具名称（去除首尾空格）
        3. 在工具注册表中查找指定工具
        4. 返回查找结果的布尔值
        5. 记录查询操作的调试日志
        
        使用场景：
        - 工具注册前的重复性检查
        - Agent执行任务前的工具可用性验证
        - 条件性工具加载和管理
        - 系统诊断和工具清单验证
        - 动态工具发现和管理流程
        
        性能特点：
        - O(1) 时间复杂度的字典查找
        - 轻量级操作，适合频繁调用
        - 无副作用，不影响工具状态
        """
        
        # 1. 验证输入参数的有效性
        # 检查工具名称是否为字符串类型
        if not isinstance(tool_name, str):
            error_msg = f"工具名称必须是字符串类型，当前类型: {type(tool_name).__name__}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 检查工具名称是否为空
        if not tool_name:
            error_msg = "工具名称不能为空字符串"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 2. 标准化工具名称
        # 去除首尾空格，确保查找的准确性
        normalized_name = tool_name.strip()
        
        # 再次检查标准化后的名称是否为空
        if not normalized_name:
            error_msg = "工具名称不能为空白字符串"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 3. 在工具注册表中查找指定工具
        # _tools字典结构: {"tool_name": tool_instance}
        # 使用字典的 'in' 操作符进行O(1)时间复杂度的查找
        is_registered = normalized_name in self._tools
        
        # 4. 记录查询操作的调试日志
        # 根据查找结果记录不同级别的日志
        if is_registered:
            self.logger.debug(f"工具 '{normalized_name}' 已注册")
        else:
            self.logger.debug(f"工具 '{normalized_name}' 未注册")
        
        # 可选：记录详细的统计信息（仅在调试模式下）
        # 这有助于了解工具查询的模式和频率
        total_registered = len(self._tools)
        self.logger.debug(f"当前已注册工具总数: {total_registered}")
        
        # 5. 返回查找结果的布尔值
        return is_registered
    
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
