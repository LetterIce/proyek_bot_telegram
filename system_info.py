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
        
        # Add CPU usage for the process
        try:
            cpu_percent = process.cpu_percent(interval=0.1)
            if cpu_percent is None:
                info['cpu_percent'] = "Unknown"
            else:
                info['cpu_percent'] = f"{cpu_percent:.1f}%"
        except Exception:
            info['cpu_percent'] = "Unknown"
        
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
        sys_info = get_system_info() or {}
        bot_info = get_bot_process_info() or {}
        
        if not sys_info:
            return "❌ Unable to retrieve system information"
        
        stats_text = "🖥️ **Server Information:**\n\n"
        
        # OS Info
        os_val = sys_info.get('os', '')
        if os_val:
            stats_text += f"💻 OS: {os_val}"
            arch_val = sys_info.get('arch', '')
            if arch_val:
                stats_text += f" ({arch_val})"
            stats_text += "\n"
        
        hostname_val = sys_info.get('hostname', '')
        if hostname_val:
            stats_text += f"🏷️ Host: {hostname_val}\n"
        
        uptime_val = sys_info.get('uptime', '')
        if uptime_val:
            stats_text += f"⏱️ Uptime: {uptime_val}\n"
        
        # CPU Info
        stats_text += "\n💾 **Hardware:**\n"
        cpu_val = sys_info.get('cpu', '')
        if cpu_val:
            stats_text += f"🔧 CPU: {cpu_val}\n"
        cpu_usage_val = sys_info.get('cpu_usage', '')
        if cpu_usage_val:
            stats_text += f"📊 CPU Usage: {cpu_usage_val}\n"
        
        # Load average (if available)
        load_avg_val = sys_info.get('load_avg', '')
        if load_avg_val:
            stats_text += f"⚡ Load Avg (5 min): {load_avg_val}\n"
        
        # Memory Info
        mem_used = sys_info.get('memory_used', '')
        mem_total = sys_info.get('memory_total', '')
        mem_percent = sys_info.get('memory_percent', '')
        if mem_total and mem_used and mem_percent:
            stats_text += f"🧠 Memory: {mem_used} / {mem_total} ({mem_percent})\n"
        
        swap_total = sys_info.get('swap_total', '')
        swap_used = sys_info.get('swap_used', '')
        swap_percent = sys_info.get('swap_percent', '')
        try:
            swap_total_num = float(swap_total.split()[0]) if swap_total else 0
        except Exception:
            swap_total_num = 0
        if swap_total and swap_used and swap_percent and swap_total_num > 0:
            stats_text += f"💱 Swap: {swap_used} / {swap_total} ({swap_percent})\n"
        
        # Disk Info
        disk_used = sys_info.get('disk_used', '')
        disk_total = sys_info.get('disk_total', '')
        disk_percent = sys_info.get('disk_percent', '')
        if disk_total and disk_used and disk_percent:
            stats_text += f"💿 Disk: {disk_used} / {disk_total} ({disk_percent})\n"
        
        # Network Info
        local_ip = sys_info.get('local_ip', '')
        if local_ip:
            stats_text += f"🌐 Network: {local_ip}\n"
        
        # Bot Process Info
        if bot_info:
            stats_text += "\n🤖 **Bot Process:**\n"
            pid_val = bot_info.get('pid', '')
            if pid_val:
                stats_text += f"🆔 PID: {pid_val}"
                ppid_val = bot_info.get('ppid', '')
                if ppid_val:
                    stats_text += f" (Parent: {ppid_val})"
                stats_text += "\n"
            runtime_val = bot_info.get('runtime', '')
            if runtime_val:
                stats_text += f"⏰ Runtime: {runtime_val}\n"
            cpu_percent = bot_info.get('cpu_percent', '')
            if cpu_percent and isinstance(cpu_percent, str) and cpu_percent != "Unknown":
                stats_text += f"🔧 CPU Usage: {cpu_percent}\n"
            memory_mb = bot_info.get('memory_mb', '')
            if memory_mb:
                stats_text += f"🧠 Memory: {memory_mb}\n"
            threads = bot_info.get('threads', '')
            if threads:
                stats_text += f"🧵 Threads: {threads}\n"
            status = bot_info.get('status', '')
            if status:
                stats_text += f"📊 Status: {status}\n"
        
        return stats_text
        
    except Exception as e:
        logger.error(f"Error formatting system stats: {e}")
        return f"❌ Error retrieving system information: {str(e)}"
