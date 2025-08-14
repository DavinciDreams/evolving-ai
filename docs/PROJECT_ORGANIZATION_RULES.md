# Project Organization Rules

This document establishes the organizational structure and coding standards for the Self-Improving AI Agent project.

## 📁 **Directory Structure**

```
evolving-ai/
├── .env                          # Environment variables (NEVER commit)
├── .gitignore                    # Git ignore patterns
├── README.md                     # Main project documentation
├── main.py                       # Main application entry point
├── requirements.txt              # Python dependencies
├── 
├── evolving_agent/              # Main application code
│   ├── core/                    # Core agent functionality
│   ├── utils/                   # Utility modules
│   ├── knowledge/               # Knowledge management
│   ├── self_modification/       # Self-improvement capabilities
│   └── tests/                   # Unit tests for evolving_agent
│
├── tests/                       # Integration and system tests
│   ├── test_*.py               # All test files
│   ├── debug_*.py              # Debug utilities
│   └── __init__.py             # Test package init
│
├── docs/                        # Documentation
│   ├── API_DOCUMENTATION.md    # API documentation
│   ├── PRD.md                   # Product Requirements Document
│   ├── QUICKSTART.md            # Quick start guide
│   └── *.md                     # All other documentation
│
├── knowledge_base/              # Knowledge storage
├── memory_db/                   # Vector database storage
├── persistent_data/             # Agent state persistence
└── backups/                     # System backups
```

## 🚫 **File Placement Rules**

### **NEVER in Main Directory:**
- ❌ Test files (`test_*.py`, `debug_*.py`)
- ❌ Documentation files (except `README.md`)
- ❌ Temporary or experimental scripts
- ❌ API keys or sensitive data

### **Tests Directory (`tests/`):**
- ✅ All test files: `test_*.py`
- ✅ Debug utilities: `debug_*.py`
- ✅ Test configuration and fixtures
- ✅ Integration and end-to-end tests

### **Docs Directory (`docs/`):**
- ✅ All `.md` documentation files (except README.md)
- ✅ API documentation
- ✅ Architecture diagrams
- ✅ User guides and tutorials

### **Main Directory - Keep Minimal:**
- ✅ `README.md` - Main project overview
- ✅ `main.py` - Application entry point
- ✅ `requirements.txt` - Dependencies
- ✅ Configuration files (`.gitignore`, etc.)
- ✅ Core application scripts only

## 🔐 **Security Rules**

### **Environment Variables (.env):**
- ✅ ALL API keys must be in `.env` file
- ✅ ALL sensitive configuration in environment variables
- ❌ NEVER hardcode API keys in source code
- ❌ NEVER commit `.env` file to git
- ✅ Use descriptive variable names: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`

### **Configuration Pattern:**
```python
# ✅ CORRECT - Use environment variables
api_key = os.getenv("ANTHROPIC_API_KEY")
model = os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")

# ❌ WRONG - Never hardcode
api_key = "sk-ant-api03-..."  # NEVER DO THIS
```

## 📝 **Coding Standards**

### **Import Organization:**
```python
# Standard library imports
import os
import asyncio
from typing import Dict, List, Optional

# Third-party imports
import anthropic
import openai
from dotenv import load_dotenv

# Local imports
from ..utils.config import config
from ..utils.logging import setup_logger
```

### **Documentation:**
- ✅ All classes and functions must have docstrings
- ✅ Include type hints for all parameters and return values
- ✅ Document environment variables in code comments

### **Testing:**
- ✅ All tests in `tests/` directory
- ✅ Use descriptive test file names: `test_llm_interface.py`
- ✅ Mock external API calls in tests
- ✅ Include integration tests for complete workflows

## 🔄 **Maintenance Rules**

### **File Cleanup:**
- 🧹 Regularly remove duplicate files
- 🧹 Move misplaced files to correct directories
- 🧹 Delete temporary or experimental files
- 🧹 Keep main directory clean and organized

### **Documentation Updates:**
- 📚 Update docs when adding new features
- 📚 Keep API documentation current
- 📚 Document configuration changes
- 📚 Maintain clear README.md

## ⚡ **Quick Checklist**

Before committing code, verify:
- [ ] No test files in main directory
- [ ] No API keys hardcoded
- [ ] All docs in `docs/` folder
- [ ] Environment variables used for config
- [ ] Tests pass and are in `tests/` directory
- [ ] Code follows naming conventions
- [ ] Proper import organization

## 🚨 **Enforcement**

These rules should be:
- ✅ Enforced by automated tooling where possible
- ✅ Reviewed in code reviews
- ✅ Documented in commit messages when organizing
- ✅ Applied consistently across all contributors

---

**Remember: A well-organized codebase is easier to maintain, debug, and extend!**
