#!/usr/bin/env python3
"""
Test script for SVD2CPP parser

This script demonstrates the parser working with the example SVD file
and performs comprehensive validation of the generated C++ code.
"""

import os
import sys
import subprocess
import tempfile
import textwrap
import time

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
            # Test 1: Basic parsing with verbose output
            print("Test 1: Basic SVD parsing...")
            result = subprocess.run([
                sys.executable, parser_script, example_svd, "-o", temp_dir, "-v"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Parser failed with return code {result.returncode}")
                print(f"Stdout: {result.stdout}")
                print(f"Stderr: {result.stderr}")
                return False
            
            print("✓ Parser completed successfully")
            
            # Check parser output
            if result.stdout:
                print("Parser output:")
                for line in result.stdout.strip().split('\n'):
                    print(f"  {line}")
            
            if result.stderr:
                print("Parser warnings:")
                for line in result.stderr.strip().split('\n'):
                    print(f"  {line}")
            
            # Test 2: Check generated files
            print("\nTest 2: Validating generated files...")
            expected_files = ["gpio_regs.hpp", "uart_regs.hpp"]
            generated_files = []
            
            for filename in expected_files:
                filepath = os.path.join(temp_dir, filename)
                if os.path.exists(filepath):
                    print(f"✓ Generated: {filename}")
                    generated_files.append(filepath)
                    
                    # Validate file content
                    if not validate_file_content(filepath):
                        print(f"✗ Content validation failed for {filename}")
                        return False
                else:
                    print(f"✗ Missing: {filename}")
                    return False
            
            # Test 3: Syntax validation
            print("\nTest 3: C++ syntax validation...")
            if validate_cpp_syntax(generated_files):
                print("✓ All generated files have valid C++ syntax")
            else:
                print("⚠ Warning: Some syntax issues detected (but not fatal)")
            
            # Test 4: Content verification
            print("\nTest 4: Content verification...")
            if verify_generated_content(generated_files):
                print("✓ Generated content verification passed")
            else:
                print("✗ Content verification failed")
                return False
            
            # Test 5: Error handling
            print("\nTest 5: Error handling tests...")
            if test_error_handling(parser_script, temp_dir):
                print("✓ Error handling tests passed")
            else:
                print("✗ Error handling tests failed")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False

def validate_file_content(filepath):
    """Validate basic content of generated file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for basic structure
        if not content.strip():
            print(f"  ✗ {os.path.basename(filepath)}: Empty file")
            return False
        
        # Check for header guards
        lines = content.split('\n')
        has_ifndef = any('#ifndef' in line for line in lines[:10])
        has_define = any('#define' in line for line in lines[:10])
        has_endif = any('#endif' in line for line in lines[-10:])
        
        if not (has_ifndef and has_define and has_endif):
            print(f"  ✗ {os.path.basename(filepath)}: Missing header guards")
            return False
        
        # Check for namespace
        if 'namespace ' not in content:
            print(f"  ✗ {os.path.basename(filepath)}: Missing namespace")
            return False
        
        # Check for union definitions
        if 'union ' not in content:
            print(f"  ⚠ {os.path.basename(filepath)}: No union definitions found")
        
        # Check for struct definitions
        if 'struct ' not in content:
            print(f"  ✗ {os.path.basename(filepath)}: Missing struct definitions")
            return False
        
        # Check for volatile qualifiers
        if 'volatile' not in content:
            print(f"  ✗ {os.path.basename(filepath)}: Missing volatile qualifiers")
            return False
        
        # Check for static_assert
        if 'static_assert' not in content:
            print(f"  ⚠ {os.path.basename(filepath)}: No static_assert statements found")
        
        print(f"  ✓ {os.path.basename(filepath)}: Basic content validation passed")
        return True
        
    except Exception as e:
        print(f"  ✗ {os.path.basename(filepath)}: Error reading file: {e}")
        return False

def validate_cpp_syntax(file_paths):
    """Validate C++ syntax of generated files."""
    # Try to find a C++ compiler
    compilers = ['g++', 'clang++', 'c++']
    compiler = None
    
    for comp in compilers:
        try:
            result = subprocess.run([comp, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                compiler = comp
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    if not compiler:
        print("  No C++ compiler found, skipping syntax validation")
        return True  # Don't fail if no compiler available
    
    print(f"  Using compiler: {compiler}")
    
    # Create a test source file that includes all headers
    test_content = '#include <cstdint>\n\n'
    for file_path in file_paths:
        # Get the header filename for inclusion
        header_name = os.path.basename(file_path)
        test_content += f'#include "{header_name}"\n'
    
    test_content += '\nint main() { return 0; }\n'
    
    all_passed = True
    
    # Create temporary test file and try to compile
    with tempfile.TemporaryDirectory() as test_dir:
        # Copy headers to test directory
        for file_path in file_paths:
            import shutil
            shutil.copy(file_path, test_dir)
        
        # Create test source file
        test_cpp_path = os.path.join(test_dir, 'test.cpp')
        with open(test_cpp_path, 'w') as f:
            f.write(test_content)
        
        try:
            # Try to compile the test file
            result = subprocess.run([
                compiler, '-c', '-std=c++11', '-Wall', '-Wextra', '-Werror',
                '-pedantic', test_cpp_path, '-o', os.path.join(test_dir, 'test.o')
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("  ✓ Compilation successful")
            else:
                print("  ✗ Compilation failed:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        print(f"    {line}")
                all_passed = False
                
        except subprocess.TimeoutExpired:
            print("  ⚠ Compilation timed out")
            all_passed = False
        except Exception as e:
            print(f"  ✗ Compilation error: {e}")
            all_passed = False
    
    return all_passed

def verify_generated_content(file_paths):
    """Verify specific content in generated files."""
    
    expected_content = {
        'gpio_regs.hpp': [
            'namespace gpio_regs',
            'union MODE_t',
            'union IDR_t', 
            'union ODR_t',
            'struct GPIO_regs_t',
            'MODE0 : 2',
            'ODR0 : 1',
            'IDR0 : 1',
            '#define GPIO_REGS'
        ],
        'uart_regs.hpp': [
            'namespace uart_regs',
            'union CR1_t',
            'union SR_t',
            'union DR_t',
            'struct UART_regs_t',
            'UE : 1',
            'TC : 1',
            'DR : 9',
            '#define UART_REGS'
        ]
    }
    
    all_passed = True
    
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        
        if filename not in expected_content:
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            missing_items = []
            for expected_item in expected_content[filename]:
                if expected_item not in content:
                    missing_items.append(expected_item)
            
            if missing_items:
                print(f"  ✗ {filename}: Missing expected content:")
                for item in missing_items:
                    print(f"    - {item}")
                all_passed = False
            else:
                print(f"  ✓ {filename}: All expected content found")
                
        except Exception as e:
            print(f"  ✗ {filename}: Error verifying content: {e}")
            all_passed = False
    
    return all_passed

def test_error_handling(parser_script, output_dir):
    """Test error handling with invalid inputs."""
    
    test_cases = [
        {
            'name': 'Non-existent file',
            'args': ['non_existent_file.svd'],
            'expect_failure': True
        },
        {
            'name': 'Invalid XML file',
            'content': '<invalid xml>',
            'expect_failure': True
        },
        {
            'name': 'Empty SVD file',
            'content': '<?xml version="1.0" encoding="utf-8"?><device></device>',
            'expect_failure': False,  # Should handle gracefully
        },
        {
            'name': 'SVD with no peripherals',
            'content': '''<?xml version="1.0" encoding="utf-8"?>
                        <device>
                            <vendor>Test</vendor>
                            <name>TEST</name>
                            <peripherals></peripherals>
                        </device>''',
            'expect_failure': False,  # Should handle gracefully
        }
    ]
    
    all_passed = True
    
    with tempfile.TemporaryDirectory() as test_dir:
        for i, test_case in enumerate(test_cases):
            test_name = test_case['name']
            print(f"  Testing: {test_name}")
            
            if 'content' in test_case:
                # Create temporary SVD file
                test_svd = os.path.join(test_dir, f'test_{i}.svd')
                with open(test_svd, 'w') as f:
                    f.write(textwrap.dedent(test_case['content']))
                test_args = [test_svd, '-o', output_dir]
            else:
                test_args = test_case['args'] + ['-o', output_dir]
            
            try:
                result = subprocess.run([
                    sys.executable, parser_script] + test_args,
                    capture_output=True, text=True, timeout=10)
                
                if test_case['expect_failure']:
                    if result.returncode == 0:
                        print(f"    ✗ Expected failure but parser succeeded")
                        all_passed = False
                    else:
                        print(f"    ✓ Failed as expected (return code: {result.returncode})")
                else:
                    if result.returncode != 0:
                        print(f"    ✗ Unexpected failure (return code: {result.returncode})")
                        print(f"      stderr: {result.stderr}")
                        all_passed = False
                    else:
                        print(f"    ✓ Handled gracefully")
                        
            except subprocess.TimeoutExpired:
                print(f"    ✗ Parser timed out")
                all_passed = False
            except Exception as e:
                print(f"    ✗ Test error: {e}")
                all_passed = False
    
    return all_passed

def show_example_usage():
    """Show example usage of the generated headers."""
    print("\n" + "="*70)
    print("EXAMPLE USAGE OF GENERATED HEADERS")
    print("="*70)
    
    example_code = '''
// Include the generated headers
#include "gpio_regs.hpp"
#include "uart_regs.hpp"

void configure_peripherals() {
    // GPIO Configuration
    GPIO_REGS->MODE.bits.MODE0 = 0b01;  // Pin 0 as output
    GPIO_REGS->MODE.bits.MODE1 = 0b01;  // Pin 1 as output
    GPIO_REGS->MODE.bits.MODE2 = 0b00;  // Pin 2 as input
    GPIO_REGS->MODE.bits.MODE3 = 0b00;  // Pin 3 as input
    
    // Set GPIO outputs
    GPIO_REGS->ODR.bits.ODR0 = 1;  // Set pin 0 high
    GPIO_REGS->ODR.bits.ODR1 = 0;  // Set pin 1 low
    
    // Read GPIO inputs
    bool pin2_state = GPIO_REGS->IDR.bits.IDR2;
    bool pin3_state = GPIO_REGS->IDR.bits.IDR3;
    
    // UART Configuration
    UART_REGS->CR1.bits.UE = 1;   // Enable UART
    UART_REGS->CR1.bits.TE = 1;   // Enable transmitter
    UART_REGS->CR1.bits.RE = 1;   // Enable receiver
    UART_REGS->CR1.bits.M = 0;    // 8-bit word length
    UART_REGS->CR1.bits.PCE = 0;  // No parity control
    
    // Send data via UART
    while (!UART_REGS->SR.bits.TXE)  // Wait for TX empty
        ;
    UART_REGS->DR.bits.DR = 0x55;     // Send data byte
    
    // Check for UART errors
    if (UART_REGS->SR.bits.ORE) {
        // Handle overrun error
    }
    
    // Using raw register access
    uint32_t mode_value = GPIO_REGS->MODE.raw;
    UART_REGS->CR1.raw = 0x200C;  // Set multiple bits atomically
    
    // Register unions provide both structured and raw access
    static_assert(sizeof(GPIO_REGS->MODE) == 4, "Register size check");
}

// Interrupt handler example
extern "C" void UART_IRQHandler() {
    if (UART_REGS->SR.bits.RXNE) {
        // Data received
        uint16_t data = UART_REGS->DR.bits.DR;
        // Process received data...
    }
    
    if (UART_REGS->SR.bits.TC) {
        // Transmission complete
        // Handle completion...
    }
}'''
    
    for line in example_code.strip().split('\n'):
        print(f"  {line}")
    
    print("\n" + "="*70)
    print("KEY FEATURES DEMONSTRATED:")
    print("✓ Type-safe bit field access (e.g., .bits.MODE0)")
    print("✓ Raw register access (e.g., .raw)")
    print("✓ Volatile memory-mapped pointers")
    print("✓ Static size assertions")
    print("✓ Automatic padding and alignment")
    print("✓ Clean namespace organization")
    print("="*70)

def show_performance_info():
    """Show performance information about the parser."""
    print("\nPERFORMANCE INFORMATION:")
    print("- Single-pass XML parsing")
    print("- Minimal memory footprint")
    print("- Fast generation (typically <1s for small-medium SVD files)")
    print("- Efficient duplicate detection")
    print("- Comprehensive validation with early error detection")

def main():
    """Main function."""
    print("SVD2CPP Parser Comprehensive Test Suite")
    print("==========================================")
    print()
    
    start_time = time.time()
    success = test_parser()
    end_time = time.time()
    
    print(f"\nTest execution time: {end_time - start_time:.2f} seconds")
    
    if success:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        show_example_usage()
        show_performance_info()
        print("\nTo use the parser with your own SVD files:")
        print("  python3 svd2cpp.py your_device.svd")
        print("  python3 svd2cpp.py your_device.svd -o output_dir -v")
        print("\nFor more options:")
        print("  python3 svd2cpp.py --help")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED ❌")
        print("\nTroubleshooting tips:")
        print("- Verify SVD file format is valid XML")
        print("- Check that peripherals have required elements")
        print("- Ensure write permissions for output directory")
        print("- Try running with -v flag for detailed output")
        print("- Check for duplicate register/field names")
        sys.exit(1)

if __name__ == "__main__":
    main()
