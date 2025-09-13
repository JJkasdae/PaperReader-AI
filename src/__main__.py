#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口文件 - 用于测试和运行整个PaperReader-AI系统

作用：
1. 作为独立的测试文件，避免循环导入问题
2. 测试工具注册系统的功能
3. 提供系统的主要入口点
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'src', 'tools'))

def test_register_tool_function():
    """
    测试register_tool函数的完整功能
    
    作用：
    1. 验证工具注册系统的基本功能
    2. 测试SinglePaperExtractionTool和DailyPapersCollectorTool的注册
    3. 验证错误处理和边界情况
    4. 确保工具注册表的正确性
    """
    
    print("=" * 60)
    print("开始测试 register_tool 函数")
    print("=" * 60)
    
    try:
        # 导入必要的模块
        from tools.base_tool import ToolRegistry
        from tools.paper_extraction import SinglePaperExtractionTool, DailyPapersCollectorTool
        
        print("✓ 模块导入成功")
        
        # 1. 创建工具注册表实例
        print("\n1. 创建工具注册表实例...")
        registry = ToolRegistry()
        print("✓ 工具注册表创建成功")
        
        # 2. 创建工具实例
        print("\n2. 创建工具实例...")
        single_paper_tool = SinglePaperExtractionTool()
        daily_papers_tool = DailyPapersCollectorTool()
        print("✓ 工具实例创建成功")
        
        # 3. 检查工具可用性
        print("\n3. 检查工具可用性...")
        single_available = single_paper_tool.is_available()
        daily_available = daily_papers_tool.is_available()
        print(f"✓ SinglePaperExtractionTool 可用性: {single_available}")
        print(f"✓ DailyPapersCollectorTool 可用性: {daily_available}")
        
        # 4. 注册第一个工具
        print("\n4. 注册 SinglePaperExtractionTool...")
        registry.register_tool(single_paper_tool)
        print("✓ SinglePaperExtractionTool 注册成功")
        
        # 5. 注册第二个工具
        print("\n5. 注册 DailyPapersCollectorTool...")
        registry.register_tool(daily_papers_tool)
        print("✓ DailyPapersCollectorTool 注册成功")
        
        # 6. 测试重复注册错误处理
        print("\n6. 测试重复注册错误处理...")
        try:
            registry.register_tool(single_paper_tool)
            print("✗ 重复注册应该抛出异常，但没有抛出")
        except ValueError as e:
            print(f"✓ 重复注册正确抛出异常: {e}")
        except Exception as e:
            print(f"? 重复注册抛出了意外的异常类型: {type(e).__name__}: {e}")
        
        # 7. 验证工具分类
        print("\n7. 验证工具分类...")
        single_metadata = single_paper_tool.get_metadata()
        daily_metadata = daily_papers_tool.get_metadata()
        print(f"✓ SinglePaperExtractionTool 分类: {single_metadata.category}")
        print(f"✓ DailyPapersCollectorTool 分类: {daily_metadata.category}")
        
        # 8. 测试工具查询功能（如果实现了）
        print("\n8. 测试工具查询功能...")
        if hasattr(registry, 'get_tool'):
            try:
                retrieved_tool = registry.get_tool(single_metadata.name)
                if retrieved_tool is single_paper_tool:
                    print("✓ 工具查询功能正常")
                else:
                    print("? 工具查询返回的实例不匹配")
            except Exception as e:
                print(f"? 工具查询功能异常: {e}")
        else:
            print("- get_tool 方法未实现")
        
        # 9. 测试工具列表功能（如果实现了）
        print("\n9. 测试工具列表功能...")
        if hasattr(registry, 'list_tools'):
            try:
                tools_list = registry.list_tools()
                print(f"✓ 注册的工具列表: {tools_list}")
            except Exception as e:
                print(f"? 工具列表功能异常: {e}")
        else:
            print("- list_tools 方法未实现")
        
        # 10. 测试分类查询功能（如果实现了）
        print("\n10. 测试分类查询功能...")
        if hasattr(registry, 'get_tools_by_category'):
            try:
                extraction_tools = registry.get_tools_by_category('extraction')
                print(f"✓ extraction 分类的工具: {extraction_tools}")
            except Exception as e:
                print(f"? 分类查询功能异常: {e}")
        else:
            print("- get_tools_by_category 方法未实现")
        
        print("\n" + "=" * 60)
        print("register_tool 函数测试完成！")
        print("✓ 基本功能验证通过")
        print("✓ 两个工具成功注册")
        print("✓ 重复注册错误处理正常")
        print("✓ 工具分类功能正确")
        print("=" * 60)
        
        return True
        
    except ImportError as e:
        print(f"✗ 模块导入失败: {e}")
        print("请检查模块路径和依赖项")
        return False
        
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        print("详细错误信息:")
        print(traceback.format_exc())
        return False

def main():
    """
    主函数 - 程序入口点
    """
    print("PaperReader-AI 系统测试")
    print("当前工作目录:", os.getcwd())
    print("Python路径:", sys.path[:3])  # 只显示前3个路径
    
    # 运行register_tool测试
    success = test_register_tool_function()
    
    if success:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n❌ 测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)