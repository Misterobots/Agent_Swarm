#include <stdio.h>

// Function to multiply two integers
int multiply(int a, int b) {
    return a * b;
}

int main() {
    int num1 = 5;
    int num2 = 7;
    
    int result = multiply(num1, num2);
    
    printf("%d * %d = %d\n", num1, num2, result);
    
    return 0;
}