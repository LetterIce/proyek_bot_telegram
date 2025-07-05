import platform
import psutil
import socket
import subprocess
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def sanitize_text(text):
    """Sanitize text to prevent Telegram parsing errors."""
    if not text or text == 'Unknown':
        return text
    
    # Convert to string and strip whitespace
    text = str(text).strip()
    
    # Remove or replace problematic characters
    # Remove special markdown characters that might cause issues
    problematic_chars = ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Replace problematic characters with safe alternatives
    replacements = {
        '*': '•',
        '_': '-',
        '`': "'",
        '[': '(',
        ']': ')',
        '~': '-',
        '#': 'No.',
        '|': ' ',
        '{': '(',
        '}': ')'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    # Remove any remaining problematic characters
    for char in problematic_chars:
        if char not in replacements:
            text = text.replace(char, '')
    
    # Clean up multiple spaces
    import re
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def get_system_info():
    """Get comprehensive system information with robust error handling."""
    info = {
        'os': 'Unknown',
        'arch': 'Unknown',
        'hostname': 'Unknown',
        'kernel': 'Unknown',
        'uptime': 'Unknown',
        'cpu': 'Unknown',
        'cpu_usage': 'Unknown',
        'memory_total': 'Unknown',
        'memory_used': 'Unknown',
        'memory_available': 'Unknown',
        'memory_percent': 'Unknown',
        'swap_total': '0.00 GB',
        'swap_used': '0.00 GB',
        'swap_percent': '0.0%',
        'disk_total': 'Unknown',
        'disk_used': 'Unknown',
        'disk_free': 'Unknown',
        'disk_percent': 'Unknown',
        'local_ip': 'Unknown'
    }
    
    try:
        # Basic system info
        try:
            info['os'] = f"{platform.system()} {platform.release()}"
        except:
            pass
            
        try:
            info['arch'] = platform.machine()
        except:
            pass
            
        try:
            info['hostname'] = socket.gethostname()
        except:
            pass
            
        try:
            info['kernel'] = platform.release()
        except:
            pass
        
        # Get detailed OS info based on platform
        try:
            if platform.system() == "Linux":
                try:
                    with open('/etc/os-release', 'r') as f:
                        for line in f:
                            if line.startswith('PRETTY_NAME='):
                                info['os'] = line.split('=')[1].strip().strip('"')
                                break
                except (FileNotFoundError, PermissionError):
                    try:
                        result = subprocess.run(['lsb_release', '-d'], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            info['os'] = result.stdout.split('\t')[1].strip()
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                        pass
            elif platform.system() == "Windows":
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                    product_name = winreg.QueryValueEx(key, "ProductName")[0]
                    build_number = winreg.QueryValueEx(key, "CurrentBuild")[0]
                    info['os'] = f"{product_name} (Build {build_number})"
                    winreg.CloseKey(key)
                except (ImportError, OSError, WindowsError):
                    pass
        except Exception as e:
            logger.debug(f"Could not get detailed OS info: {e}")
        
        # Uptime
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
            logger.debug(f"Could not get uptime: {e}")
        
        # CPU info
        try:
            cpu_info = None
            if platform.system() == "Linux":
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if 'model name' in line:
                                cpu_info = line.split(':')[1].strip()
                                break
                except (FileNotFoundError, PermissionError):
                    pass
            
            if not cpu_info:
                try:
                    cpu_info = platform.processor()
                except:
                    pass
                    
            if not cpu_info or cpu_info.strip() == "":
                if platform.system() == "Windows":
                    try:
                        import winreg
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                        cpu_info = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                        winreg.CloseKey(key)
                    except (ImportError, OSError, WindowsError):
                        pass
                        
            if cpu_info and cpu_info.strip():
                info['cpu'] = cpu_info
            else:
                try:
                    cpu_count = psutil.cpu_count()
                    info['cpu'] = f"Unknown CPU ({cpu_count} cores)" if cpu_count else "Unknown CPU"
                except:
                    pass
                    
            # CPU usage
            try:
                cpu_usage = psutil.cpu_percent(interval=0.1)
                info['cpu_usage'] = f"{cpu_usage:.1f}%"
            except:
                pass
        except Exception as e:
            logger.debug(f"Could not get CPU info: {e}")
        
        # Memory info
        try:
            memory = psutil.virtual_memory()
            info['memory_total'] = f"{memory.total / (1024**3):.2f} GB"
            info['memory_used'] = f"{memory.used / (1024**3):.2f} GB"
            info['memory_available'] = f"{memory.available / (1024**3):.2f} GB"
            info['memory_percent'] = f"{memory.percent:.1f}%"
        except Exception as e:
            logger.debug(f"Could not get memory info: {e}")
        
        # Swap info
        try:
            swap = psutil.swap_memory()
            info['swap_total'] = f"{swap.total / (1024**3):.2f} GB"
            info['swap_used'] = f"{swap.used / (1024**3):.2f} GB"
            info['swap_percent'] = f"{swap.percent:.1f}%"
        except Exception as e:
            logger.debug(f"Could not get swap info: {e}")
        
        # Disk info
        try:
            disk_path = 'C:' if platform.system() == "Windows" else '/'
            disk = psutil.disk_usage(disk_path)
            info['disk_total'] = f"{disk.total / (1024**3):.2f} GB"
            info['disk_used'] = f"{disk.used / (1024**3):.2f} GB"
            info['disk_free'] = f"{disk.free / (1024**3):.2f} GB"
            info['disk_percent'] = f"{(disk.used/disk.total)*100:.1f}%"
        except Exception as e:
            logger.debug(f"Could not get disk info: {e}")
        
        # Network info
        try:
            interfaces = psutil.net_if_addrs()
            local_ips = []
            
            for interface_name, interface_addresses in interfaces.items():
                for address in interface_addresses:
                    if address.family == socket.AF_INET:
                        ip = address.address
                        if not ip.startswith('127.') and not ip.startswith('169.254.'):
                            local_ips.append(f"{interface_name}: {ip}")
            
            if local_ips:
                info['local_ip'] = ", ".join(local_ips[:3])
            else:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    info['local_ip'] = s.getsockname()[0]
                    s.close()
                except:
                    pass
        except Exception as e:
            logger.debug(f"Could not get network info: {e}")
        
        # Load average (Unix-like systems only)
        try:
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
                info['load_avg'] = f"{load_avg[1]:.2f}"
        except:
            pass
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return info

def get_bot_process_info():
    """Get information about the bot process with robust error handling."""
    info = {
        'pid': 'Unknown',
        'ppid': 'Unknown',
        'name': 'Unknown',
        'memory_mb': 'Unknown',
        'memory_vms': 'Unknown',
        'cpu_percent': 'Unknown',
        'threads': 'Unknown',
        'status': 'Unknown',
        'runtime': 'Unknown',
        'cwd': 'Unknown'
    }
    
    try:
        process = psutil.Process()
        
        try:
            info['pid'] = process.pid
        except:
            pass
            
        try:
            info['ppid'] = process.ppid()
        except:
            pass
            
        try:
            info['name'] = process.name()
        except:
            pass
        
        try:
            memory_info = process.memory_info()
            info['memory_mb'] = f"{memory_info.rss / (1024**2):.1f} MB"
            info['memory_vms'] = f"{memory_info.vms / (1024**2):.1f} MB"
        except:
            pass
        
        try:
            cpu_percent = process.cpu_percent(interval=0.1)
            if cpu_percent is not None:
                info['cpu_percent'] = f"{cpu_percent:.1f}%"
        except:
            pass
        
        try:
            info['threads'] = process.num_threads()
        except:
            pass
            
        try:
            info['status'] = process.status()
        except:
            pass
        
        try:
            create_time = datetime.fromtimestamp(process.create_time())
            runtime = datetime.now() - create_time
            hours, remainder = divmod(runtime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if runtime.days > 0:
                info['runtime'] = f"{runtime.days} days, {hours} hours, {minutes} mins"
            else:
                info['runtime'] = f"{hours} hours, {minutes} mins"
        except:
            pass
        
        try:
            info['cwd'] = process.cwd()
        except:
            pass
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting bot process info: {e}")
        return info

def format_system_stats():
    """Format system information for display with error handling."""
    try:
        sys_info = get_system_info()
        bot_info = get_bot_process_info()
        
        stats_text = "🖥️ Server Information:\n\n"
        
        # OS Info
        if sys_info.get('os') != 'Unknown':
            os_info = sanitize_text(sys_info['os'])
            stats_text += f"💻 OS: {os_info}"
            if sys_info.get('arch') != 'Unknown':
                arch_info = sanitize_text(sys_info['arch'])
                stats_text += f" ({arch_info})"
            stats_text += "\n"
        
        if sys_info.get('hostname') != 'Unknown':
            hostname = sanitize_text(sys_info['hostname'])
            stats_text += f"🏷️ Host: {hostname}\n"
        
        if sys_info.get('uptime') != 'Unknown':
            uptime = sanitize_text(sys_info['uptime'])
            stats_text += f"⏱️ Uptime: {uptime}\n"
        
        # CPU Info
        stats_text += "\n💾 Hardware:\n"
        if sys_info.get('cpu') != 'Unknown':
            cpu_info = sanitize_text(sys_info['cpu'])
            stats_text += f"🔧 CPU: {cpu_info}\n"
        if sys_info.get('cpu_usage') != 'Unknown':
            cpu_usage = sanitize_text(sys_info['cpu_usage'])
            stats_text += f"📊 CPU Usage: {cpu_usage}\n"
        
        # Load average (if available)
        if sys_info.get('load_avg'):
            load_avg = sanitize_text(sys_info['load_avg'])
            stats_text += f"⚡ Load Avg (5 min): {load_avg}\n"
        
        # Memory Info
        if (sys_info.get('memory_total') != 'Unknown' and 
            sys_info.get('memory_used') != 'Unknown' and 
            sys_info.get('memory_percent') != 'Unknown'):
            mem_used = sanitize_text(sys_info['memory_used'])
            mem_total = sanitize_text(sys_info['memory_total'])
            mem_percent = sanitize_text(sys_info['memory_percent'])
            stats_text += f"🧠 Memory: {mem_used} / {mem_total} ({mem_percent})\n"
        
        # Swap Info (only if swap exists)
        try:
            swap_total_num = float(sys_info.get('swap_total', '0').split()[0])
            if swap_total_num > 0:
                swap_used = sanitize_text(sys_info['swap_used'])
                swap_total = sanitize_text(sys_info['swap_total'])
                swap_percent = sanitize_text(sys_info['swap_percent'])
                stats_text += f"💱 Swap: {swap_used} / {swap_total} ({swap_percent})\n"
        except (ValueError, AttributeError):
            pass
        
        # Disk Info
        if (sys_info.get('disk_total') != 'Unknown' and 
            sys_info.get('disk_used') != 'Unknown' and 
            sys_info.get('disk_percent') != 'Unknown'):
            disk_used = sanitize_text(sys_info['disk_used'])
            disk_total = sanitize_text(sys_info['disk_total'])
            disk_percent = sanitize_text(sys_info['disk_percent'])
            stats_text += f"💿 Disk: {disk_used} / {disk_total} ({disk_percent})\n"
        
        # Network Info
        if sys_info.get('local_ip') != 'Unknown':
            local_ip = sanitize_text(sys_info['local_ip'])
            stats_text += f"🌐 Network: {local_ip}\n"
        
        # Bot Process Info
        if any(v != 'Unknown' for v in bot_info.values()):
            stats_text += "\n🤖 Bot Process:\n"
            if bot_info.get('pid') != 'Unknown':
                pid = sanitize_text(str(bot_info['pid']))
                stats_text += f"🆔 PID: {pid}"
                if bot_info.get('ppid') != 'Unknown':
                    ppid = sanitize_text(str(bot_info['ppid']))
                    stats_text += f" (Parent: {ppid})"
                stats_text += "\n"
            if bot_info.get('runtime') != 'Unknown':
                runtime = sanitize_text(bot_info['runtime'])
                stats_text += f"⏰ Runtime: {runtime}\n"
            if bot_info.get('cpu_percent') != 'Unknown':
                cpu_percent = sanitize_text(bot_info['cpu_percent'])
                stats_text += f"🔧 CPU Usage: {cpu_percent}\n"
            if bot_info.get('memory_mb') != 'Unknown':
                memory_mb = sanitize_text(bot_info['memory_mb'])
                stats_text += f"🧠 Memory: {memory_mb}\n"
            if bot_info.get('threads') != 'Unknown':
                threads = sanitize_text(str(bot_info['threads']))
                stats_text += f"🧵 Threads: {threads}\n"
            if bot_info.get('status') != 'Unknown':
                status = sanitize_text(bot_info['status'])
                stats_text += f"📊 Status: {status}\n"
        
        
        return stats_text
        
    except Exception as e:
        logger.error(f"Error formatting system stats: {e}")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"🖥️ System Information:\n\n❌ Error retrieving detailed stats, but bot is running.\n\n📅 Time: {timestamp}"
