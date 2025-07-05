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
        
        # Get detailed OS info based on platform
        try:
            if platform.system() == "Linux":
                # Try multiple methods to get Linux distribution info
                try:
                    with open('/etc/os-release', 'r') as f:
                        for line in f:
                            if line.startswith('PRETTY_NAME='):
                                info['os'] = line.split('=')[1].strip().strip('"')
                                break
                except FileNotFoundError:
                    try:
                        # Fallback to lsb_release
                        result = subprocess.run(['lsb_release', '-d'], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            info['os'] = result.stdout.split('\t')[1].strip()
                    except:
                        pass
            elif platform.system() == "Windows":
                # Get Windows version details
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                    product_name = winreg.QueryValueEx(key, "ProductName")[0]
                    build_number = winreg.QueryValueEx(key, "CurrentBuild")[0]
                    info['os'] = f"{product_name} (Build {build_number})"
                    winreg.CloseKey(key)
                except:
                    pass
        except:
            pass
        
        # Uptime - using psutil boot_time
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = datetime.now().timestamp() - boot_time
            uptime_delta = timedelta(seconds=uptime_seconds)
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                info['uptime'] = f"{days} days, {hours} hours, {minutes} mins"
            else:
                info['uptime'] = f"{hours} hours, {minutes} mins"
        except Exception as e:
            logger.warning(f"Could not get uptime: {e}")
            info['uptime'] = "Unknown"
        
        # CPU info - get actual processor information
        try:
            cpu_info = None
            if platform.system() == "Linux":
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if 'model name' in line:
                                cpu_info = line.split(':')[1].strip()
                                break
                except Exception as e:
                    logger.warning(f"Could not read /proc/cpuinfo: {e}")
            if not cpu_info:
                cpu_info = platform.processor()
            if not cpu_info or cpu_info.strip() == "":
                if platform.system() == "Windows":
                    try:
                        import winreg
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                        cpu_info = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                        winreg.CloseKey(key)
                    except:
                        pass
                # Final fallback
                if not cpu_info:
                    cpu_info = f"Unknown CPU ({psutil.cpu_count()} cores)"
            info['cpu'] = cpu_info
            # Get actual CPU usage with a short interval
            cpu_usage = psutil.cpu_percent(interval=0.1)
            info['cpu_usage'] = f"{cpu_usage:.1f}%"
        except Exception as e:
            logger.warning(f"Could not get CPU info: {e}")
            info['cpu'] = "Unknown"
            info['cpu_cores'] = "Unknown"
            info['cpu_usage'] = "Unknown"
        
        # Memory info - get actual memory usage
        try:
            memory = psutil.virtual_memory()
            info['memory_total'] = f"{memory.total / (1024**3):.2f} GB"
            info['memory_used'] = f"{memory.used / (1024**3):.2f} GB"
            info['memory_available'] = f"{memory.available / (1024**3):.2f} GB"
            info['memory_percent'] = f"{memory.percent:.1f}%"
        except Exception as e:
            logger.warning(f"Could not get memory info: {e}")
            info['memory_total'] = "Unknown"
            info['memory_used'] = "Unknown"
            info['memory_percent'] = "Unknown"
        
        # Swap info - get actual swap usage
        try:
            swap = psutil.swap_memory()
            info['swap_total'] = f"{swap.total / (1024**3):.2f} GB"
            info['swap_used'] = f"{swap.used / (1024**3):.2f} GB"
            info['swap_percent'] = f"{swap.percent:.1f}%"
        except Exception as e:
            logger.warning(f"Could not get swap info: {e}")
            info['swap_total'] = "0.00 GB"
            info['swap_used'] = "0.00 GB"
            info['swap_percent'] = "0.0%"
        
        # Disk info - get actual disk usage for the main partition
        try:
            if platform.system() == "Windows":
                # Use C: drive for Windows
                disk = psutil.disk_usage('C:')
            else:
                # Use root for Unix-like systems
                disk = psutil.disk_usage('/')
            
            info['disk_total'] = f"{disk.total / (1024**3):.2f} GB"
            info['disk_used'] = f"{disk.used / (1024**3):.2f} GB"
            info['disk_free'] = f"{disk.free / (1024**3):.2f} GB"
            info['disk_percent'] = f"{(disk.used/disk.total)*100:.1f}%"
        except Exception as e:
            logger.warning(f"Could not get disk info: {e}")
            info['disk_total'] = "Unknown"
            info['disk_used'] = "Unknown"
            info['disk_percent'] = "Unknown"
        
        # Network info - get actual network interfaces and IPs
        try:
            # Get all network interfaces
            interfaces = psutil.net_if_addrs()
            local_ips = []
            
            for interface_name, interface_addresses in interfaces.items():
                for address in interface_addresses:
                    if address.family == socket.AF_INET:  # IPv4
                        ip = address.address
                        if not ip.startswith('127.') and not ip.startswith('169.254.'):
                            local_ips.append(f"{interface_name}: {ip}")
            
            if local_ips:
                info['local_ip'] = ", ".join(local_ips[:3])  # Show max 3 IPs
            else:
                # Fallback method
                try:
                    # Connect to a remote server to find local IP
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    info['local_ip'] = s.getsockname()[0]
                    s.close()
                except:
                    info['local_ip'] = "Unknown"
        except Exception as e:
            logger.warning(f"Could not get network info: {e}")
            info['local_ip'] = "Unknown"
        
        # Get load average (Unix-like systems only)
        try:
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
                info['load_avg'] = f"{load_avg[1]:.2f}"  # 5-minute interval
        except:
            pass
        
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
        info['ppid'] = process.ppid()
        info['name'] = process.name()
        
        memory_info = process.memory_info()
        info['memory_mb'] = f"{memory_info.rss / (1024**2):.1f} MB"
        info['memory_vms'] = f"{memory_info.vms / (1024**2):.1f} MB"
        
        # Process details
        info['threads'] = process.num_threads()
        info['status'] = process.status()
        
        # Process start time and runtime
        create_time = datetime.fromtimestamp(process.create_time())
        runtime = datetime.now() - create_time
        hours, remainder = divmod(runtime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if runtime.days > 0:
            info['runtime'] = f"{runtime.days} days, {hours} hours, {minutes} mins"
        else:
            info['runtime'] = f"{hours} hours, {minutes} mins"
        
        # Working directory
        try:
            info['cwd'] = process.cwd()
        except:
            info['cwd'] = "Unknown"
        
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
                stats_text += f" ({sys_info['arch']})"
            stats_text += "\n"
        
        if sys_info.get('hostname'):
            stats_text += f"🏷️ Host: {sys_info['hostname']}\n"
        
        if sys_info.get('uptime'):
            stats_text += f"⏱️ Uptime: {sys_info['uptime']}\n"
        
        # CPU Info
        stats_text += "\n💾 **Hardware:**\n"
        if sys_info.get('cpu'):
            stats_text += f"🔧 CPU: {sys_info['cpu']}\n"
        if sys_info.get('cpu_cores'):
            cores_text = f"🔗 Cores: {sys_info['cpu_cores']}"
            if sys_info.get('cpu_cores_physical'):
                cores_text += f" ({sys_info['cpu_cores_physical']} physical)"
            stats_text += cores_text + "\n"
        if sys_info.get('cpu_usage'):
            stats_text += f"📊 CPU Usage: {sys_info['cpu_usage']}\n"
        
        # Load average (if available)
        if sys_info.get('load_avg'):
            stats_text += f"⚡ Load Avg (5 min): {sys_info['load_avg']}\n"
        
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
            stats_text += f"🌐 Network: {sys_info['local_ip']}\n"
        
        # Bot Process Info
        if bot_info:
            stats_text += "\n🤖 **Bot Process:**\n"
            if bot_info.get('pid'):
                stats_text += f"🆔 PID: {bot_info['pid']}"
                if bot_info.get('ppid'):
                    stats_text += f" (Parent: {bot_info['ppid']})"
                stats_text += "\n"
            if bot_info.get('runtime'):
                stats_text += f"⏰ Runtime: {bot_info['runtime']}\n"
            if bot_info.get('cpu_percent'):
                stats_text += f"🔧 CPU Usage: {bot_info['cpu_percent']}\n"
            if bot_info.get('memory_mb'):
                stats_text += f"🧠 Memory: {bot_info['memory_mb']}\n"
            if bot_info.get('threads'):
                stats_text += f"🧵 Threads: {bot_info['threads']}\n"
            if bot_info.get('status'):
                stats_text += f"📊 Status: {bot_info['status']}\n"
        
        # Python Info
        if sys_info.get('python_version'):
            stats_text += f"🐍 Python: {sys_info['python_version']}\n"
        
        return stats_text
        
    except Exception as e:
        logger.error(f"Error formatting system stats: {e}")
        return f"❌ Error retrieving system information: {str(e)}"
