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
        name_elem = peripheral_elem.find('name')
        if name_elem is None:
            return None
        
        name = name_elem.text.strip()
        
        # Get description
        desc_elem = peripheral_elem.find('description')
        description = desc_elem.text.strip() if desc_elem is not None else ""
        
        # Get base address
        base_addr_elem = peripheral_elem.find('baseAddress')
        if base_addr_elem is None:
            return None
        base_address = int(base_addr_elem.text, 0)
        
        # Parse registers
        registers = []
        registers_elem = peripheral_elem.find('registers')
        if registers_elem is not None:
            for register_elem in registers_elem.findall('register'):
                register = self._parse_register(register_elem)
                if register:
                    registers.append(register)
        
        return Peripheral(name, description, base_address, registers)
    
    def _parse_register(self, register_elem: ET.Element) -> Optional[Register]:
        """Parse a single register from XML element."""
        name_elem = register_elem.find('name')
        if name_elem is None:
            return None
        
        name = name_elem.text.strip()
        
        # Get description
        desc_elem = register_elem.find('description')
        description = desc_elem.text.strip() if desc_elem is not None else ""
        
        # Get address offset
        offset_elem = register_elem.find('addressOffset')
        if offset_elem is None:
            return None
        address_offset = int(offset_elem.text, 0)
        
        # Get size (default to 32 bits)
        size_elem = register_elem.find('size')
        size = int(size_elem.text) // 8 if size_elem is not None else 4
        
        # Get access (default to read-write)
        access_elem = register_elem.find('access')
        access = access_elem.text if access_elem is not None else "read-write"
        
        # Get reset value (default to 0)
        reset_elem = register_elem.find('resetValue')
        reset_value = int(reset_elem.text, 0) if reset_elem is not None else 0
        
        # Parse bit fields
        bit_fields = []
        fields_elem = register_elem.find('fields')
        if fields_elem is not None:
            for field_elem in fields_elem.findall('field'):
                bit_field = self._parse_bit_field(field_elem)
                if bit_field:
                    bit_fields.append(bit_field)
        
        return Register(name, description, address_offset, size, access, reset_value, bit_fields)
    
    def _parse_bit_field(self, field_elem: ET.Element) -> Optional[BitField]:
        """Parse a single bit field from XML element."""
        name_elem = field_elem.find('name')
        if name_elem is None:
            return None
        
        name = name_elem.text.strip()
        
        # Get description
        desc_elem = field_elem.find('description')
        description = desc_elem.text.strip() if desc_elem is not None else ""
        
        # Get bit range
        bit_offset_elem = field_elem.find('bitOffset')
        bit_width_elem = field_elem.find('bitWidth')
        
        if bit_offset_elem is not None and bit_width_elem is not None:
            bit_offset = int(bit_offset_elem.text)
            bit_width = int(bit_width_elem.text)
        else:
            # Try alternative format with lsb/msb
            lsb_elem = field_elem.find('lsb')
            msb_elem = field_elem.find('msb')
            if lsb_elem is not None and msb_elem is not None:
                lsb = int(lsb_elem.text)
                msb = int(msb_elem.text)
                bit_offset = lsb
                bit_width = msb - lsb + 1
            else:
                return None
        
        # Get access
        access_elem = field_elem.find('access')
        access = access_elem.text if access_elem is not None else "read-write"
        
        return BitField(name, description, bit_offset, bit_width, access)


class CPPGenerator:
    """C++ code generator for registers and bit fields."""
    
    def __init__(self, peripherals: List[Peripheral], output_dir: str = "generated"):
        self.peripherals = peripherals
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def generate(self):
        """Generate C++ files for all peripherals."""
        for peripheral in self.peripherals:
            self._generate_peripheral_header(peripheral)
    
    def _generate_peripheral_header(self, peripheral: Peripheral):
        """Generate C++ header file for a peripheral."""
        header_filename = f"{peripheral.name.lower()}_regs.hpp"
        header_path = os.path.join(self.output_dir, header_filename)
        
        with open(header_path, 'w') as f:
            self._write_header_preamble(f, peripheral)
            self._write_register_structs(f, peripheral)
            self._write_peripheral_struct(f, peripheral)
            self._write_header_postamble(f, peripheral)
        
        print(f"Generated: {header_path}")
    
    def _write_header_preamble(self, f, peripheral: Peripheral):
        """Write header file preamble."""
        guard_name = f"{peripheral.name.upper()}_REGS_HPP"
        f.write(f"""#ifndef {guard_name}
#define {guard_name}

#include <cstdint>

/**
 * @file {peripheral.name.lower()}_regs.hpp
 * @brief {peripheral.description}
 * @details Generated from SVD file - DO NOT EDIT MANUALLY
 * 
 * Base Address: 0x{peripheral.base_address:08X}
 */

namespace {peripheral.name.lower()}_regs {{

""")
    
    def _write_register_structs(self, f, peripheral: Peripheral):
        """Write register structures with bit fields."""
        for register in peripheral.registers:
            # Write register comment
            f.write(f"""/**
 * @brief {register.description}
 * @details Offset: 0x{register.address_offset:04X}, Size: {register.size} bytes
 * @details Reset value: 0x{register.reset_value:08X}
 */\n""")
            
            # Write register union
            f.write(f"union {register.name}_t {{\n")
            
            # Raw value access
            if register.size == 1:
                f.write("    uint8_t raw;\n")
            elif register.size == 2:
                f.write("    uint16_t raw;\n")
            elif register.size == 4:
                f.write("    uint32_t raw;\n")
            elif register.size == 8:
                f.write("    uint64_t raw;\n")
            else:
                f.write(f"    uint8_t raw[{register.size}];\n")
            
            # Bit field struct
            if register.bit_fields:
                f.write("    struct {\n")
                
                # Sort bit fields by offset
                sorted_fields = sorted(register.bit_fields, key=lambda x: x.bit_offset)
                
                current_bit = 0
                for field in sorted_fields:
                    # Add padding if needed
                    if field.bit_offset > current_bit:
                        padding_bits = field.bit_offset - current_bit
                        f.write(f"        uint{register.size_bits}_t : {padding_bits};\n")
                    
                    # Write field comment
                    f.write(f"        /// {field.description}\n")
                    
                    # Write bit field
                    f.write(f"        uint{register.size_bits}_t {field.name} : {field.bit_width};\n")
                    
                    current_bit = field.bit_offset + field.bit_width
                
                # Add final padding if needed
                if current_bit < register.size_bits:
                    remaining_bits = register.size_bits - current_bit
                    f.write(f"        uint{register.size_bits}_t : {remaining_bits};\n")
                
                f.write("    } bits;\n")
            
            f.write("};\n\n")
    
    def _write_peripheral_struct(self, f, peripheral: Peripheral):
        """Write peripheral structure containing all registers."""
        f.write(f"""/**
 * @brief {peripheral.description} register block
 * @details Base address: 0x{peripheral.base_address:08X}
 */
struct {peripheral.name}_regs_t {{
""")
        
        # Sort registers by address offset
        sorted_registers = sorted(peripheral.registers, key=lambda x: x.address_offset)
        
        current_offset = 0
        for register in sorted_registers:
            # Add padding if needed
            if register.address_offset > current_offset:
                padding_bytes = register.address_offset - current_offset
                f.write(f"    uint8_t _reserved_{current_offset:04X}[{padding_bytes}];\n")
            
            # Write register
            f.write(f"    {register.name}_t {register.name};\n")
            current_offset = register.address_offset + register.size
        
        f.write("};\n\n")
        
        # Add memory-mapped pointer
        f.write(f"""// Memory-mapped peripheral instance
#define {peripheral.name}_REGS (reinterpret_cast<volatile {peripheral.name}_regs_t*>(0x{peripheral.base_address:08X}))

""")
    
    def _write_header_postamble(self, f, peripheral: Peripheral):
        """Write header file postamble."""
        f.write(f"""}} // namespace {peripheral.name.lower()}_regs

#endif // {peripheral.name.upper()}_REGS_HPP
""")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Convert SVD files to C++ register interfaces")
    parser.add_argument("svd_file", help="Path to SVD file")
    parser.add_argument("-o", "--output", default="generated", 
                       help="Output directory (default: generated)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.svd_file):
        print(f"Error: SVD file '{args.svd_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Parse SVD file
        print(f"Parsing SVD file: {args.svd_file}")
        svd_parser = SVDParser(args.svd_file)
        peripherals = svd_parser.parse()
        
        if not peripherals:
            print("Warning: No peripherals found in SVD file")
            return
        
        print(f"Found {len(peripherals)} peripheral(s)")
        if args.verbose:
            for peripheral in peripherals:
                print(f"  - {peripheral.name}: {len(peripheral.registers)} register(s)")
        
        # Generate C++ files
        print(f"Generating C++ files in: {args.output}")
        cpp_generator = CPPGenerator(peripherals, args.output)
        cpp_generator.generate()
        
        print("Generation complete!")
        
    except ET.ParseError as e:
        print(f"Error parsing SVD file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
