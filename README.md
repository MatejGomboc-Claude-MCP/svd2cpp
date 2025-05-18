# SVD2CPP - ARM SVD to C++ Register Interface Generator

A Python3 parser that converts ARM SVD (System View Description) files into C++ register interfaces using union and bit field struct constructs.

## Features

- **Comprehensive SVD Parsing**: Supports standard ARM SVD file format
- **Union + Bit Field Generation**: Creates type-safe C++ interfaces with both raw and bit field access
- **Memory Layout Preservation**: Maintains proper register offsets and padding
- **Automatic Documentation**: Generates comments from SVD descriptions
- **Multiple Register Sizes**: Supports 8, 16, 32, and 64-bit registers
- **Namespace Isolation**: Each peripheral gets its own namespace to avoid conflicts

## Installation

Clone the repository:
```bash
git clone https://github.com/MatejGomboc-Claude-MCP/svd2cpp.git
cd svd2cpp
```

## Usage

### Basic Usage

```bash
python3 svd2cpp.py path/to/your/device.svd
```

### Advanced Usage

```bash
# Specify output directory
python3 svd2cpp.py device.svd -o output_folder

# Enable verbose output
python3 svd2cpp.py device.svd -v

# Help
python3 svd2cpp.py --help
```

## Generated Code Structure

For each peripheral, the generator creates:

1. **Register Union Types**: Each register becomes a union with:
   - `raw` member for direct access
   - `bits` struct for bit field access

2. **Peripheral Struct**: Contains all registers with proper memory layout

3. **Memory-Mapped Pointer**: Convenient macro for accessing the peripheral

### Example Generated Code

```cpp
#ifndef GPIO_REGS_HPP
#define GPIO_REGS_HPP

#include <cstdint>

namespace gpio_regs {

/**
 * @brief General Purpose I/O Control Register
 * @details Offset: 0x0000, Size: 4 bytes
 * @details Reset value: 0x00000000
 */
union CTRL_t {
    uint32_t raw;
    struct {
        /// Enable GPIO functionality
        uint32_t ENABLE : 1;
        /// GPIO direction (0=input, 1=output)
        uint32_t DIRECTION : 1;
        uint32_t : 6;
        /// Pull-up enable
        uint32_t PULLUP : 1;
        /// Pull-down enable  
        uint32_t PULLDOWN : 1;
        uint32_t : 22;
    } bits;
};

/**
 * @brief General Purpose I/O register block
 * @details Base address: 0x40020000
 */
struct GPIO_regs_t {
    CTRL_t CTRL;
    uint8_t _reserved_0004[12];
    DATA_t DATA;
};

// Memory-mapped peripheral instance
#define GPIO_REGS (reinterpret_cast<volatile GPIO_regs_t*>(0x40020000))

} // namespace gpio_regs

#endif // GPIO_REGS_HPP
```

### Usage in Code

```cpp
#include "gpio_regs.hpp"

void configure_gpio() {
    // Using bit fields
    GPIO_REGS->CTRL.bits.ENABLE = 1;
    GPIO_REGS->CTRL.bits.DIRECTION = 1;  // Output
    GPIO_REGS->CTRL.bits.PULLUP = 0;
    
    // Using raw access
    GPIO_REGS->DATA.raw = 0xFF;
    
    // Reading
    bool is_enabled = GPIO_REGS->CTRL.bits.ENABLE;
    uint32_t ctrl_value = GPIO_REGS->CTRL.raw;
}
```

## SVD File Requirements

The parser supports standard ARM SVD files with:
- `<peripheral>` elements with name, baseAddress, and registers
- `<register>` elements with name, addressOffset, size, and optional fields  
- `<field>` elements with name, bitOffset, bitWidth (or lsb/msb)
- Optional descriptions, access types, and reset values

## Project Structure

```
svd2cpp/
├── svd2cpp.py          # Main parser script
├── README.md           # This file  
├── examples/           # Example SVD files and generated output
├── tests/              # Unit tests
└── generated/          # Default output directory (created at runtime)
```

## Supported Features

### Register Features
- [x] 8, 16, 32, 64-bit registers
- [x] Register arrays (future enhancement)
- [x] Reset values
- [x] Access types (read-only, write-only, read-write)

### Bit Field Features  
- [x] Individual bit fields
- [x] Multi-bit fields
- [x] Automatic padding
- [x] Bit field descriptions
- [x] Access restrictions

### Code Generation Features
- [x] Type-safe unions
- [x] Memory layout preservation
- [x] Automatic documentation
- [x] Namespace isolation
- [x] Preprocessor guards

## Roadmap

- [ ] Register arrays support
- [ ] Enumerated values for bit fields
- [ ] Cluster support
- [ ] Custom templates
- [ ] Multiple output formats (JSON, YAML)
- [ ] Interrupt definitions
- [ ] Derived peripherals

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)  
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Requirements

- Python 3.6 or higher
- Standard library only (no external dependencies)

## Acknowledgments

- ARM for the SVD specification
- CMSIS project for SVD examples
- All contributors to this project
