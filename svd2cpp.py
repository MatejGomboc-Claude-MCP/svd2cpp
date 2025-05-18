#!/usr/bin/env python3
"""
SVD to C++ Register Interface Generator

This script parses ARM SVD (System View Description) files and generates
C++ register interfaces using union and bit field struct constructs.

Author: SVD2CPP Project
License: MIT
"""

import xml.etree.ElementTree as ET
import argparse
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class BitField:
    """Represents a bit field within a register."""
    name: str
    description: str
    bit_offset: int
    bit_width: int
    access: str = "read-write"
    
    @property
    def bit_mask(self) -> int:
        """Calculate the bit mask for this field."""
        return ((1 << self.bit_width) - 1) << self.bit_offset

    @property
    def end_bit(self) -> int:
        """Return the last bit position of this field."""
        return self.bit_offset + self.bit_width - 1


@dataclass
class Register:
    """Represents a hardware register."""
    name: str
    description: str
    address_offset: int
    size: int
    access: str
    reset_value: int
    bit_fields: List[BitField]
    
    @property
    def size_bits(self) -> int:
        """Register size in bits."""
        return self.size * 8


@dataclass
class Peripheral:
    """Represents a hardware peripheral containing registers."""
    name: str
    description: str
    base_address: int
    registers: List[Register]


class SVDParser:
    """Parser for ARM SVD files."""
    
    def __init__(self, svd_file: str):
        self.svd_file = svd_file
        self.tree = ET.parse(svd_file)
        self.root = self.tree.getroot()
        self.peripherals: List[Peripheral] = []
    
    def _get_text_content(self, element: Optional[ET.Element]) -> str:
        """Safely get text content from an XML element."""
        if element is None or element.text is None:
            return ""
        return element.text.strip()
    
    def _try_parse_int(self, text: str, default: int = 0) -> int:
        """Safely parse integer from text with various formats."""
        if not text:
            return default
        text = text.strip()
        try:
            # Handle hexadecimal
            if text.startswith('0x') or text.startswith('0X'):
                return int(text, 16)
            # Handle binary
            if text.startswith('0b') or text.startswith('0B'):
                return int(text, 2)
            # Handle regular decimal
            return int(text)
        except (ValueError, TypeError):
            return default

    def _find_element_by_name(self, parent: ET.Element, names: List[str]) -> Optional[ET.Element]:
        """Find first element matching any of the given names."""
        for name in names:
            elem = parent.find(name)
            if elem is not None:
                return elem
        return None

    def parse(self) -> List[Peripheral]:
        """Parse the SVD file and extract peripherals."""
        self.peripherals = []
        
        # Find all peripherals
        for peripheral_elem in self.root.findall('.//peripheral'):
            peripheral = self._parse_peripheral(peripheral_elem)
            if peripheral and peripheral.registers:
                self.peripherals.append(peripheral)
        
        return self.peripherals
    
    def _parse_peripheral(self, peripheral_elem: ET.Element) -> Optional[Peripheral]:
        """Parse a single peripheral from XML element."""
        # Try both 'name' and 'n' tags for name
        name_elem = self._find_element_by_name(peripheral_elem, ['name', 'n'])
        if name_elem is None:
            return None
        
        name = self._get_text_content(name_elem)
        if not name:
            return None
        
        # Sanitize peripheral name for C++ (only alphanumeric and underscore)
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Get description
        desc_elem = peripheral_elem.find('description')
        description = self._get_text_content(desc_elem)
        
        # Get base address (required)
        base_addr_elem = peripheral_elem.find('baseAddress')
        if base_addr_elem is None:
            return None
        
        base_address_text = self._get_text_content(base_addr_elem)
        base_address = self._try_parse_int(base_address_text)
        if base_address == 0 and base_address_text != "0" and base_address_text != "0x0":
            return None  # Invalid address
        
        # Parse registers
        registers = []
        registers_elem = peripheral_elem.find('registers')
        if registers_elem is not None:
            for register_elem in registers_elem.findall('register'):
                register = self._parse_register(register_elem)
                if register:
                    registers.append(register)
        
        # Sort registers by address offset for proper memory layout
        registers.sort(key=lambda r: r.address_offset)
        
        return Peripheral(name, description, base_address, registers)
    
    def _parse_register(self, register_elem: ET.Element) -> Optional[Register]:
        """Parse a single register from XML element."""
        # Try both 'name' and 'n' tags for name
        name_elem = self._find_element_by_name(register_elem, ['name', 'n'])
        if name_elem is None:
            return None
        
        name = self._get_text_content(name_elem)
        if not name:
            return None
        
        # Sanitize register name for C++
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Get description
        desc_elem = register_elem.find('description')
        description = self._get_text_content(desc_elem)
        
        # Get address offset (required)
        offset_elem = register_elem.find('addressOffset')
        if offset_elem is None:
            return None
        
        offset_text = self._get_text_content(offset_elem)
        address_offset = self._try_parse_int(offset_text)
        
        # Get size in bits, default to 32 bits
        size_elem = register_elem.find('size')
        if size_elem is not None:
            size_bits = self._try_parse_int(self._get_text_content(size_elem), 32)
        else:
            size_bits = 32
        
        # Convert to bytes, ensuring even byte boundary
        size = (size_bits + 7) // 8
        
        # Get access (default to read-write)
        access_elem = register_elem.find('access')
        access = self._get_text_content(access_elem) if access_elem is not None else "read-write"
        
        # Get reset value (default to 0)
        reset_elem = register_elem.find('resetValue')
        reset_value = self._try_parse_int(self._get_text_content(reset_elem), 0)
        
        # Parse bit fields
        bit_fields = []
        fields_elem = register_elem.find('fields')
        if fields_elem is not None:
            for field_elem in fields_elem.findall('field'):
                bit_field = self._parse_bit_field(field_elem, size_bits)
                if bit_field:
                    bit_fields.append(bit_field)
        
        # Sort bit fields by offset and validate they don't overlap
        bit_fields.sort(key=lambda f: f.bit_offset)
        validated_fields = self._validate_bit_fields(bit_fields, size_bits)
        
        return Register(name, description, address_offset, size, access, reset_value, validated_fields)
    
    def _parse_bit_field(self, field_elem: ET.Element, register_size_bits: int) -> Optional[BitField]:
        """Parse a single bit field from XML element."""
        # Try both 'name' and 'n' tags for name
        name_elem = self._find_element_by_name(field_elem, ['name', 'n'])
        if name_elem is None:
            return None
        
        name = self._get_text_content(name_elem)
        if not name:
            return None
        
        # Sanitize field name for C++
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Get description
        desc_elem = field_elem.find('description')
        description = self._get_text_content(desc_elem)
        
        # Get bit range - try multiple formats
        bit_offset_elem = field_elem.find('bitOffset')
        bit_width_elem = field_elem.find('bitWidth')
        
        if bit_offset_elem is not None and bit_width_elem is not None:
            bit_offset = self._try_parse_int(self._get_text_content(bit_offset_elem))
            bit_width = self._try_parse_int(self._get_text_content(bit_width_elem))
        else:
            # Try alternative format with lsb/msb
            lsb_elem = field_elem.find('lsb')
            msb_elem = field_elem.find('msb')
            if lsb_elem is not None and msb_elem is not None:
                lsb = self._try_parse_int(self._get_text_content(lsb_elem))
                msb = self._try_parse_int(self._get_text_content(msb_elem))
                bit_offset = lsb
                bit_width = msb - lsb + 1
            else:
                # Try bitRange format (e.g., "[7:0]")
                bit_range_elem = field_elem.find('bitRange')
                if bit_range_elem is not None:
                    bit_range_text = self._get_text_content(bit_range_elem)
                    match = re.match(r'\[(\d+):(\d+)\]', bit_range_text)
                    if match:
                        msb = int(match.group(1))
                        lsb = int(match.group(2))
                        bit_offset = lsb
                        bit_width = msb - lsb + 1
                    else:
                        return None
                else:
                    return None
        
        # Validate bit field bounds
        if bit_offset < 0 or bit_width <= 0:
            return None
        if bit_offset + bit_width > register_size_bits:
            return None
        
        # Get access
        access_elem = field_elem.find('access')
        access = self._get_text_content(access_elem) if access_elem is not None else "read-write"
        
        return BitField(name, description, bit_offset, bit_width, access)

    def _validate_bit_fields(self, bit_fields: List[BitField], register_size_bits: int) -> List[BitField]:
        """Validate bit fields don't overlap and are within register bounds."""
        if not bit_fields:
            return []
        
        validated = []
        for field in bit_fields:
            # Check if field fits in register
            if field.bit_offset + field.bit_width > register_size_bits:
                print(f"Warning: Bit field '{field.name}' extends beyond register size, skipping")
                continue
            
            # Check for overlap with previous fields
            overlap = False
            for prev_field in validated:
                if not (field.bit_offset >= prev_field.end_bit + 1 or field.end_bit < prev_field.bit_offset):
                    print(f"Warning: Bit field '{field.name}' overlaps with '{prev_field.name}', skipping")
                    overlap = True
                    break
            
            if not overlap:
                validated.append(field)
        
        return validated


class CPPGenerator:
    """C++ code generator for registers and bit fields."""
    
    def __init__(self, peripherals: List[Peripheral], output_dir: str = "generated"):
        self.peripherals = peripherals
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def _sanitize_identifier(self, name: str) -> str:
        """Sanitize identifier for C++ (ensure it starts with letter/underscore)."""
        # Remove invalid characters
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Ensure it starts with letter or underscore
        if name and name[0].isdigit():
            name = '_' + name
        
        # Ensure it's not empty
        if not name:
            name = '_unnamed'
            
        return name
    
    def _get_cpp_integer_type(self, size_bits: int) -> str:
        """Get appropriate C++ integer type for given bit size."""
        if size_bits <= 8:
            return "uint8_t"
        elif size_bits <= 16:
            return "uint16_t"
        elif size_bits <= 32:
            return "uint32_t"
        elif size_bits <= 64:
            return "uint64_t"
        else:
            # For very large registers, use array
            return "uint8_t"
    
    def generate(self):
        """Generate C++ files for all peripherals."""
        for peripheral in self.peripherals:
            self._generate_peripheral_header(peripheral)
    
    def _generate_peripheral_header(self, peripheral: Peripheral):
        """Generate C++ header file for a peripheral."""
        safe_name = self._sanitize_identifier(peripheral.name.lower())
        header_filename = f"{safe_name}_regs.hpp"
        header_path = os.path.join(self.output_dir, header_filename)
        
        try:
            with open(header_path, 'w') as f:
                self._write_header_preamble(f, peripheral)
                self._write_register_structs(f, peripheral)
                self._write_peripheral_struct(f, peripheral)
                self._write_header_postamble(f, peripheral)
            
            print(f"Generated: {header_path}")
        except IOError as e:
            print(f"Error generating {header_path}: {e}")
    
    def _write_header_preamble(self, f, peripheral: Peripheral):
        """Write header file preamble."""
        safe_name = self._sanitize_identifier(peripheral.name.upper())
        guard_name = f"{safe_name}_REGS_HPP"
        
        f.write(f"""#ifndef {guard_name}
#define {guard_name}

#include <cstdint>

/**
 * @file {self._sanitize_identifier(peripheral.name.lower())}_regs.hpp
 * @brief {peripheral.description}
 * @details Generated from SVD file - DO NOT EDIT MANUALLY
 * 
 * Base Address: 0x{peripheral.base_address:08X}
 */

namespace {self._sanitize_identifier(peripheral.name.lower())}_regs {{

""")
    
    def _write_register_structs(self, f, peripheral: Peripheral):
        """Write register structures with bit fields."""
        for register in peripheral.registers:
            # Sanitize register name
            safe_reg_name = self._sanitize_identifier(register.name)
            
            # Write register comment
            f.write(f"""/**
 * @brief {register.description}
 * @details Offset: 0x{register.address_offset:04X}, Size: {register.size} bytes
 * @details Reset value: 0x{register.reset_value:08X}
 * @details Access: {register.access}
 */\n""")
            
            # Write register union
            f.write(f"union {safe_reg_name}_t {{\n")
            
            # Raw value access
            size_bits = register.size_bits
            if register.size <= 8:
                raw_type = self._get_cpp_integer_type(size_bits)
                f.write(f"    {raw_type} raw;\n")
            else:
                # For larger registers, use array
                f.write(f"    uint8_t raw[{register.size}];\n")
            
            # Bit field struct (only if register is <= 64 bits and has fields)
            if register.bit_fields and size_bits <= 64:
                f.write("    struct {\n")
                
                # Sort bit fields by offset
                sorted_fields = sorted(register.bit_fields, key=lambda x: x.bit_offset)
                
                current_bit = 0
                field_counter = 0
                
                for field in sorted_fields:
                    # Add padding if needed
                    if field.bit_offset > current_bit:
                        padding_bits = field.bit_offset - current_bit
                        f.write(f"        {self._get_cpp_integer_type(size_bits)} : {padding_bits};\n")
                    
                    # Write field comment
                    if field.description:
                        f.write(f"        /// {field.description}\n")
                    
                    # Sanitize field name
                    safe_field_name = self._sanitize_identifier(field.name)
                    
                    # Write bit field
                    f.write(f"        {self._get_cpp_integer_type(size_bits)} {safe_field_name} : {field.bit_width};\n")
                    
                    current_bit = field.bit_offset + field.bit_width
                    field_counter += 1
                
                # Add final padding if needed
                if current_bit < size_bits:
                    remaining_bits = size_bits - current_bit
                    f.write(f"        {self._get_cpp_integer_type(size_bits)} : {remaining_bits};\n")
                
                f.write("    } bits;\n")
            
            f.write("};\n\n")
            
            # Add static_assert for size validation
            f.write(f"static_assert(sizeof({safe_reg_name}_t) == {register.size}, "
                   f"\"Size mismatch for {safe_reg_name}_t\");\n\n")
    
    def _write_peripheral_struct(self, f, peripheral: Peripheral):
        """Write peripheral structure containing all registers."""
        safe_peripheral_name = self._sanitize_identifier(peripheral.name.upper())
        
        f.write(f"""/**
 * @brief {peripheral.description} register block
 * @details Base address: 0x{peripheral.base_address:08X}
 */
struct {safe_peripheral_name}_regs_t {{
""")
        
        # Sort registers by address offset
        sorted_registers = sorted(peripheral.registers, key=lambda x: x.address_offset)
        
        current_offset = 0
        reserved_counter = 0
        
        for register in sorted_registers:
            # Add padding if needed
            if register.address_offset > current_offset:
                padding_bytes = register.address_offset - current_offset
                if padding_bytes > 0:
                    f.write(f"    uint8_t _reserved_{reserved_counter:03d}[{padding_bytes}];\n")
                    reserved_counter += 1
            
            # Write register
            safe_reg_name = self._sanitize_identifier(register.name)
            f.write(f"    volatile {safe_reg_name}_t {safe_reg_name};\n")
            current_offset = register.address_offset + register.size
        
        f.write("};\n\n")
        
        # Add static assert for alignment
        f.write(f"static_assert(sizeof({safe_peripheral_name}_regs_t) >= {current_offset}, "
               f"\"Size mismatch for {safe_peripheral_name}_regs_t\");\n\n")
        
        # Add memory-mapped pointer
        f.write(f"""// Memory-mapped peripheral instance
#define {safe_peripheral_name}_REGS \\
    (reinterpret_cast<volatile {safe_peripheral_name}_regs_t*>(0x{peripheral.base_address:08X}U))

""")
    
    def _write_header_postamble(self, f, peripheral: Peripheral):
        """Write header file postamble."""
        safe_name = self._sanitize_identifier(peripheral.name.upper())
        f.write(f"""}} // namespace {self._sanitize_identifier(peripheral.name.lower())}_regs

#endif // {safe_name}_REGS_HPP
""")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Convert SVD files to C++ register interfaces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s device.svd                     # Generate in ./generated/
  %(prog)s device.svd -o my_output/       # Generate in ./my_output/
  %(prog)s device.svd -v                  # Verbose output
"""
    )
    parser.add_argument("svd_file", help="Path to SVD file")
    parser.add_argument("-o", "--output", default="generated", 
                       help="Output directory (default: generated)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.svd_file):
        print(f"Error: SVD file '{args.svd_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    if not os.access(args.svd_file, os.R_OK):
        print(f"Error: Cannot read SVD file '{args.svd_file}'", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Parse SVD file
        if args.verbose:
            print(f"Parsing SVD file: {args.svd_file}")
        
        svd_parser = SVDParser(args.svd_file)
        peripherals = svd_parser.parse()
        
        if not peripherals:
            print("Warning: No valid peripherals found in SVD file")
            return
        
        print(f"Found {len(peripherals)} peripheral(s)")
        
        if args.verbose:
            for peripheral in peripherals:
                print(f"  - {peripheral.name}: {len(peripheral.registers)} register(s) at 0x{peripheral.base_address:08X}")
                for register in peripheral.registers:
                    print(f"    - {register.name}: {len(register.bit_fields)} bit field(s)")
        
        # Generate C++ files
        print(f"Generating C++ files in: {os.path.abspath(args.output)}")
        cpp_generator = CPPGenerator(peripherals, args.output)
        cpp_generator.generate()
        
        print("Generation complete!")
        
    except ET.ParseError as e:
        print(f"Error parsing SVD file: {e}", file=sys.stderr)
        if args.verbose:
            print(f"Parse error details: line {e.position[0]}, column {e.position[1]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
