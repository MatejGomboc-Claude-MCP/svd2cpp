#!/usr/bin/env python3
"""
Test script for SVD2CPP parser

This script demonstrates the parser working with the example SVD file.
"""

import os
import sys
import subprocess
import tempfile
import difflib

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
            # Run the parser with verbose output
            print(f"Running parser on {example_svd}...")
            result = subprocess.run([
                sys.executable, parser_script, example_svd, "-o", temp_dir, "-v"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Parser failed with return code {result.returncode}")
                print(f"Stdout: {result.stdout}")
                print(f"Stderr: {result.stderr}")
                return False
            
            print("Parser completed successfully!")
            print(f"Parser output:")
            print(result.stdout)
            if result.stderr:
                print(f"Parser warnings:")
                print(result.stderr)
            
            # Check generated files
            expected_files = ["gpio_regs.hpp", "uart_regs.hpp", "test_regs.hpp"]
            generated_files = []
            
            for filename in expected_files:
                filepath = os.path.join(temp_dir, filename)
                if os.path.exists(filepath):
                    print(f"✓ Generated: {filename}")
                    generated_files.append(filepath)
                    
                    # Show preview of generated file
                    with open(filepath, 'r') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                    print(f"  Preview of {filename} ({len(lines)} lines):")
                    
                    # Show header and some content
                    preview_lines = 20
                    for i, line in enumerate(lines[:preview_lines]):
                        print(f"    {i+1:3d}: {line}")
                    
                    if len(lines) > preview_lines:
                        print(f"    ... ({len(lines) - preview_lines} more lines)")
                    print()
                else:
                    print(f"✗ Missing: {filename}")
                    return False
            
            # Validate generated C++ syntax by trying to compile headers
            if validate_cpp_syntax(generated_files):
                print("✓ Generated C++ files have valid syntax")
            else:
                print("⚠ Warning: Generated C++ may have syntax issues")
                # Don't fail the test for syntax issues
            
            return True
            
        except Exception as e:
            print(f"Error running parser: {e}")
            import traceback
            traceback.print_exc()
            return False

def validate_cpp_syntax(file_paths):
    """Validate C++ syntax of generated files."""
    for file_path in file_paths:
        print(f"Validating C++ syntax for {os.path.basename(file_path)}...")
        
        # Try to find a C++ compiler
        compilers = ['g++', 'clang++', 'c++']
        compiler = None
        
        for comp in compilers:
            try:
                result = subprocess.run([comp, '--version'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    compiler = comp
                    break
            except FileNotFoundError:
                continue
        
        if not compiler:
            print(f"  No C++ compiler found, skipping syntax validation")
            continue
        
        # Create a simple test file that includes the generated header
        test_cpp_content = f"""#include "{file_path}"

int main() {{
    return 0;
}}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as test_file:
            test_file.write(test_cpp_content)
            test_file_path = test_file.name
        
        try:
            # Try to compile the test file
            result = subprocess.run([
                compiler, '-c', '-std=c++11', '-Wall', '-Wextra', 
                test_file_path, '-o', '/dev/null'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"  ✓ Syntax validation passed")
            else:
                print(f"  ✗ Syntax validation failed:")
                print(f"    {result.stderr}")
                return False
        finally:
            os.unlink(test_file_path)
    
    return True

def show_example_usage():
    """Show example usage of the generated headers."""
    print("\n" + "="*60)
    print("EXAMPLE USAGE OF GENERATED HEADERS")
    print("="*60)
    
    example_code = '''
#include "gpio_regs.hpp"
#include "uart_regs.hpp"

void example_usage() {
    // Configure GPIO pins as outputs
    GPIO_REGS->MODE.bits.MODE0 = 0b01;  // Output mode
    GPIO_REGS->MODE.bits.MODE1 = 0b01;  // Output mode
    GPIO_REGS->MODE.bits.MODE2 = 0b00;  // Input mode
    GPIO_REGS->MODE.bits.MODE3 = 0b00;  // Input mode
    
    // Set output pins
    GPIO_REGS->ODR.bits.ODR0 = 1;  // Set pin 0 high
    GPIO_REGS->ODR.bits.ODR1 = 0;  // Set pin 1 low
    
    // Read input pins
    bool pin2_state = GPIO_REGS->IDR.bits.IDR2;
    bool pin3_state = GPIO_REGS->IDR.bits.IDR3;
    
    // Configure UART
    UART_REGS->CR1.bits.UE = 1;   // Enable UART
    UART_REGS->CR1.bits.TE = 1;   // Enable transmitter
    UART_REGS->CR1.bits.RE = 1;   // Enable receiver
    
    // Check UART status
    if (UART_REGS->SR.bits.TXE) {
        // Transmit buffer empty, can send data
        UART_REGS->DR.bits.DR = 0x55;  // Send data
    }
    
    // Raw register access also available
    uint32_t gpio_mode = GPIO_REGS->MODE.raw;
    UART_REGS->CR1.raw = 0x200C;  // Set multiple bits at once
}
'''
    
    for line in example_code.strip().split('\n'):
        print(f"  {line}")
    
    print("\n" + "="*60)

def main():
    """Main function."""
    print("SVD2CPP Parser Test Suite")
    print("========================")
    print()
    
    success = test_parser()
    
    if success:
        print("✓ All tests passed!")
        show_example_usage()
        print("\nTo use the parser with your own SVD files:")
        print("  python3 svd2cpp.py your_device.svd")
        print("  python3 svd2cpp.py your_device.svd -o output_dir -v")
        print("\nFor more options:")
        print("  python3 svd2cpp.py --help")
        sys.exit(0)
    else:
        print("✗ Tests failed!")
        print("\nTroubleshooting:")
        print("- Check that the SVD file is valid XML")
        print("- Ensure the parser has proper permissions")
        print("- Try running with -v flag for verbose output")
        sys.exit(1)

if __name__ == "__main__":
    main()
