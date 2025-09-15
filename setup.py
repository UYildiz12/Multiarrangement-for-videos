#!/usr/bin/env python3
"""Setup script for multiarrangement with optional C extensions."""

from setuptools import setup, Extension
import numpy as np
import sys
import os

# Check if we can build C extensions
def can_build_c_extensions():
    """Check if C extensions can be built on this system."""
    # On Windows, check for Visual Studio build tools
    if sys.platform == "win32":
        # Check for Visual Studio build tools
        vs_paths = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools",
            r"C:\Program Files\Microsoft Visual Studio\2019\BuildTools",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools",
            r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools",
        ]
        
        for path in vs_paths:
            if os.path.exists(path):
                return True
        
        # Check for cl.exe in PATH
        try:
            import subprocess
            result = subprocess.run(["cl"], capture_output=True, text=True)
            return result.returncode != 1  # cl.exe exists but shows usage
        except:
            pass
        
        return False
    
    # On Unix-like systems, check for gcc
    try:
        import subprocess
        result = subprocess.run(["gcc", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

# Try to build C extension, but make it optional
ext_modules = []
if can_build_c_extensions():
    try:
        # C extension for high-performance batch generation
        # Platform-aware compile/link args
        if sys.platform == "win32":
            # MSVC: use /O2 and avoid -std=c11 (not supported)
            compile_args = ['/O2']
            link_args = []
        else:
            compile_args = ['-O3', '-std=c11']
            link_args = ['-lm'] if 'linux' in sys.platform else []

        greedy_extension = Extension(
            'multiarrangement.greedy_c',
            sources=['src/greedy_module.c'],
            include_dirs=[np.get_include()],
            extra_compile_args=compile_args,
            extra_link_args=link_args,
        )
        ext_modules = [greedy_extension]
        print("C extension will be built")
    except Exception as e:
        print(f"C extension disabled: {e}")
        print("The package will work with pure Python implementations")
        ext_modules = []
else:
    print("C extension disabled: No C compiler available")
    print("The package will work with pure Python implementations")
    ext_modules = []

setup(
    ext_modules=ext_modules,
    zip_safe=False,
)
