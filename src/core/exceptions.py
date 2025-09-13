"""
自定义异常模块
作用：定义系统特定的异常类型
"""

class PaperReaderError(Exception):
    """系统基础异常"""
    pass

class ToolRegistrationError(PaperReaderError):
    """工具注册异常"""
    pass

class ToolNotFoundError(PaperReaderError):
    """工具未找到异常"""
    pass

class AgentExecutionError(PaperReaderError):
    """Agent执行异常"""
    pass