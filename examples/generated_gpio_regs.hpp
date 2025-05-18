#ifndef GPIO_REGS_HPP
#define GPIO_REGS_HPP

#include <cstdint>

/**
 * @file gpio_regs.hpp
 * @brief General Purpose I/O
 * @details Generated from SVD file - DO NOT EDIT MANUALLY
 * 
 * Base Address: 0x40020000
 */

namespace gpio_regs {

/**
 * @brief GPIO Mode Register
 * @details Offset: 0x0000, Size: 4 bytes
 * @details Reset value: 0x00000000
 */
union MODE_t {
    uint32_t raw;
    struct {
        /// Pin 0 mode
        uint32_t MODE0 : 2;
        /// Pin 1 mode
        uint32_t MODE1 : 2;
        /// Pin 2 mode
        uint32_t MODE2 : 2;
        /// Pin 3 mode
        uint32_t MODE3 : 2;
        uint32_t : 24;
    } bits;
};

/**
 * @brief GPIO Input Data Register
 * @details Offset: 0x0010, Size: 4 bytes
 * @details Reset value: 0x00000000
 */
union IDR_t {
    uint32_t raw;
    struct {
        /// Pin 0 input
        uint32_t IDR0 : 1;
        /// Pin 1 input
        uint32_t IDR1 : 1;
        /// Pin 2 input
        uint32_t IDR2 : 1;
        /// Pin 3 input
        uint32_t IDR3 : 1;
        uint32_t : 28;
    } bits;
};

/**
 * @brief GPIO Output Data Register
 * @details Offset: 0x0014, Size: 4 bytes
 * @details Reset value: 0x00000000
 */
union ODR_t {
    uint32_t raw;
    struct {
        /// Pin 0 output
        uint32_t ODR0 : 1;
        /// Pin 1 output
        uint32_t ODR1 : 1;
        /// Pin 2 output
        uint32_t ODR2 : 1;
        /// Pin 3 output
        uint32_t ODR3 : 1;
        uint32_t : 28;
    } bits;
};

/**
 * @brief General Purpose I/O register block
 * @details Base address: 0x40020000
 */
struct GPIO_regs_t {
    MODE_t MODE;
    uint8_t _reserved_0004[12];
    IDR_t IDR;
    ODR_t ODR;
};

// Memory-mapped peripheral instance
#define GPIO_REGS (reinterpret_cast<volatile GPIO_regs_t*>(0x40020000))

} // namespace gpio_regs

#endif // GPIO_REGS_HPP
