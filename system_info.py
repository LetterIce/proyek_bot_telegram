import platform
import psutil
import socket
import subprocess
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def get_system_info():
    """Get comprehensive system information."""
    try:
        info = {}
        
        # Basic system info
        info['os'] = f"{platform.system()} {platform.release()}"
        info['arch'] = platform.machine()
        info['hostname'] = socket.gethostname()
        info['kernel'] = platform.release()
        
        # Try to get more detailed OS info
        try:
            if platform.system() == "Linux":
                with open('/etc/os-release', 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.startswith('PRETTY_NAME='):
                            info['os'] = line.split('=')[1].strip().strip('"')
                            break
        except:
            pass
        
        # Uptime
        try:
            uptime_seconds = psutil.boot_time()
            uptime_delta = datetime.now() - datetime.fromtimestamp(uptime_seconds)
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                info['uptime'] = f"{days} days, {hours} hours, {minutes} mins"
            else:
                info['uptime'] = f"{hours} hours, {minutes} mins"
        except:
            info['uptime'] = "Unknown"
        
        # CPU info
        try:
            cpu_info = platform.processor()
            if not cpu_info:
                # Try alternative method
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        lines = f.readlines()
                        for line in lines:
                            if 'model name' in line:
                                cpu_info = line.split(':')[1].strip()
                                break
                except:
                    cpu_info = f"{psutil.cpu_count()} cores"
            
            info['cpu'] = cpu_info
            info['cpu_cores'] = psutil.cpu_count()
            info['cpu_usage'] = f"{psutil.cpu_percent(interval=1):.1f}%"
        except:
            info['cpu'] = "Unknown"
            info['cpu_cores'] = "Unknown"
            info['cpu_usage'] = "Unknown"
        
        # Memory info
        try:
            memory = psutil.virtual_memory()
            info['memory_total'] = f"{memory.total / (1024**3):.2f} GB"
            info['memory_used'] = f"{memory.used / (1024**3):.2f} GB"
            info['memory_percent'] = f"{memory.percent:.1f}%"
        except:
            info['memory_total'] = "Unknown"
            info['memory_used'] = "Unknown"
            info['memory_percent'] = "Unknown"
        
        # Swap info
        try:
            swap = psutil.swap_memory()
            info['swap_total'] = f"{swap.total / (1024**3):.2f} GB"
            info['swap_used'] = f"{swap.used / (1024**3):.2f} GB"
            info['swap_percent'] = f"{swap.percent:.1f}%"
        except:
            info['swap_total'] = "Unknown"
            info['swap_used'] = "Unknown"
            info['swap_percent'] = "Unknown"
        
        # Disk info
        try:
            disk = psutil.disk_usage('/')
            info['disk_total'] = f"{disk.total / (1024**3):.2f} GB"
            info['disk_used'] = f"{disk.used / (1024**3):.2f} GB"
            info['disk_percent'] = f"{(disk.used/disk.total)*100:.1f}%"
        except:
            info['disk_total'] = "Unknown"
            info['disk_used'] = "Unknown"
            info['disk_percent'] = "Unknown"
        
        # Network info
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            info['local_ip'] = local_ip
        except:
            info['local_ip'] = "Unknown"
        
        # Python version
        info['python_version'] = platform.python_version()
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {}

def get_bot_process_info():
    """Get information about the bot process."""
    try:
        process = psutil.Process()
        info = {}
        
        # Process info
        info['pid'] = process.pid
        info['cpu_percent'] = f"{process.cpu_percent():.1f}%"
        info['memory_mb'] = f"{process.memory_info().rss / (1024**2):.1f} MB"
        info['threads'] = process.num_threads()
        
        # Process start time
        create_time = datetime.fromtimestamp(process.create_time())
        runtime = datetime.now() - create_time
        hours, remainder = divmod(runtime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if runtime.days > 0:
            info['runtime'] = f"{runtime.days} days, {hours} hours, {minutes} mins"
        else:
            info['runtime'] = f"{hours} hours, {minutes} mins"
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting bot process info: {e}")
        return {}

def format_system_stats():
    """Format system information for display."""
    try:
        sys_info = get_system_info()
        bot_info = get_bot_process_info()
        
        if not sys_info:
            return "❌ Unable to retrieve system information"
        
        stats_text = "🖥️ **Server Information:**\n\n"
        
        # OS Info
        if sys_info.get('os'):
            stats_text += f"💻 OS: {sys_info['os']}"
            if sys_info.get('arch'):
                stats_text += f" {sys_info['arch']}"
            stats_text += "\n"
        
        if sys_info.get('hostname'):
            stats_text += f"🏷️ Host: {sys_info['hostname']}\n"
        
        if sys_info.get('kernel'):
            stats_text += f"⚙️ Kernel: {sys_info['kernel']}\n"
        
        if sys_info.get('uptime'):
            stats_text += f"⏱️ Uptime: {sys_info['uptime']}\n"
        
        # CPU Info
        stats_text += "\n💾 **Hardware:**\n"
        if sys_info.get('cpu'):
            stats_text += f"🔧 CPU: {sys_info['cpu']}\n"
        if sys_info.get('cpu_cores'):
            stats_text += f"🔗 Cores: {sys_info['cpu_cores']}\n"
        if sys_info.get('cpu_usage'):
            stats_text += f"📊 CPU Usage: {sys_info['cpu_usage']}\n"
        
        # Memory Info
        if sys_info.get('memory_total'):
            stats_text += f"🧠 Memory: {sys_info['memory_used']} / {sys_info['memory_total']} ({sys_info['memory_percent']})\n"
        
        if sys_info.get('swap_total') and float(sys_info['swap_total'].split()[0]) > 0:
            stats_text += f"💱 Swap: {sys_info['swap_used']} / {sys_info['swap_total']} ({sys_info['swap_percent']})\n"
        
        # Disk Info
        if sys_info.get('disk_total'):
            stats_text += f"💿 Disk: {sys_info['disk_used']} / {sys_info['disk_total']} ({sys_info['disk_percent']})\n"
        
        # Network Info
        if sys_info.get('local_ip'):
            stats_text += f"🌐 Local IP: {sys_info['local_ip']}\n"
        
        # Bot Process Info
        if bot_info:
            stats_text += "\n🤖 **Bot Process:**\n"
            if bot_info.get('pid'):
                stats_text += f"🆔 PID: {bot_info['pid']}\n"
            if bot_info.get('runtime'):
                stats_text += f"⏰ Runtime: {bot_info['runtime']}\n"
            if bot_info.get('cpu_percent'):
                stats_text += f"🔧 CPU Usage: {bot_info['cpu_percent']}\n"
            if bot_info.get('memory_mb'):
                stats_text += f"🧠 Memory: {bot_info['memory_mb']}\n"
            if bot_info.get('threads'):
                stats_text += f"🧵 Threads: {bot_info['threads']}\n"
        
        # Python Info
        if sys_info.get('python_version'):
            stats_text += f"🐍 Python: {sys_info['python_version']}\n"
        
        return stats_text
        
    except Exception as e:
        logger.error(f"Error formatting system stats: {e}")
        return f"❌ Error retrieving system information: {str(e)}"
