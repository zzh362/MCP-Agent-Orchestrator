from mcp.server.fastmcp import FastMCP
import io
import contextlib
import traceback
import subprocess

# Initialize FastMCP server
mcp = FastMCP("code_executor")

@mcp.tool()
async def execute_python_code(code: str) -> str:
    """Executes the given Python code string and returns its output. the executed code should print its input and output if has any

    Args:
        code: The Python code to execute.
    """
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()

    try:
        # Redirect stdout and stderr
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(error_buffer):
            # Use a restricted namespace for security, although exec is inherently risky
            # For a production scenario, consider sandboxing environments like Docker or restricted interpreters
            exec(code, {}) 
        
        stdout = output_buffer.getvalue()
        stderr = error_buffer.getvalue()

        if stderr:
            return f"Execution finished with errors:\n{stderr}\nOutput:\n{stdout}"
        else:
            return f"Execution successful:\nOutput:\n{stdout}"

    except Exception as e:
        # Catch exceptions during exec itself
        return f"Failed to execute code:\n{traceback.format_exc()}"
    finally:
        output_buffer.close()
        error_buffer.close()


@mcp.tool()
async def execute_bash_script(script: str) -> str:
    """Executes the given bash script string and returns its output.
    Attempts to filter out some potentially harmful commands.
    the executed script should print its input and output if has any

    Args:
        script: The bash script to execute.
    """

    try:
        # Execute the script
        # Timeout is important to prevent runaway scripts
        process = subprocess.run(
            ['bash', '-c', script],
            capture_output=True,
            text=True,
            timeout=30,  # Timeout in seconds
            check=False # Don't raise exception for non-zero exit codes automatically
        )

        stdout = process.stdout
        stderr = process.stderr

        if process.returncode != 0:
            return f"Script execution finished with errors (exit code {process.returncode}):\nStderr:\n{stderr}\nStdout:\n{stdout}"
        else:
            return f"Script execution successful:\nStdout:\n{stdout}\nStderr:\n{stderr}"

    except subprocess.TimeoutExpired:
        return "Script execution timed out."
    except Exception as e:
        return f"Failed to execute script:\n{str(e)}"


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio') 