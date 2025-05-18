#include "gpio_regs.hpp"
#include "uart_regs.hpp"

/**
 * Example usage of generated register interfaces
 */

void gpio_example() {
    // Configure GPIO pins as outputs
    GPIO_REGS->MODE.bits.MODE0 = 0b01;  // Output
    GPIO_REGS->MODE.bits.MODE1 = 0b01;  // Output
    GPIO_REGS->MODE.bits.MODE2 = 0b00;  // Input
    GPIO_REGS->MODE.bits.MODE3 = 0b00;  // Input
    
    // Set output pins
    GPIO_REGS->ODR.bits.ODR0 = 1;
    GPIO_REGS->ODR.bits.ODR1 = 0;
    
    // Read input pins
    bool pin2_state = GPIO_REGS->IDR.bits.IDR2;
    bool pin3_state = GPIO_REGS->IDR.bits.IDR3;
    
    // Raw register access
    uint32_t mode_register = GPIO_REGS->MODE.raw;
    GPIO_REGS->ODR.raw = 0x03;  // Set pins 0 and 1
}

void uart_example() {
    // Configure UART
    UART_REGS->CR1.bits.UE = 1;   // Enable UART
    UART_REGS->CR1.bits.TE = 1;   // Enable transmitter
    UART_REGS->CR1.bits.RE = 1;   // Enable receiver
    UART_REGS->CR1.bits.M = 0;    // 8-bit word length
    UART_REGS->CR1.bits.PCE = 0;  // No parity
    
    // Send data
    void send_byte(uint8_t data) {
        // Wait for TX empty
        while (!UART_REGS->SR.bits.TXE);
        
        // Send data
        UART_REGS->DR.bits.DR = data;
    }
    
    // Receive data
    uint8_t receive_byte() {
        // Wait for data available
        while (!UART_REGS->SR.bits.RXNE);
        
        // Read data
        return UART_REGS->DR.bits.DR & 0xFF;
    }
    
    // Check for errors
    bool check_overrun_error() {
        return UART_REGS->SR.bits.ORE;
    }
}

int main() {
    gpio_example();
    uart_example();
    return 0;
}