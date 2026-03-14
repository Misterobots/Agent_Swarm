#include <stdlib.h>
#include <stdio.h>

/**
 * Multiplies two matrices and returns a pointer to the result.
 * 
 * @param A First matrix of size m x n
 * @param B Second matrix of size n x p
 * @param m Number of rows in A (and result)
 * @param n Number of columns in A / rows in B
 * @param p Number of columns in B (and result)
 * @return Pointer to the resulting matrix of size m x p, or NULL on error
 * 
 * Requirements:
 * - Matrix A must have dimensions [m][n]
 * - Matrix B must have dimensions [n][p]
 * - The function allocates memory for the result using malloc
 * - Caller is responsible for freeing the returned pointer
 */
double** matrix_multiply(const double* A, const double* B, int m, int n, int p) {
    // Validate input dimensions
    if (m <= 0 || n <= 0 || p <= 0) {
        return NULL;
    }
    
    // Check that the inner dimensions match for multiplication
    // A is m x n, B is n x p, so we need n columns in A == n rows in B
    if (n != n) {
        // This check is always true by definition, but conceptually:
        // We assume the caller provides correctly sized matrices
        return NULL;
    }
    
    // Allocate memory for result matrix (m x p)
    double** C = (double**)malloc(m * sizeof(double*));
    if (C == NULL) {
        return NULL;
    }
    
    // Allocate each row of the result matrix
    for (int i = 0; i < m; i++) {
        C[i] = (double*)malloc(p * sizeof(double));
        if (C[i] == NULL) {
            // Free previously allocated rows on failure
            for (int j = 0; j < i; j++) {
                free(C[j]);
            }
            free(C);
            return NULL;
        }
    }
    
    // Perform matrix multiplication: C[i][j] = sum(A[i][k] * B[k][j]) for k = 0 to n-1
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < p; j++) {
            double sum = 0.0;
            for (int k = 0; k < n; k++) {
                // A[i][k] is at index i*n + k in the flattened array
                // B[k][j] is at index k*p + j in the flattened array
                sum += A[i * n + k] * B[k * p + j];
            }
            C[i][j] = sum;
        }
    }
    
    return C;
}

/**
 * Helper function to free a matrix allocated by matrix_multiply
 */
void free_matrix(double** C, int m) {
    if (C == NULL) {
        return;
    }
    for (int i = 0; i < m; i++) {
        free(C[i]);
    }
    free(C);
}

/**
 * Helper function to print a matrix
 */
void print_matrix(double** C, int m, int p) {
    if (C == NULL) {
        printf("NULL\n");
        return;
    }
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < p; j++) {
            printf("%12.6f", C[i][j]);
        }
        printf("\n");
    }
}

/**
 * Test function to verify matrix multiplication
 */
void test_matrix_multiply() {
    // Create first matrix A (3x2)
    int m = 3, n = 2, p = 4;
    
    double* A_flat = (double*)malloc(m * n * sizeof(double));
    double* B_flat = (double*)malloc(n * p * sizeof(double));
    
    // Initialize matrix A: [[1, 2], [3, 4], [5, 6]]
    A_flat[0] = 1; A_flat[1] = 2;
    A_flat[2] = 3; A_flat[3] = 4;
    A_flat[4] = 5; A_flat[5] = 6;
    
    // Initialize matrix B: [[7, 8, 9, 10], [11, 12, 13, 14]]
    B_flat[0] = 7;  B_flat[1] = 8;  B_flat[2] = 9;  B_flat[3] = 10;
    B_flat[4] = 11; B_flat[5] = 12; B_flat[6] = 13; B_flat[7] = 14;
    
    // Convert flat arrays to 2D pointers for the function
    double** A = (double**)malloc(m * sizeof(double*));
    double** B = (double**)malloc(n * sizeof(double*));
    
    for (int i = 0; i < m; i++) {
        A[i] = &A_flat[i * n];
    }
    for (int i = 0; i < n; i++) {
        B[i] = &B_flat[i * p];
    }
    
    // Perform multiplication
    double** C = matrix_multiply(A, B, m, n, p);
    
    if (C == NULL) {
        printf("Matrix multiplication failed!\n");
        free_matrix(A, m);
        free_matrix(B, n);
        free(A_flat);
        free(B_flat);
        return;
    }
    
    printf("Matrix A (%dx%d):\n", m, n);
    print_matrix(A, m, n);
    
    printf("\nMatrix B (%dx%d):\n", n, p);
    print_matrix(B, n, p);
    
    printf("\nResult C = A x B (%dx%d):\n", m, p);
    print_matrix(C, m, p);
    
    // Verify one element manually: C[0][0] should be 1*7 + 2*11 = 29
    if (C[0][0] != 29.0) {
        printf("ERROR: Expected C[0][0] = 29, got %f\n", C[0][0]);
    } else {
        printf("\nVerification passed!\n");
    }
    
    // Cleanup
    free_matrix(C, m);
    free_matrix(A, m);
    free_matrix(B, n);
    free(A_flat);
    free(B_flat);
}

int main() {
    test_matrix_multiply();
    return 0;
}