"""
开发测试入口
作用：用于开发阶段的测试和调试
"""
# 统一导入路径
from core import ToolManager
from tools import SinglePaperExtractionTool, DailyPapersCollectorTool, LLMPaperSummarizerTool
import sys
import os
import asyncio
from dotenv import load_dotenv

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

def test_llm_summarizer_execute_impl():
    """
    测试LLM总结工具的_execute_impl函数，详细打印每一步的输入和输出
    
    功能说明:
    1. 测试完整的论文总结工作流程
    2. 验证资源清理功能的正确性
    3. 详细记录每个步骤的执行情况
    4. 提供完整的错误处理和日志输出
    
    测试内容:
    - API密钥验证
    - 工具实例创建和可用性检查
    - 参数准备和验证
    - _execute_impl函数执行
    - 资源清理验证
    - 结果分析和展示
    
    返回:
        bool: 测试是否成功
    """
    
    print("=== LLM总结工具_execute_impl函数测试 ===")
    print("测试_execute_impl函数的完整工作流程，包括新增的资源清理功能...\n")
    
    try:
        # ===========================================
        # 1. 环境准备和API密钥验证
        # ===========================================
        print("🔧 环境准备和API密钥验证")
        print("-" * 50)
        
        # 加载环境变量
        load_dotenv()
        print("✅ 环境变量加载完成")
        
        # 检查API密钥
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ 错误: 未找到OPENAI_API_KEY环境变量")
            print("   请在项目根目录创建.env文件并添加: OPENAI_API_KEY=your_api_key")
            return False
        
        if not api_key.startswith('sk-'):
            print("❌ 错误: OPENAI_API_KEY格式不正确，应该以'sk-'开头")
            return False
        
        print(f"✅ API密钥检查通过: {api_key[:10]}...{api_key[-4:]}")
        
        # ===========================================
        # 2. 创建LLM总结工具实例
        # ===========================================
        print("\n🛠️ 创建LLM总结工具实例")
        print("-" * 50)
        
        llm_tool = LLMPaperSummarizerTool()
        print(f"✅ 成功创建工具实例: {type(llm_tool).__name__}")
        print(f"   📝 工具名称: {llm_tool.get_metadata().name}")
        print(f"   📋 工具描述: {llm_tool.get_metadata().description}")
        
        # 验证工具内部组件
        print(f"   🔧 OpenAI客户端状态: {'已初始化' if llm_tool.client else '未初始化'}")
        print(f"   📊 默认模型: {llm_tool.default_model}")
        print(f"   🌡️ 默认温度: {llm_tool.default_temperature}")
        
        # ===========================================
        # 3. 测试工具可用性检查
        # ===========================================
        print("\n🔍 测试工具可用性检查")
        print("-" * 50)
        
        is_available = llm_tool.is_available()
        if is_available:
            print("✅ 工具可用性检查通过")
            print(f"   - OpenAI客户端已初始化: {llm_tool.client is not None}")
            print(f"   - 资源清理功能可用: {hasattr(llm_tool, 'cleanup')}")
        else:
            print("❌ 工具可用性检查失败")
            return False
        
        # ===========================================
        # 4. 准备测试参数
        # ===========================================
        print("\n📋 准备测试参数")
        print("-" * 50)
        
        # 获取用户输入的PDF文件路径
        pdf_path = input("请输入PDF文件的完整路径: ").strip()
        if not pdf_path:
            print("❌ 未提供PDF文件路径")
            return False
        
        # 验证PDF文件存在性和格式
        if not os.path.exists(pdf_path):
            print(f"❌ PDF文件不存在: {pdf_path}")
            return False
        
        if not pdf_path.lower().endswith('.pdf'):
            print(f"❌ 文件不是PDF格式: {pdf_path}")
            return False
        
        print(f"✅ PDF文件验证通过: {os.path.basename(pdf_path)}")
        
        # 获取可选参数（提供更详细的说明）
        print("\n📝 配置可选参数（直接回车使用默认值）:")
        title = input("  论文标题 (可选): ").strip() or None
        abstract = input("  论文摘要 (可选): ").strip() or None
        language = input("  输出语言 (默认English): ").strip() or "English"
        model = input("  OpenAI模型 (默认gpt-4o-mini): ").strip() or "gpt-4o-mini"
        temperature = input("  温度参数 (默认0.1): ").strip()
        temperature = float(temperature) if temperature else 0.1
        
        # 构建测试参数字典
        test_params = {
            'pdf_path': pdf_path,
            'title': title,
            'abstract': abstract,
            'language': language,
            'model': model,
            'temperature': temperature
        }
        
        # 显示参数详情
        print(f"\n📊 测试参数详情:")
        print(f"   📄 PDF路径: {test_params['pdf_path']}")
        print(f"   📝 论文标题: {test_params['title'] or '未提供'}")
        
        # 摘要预览（如果太长则截断）
        abstract_preview = test_params['abstract']
        if abstract_preview:
            if len(abstract_preview) > 100:
                abstract_preview = abstract_preview[:100] + "..."
        print(f"   📋 论文摘要: {abstract_preview or '未提供'}")
        
        print(f"   🌐 输出语言: {test_params['language']}")
        print(f"   🤖 OpenAI模型: {test_params['model']}")
        print(f"   🌡️ 温度参数: {test_params['temperature']}")
        
        # 获取文件信息
        file_size = os.path.getsize(pdf_path)
        print(f"   📏 文件大小: {file_size / 1024 / 1024:.2f} MB")
        
        # ===========================================
        # 5. 执行_execute_impl函数
        # ===========================================
        print("\n🚀 执行_execute_impl函数")
        print("-" * 50)
        print("开始执行论文总结流程，包括资源管理和清理...")
        print(f"⏰ 开始时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 记录开始时间用于计算执行时长
        import time
        start_time = time.time()
        
        # 调用_execute_impl函数（现在包含资源清理功能）
        result = llm_tool._execute_impl(**test_params)
        
        # 记录结束时间
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"⏰ 结束时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  总执行时间: {execution_time:.2f} 秒")
        
        # ===========================================
        # 6. 分析和展示执行结果
        # ===========================================
        print("\n📊 分析和展示执行结果")
        print("-" * 50)
        
        # 验证函数执行结果
        if result:
            print(f"✅ _execute_impl函数执行成功")
            print(f"📊 返回结果类型: {type(result)}")
            
            # 分析结果结构
            if isinstance(result, dict):
                print(f"📋 结果字典包含 {len(result)} 个键:")
                for key in result.keys():
                    print(f"   🔑 {key}")
                
                # ===========================================
                # 6.1 分析执行状态
                # ===========================================
                print(f"\n🔍 执行状态分析:")
                
                # 检查成功状态
                if 'success' in result:
                    success_status = result['success']
                    print(f"   ✅ 执行状态: {'成功' if success_status else '失败'}")
                else:
                    print(f"   ⚠️ 未找到success字段")
                
                # 检查错误信息
                if 'error' in result and result['error']:
                    print(f"   ❌ 错误信息: {result['error']}")
                else:
                    print(f"   ✅ 无错误信息")
                
                # ===========================================
                # 6.2 分析总结内容
                # ===========================================
                print(f"\n📄 总结内容分析:")
                
                if 'summary' in result and result['summary']:
                    summary = result['summary']
                    print(f"   📊 总结数据类型: {type(summary)}")
                    
                    if isinstance(summary, dict):
                        print(f"   📋 总结包含 {len(summary)} 个部分:")
                        
                        # 分析每个总结部分
                        expected_parts = ['motivation', 'methodology', 'contributions', 'challenges']
                        for part in expected_parts:
                            if part in summary:
                                content = summary[part]
                                content_length = len(content) if content else 0
                                print(f"      📝 {part}: {content_length} 字符")
                                
                                # 显示内容预览
                                if content and len(content) > 0:
                                    preview = content[:150] + "..." if len(content) > 150 else content
                                    print(f"         预览: {preview}")
                                else:
                                    print(f"         ⚠️ 内容为空")
                            else:
                                print(f"      ❌ 缺少 {part} 部分")
                        
                        # 检查额外的字段
                        extra_fields = [key for key in summary.keys() if key not in expected_parts]
                        if extra_fields:
                            print(f"      📎 额外字段: {', '.join(extra_fields)}")
                    else:
                        # 如果summary不是字典，显示其内容预览
                        preview = str(summary)[:200] + "..." if len(str(summary)) > 200 else str(summary)
                        print(f"      📄 内容预览: {preview}")
                else:
                    print(f"   ❌ 未找到summary字段或内容为空")
                
                # ===========================================
                # 6.3 分析元数据
                # ===========================================
                print(f"\n📊 元数据分析:")
                
                if 'metadata' in result and result['metadata']:
                    metadata = result['metadata']
                    print(f"   📊 元数据类型: {type(metadata)}")
                    
                    if isinstance(metadata, dict):
                        print(f"   📋 元数据包含 {len(metadata)} 个字段:")
                        for key, value in metadata.items():
                            print(f"      📊 {key}: {value}")
                    else:
                        print(f"      📄 元数据内容: {metadata}")
                else:
                    print(f"   ⚠️ 未找到metadata字段")
                
                # ===========================================
                # 6.4 验证资源清理
                # ===========================================
                print(f"\n🧹 资源清理验证:")
                
                # 检查是否有资源清理相关的信息
                cleanup_fields = ['cleanup_result', 'resources_cleaned', 'cleanup_status']
                cleanup_info_found = False
                
                for field in cleanup_fields:
                    if field in result:
                        print(f"   ✅ 找到清理信息字段: {field} = {result[field]}")
                        cleanup_info_found = True
                
                if not cleanup_info_found:
                    print(f"   ℹ️ 结果中未包含显式的资源清理信息")
                    print(f"   📝 说明: 资源清理在_execute_impl函数的finally块中自动执行")
                    print(f"   🔧 清理过程: 自动删除上传的文件和创建的对话线程")
                
                # ===========================================
                # 6.5 其他字段分析
                # ===========================================
                other_fields = [key for key in result.keys() 
                              if key not in ['success', 'summary', 'metadata', 'error'] + cleanup_fields]
                
                if other_fields:
                    print(f"\n📎 其他字段分析:")
                    for key in other_fields:
                        value = result[key]
                        if isinstance(value, str) and len(value) > 100:
                            preview = value[:100] + "..."
                            print(f"   📄 {key}: {preview}")
                        else:
                            print(f"   📊 {key}: {value}")
            else:
                # 如果结果不是字典类型
                print(f"⚠️ 结果不是字典类型，直接显示内容:")
                print(f"📄 结果内容: {result}")
            
            # ===========================================
            # 7. 测试总结
            # ===========================================
            print(f"\n🎯 测试总结")
            print("-" * 50)
            print(f"✅ _execute_impl函数测试完成")
            print(f"⏱️  总执行时间: {execution_time:.2f} 秒")
            print(f"🔧 资源清理: 自动执行（在finally块中）")
            print(f"📊 返回数据: {'结构完整' if isinstance(result, dict) and 'success' in result else '需要检查'}")
            
            return True
        else:
            print("❌ _execute_impl函数返回了空值")
            print("🔍 可能的原因:")
            print("   - 函数执行过程中发生了未捕获的异常")
            print("   - 函数逻辑存在问题导致返回None")
            print("   - OpenAI API调用失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        print("\n🔍 详细错误信息:")
        traceback.print_exc()
        return False

def test_llm_summarizer_assistant():
    """测试LLM总结工具的get_or_create_assistant函数"""
    
    print("=== LLM总结工具Assistant测试 ===")
    print("测试get_or_create_assistant函数是否能成功调用LLM...\n")
    
    try:
        # 加载环境变量
        load_dotenv()
        
        # 检查API密钥
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ 错误: 未找到OPENAI_API_KEY环境变量")
            print("   请在项目根目录创建.env文件并添加: OPENAI_API_KEY=your_api_key")
            return False
        
        if not api_key.startswith('sk-'):
            print("❌ 错误: OPENAI_API_KEY格式不正确，应该以'sk-'开头")
            return False
        
        print(f"✅ API密钥检查通过: {api_key[:10]}...{api_key[-4:]}")
        
        # 创建LLM总结工具实例
        print("\n1️⃣ 创建LLM总结工具实例")
        print("-" * 40)
        
        llm_tool = LLMPaperSummarizerTool()
        print(f"✅ 成功创建工具实例: {type(llm_tool).__name__}")
        
        # 测试工具可用性检查
        print("\n2️⃣ 测试工具可用性检查")
        print("-" * 40)
        
        is_available = llm_tool.is_available()
        if is_available:
            print("✅ 工具可用性检查通过")
            print(f"   - OpenAI客户端已初始化: {llm_tool.client is not None}")
        else:
            print("❌ 工具可用性检查失败")
            return False
        
        # 测试get_or_create_assistant函数
        print("\n3️⃣ 测试get_or_create_assistant函数")
        print("-" * 40)
        
        # 测试参数 - 只传入get_or_create_assistant支持的参数
        test_params = {
            'model': 'gpt-4o-mini',  # 使用更便宜的模型进行测试
            'temperature': 0.1
        }
        
        print(f"测试参数: {test_params}")
        print("正在调用get_or_create_assistant...")
        
        assistant_id = llm_tool.get_or_create_assistant(**test_params)
        
        if assistant_id:
            print(f"✅ 成功获取/创建Assistant")
            print(f"   Assistant ID: {assistant_id}")
            print(f"   缓存的Assistant ID: {llm_tool.assistant_id}")
            
            # 验证Assistant是否真的存在
            print("\n4️⃣ 验证Assistant存在性")
            print("-" * 40)
            
            try:
                assistant = llm_tool.client.beta.assistants.retrieve(assistant_id)
                print(f"✅ Assistant验证成功")
                print(f"   名称: {assistant.name}")
                print(f"   模型: {assistant.model}")
                print(f"   工具数量: {len(assistant.tools) if assistant.tools else 0}")
                
                # 测试重复调用（应该返回缓存的ID）
                print("\n5️⃣ 测试缓存机制")
                print("-" * 40)
                
                cached_assistant_id = llm_tool.get_or_create_assistant(**test_params)
                if cached_assistant_id == assistant_id:
                    print("✅ 缓存机制工作正常，返回了相同的Assistant ID")
                else:
                    print(f"⚠️  缓存机制异常，返回了不同的ID: {cached_assistant_id}")
                
                return True
                
            except Exception as e:
                print(f"❌ Assistant验证失败: {e}")
                return False
        else:
            print("❌ get_or_create_assistant返回了空值")
            return False
            
    except Exception as e:
        # ===========================================
        # 异常处理和错误分析
        # ===========================================
        print(f"\n❌ 测试过程中发生错误")
        print("-" * 50)
        print(f"🔍 错误类型: {type(e).__name__}")
        print(f"📝 错误信息: {str(e)}")
        
        # 提供详细的错误分析
        print(f"\n🔧 错误分析:")
        
        # 根据错误类型提供具体的解决建议
        if "OpenAI" in str(e) or "API" in str(e):
            print(f"   🌐 这是OpenAI API相关错误")
            print(f"   💡 建议检查:")
            print(f"      - API密钥是否正确且有效")
            print(f"      - 网络连接是否正常")
            print(f"      - API配额是否充足")
            print(f"      - 请求参数是否符合要求")
            
        elif "FileNotFoundError" in str(type(e)):
            print(f"   📄 这是文件相关错误")
            print(f"   💡 建议检查:")
            print(f"      - PDF文件路径是否正确")
            print(f"      - 文件是否存在且可读")
            print(f"      - 文件权限是否正确")
            
        elif "ValueError" in str(type(e)):
            print(f"   📊 这是参数值错误")
            print(f"   💡 建议检查:")
            print(f"      - 输入参数的格式和类型")
            print(f"      - 温度参数是否在有效范围内")
            print(f"      - 模型名称是否正确")
            
        else:
            print(f"   ❓ 未知错误类型")
            print(f"   💡 建议:")
            print(f"      - 检查代码逻辑")
            print(f"      - 查看详细的错误堆栈信息")
            print(f"      - 确认所有依赖项已正确安装")
        
        # 显示错误堆栈信息（用于调试）
        import traceback
        print(f"\n🔍 详细错误堆栈:")
        print(f"{'='*50}")
        traceback.print_exc()
        print(f"{'='*50}")
        
        # 提供恢复建议
        print(f"\n🔄 恢复建议:")
        print(f"   1. 检查并修复上述提到的问题")
        print(f"   2. 确认环境配置正确")
        print(f"   3. 重新运行测试")
        print(f"   4. 如果问题持续，请检查llm_summarizer.py中的代码逻辑")
        
        return False



def main():
    """主测试函数"""
    print("选择测试模式:")
    print("1. 工具管理器测试")
    print("2. LLM总结工具Assistant测试")
    print("3. LLM总结工具完整工作流程测试 (新增)")
    print("4. parse_structured_response函数测试 (新增)")
    print("5. LLM总结工具_execute_impl函数测试 (新增)")
    print("6. 运行所有测试")
    
    choice = input("\n请输入选择 (1/2/3/4/5/6): ").strip()
    
    if choice == '1':
        test_tool_manager()
    elif choice == '2':
        success = test_llm_summarizer_assistant()
        if success:
            print("\n🎉 LLM总结工具Assistant测试完成！")
        else:
            print("\n💥 LLM总结工具Assistant测试失败！")
    elif choice == '3':
        success = test_llm_summarizer_full_workflow()
        if success:
            print("\n🎉 LLM总结工具完整工作流程测试完成！")
        else:
            print("\n💥 LLM总结工具完整工作流程测试失败！")
    elif choice == '4':
        success = test_parse_structured_response()
        if success:
            print("\n🎉 parse_structured_response函数测试完成！")
        else:
            print("\n💥 parse_structured_response函数测试失败！")
    elif choice == '5':
        success = test_llm_summarizer_execute_impl()
        if success:
            print("\n🎉 LLM总结工具_execute_impl函数测试完成！")
        else:
            print("\n💥 LLM总结工具_execute_impl函数测试失败！")
    elif choice == '6':
        print("\n=== 运行所有测试 ===")
        
        # 测试1: 工具管理器
        print("\n" + "="*60)
        print("测试1: 工具管理器测试")
        print("="*60)
        test_tool_manager()
        
        # 测试2: Assistant测试
        print("\n" + "="*60)
        print("测试2: LLM总结工具Assistant测试")
        print("="*60)
        success_assistant = test_llm_summarizer_assistant()
        
        # 测试3: 完整工作流程测试
        print("\n" + "="*60)
        print("测试3: LLM总结工具完整工作流程测试")
        print("="*60)
        success_workflow = test_llm_summarizer_full_workflow()
        
        # 测试4: parse_structured_response函数测试
        print("\n" + "="*60)
        print("测试4: parse_structured_response函数测试")
        print("="*60)
        success_parse = test_parse_structured_response()
        
        # 测试5: _execute_impl函数测试
        print("\n" + "="*60)
        print("测试5: LLM总结工具_execute_impl函数测试")
        print("="*60)
        success_execute_impl = test_llm_summarizer_execute_impl()
        
        # 总结所有测试结果
        print("\n" + "="*60)
        print("所有测试结果总结")
        print("="*60)
        print(f"✓ 工具管理器测试: 已完成")
        print(f"{'✓' if success_assistant else '✗'} Assistant测试: {'成功' if success_assistant else '失败'}")
        print(f"{'✓' if success_workflow else '✗'} 完整工作流程测试: {'成功' if success_workflow else '失败'}")
        print(f"{'✓' if success_parse else '✗'} parse_structured_response测试: {'成功' if success_parse else '失败'}")
        print(f"{'✓' if success_execute_impl else '✗'} _execute_impl函数测试: {'成功' if success_execute_impl else '失败'}")
        
        if success_assistant and success_workflow and success_parse and success_execute_impl:
            print("\n🎉 所有测试完成且成功！")
        else:
            print("\n💥 部分测试失败，请检查错误信息！")
    else:
        print("无效选择，默认运行工具管理器测试")
        test_tool_manager()

if __name__ == "__main__":
    main()