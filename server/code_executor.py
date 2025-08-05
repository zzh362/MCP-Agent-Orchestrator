from mcp.server.fastmcp import FastMCP
import io
import contextlib
import traceback
import subprocess

# Initialize FastMCP server
mcp = FastMCP("code_executor")

@mcp.tool()
async def execute_python_code(code: str) -> str:
    """执行给定的Python代码字符串并返回其输出。被执行的代码应打印其输入和输出（如果有）

    Args:
        code: 要执行的Python代码。
    """
    # 创建字符串缓冲区来捕获标准输出和标准错误输出
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()

    try:
        # 重定向标准输出和标准错误以捕获执行代码的输出
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(error_buffer):
            # 使用受限的命名空间以提高安全性，尽管exec本身具有风险
            # 对于生产场景，请考虑使用沙箱环境如Docker或受限解释器
            exec(code, {}) 
        
        # 获取标准输出和标准错误的内容
        stdout = output_buffer.getvalue()
        stderr = error_buffer.getvalue()

        # 根据是否有错误输出返回相应的结果
        if stderr:
            return f"执行完成但有错误:\n{stderr}\n输出:\n{stdout}"
        else:
            return f"执行成功:\n输出:\n{stdout}"

    except Exception as e:
        # 捕获exec执行过程中出现的异常
        return f"执行代码失败:\n{traceback.format_exc()}"
    finally:
        # 清理缓冲区资源
        output_buffer.close()
        error_buffer.close()


@mcp.tool()
async def execute_bash_script(script: str) -> str:
    """执行给定的bash脚本字符串并返回其输出。
    尝试过滤掉一些潜在的有害命令。
    执行的脚本应打印其输入和输出（如果有）

    Args:
        script: 要执行的bash脚本。

    Returns:
        str: 脚本执行的结果，包括标准输出和标准错误输出，
             或者如果执行失败或超时则返回错误信息。
    """

    try:
        # 执行脚本
        # 超时设置很重要，可以防止脚本失控运行
        process = subprocess.run(
            ['bash', '-c', script],
            capture_output=True,           # 捕获标准输出和标准错误
            text=True,                     # 以文本模式处理输出
            timeout=30,                    # 超时时间（秒）
            check=False                    # 不自动为非零退出码抛出异常
        )

        stdout = process.stdout            # 获取标准输出
        stderr = process.stderr            # 获取标准错误

        # 检查脚本是否成功执行
        if process.returncode != 0:
            return f"脚本执行完成但有错误 (退出码 {process.returncode}):\n标准错误:\n{stderr}\n标准输出:\n{stdout}"
        else:
            return f"脚本执行成功:\n标准输出:\n{stdout}\n标准错误:\n{stderr}"

    except subprocess.TimeoutExpired:
        # 处理超时情况
        return "脚本执行超时。"
    except Exception as e:
        # 处理其他异常情况
        return f"执行脚本失败:\n{str(e)}"


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio') 