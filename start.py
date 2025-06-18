#!/usr/bin/env python3
"""
Redis RAG Chatbot Startup Script
This script helps users set up and run the Redis RAG chatbot system.
"""

import os
import sys
import time
import subprocess
import logging
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemChecker:
    """Check system prerequisites and configuration."""
    
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
    
    def print_header(self):
        """Print welcome header."""
        print("=" * 60)
        print("🤖 Redis RAG Chatbot - System Startup")
        print("=" * 60)
        print()
    
    def check_python_version(self) -> bool:
        """Check Python version."""
        print("🐍 Checking Python version...")
        version = sys.version_info
        
        if version.major == 3 and version.minor >= 8:
            print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
            self.checks_passed += 1
            return True
        else:
            print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (Need Python 3.8+)")
            self.checks_failed += 1
            return False
    
    def check_redis_connection(self) -> bool:
        """Check Redis connection and RediSearch module."""
        print("🔴 Checking Redis connection...")
        
        try:
            import redis
            from config import settings
            
            # Try to connect to Redis
            r = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True
            )
            
            # Test connection
            r.ping()
            print(f"   ✅ Redis connection successful ({settings.redis_host}:{settings.redis_port})")
            
            # Check for RediSearch module
            modules = r.execute_command("MODULE", "LIST")
            has_search = any("search" in str(module).lower() for module in modules)
            
            if has_search:
                print("   ✅ RediSearch module loaded")
                self.checks_passed += 2
                return True
            else:
                print("   ❌ RediSearch module not found")
                print("   💡 Install Redis Stack: docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest")
                self.checks_failed += 1
                return False
                
        except ImportError:
            print("   ❌ Redis Python client not installed")
            print("   💡 Run: pip install redis")
            self.checks_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Redis connection failed: {str(e)}")
            print("   💡 Make sure Redis is running and accessible")
            self.checks_failed += 1
            return False
    
    def check_environment_variables(self) -> bool:
        """Check required environment variables."""
        print("🔧 Checking environment configuration...")
        
        required_vars = {
            'OPENAI_API_KEY': 'OpenAI API key for embeddings and chat',
        }
        
        optional_vars = {
            'GOOGLE_CLIENT_ID': 'Google Drive integration',
            'GOOGLE_CLIENT_SECRET': 'Google Drive integration',
            'REDIS_HOST': 'Redis connection',
            'REDIS_PORT': 'Redis connection',
        }
        
        missing_required = []
        
        # Check required variables
        for var, description in required_vars.items():
            if os.getenv(var):
                print(f"   ✅ {var} is set")
            else:
                print(f"   ❌ {var} missing ({description})")
                missing_required.append(var)
        
        # Check optional variables
        for var, description in optional_vars.items():
            if os.getenv(var):
                print(f"   ✅ {var} is set")
            else:
                print(f"   ⚠️  {var} not set ({description})")
                self.warnings.append(f"{var} not configured - {description} won't work")
        
        if missing_required:
            print(f"   💡 Create a .env file with: {', '.join(missing_required)}")
            self.checks_failed += 1
            return False
        else:
            self.checks_passed += 1
            return True
    
    def check_dependencies(self) -> bool:
        """Check Python dependencies."""
        print("📦 Checking Python dependencies...")
        
        required_packages = [
            'fastapi',
            'uvicorn',
            'redis',
            'openai',
            'unstructured',
            'google-api-python-client',
            'numpy',
            'pydantic'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                print(f"   ✅ {package}")
            except ImportError:
                print(f"   ❌ {package} not installed")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"   💡 Install missing packages: pip install {' '.join(missing_packages)}")
            self.checks_failed += 1
            return False
        else:
            self.checks_passed += 1
            return True
    
    def check_directories(self) -> bool:
        """Check required directories exist."""
        print("📁 Checking directories...")
        
        from config import settings
        
        directories = [
            settings.upload_dir,
        ]
        
        for directory in directories:
            if os.path.exists(directory):
                print(f"   ✅ {directory} exists")
            else:
                print(f"   ⚠️  {directory} doesn't exist, creating...")
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"   ✅ Created {directory}")
                except Exception as e:
                    print(f"   ❌ Failed to create {directory}: {str(e)}")
                    self.checks_failed += 1
                    return False
        
        self.checks_passed += 1
        return True
    
    def test_openai_connection(self) -> bool:
        """Test OpenAI API connection."""
        print("🤖 Testing OpenAI API connection...")
        
        try:
            import openai
            from config import settings
            
            client = openai.OpenAI(api_key=settings.openai_api_key)
            
            # Test with a simple embedding call
            response = client.embeddings.create(
                input="test",
                model=settings.embedding_model
            )
            
            if response.data and len(response.data) > 0:
                print("   ✅ OpenAI API connection successful")
                self.checks_passed += 1
                return True
            else:
                print("   ❌ OpenAI API returned empty response")
                self.checks_failed += 1
                return False
                
        except Exception as e:
            print(f"   ❌ OpenAI API test failed: {str(e)}")
            print("   💡 Check your API key and credits")
            self.checks_failed += 1
            return False
    
    def run_all_checks(self) -> bool:
        """Run all system checks."""
        self.print_header()
        
        checks = [
            self.check_python_version,
            self.check_dependencies,
            self.check_environment_variables,
            self.check_directories,
            self.check_redis_connection,
            self.test_openai_connection,
        ]
        
        all_passed = True
        
        for check in checks:
            try:
                result = check()
                if not result:
                    all_passed = False
                print()
            except Exception as e:
                logger.error(f"Check failed with exception: {str(e)}")
                all_passed = False
                print()
        
        # Print summary
        print("=" * 60)
        print("📊 SYSTEM CHECK SUMMARY")
        print("=" * 60)
        print(f"✅ Checks passed: {self.checks_passed}")
        print(f"❌ Checks failed: {self.checks_failed}")
        
        if self.warnings:
            print(f"⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        print()
        
        if all_passed:
            print("🎉 All checks passed! System is ready to run.")
            return True
        else:
            print("❌ Some checks failed. Please fix the issues above before running the system.")
            return False


def show_startup_options():
    """Show startup options to the user."""
    print("🚀 STARTUP OPTIONS")
    print("=" * 60)
    print("1. Run system checks only")
    print("2. Start the application (after checks)")
    print("3. Start with development mode (auto-reload)")
    print("4. Show configuration")
    print("5. Exit")
    print()


def show_configuration():
    """Show current configuration."""
    print("⚙️  CURRENT CONFIGURATION")
    print("=" * 60)
    
    try:
        from config import settings
        
        config_items = [
            ("Redis Host", settings.redis_host),
            ("Redis Port", settings.redis_port),
            ("OpenAI Model", settings.chat_model),
            ("Embedding Model", settings.embedding_model),
            ("App Host", settings.app_host),
            ("App Port", settings.app_port),
            ("Upload Directory", settings.upload_dir),
            ("Max Chunk Size", settings.max_chunk_size),
            ("Top K Results", settings.top_k_results),
        ]
        
        for label, value in config_items:
            print(f"{label:20}: {value}")
        
        # Show sensitive config without values
        sensitive_items = [
            ("OpenAI API Key", "Set" if settings.openai_api_key else "Not Set"),
            ("Google Client ID", "Set" if settings.google_client_id else "Not Set"),
            ("Google Client Secret", "Set" if settings.google_client_secret else "Not Set"),
        ]
        
        print("\nSensitive Configuration:")
        for label, status in sensitive_items:
            status_icon = "✅" if status == "Set" else "❌"
            print(f"{label:20}: {status_icon} {status}")
        
    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
    
    print()


def start_application(dev_mode=False):
    """Start the FastAPI application."""
    print("🚀 Starting Redis RAG Chatbot...")
    print("=" * 60)
    
    try:
        import uvicorn
        from config import settings
        
        print(f"Server will start at: http://{settings.app_host}:{settings.app_port}")
        print("Press Ctrl+C to stop the server")
        print()
        
        if dev_mode:
            print("🔧 Development mode: Auto-reload enabled")
            uvicorn.run(
                "main:app",
                host=settings.app_host,
                port=settings.app_port,
                reload=True,
                log_level="info"
            )
        else:
            uvicorn.run(
                "main:app",
                host=settings.app_host,
                port=settings.app_port,
                log_level="info"
            )
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error starting application: {str(e)}")
        sys.exit(1)


def main():
    """Main startup function."""
    checker = SystemChecker()
    
    while True:
        show_startup_options()
        
        try:
            choice = input("Choose an option (1-5): ").strip()
            
            if choice == "1":
                print("\n" + "="*60)
                checker.run_all_checks()
                input("\nPress Enter to continue...")
                
            elif choice == "2":
                print("\n" + "="*60)
                if checker.run_all_checks():
                    input("\nPress Enter to start the application...")
                    start_application(dev_mode=False)
                    break
                else:
                    input("\nFix the issues above and try again. Press Enter to continue...")
                    
            elif choice == "3":
                print("\n" + "="*60)
                if checker.run_all_checks():
                    input("\nPress Enter to start in development mode...")
                    start_application(dev_mode=True)
                    break
                else:
                    input("\nFix the issues above and try again. Press Enter to continue...")
                    
            elif choice == "4":
                print("\n" + "="*60)
                show_configuration()
                input("Press Enter to continue...")
                
            elif choice == "5":
                print("👋 Goodbye!")
                sys.exit(0)
                
            else:
                print("❌ Invalid choice. Please select 1-5.")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            time.sleep(2)
        
        # Clear screen for next iteration (works on Unix/Linux/Mac)
        os.system('clear' if os.name == 'posix' else 'cls')


if __name__ == "__main__":
    main() 