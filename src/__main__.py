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

def test_tool_registration():
    """测试工具注册功能"""
    
    registry = ToolManager()
    
    # 注册工具
    single_tool = SinglePaperExtractionTool()
    daily_tool = DailyPapersCollectorTool()
    
    print("开始测试工具注册...")
    
    try:
        # 测试注册第一个工具
        registry.register_tool(single_tool)
        print(f"✓ 成功注册工具: {single_tool.get_metadata().name}")
        
        # 测试注册第二个工具
        registry.register_tool(daily_tool)
        print(f"✓ 成功注册工具: {daily_tool.get_metadata().name}")
        
        # 测试重复注册（应该抛出异常）
        try:
            registry.register_tool(single_tool)
            print("✗ 重复注册检测失败")
        except Exception as e:
            print(f"✓ 重复注册检测正常: {e}")
            
        print(f"\n当前已注册工具数量: {len(registry._tools)}")
        print(f"已注册工具名称: {list(registry._tools.keys())}")
        print(f"工具分类: {dict(registry._categories)}")
        
        # 测试工具注销功能
        print("\n开始测试工具注销...")
        
        # 测试注销存在的工具
        tool_to_unregister = single_tool.get_metadata().name
        result = registry.unregister_tool(tool_to_unregister)
        if result:
            print(f"✓ 成功注销工具: {tool_to_unregister}")
        else:
            print(f"✗ 注销工具失败: {tool_to_unregister}")
            
        # 测试注销不存在的工具
        try:
            result = registry.unregister_tool("不存在的工具")
            if not result:
                print("✓ 正确处理不存在工具的注销请求")
            else:
                print("✗ 不存在工具注销检测失败")
        except Exception as e:
            print(f"✗ 注销不存在工具时发生异常: {e}")
            
        # 测试无效参数
        try:
            registry.unregister_tool("")
            print("✗ 空字符串参数验证失败")
        except ValueError:
            print("✓ 空字符串参数验证正常")
        except Exception as e:
            print(f"✗ 空字符串参数验证异常: {e}")
            
        print(f"\n注销后工具数量: {len(registry._tools)}")
        print(f"剩余工具名称: {list(registry._tools.keys())}")
        print(f"剩余工具分类: {dict(registry._categories)}")
        
        # 测试工具获取功能
        print("\n开始测试工具获取...")
        
        # 测试获取存在的工具
        remaining_tool_name = daily_tool.get_metadata().name
        retrieved_tool = registry.get_tool(remaining_tool_name)
        if retrieved_tool is not None:
            print(f"✓ 成功获取工具: {remaining_tool_name}")
            print(f"  工具类型: {type(retrieved_tool).__name__}")
            print(f"  工具描述: {retrieved_tool.get_metadata().description[:50]}...")
        else:
            print(f"✗ 获取工具失败: {remaining_tool_name}")
            
        # 测试获取不存在的工具
        non_existent_tool = registry.get_tool("不存在的工具")
        if non_existent_tool is None:
            print("✓ 正确处理不存在工具的获取请求")
        else:
            print("✗ 不存在工具获取检测失败")
            
        # 测试无效参数
        try:
            registry.get_tool("")
            print("✗ 空字符串参数验证失败")
        except ValueError:
            print("✓ 空字符串参数验证正常")
        except Exception as e:
            print(f"✗ 空字符串参数验证异常: {e}")
            
        try:
            registry.get_tool(None)
            print("✗ None参数验证失败")
        except ValueError:
            print("✓ None参数验证正常")
        except Exception as e:
            print(f"✗ None参数验证异常: {e}")
        
    except Exception as e:
        print(f"✗ 工具注册失败: {e}")

if __name__ == "__main__":
    test_tool_registration()