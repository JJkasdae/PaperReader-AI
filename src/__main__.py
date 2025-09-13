"""
开发测试入口
作用：用于开发阶段的测试和调试
"""
# 统一导入路径
from core import ToolManager
from tools import SinglePaperExtractionTool, DailyPapersCollectorTool
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

def test_tool_manager():
    """按指定顺序测试工具管理器功能"""
    
    registry = ToolManager()
    
    # 创建工具实例
    single_tool = SinglePaperExtractionTool()
    daily_tool = DailyPapersCollectorTool()
    
    print("=== 工具管理器功能测试 ===")
    print("按照指定顺序执行测试...\n")
    
    try:
        # 1. 注册现在可用的两个工具
        print("1️⃣ 注册工具测试")
        print("-" * 30)
        
        # 注册第一个工具
        registry.register_tool(single_tool)
        print(f"✓ 成功注册工具: {single_tool.get_metadata().name}")
        
        # 注册第二个工具
        registry.register_tool(daily_tool)
        print(f"✓ 成功注册工具: {daily_tool.get_metadata().name}")
        
        print(f"✓ 工具注册完成，共注册 {len(registry._tools)} 个工具\n")
        
        # 2. 列出工具数量统计
        print("2️⃣ 工具数量统计测试")
        print("-" * 30)
        
        stats = registry.get_tool_count()
        if isinstance(stats, dict):
            total_tools = stats.get('total', 0)
            categories = stats.get('categories', {})
            category_count = stats.get('category_count', 0)
            
            print(f"📊 统计结果:")
            print(f"   - 总工具数: {total_tools}")
            print(f"   - 分类总数: {category_count}")
            
            if categories:
                print(f"   - 分类详情:")
                for category, count in categories.items():
                    print(f"     * {category}: {count} 个工具")
            
            print(f"✓ 工具统计功能正常\n")
        else:
            print(f"✗ 工具统计功能异常: {type(stats)}\n")
        
        # 3. 列出所有的可用工具
        print("3️⃣ 可用工具列表测试")
        print("-" * 30)
        
        available_tools = registry.list_available_tools()
        if available_tools:
            print(f"📋 可用工具列表 (共 {len(available_tools)} 个):")
            for i, metadata in enumerate(available_tools, 1):
                print(f"   {i}. {metadata.name}")
                print(f"      描述: {metadata.description[:60]}{'...' if len(metadata.description) > 60 else ''}")
                print(f"      分类: {getattr(metadata, 'category', '未指定')}")
            print(f"✓ 工具列表功能正常\n")
        else:
            print(f"✗ 工具列表为空\n")
            
        # 4. 获取一个工具
        print("4️⃣ 工具获取测试")
        print("-" * 30)
        
        # 获取第一个已注册的工具
        tool_name_to_get = single_tool.get_metadata().name
        retrieved_tool = registry.get_tool(tool_name_to_get)
        
        if retrieved_tool is not None:
            print(f"✓ 成功获取工具: {tool_name_to_get}")
            print(f"   工具类型: {type(retrieved_tool).__name__}")
            print(f"   工具描述: {retrieved_tool.get_metadata().description[:50]}...")
        else:
            print(f"✗ 获取工具失败: {tool_name_to_get}")
        
        # 测试获取不存在的工具
        non_existent_tool = registry.get_tool("不存在的工具")
        if non_existent_tool is None:
            print("✓ 正确处理不存在工具的获取请求")
        else:
            print("✗ 不存在工具获取检测失败")
        
        print(f"✓ 工具获取功能正常\n")
    
        # 5. 注销一个工具
        print("5️⃣ 工具注销测试")
        print("-" * 30)
        
        # 注销第一个工具
        tool_to_unregister = single_tool.get_metadata().name
        result = registry.unregister_tool(tool_to_unregister)
        
        if result:
            print(f"✓ 成功注销工具: {tool_to_unregister}")
        else:
            print(f"✗ 注销工具失败: {tool_to_unregister}")
        
        # 验证注销结果
        print(f"   注销后工具数量: {len(registry._tools)}")
        print(f"   剩余工具: {list(registry._tools.keys())}")
        
        # 测试注销不存在的工具
        result = registry.unregister_tool("不存在的工具")
        if not result:
            print("✓ 正确处理不存在工具的注销请求")
        else:
            print("✗ 不存在工具注销检测失败")
        
        print(f"✓ 工具注销功能正常\n")
        
        # 6. 检查一个工具是否被注册
        print("6️⃣ 工具注册状态检查测试")
        print("-" * 30)
        
        # 检查已注册的工具
        remaining_tools = list(registry._tools.keys())
        if remaining_tools:
            test_tool_name = remaining_tools[0]
            is_registered = registry.is_tool_registered(test_tool_name)
            if is_registered:
                print(f"✓ 工具 '{test_tool_name}' 注册状态: 已注册")
            else:
                print(f"✗ 工具 '{test_tool_name}' 注册状态检查错误")
        
        # 检查已注销的工具
        is_registered = registry.is_tool_registered(tool_to_unregister)
        if not is_registered:
            print(f"✓ 工具 '{tool_to_unregister}' 注册状态: 已注销")
        else:
            print(f"✗ 工具 '{tool_to_unregister}' 注册状态检查错误")
        
        # 检查从未注册的工具
        fake_tool_name = "never_registered_tool"
        is_registered = registry.is_tool_registered(fake_tool_name)
        if not is_registered:
            print(f"✓ 工具 '{fake_tool_name}' 注册状态: 未注册")
        else:
            print(f"✗ 工具 '{fake_tool_name}' 注册状态检查错误")
        
        print(f"✓ 工具注册状态检查功能正常\n")
        
        print("=== 所有测试完成 ===")
        print(f"最终状态: 共有 {len(registry._tools)} 个已注册工具")
        if registry._tools:
            print(f"已注册工具: {list(registry._tools.keys())}")
                
    except Exception as e:
        print(f"✗ 工具注册失败: {e}")

if __name__ == "__main__":
    test_tool_manager()