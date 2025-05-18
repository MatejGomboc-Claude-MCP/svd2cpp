#!/usr/bin/env python3
"""
Test script for SVD2CPP parser

This script demonstrates the parser working with the example SVD file.
"""

import os
import sys
import subprocess
import tempfile

def test_parser():
    """Test the SVD parser with the example file."""
    
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the parser and example SVD
    parser_script = os.path.join(current_dir, "svd2cpp.py")
    example_svd = os.path.join(current_dir, "examples", "simple_mcu.svd")
    
    # Check if files exist
    if not os.path.exists(parser_script):
        print(f"Error: Parser script not found: {parser_script}")
        return False
    
    if not os.path.exists(example_svd):
        print(f"Error: Example SVD not found: {example_svd}")
        return False
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Run the parser
            print(f"Running parser on {example_svd}...")
            result = subprocess.run([
                sys.executable, parser_script, example_svd, "-o", temp_dir, "-v"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Parser failed with return code {result.returncode}")
                print(f"Stderr: {result.stderr}")
                return False
            
            print("Parser completed successfully!")
            print(f"Output: {result.stdout}")
            
            # Check generated files
            expected_files = ["gpio_regs.hpp", "uart_regs.hpp"]
            for filename in expected_files:
                filepath = os.path.join(temp_dir, filename)
                if os.path.exists(filepath):
                    print(f"✓ Generated: {filename}")
                    
                    # Show first few lines of generated file
                    with open(filepath, 'r') as f:
                        lines = f.readlines()[:15]
                        print(f"  Preview of {filename}:")
                        for line in lines:
                            print(f"    {line.rstrip()}")
                        print("    ...")
                        print()
                else:
                    print(f"✗ Missing: {filename}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error running parser: {e}")
            return False

def main():
    """Main function."""
    print("SVD2CPP Parser Test")
    print("==================")
    print()
    
    success = test_parser()
    
    if success:
        print("✓ All tests passed!")
        print()
        print("To use the parser with your own SVD files:")
        print("  python3 svd2cpp.py your_device.svd")
        print("  python3 svd2cpp.py your_device.svd -o output_dir")
        sys.exit(0)
    else:
        print("✗ Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
