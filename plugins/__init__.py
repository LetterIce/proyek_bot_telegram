import os
import importlib
import logging
from typing import Dict, List, Any
from telegram.ext import Application

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Any] = {}
        self.plugin_dir = os.path.dirname(__file__)
    
    def load_plugins(self, application: Application) -> List[str]:
        """Load all plugins from the plugins directory."""
        loaded_plugins = []
        
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                plugin_name = filename[:-3]
                try:
                    module = importlib.import_module(f'plugins.{plugin_name}')
                    if hasattr(module, 'setup'):
                        module.setup(application)
                        self.plugins[plugin_name] = module
                        loaded_plugins.append(plugin_name)
                        logger.info(f"Loaded plugin: {plugin_name}")
                    else:
                        logger.warning(f"Plugin {plugin_name} has no setup function")
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_name}: {e}")
        
        return loaded_plugins
    
    def get_plugin_info(self) -> Dict[str, Dict]:
        """Get information about loaded plugins."""
        plugin_info = {}
        for name, module in self.plugins.items():
            info = {
                'name': name,
                'description': getattr(module, '__description__', 'No description'),
                'version': getattr(module, '__version__', '1.0.0'),
                'author': getattr(module, '__author__', 'Unknown')
            }
            plugin_info[name] = info
        return plugin_info

# Global plugin manager instance
plugin_manager = PluginManager()
