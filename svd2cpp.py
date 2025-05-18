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
import html
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class BitField:
    """Represents a bit field within a register."""
    name: str
    description: str
    bit_offset: int
    bit_width: int
    access: str = "read-write"
    
    def __post_init__(self):
        """Validate bit field parameters after initialization."""
        if self.bit_width <= 0:
            raise ValueError(f"Bit width must be positive: {self.bit_width}")
        if self.bit_offset < 0:
            raise ValueError(f"Bit offset must be non-negative: {self.bit_offset}")
    
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
    
    def __post_init__(self):
        """Validate register parameters after initialization."""
        if self.size <= 0:
            raise ValueError(f"Register size must be positive: {self.size}")
        if self.address_offset < 0:
            raise ValueError(f"Address offset must be non-negative: {self.address_offset}")
        if self.reset_value < 0:
            raise ValueError(f"Reset value must be non-negative: {self.reset_value}")
    
    @property
    def size_bits(self) -> int:
        """Register size in bits."""
        return self.size * 8
    
    @property
    def max_value(self) -> int:
        """Maximum value that can be stored in this register."""
        return (1 << self.size_bits) - 1


@dataclass
class Peripheral:
    """Represents a hardware peripheral containing registers."""
    name: str
    description: str
    base_address: int
    registers: List[Register]
    
    def __post_init__(self):
        """Validate peripheral parameters after initialization."""
        if not self.registers:
            raise ValueError("Peripheral must have at least one register")
        # Check for duplicate register names
        reg_names = [reg.name for reg in self.registers]
        duplicates = set([name for name in reg_names if reg_names.count(name) > 1])
        if duplicates:
            raise ValueError(f"Duplicate register names found: {duplicates}")


class SVDParser:
    """Parser for ARM SVD files."""
    
    def __init__(self, svd_file: str):
        self.svd_file = svd_file
        self.tree = ET.parse(svd_file)
        self.root = self.tree.getroot()
        self.peripherals: List[Peripheral] = []
        self.processed_peripheral_names: Set[str] = set()
    
    def _get_text_content(self, element: Optional[ET.Element]) -> str:
        """Safely get text content from an XML element, handle HTML entities."""
        if element is None or element.text is None:
            return ""
        # Handle HTML entities and normalize whitespace
        text = html.unescape(element.text.strip())
        # Replace multiple whitespace with single space
        return re.sub(r'\s+', ' ', text)
    
    def _try_parse_int(self, text: str, default: int = 0) -> int:
        """Safely parse integer from text with various formats."""
        if not text:
            return default
        text = text.strip()
        try:
            # Handle hexadecimal
            if text.lower().startswith('0x'):
                return int(text, 16)
            # Handle binary
            elif text.lower().startswith('0b'):
                return int(text, 2)
            # Handle octal (0 prefix but not 0x or 0b)
            elif text.startswith('0') and len(text) > 1 and text[1].isdigit():
                return int(text, 8)
            # Handle C-style suffixes (UL, LL, etc.)
            elif re.match(r'^[0-9]+[UuLl]*$', text):
                return int(re.sub(r'[UuLl]+$', '', text))
            # Handle regular decimal
            else:
                return int(text)
        except (ValueError, TypeError, OverflowError):
            print(f"Warning: Failed to parse integer '{text}', using default {default}")
            return default

    def _find_element_by_name(self, parent: ET.Element, names: List[str]) -> Optional[ET.Element]:
        """Find first element matching any of the given names."""
        for name in names:
            elem = parent.find(name)
            if elem is not None:
                return elem
        return None

    def _sanitize_xml_description(self, description: str) -> str:
        """Clean up XML description text for C++ comments."""
        if not description:
            return ""
        # Remove XML tags
        description = re.sub(r'<[^>]+>', ' ', description)
        # Handle common escape sequences
        description = description.replace('&lt;', '<').replace('&gt;', '>')
        description = description.replace('&amp;', '&').replace('&quot;', '"')
        # Normalize whitespace
        description = re.sub(r'\s+', ' ', description).strip()
        # Escape C++ comment sequences
        description = description.replace('*/', '* /')
        return description

    def parse(self) -> List[Peripheral]:
        """Parse the SVD file and extract peripherals."""
        self.peripherals = []
        self.processed_peripheral_names.clear()
        
        # Find all peripherals
        peripheral_elements = self.root.findall('.//peripheral')
        if not peripheral_elements:
            print("Warning: No peripheral elements found in SVD file")
            return []
        
        for peripheral_elem in peripheral_elements:
            try:
                peripheral = self._parse_peripheral(peripheral_elem)
                if peripheral and peripheral.registers:
                    self.peripherals.append(peripheral)
            except Exception as e:
                print(f"Warning: Failed to parse peripheral: {e}")
                continue
        
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
        
        # Check for duplicate peripheral names
        if name in self.processed_peripheral_names:
            print(f"Warning: Duplicate peripheral name '{name}', skipping")
            return None
        self.processed_peripheral_names.add(name)
        
        # Sanitize peripheral name for C++ (only alphanumeric and underscore)
        original_name = name
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Get description and clean it
        desc_elem = peripheral_elem.find('description')
        description = self._sanitize_xml_description(self._get_text_content(desc_elem))
        
        # Get base address (required)
        base_addr_elem = peripheral_elem.find('baseAddress')
        if base_addr_elem is None:
            print(f"Warning: No base address found for peripheral '{original_name}'")
            return None
        
        base_address_text = self._get_text_content(base_addr_elem)
        base_address = self._try_parse_int(base_address_text)
        
        # Validate base address
        if base_address < 0:
            print(f"Warning: Invalid base address for peripheral '{original_name}': {base_address_text}")
            return None
        
        # Parse registers
        registers = []
        processed_register_names: Set[str] = set()
        
        registers_elem = peripheral_elem.find('registers')
        if registers_elem is not None:
            for register_elem in registers_elem.findall('register'):
                try:
                    register = self._parse_register(register_elem, processed_register_names)
                    if register:
                        registers.append(register)
                        processed_register_names.add(register.name)
                except Exception as e:
                    print(f"Warning: Failed to parse register in peripheral '{name}': {e}")
                    continue
        
        if not registers:
            print(f"Warning: No valid registers found for peripheral '{name}'")
            return None
        
        # Sort registers by address offset for proper memory layout
        registers.sort(key=lambda r: r.address_offset)
        
        # Check for overlapping registers
        self._validate_register_layout(registers, name)
        
        return Peripheral(name, description, base_address, registers)
    
    def _validate_register_layout(self, registers: List[Register], peripheral_name: str):
        """Validate that registers don't overlap in memory."""
        for i in range(len(registers) - 1):
            current = registers[i]
            next_reg = registers[i + 1]
            
            current_end = current.address_offset + current.size
            if current_end > next_reg.address_offset:
                print(f"Warning: Overlapping registers in peripheral '{peripheral_name}': "
                      f"{current.name} (0x{current.address_offset:04X}-0x{current_end:04X}) "
                      f"overlaps with {next_reg.name} (0x{next_reg.address_offset:04X})")
    
    def _parse_register(self, register_elem: ET.Element, processed_names: Set[str]) -> Optional[Register]:
        """Parse a single register from XML element."""
        # Try both 'name' and 'n' tags for name
        name_elem = self._find_element_by_name(register_elem, ['name', 'n'])
        if name_elem is None:
            return None
        
        name = self._get_text_content(name_elem)
        if not name:
            return None
        
        # Check for duplicate register names
        if name in processed_names:
            print(f"Warning: Duplicate register name '{name}', skipping")
            return None
        
        # Sanitize register name for C++
        original_name = name
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Get description and clean it
        desc_elem = register_elem.find('description')
        description = self._sanitize_xml_description(self._get_text_content(desc_elem))
        
        # Get address offset (required)
        offset_elem = register_elem.find('addressOffset')
        if offset_elem is None:
            print(f"Warning: No address offset found for register '{original_name}'")
            return None
        
        offset_text = self._get_text_content(offset_elem)
        address_offset = self._try_parse_int(offset_text)
        
        if address_offset < 0:
            print(f"Warning: Invalid address offset for register '{original_name}': {offset_text}")
            return None
        
        # Get size in bits, default to 32 bits
        size_elem = register_elem.find('size')
        if size_elem is not None:
            size_bits = self._try_parse_int(self._get_text_content(size_elem), 32)
        else:
            size_bits = 32
        
        # Validate size
        if size_bits <= 0 or size_bits > 1024:  # Reasonable upper limit
            print(f"Warning: Invalid register size for '{original_name}': {size_bits} bits")
            size_bits = 32
        
        # Convert to bytes, ensuring minimum of 1 byte
        size = max(1, (size_bits + 7) // 8)
        
        # Get access (default to read-write)
        access_elem = register_elem.find('access')
        access = self._get_text_content(access_elem) if access_elem is not None else "read-write"
        
        # Validate access types
        valid_access = {"read-only", "write-only", "read-write", "writeOnce", "read-writeOnce"}
        if access not in valid_access:
            print(f"Warning: Unknown access type '{access}' for register '{original_name}', using 'read-write'")
            access = "read-write"
        
        # Get reset value (default to 0)
        reset_elem = register_elem.find('resetValue')
        reset_value = self._try_parse_int(self._get_text_content(reset_elem), 0)
        
        # Validate reset value fits in register
        max_value = (1 << size_bits) - 1
        if reset_value > max_value:
            print(f"Warning: Reset value 0x{reset_value:X} too large for register '{original_name}' "
                  f"({size_bits} bits), truncating")
            reset_value &= max_value
        
        # Parse bit fields
        bit_fields = []
        processed_field_names: Set[str] = set()
        
        fields_elem = register_elem.find('fields')
        if fields_elem is not None:
            for field_elem in fields_elem.findall('field'):
                try:
                    bit_field = self._parse_bit_field(field_elem, size_bits, processed_field_names)
                    if bit_field:
                        bit_fields.append(bit_field)
                        processed_field_names.add(bit_field.name)
                except Exception as e:
                    print(f"Warning: Failed to parse bit field in register '{name}': {e}")
                    continue
        
        # Sort bit fields by offset and validate they don't overlap
        bit_fields.sort(key=lambda f: f.bit_offset)
        validated_fields = self._validate_bit_fields(bit_fields, size_bits, name)
        
        return Register(name, description, address_offset, size, access, reset_value, validated_fields)
    
    def _parse_bit_field(self, field_elem: ET.Element, register_size_bits: int, processed_names: Set[str]) -> Optional[BitField]:
        """Parse a single bit field from XML element."""
        # Try both 'name' and 'n' tags for name
        name_elem = self._find_element_by_name(field_elem, ['name', 'n'])
        if name_elem is None:
            return None
        
        name = self._get_text_content(name_elem)
        if not name:
            return None
        
        # Check for duplicate field names
        if name in processed_names:
            print(f"Warning: Duplicate bit field name '{name}', skipping")
            return None
        
        # Sanitize field name for C++
        original_name = name
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Get description and clean it
        desc_elem = field_elem.find('description')
        description = self._sanitize_xml_description(self._get_text_content(desc_elem))
        
        # Get bit range - try multiple formats
        bit_offset = None
        bit_width = None
        
        # Method 1: bitOffset + bitWidth
        bit_offset_elem = field_elem.find('bitOffset')
        bit_width_elem = field_elem.find('bitWidth')
        
        if bit_offset_elem is not None and bit_width_elem is not None:
            bit_offset = self._try_parse_int(self._get_text_content(bit_offset_elem))
            bit_width = self._try_parse_int(self._get_text_content(bit_width_elem))
        else:
            # Method 2: lsb + msb
            lsb_elem = field_elem.find('lsb')
            msb_elem = field_elem.find('msb')
            if lsb_elem is not None and msb_elem is not None:
                lsb = self._try_parse_int(self._get_text_content(lsb_elem))
                msb = self._try_parse_int(self._get_text_content(msb_elem))
                if msb >= lsb:
                    bit_offset = lsb
                    bit_width = msb - lsb + 1
            else:
                # Method 3: bitRange format (e.g., "[7:0]" or "[31]")
                bit_range_elem = field_elem.find('bitRange')
                if bit_range_elem is not None:
                    bit_range_text = self._get_text_content(bit_range_elem)
                    # Try [msb:lsb] format
                    match = re.match(r'\[(\d+):(\d+)\]', bit_range_text)
                    if match:
                        msb = int(match.group(1))
                        lsb = int(match.group(2))
                        if msb >= lsb:
                            bit_offset = lsb
                            bit_width = msb - lsb + 1
                    else:
                        # Try [bit] format (single bit)
                        match = re.match(r'\[(\d+)\]', bit_range_text)
                        if match:
                            bit_offset = int(match.group(1))
                            bit_width = 1
        
        # Validate bit field bounds
        if bit_offset is None or bit_width is None:
            print(f"Warning: Could not determine bit range for field '{original_name}'")
            return None
        
        if bit_offset < 0 or bit_width <= 0:
            print(f"Warning: Invalid bit range for field '{original_name}': offset={bit_offset}, width={bit_width}")
            return None
        
        if bit_offset + bit_width > register_size_bits:
            print(f"Warning: Bit field '{original_name}' extends beyond register size "
                  f"(offset={bit_offset}, width={bit_width}, register_size={register_size_bits})")
            return None
        
        # Get access
        access_elem = field_elem.find('access')
        access = self._get_text_content(access_elem) if access_elem is not None else "read-write"
        
        # Validate access types
        valid_access = {"read-only", "write-only", "read-write", "writeOnce", "read-writeOnce"}
        if access not in valid_access:
            print(f"Warning: Unknown access type '{access}' for field '{original_name}', using 'read-write'")
            access = "read-write"
        
        return BitField(name, description, bit_offset, bit_width, access)

    def _validate_bit_fields(self, bit_fields: List[BitField], register_size_bits: int, register_name: str) -> List[BitField]:
        """Validate bit fields don't overlap and are within register bounds."""
        if not bit_fields:
            return []
        
        validated = []
        for field in bit_fields:
            # Check if field fits in register
            if field.bit_offset + field.bit_width > register_size_bits:
                print(f"Warning: Bit field '{field.name}' in register '{register_name}' "
                      f"extends beyond register size, skipping")
                continue
            
            # Check for overlap with previous fields
            overlap = False
            for prev_field in validated:
                # Two fields overlap if neither is completely before the other
                if not (field.bit_offset > prev_field.end_bit or field.end_bit < prev_field.bit_offset):
                    print(f"Warning: Bit field '{field.name}' overlaps with '{prev_field.name}' "
                          f"in register '{register_name}', skipping")
                    overlap = True
                    break
            
            if not overlap:
                validated.append(field)
        
        return validated


class CPPGenerator:
    """C++ code generator for registers and bit fields."""
    
    # C++ keywords that cannot be used as identifiers
    CPP_KEYWORDS = {
        'alignas', 'alignof', 'and', 'and_eq', 'asm', 'auto', 'bitand', 'bitor', 
        'bool', 'break', 'case', 'catch', 'char', 'char16_t', 'char32_t', 'class', 
        'compl', 'concept', 'const', 'constexpr', 'const_cast', 'continue', 'co_await',
        'co_return', 'co_yield', 'decltype', 'default', 'delete', 'do', 'double', 
        'dynamic_cast', 'else', 'enum', 'explicit', 'export', 'extern', 'false', 
        'float', 'for', 'friend', 'goto', 'if', 'inline', 'int', 'long', 'mutable', 
        'namespace', 'new', 'noexcept', 'not', 'not_eq', 'nullptr', 'operator', 'or', 
        'or_eq', 'private', 'protected', 'public', 'register', 'reinterpret_cast', 
        'requires', 'return', 'short', 'signed', 'sizeof', 'static', 'static_assert', 
        'static_cast', 'struct', 'switch', 'template', 'this', 'thread_local', 'throw', 
        'true', 'try', 'typedef', 'typeid', 'typename', 'union', 'unsigned', 'using', 
        'virtual', 'void', 'volatile', 'wchar_t', 'while', 'xor', 'xor_eq'
    }
    
    def __init__(self, peripherals: List[Peripheral], output_dir: str = "generated"):
        self.peripherals = peripherals
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Cannot create output directory '{output_dir}': {e}")
    
    def _sanitize_identifier(self, name: str) -> str:
        """Sanitize identifier for C++ (ensure it's valid and not a keyword)."""
        if not name:
            return '_unnamed'
        
        # Remove invalid characters
        name = re.sub(r'[^A-Za-z0-9_]', '_', name)
        
        # Ensure it starts with letter or underscore
        if name and name[0].isdigit():
            name = '_' + name
        
        # Handle empty names
        if not name:
            name = '_unnamed'
        
        # Check for C++ keywords
        if name.lower() in self.CPP_KEYWORDS:
            name = name + '_'
        
        # Avoid names starting with underscore followed by capital letter
        # (reserved for implementation)
        if len(name) > 1 and name[0] == '_' and name[1].isupper():
            name = 'reg_' + name[1:]
        
        return name
    
    def _get_cpp_integer_type(self, size_bits: int) -> str:
        """Get appropriate C++ integer type for given bit size."""
        if size_bits <= 0:
            return "uint8_t"
        elif size_bits <= 8:
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
    
    def _escape_cpp_comment(self, text: str) -> str:
        """Escape text for safe inclusion in C++ comments."""
        if not text:
            return ""
        # Replace */ with * / to avoid closing comments early
        text = text.replace('*/', '* /')
        # Remove line breaks for single-line comments
        text = text.replace('\n', ' ').replace('\r', ' ')
        # Limit length to avoid extremely long comments
        if len(text) > 200:
            text = text[:197] + "..."
        return text
    
    def generate(self):
        """Generate C++ files for all peripherals."""
        if not self.peripherals:
            print("Warning: No peripherals to generate")
            return
        
        generated_files = []
        for peripheral in self.peripherals:
            try:
                file_path = self._generate_peripheral_header(peripheral)
                if file_path:
                    generated_files.append(file_path)
            except Exception as e:
                print(f"Error generating header for peripheral '{peripheral.name}': {e}")
                continue
        
        if generated_files:
            print(f"Successfully generated {len(generated_files)} header file(s)")
        else:
            print("Warning: No header files were generated")
    
    def _generate_peripheral_header(self, peripheral: Peripheral) -> Optional[str]:
        """Generate C++ header file for a peripheral."""
        safe_name = self._sanitize_identifier(peripheral.name.lower())
        header_filename = f"{safe_name}_regs.hpp"
        header_path = os.path.join(self.output_dir, header_filename)
        
        try:
            with open(header_path, 'w', encoding='utf-8') as f:
                self._write_header_preamble(f, peripheral)
                self._write_register_structs(f, peripheral)
                self._write_peripheral_struct(f, peripheral)
                self._write_header_postamble(f, peripheral)
            
            print(f"Generated: {header_path}")
            return header_path
        except (IOError, OSError) as e:
            print(f"Error writing to {header_path}: {e}")
            return None
    
    def _write_header_preamble(self, f, peripheral: Peripheral):
        """Write header file preamble."""
        safe_name = self._sanitize_identifier(peripheral.name.upper())
        guard_name = f"{safe_name}_REGS_HPP"
        namespace_name = self._sanitize_identifier(peripheral.name.lower())
        
        # Escape description for comment
        safe_description = self._escape_cpp_comment(peripheral.description)
        
        f.write(f"""#ifndef {guard_name}
#define {guard_name}

#include <cstdint>

/**
 * @file {namespace_name}_regs.hpp
 * @brief {safe_description}
 * @details Generated from SVD file - DO NOT EDIT MANUALLY
 * 
 * Base Address: 0x{peripheral.base_address:08X}
 */

namespace {namespace_name}_regs {{

""")
    
    def _write_register_structs(self, f, peripheral: Peripheral):
        """Write register structures with bit fields."""
        for register in peripheral.registers:
            # Sanitize register name
            safe_reg_name = self._sanitize_identifier(register.name)
            
            # Escape description for comment
            safe_description = self._escape_cpp_comment(register.description)
            
            # Write register comment with comprehensive information
            f.write(f"""/**
 * @brief {safe_description}
 * @details Offset: 0x{register.address_offset:04X}, Size: {register.size} bytes ({register.size_bits} bits)
 * @details Reset value: 0x{register.reset_value:0{register.size*2}X}
 * @details Access: {register.access}
 */
""")
            
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
                
                for field in sorted_fields:
                    # Add padding if needed
                    if field.bit_offset > current_bit:
                        padding_bits = field.bit_offset - current_bit
                        f.write(f"        {self._get_cpp_integer_type(size_bits)} : {padding_bits};\n")
                    
                    # Write field comment if available
                    if field.description:
                        safe_field_desc = self._escape_cpp_comment(field.description)
                        f.write(f"        /// {safe_field_desc} (bits {field.bit_offset}:{field.end_bit})\n")
                    
                    # Sanitize field name
                    safe_field_name = self._sanitize_identifier(field.name)
                    
                    # Write bit field with access comment
                    if field.access != "read-write":
                        f.write(f"        {self._get_cpp_integer_type(size_bits)} {safe_field_name} : {field.bit_width}; // {field.access}\n")
                    else:
                        f.write(f"        {self._get_cpp_integer_type(size_bits)} {safe_field_name} : {field.bit_width};\n")
                    
                    current_bit = field.bit_offset + field.bit_width
                
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
        safe_description = self._escape_cpp_comment(peripheral.description)
        
        f.write(f"""/**
 * @brief {safe_description} register block
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
            elif register.address_offset < current_offset:
                # Warn about overlapping registers
                print(f"Warning: Register {register.name} overlaps previous registers at offset 0x{register.address_offset:04X}")
            
            # Write register
            safe_reg_name = self._sanitize_identifier(register.name)
            f.write(f"    volatile {safe_reg_name}_t {safe_reg_name};\n")
            current_offset = register.address_offset + register.size
        
        f.write("};\n\n")
        
        # Add static assert for minimum size (actual size may be larger due to alignment)
        f.write(f"static_assert(sizeof({safe_peripheral_name}_regs_t) >= {current_offset}, "
                f"\"Size mismatch for {safe_peripheral_name}_regs_t\");\n\n")
        
        # Add memory-mapped pointer with proper volatile qualifier
        f.write(f"""// Memory-mapped peripheral instance
#define {safe_peripheral_name}_REGS \\
    (reinterpret_cast<volatile {safe_peripheral_name}_regs_t*>(0x{peripheral.base_address:08X}UL))

""")
    
    def _write_header_postamble(self, f, peripheral: Peripheral):
        """Write header file postamble."""
        safe_name = self._sanitize_identifier(peripheral.name.upper())
        namespace_name = self._sanitize_identifier(peripheral.name.lower())
        
        f.write(f"""}} // namespace {namespace_name}_regs

#endif // {safe_name}_REGS_HPP
""")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Convert SVD files to C++ register interfaces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s device.svd                    # Generate in ./generated/
  %(prog)s device.svd -o my_output/      # Generate in ./my_output/
  %(prog)s device.svd -v                 # Verbose output
"""
    )
    parser.add_argument("svd_file", help="Path to SVD file")
    parser.add_argument("-o", "--output", default="generated", 
                       help="Output directory (default: generated)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--version", action="version", version="SVD2CPP 1.0.0")
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.svd_file):
        print(f"Error: SVD file '{args.svd_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isfile(args.svd_file):
        print(f"Error: '{args.svd_file}' is not a regular file", file=sys.stderr)
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
            if args.verbose:
                print("This could be due to:")
                print("- Invalid SVD format")
                print("- No peripheral elements in the file")
                print("- All peripherals failed validation")
            return
        
        print(f"Found {len(peripherals)} valid peripheral(s)")
        
        if args.verbose:
            for peripheral in peripherals:
                print(f"  - {peripheral.name}: {len(peripheral.registers)} register(s) at 0x{peripheral.base_address:08X}")
                for register in peripheral.registers:
                    print(f"    - {register.name}: {len(register.bit_fields)} bit field(s) "
                          f"(size: {register.size} bytes, access: {register.access})")
        
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
    except FileNotFoundError as e:
        print(f"File not found error: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"Permission error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
