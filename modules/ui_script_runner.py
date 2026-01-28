"""
UI Script Runner - Subprocess management for running pipeline scripts.
"""

import os
import sys
import subprocess
import threading

from shared_logging import get_logger

logger = get_logger("pipeline")


class ScriptRunner:
    """Handles running external scripts."""

    @staticmethod
    def run_script(script_path, args=None, env_vars=None, callback=None):
        """Run a Python script as a subprocess."""
        if not os.path.exists(script_path):
            error_msg = f"Script not found: {script_path}"
            logger.error(error_msg)
            if callback:
                callback(error_msg, "error")
            return False

        cmd = [sys.executable, script_path] + (args or [])
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        logger.info(f"Running script: {' '.join(cmd)}")
        if callback:
            callback(f"Running: {os.path.basename(script_path)}", "info")

        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            def monitor_output():
                for line in iter(process.stdout.readline, ''):
                    if line.strip():
                        logger.info(line.strip())
                        if callback:
                            callback(line.strip(), "info")

                # Filter out Python warnings from stderr
                warning_indicators = ['Warning:', 'SyntaxWarning', 'DeprecationWarning', 'FutureWarning', 'UserWarning']
                warning_context_lines = 0  # Track lines after a warning (usually code context)

                for line in iter(process.stderr.readline, ''):
                    if line.strip():
                        stripped_line = line.strip()

                        # Check if this line contains a Python warning
                        is_warning_line = any(indicator in stripped_line for indicator in warning_indicators)

                        if is_warning_line:
                            # This is a warning - skip it and the next 2 lines (usually file path + code)
                            warning_context_lines = 2
                            continue

                        if warning_context_lines > 0:
                            # Skip context lines after a warning
                            warning_context_lines -= 1
                            continue

                        # This is a real error - show it
                        logger.error(stripped_line)
                        if callback:
                            callback(stripped_line, "error")

                exit_code = process.wait()

                if exit_code == 0:
                    success_msg = f"✓ Completed: {os.path.basename(script_path)}"
                    logger.info(success_msg)
                    if callback:
                        callback(success_msg, "success")
                else:
                    error_msg = f"✗ Failed (exit code {exit_code}): {os.path.basename(script_path)}"
                    logger.error(error_msg)
                    if callback:
                        callback(error_msg, "error")

            threading.Thread(target=monitor_output, daemon=True).start()
            return True

        except Exception as e:
            error_msg = f"Error running script: {e}"
            logger.error(error_msg)
            if callback:
                callback(error_msg, "error")
            return False
