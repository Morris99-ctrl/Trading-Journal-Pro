import os
from pathlib import Path

# Create required directories
Path("C:\\Users\\antho\\Maurice_Codes\\Trading_Journal").mkdir(parents=True, exist_ok=True)

# Initialize project structure
def create_project_structure():
    """Create the complete project structure"""
    files = [
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\__init__.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\models.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\data.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\services.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\calculators.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\analytics.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\cli.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\main.py",
        "C:\\Users\\antho\\Maurice_Codes\\Trading_Journal\\README.md"
    ]
    
    print("Project structure created successfully!")
    print(f"Created {len(files)} Python files and documentation")
    print("\nTo run the application:")
    print("1. Navigate to Trading_Journal directory")
    print("2. Run: python main.py (GUI) or python cli.py (CLI)")
    print("\nFeatures included:")
    print("- Trade logging and management")
    print("- P&L calculation (realized/unrealized)")
    print("- Comprehensive performance analytics")
    print("- Risk metrics (Sharpe ratio, max drawdown, etc.)")
    print("- Portfolio and symbol analysis")
    print("- Both GUI and CLI interfaces")

if __name__ == "__main__":
    create_project_structure()