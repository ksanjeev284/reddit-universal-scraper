"""
Lightweight Plugin System for Post-Processing
Plugins can process posts and comments after scraping.
"""
from abc import ABC, abstractmethod
from pathlib import Path
import importlib.util
import sys


class Plugin(ABC):
    """
    Base class for scraper plugins.
    
    To create a plugin:
    1. Create a new .py file in the plugins/ directory
    2. Create a class that inherits from Plugin
    3. Implement the process_posts() method
    4. Optionally implement process_comments()
    
    Example:
        class MyPlugin(Plugin):
            name = "my_plugin"
            description = "Does something cool"
            
            def process_posts(self, posts):
                for post in posts:
                    post['processed'] = True
                return posts
    """
    name = "base"
    description = "Base plugin"
    enabled = True
    
    @abstractmethod
    def process_posts(self, posts: list) -> list:
        """
        Process posts after scraping.
        
        Args:
            posts: List of post dictionaries
        
        Returns:
            Modified list of posts
        """
        pass
    
    def process_comments(self, comments: list) -> list:
        """
        Process comments after scraping (optional).
        
        Args:
            comments: List of comment dictionaries
        
        Returns:
            Modified list of comments
        """
        return comments
    
    def __repr__(self):
        return f"<Plugin: {self.name}>"


def load_plugins(plugin_dir=None):
    """
    Load all plugins from the plugins directory.
    
    Args:
        plugin_dir: Path to plugins directory
    
    Returns:
        List of plugin instances
    """
    if plugin_dir is None:
        plugin_dir = Path(__file__).parent
    else:
        plugin_dir = Path(plugin_dir)
    
    plugins = []
    
    for file in plugin_dir.glob('**/*.py'):
        # Skip __init__.py and base files
        if file.name.startswith("_"):
            continue
        
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(file.stem, file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[file.stem] = module
            spec.loader.exec_module(module)
            
            # Find Plugin subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, Plugin) and 
                    attr != Plugin and
                    hasattr(attr, 'name')):
                    
                    plugin_instance = attr()
                    if plugin_instance.enabled:
                        plugins.append(plugin_instance)
                        
        except Exception as e:
            print(f"⚠️ Failed to load plugin {file.name}: {e}")
    
    return plugins


def run_plugins(posts, comments, plugins):
    """
    Run all plugins on scraped data.
    
    Args:
        posts: List of posts
        comments: List of comments
        plugins: List of plugin instances
    
    Returns:
        Tuple of (processed_posts, processed_comments)
    """
    for plugin in plugins:
        try:
            print(f"🔌 Running plugin: {plugin.name}")
            posts = plugin.process_posts(posts)
            comments = plugin.process_comments(comments)
        except Exception as e:
            print(f"⚠️ Plugin {plugin.name} failed: {e}")
    
    return posts, comments


def list_plugins(plugin_dir=None):
    """List all available plugins."""
    plugins = load_plugins(plugin_dir)
    
    print("\n🔌 Available Plugins:")
    print("-" * 50)
    
    if not plugins:
        print("   No plugins found")
    else:
        for plugin in plugins:
            status = "✅" if plugin.enabled else "❌"
            print(f"   {status} {plugin.name:<20} {plugin.description}")
    
    print("-" * 50)
    return plugins
