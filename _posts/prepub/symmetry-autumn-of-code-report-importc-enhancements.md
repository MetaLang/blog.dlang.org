---
title: "Symmetry Autumn of Code Report: ImportC Enhancements"
author: Emmanuel Nyarko

categories:
  - Symmetry Autumn of Code
  - Compilers & Tools
  - The Language
  - Code
  - Community
---

Having a central compiler that can compile code from other interoperable languages has long been one of D's major goals. And of course, that language is C. Over the years, D has adopted a powerful initiative to compile C code directly through ImportC, and several improvements were made during the 2025 term of Symmetry Autumn of Code. 

You can [read more on ImportC here](https://dlang.org/spec/importc.html).

The D programming community has engineered powerful compilers with very fast compile times. C has many libraries that are widely used in numerous systems. Considering D's edge in performance and safety, the ability to compile legacy C code enhances the ease of adoption in several domains. For example, a ticketing system written in C that has functioned for years cannot be easily rewritten in a modern programming language just to improve it. Not every development team is ready for that, considering the cost of re-engineering.

## Breaking Through Technical Barriers

### Complex numbers and s7 library support

Complex numbers are heavily used in control systems, signal processing, graphics, and scientific computing. C has been the language of choice for writing libraries used in high-performance DSP, embedded systems, and real-time signal pipelines. 

Historically, we had a hard time compiling C complex numbers from the frontend. It was even harder, sometimes impossible, to compile libraries with complex signatures, like the scientific **s7** library. There have been massive improvements in compiling such code, and we can now compile almost any C complex code. Below is a simple code snippet that now compiles successfully with D:

```c
#include <complex.h>
#include <stdio.h>
#include <assert.h>

struct com
{
    int r;
    int c;
};

void foo()
{
    struct com obj = { 1, 3 };
    _Complex double x = { obj.r, obj.c }; // real + im*i

    assert(creal(x) == 1.000000);
    assert(cimag(x) == 3.000000);
    return;
}

int main()
{
    foo();
    return 0;
}
```

## Deepening C99 support

### Designated Initializers

ImportC can now compile C's designated initializers. If you have tried compiling C code involving designated initializers in the past, you will have realized that nested struct initializers were not supported and caused compiler errors. This has been significantly improved and fixed.

```c
struct top
{
    int a;
    int b;
};

union t_union
{
    int f;
    int g;
};

struct Foo
{
    int x;
    int y;
    struct top f;
};

struct Bar
{
    struct Foo b;
    int arr[3];
    union t_union u;
};

struct Bar test = {
    .b.x = 5,
    .b.y = 7,
    .b.f = {8, 9},
    .arr[0] = 10,
    .arr[1] = 11,
    .u.f = 13
};
```
This is a simple snippet we can look at to the implementation of C struct designated initializers. As with C, you can go as deep as you want, and we will compile that for you while ensuring your struct members contain the desired data.

### Compound Literals

Taking the address of compound literals with ImportC did not compile before. This has been fixed, and compound literals can now be used as lvalues with ImportC.

```c
int *c = &(int){90};
```
This is an integer pointer referencing a temporary int initialized to 90. Rest assured that you will read 90 at the memory address pointed to by `c`.

### Function and Variable Redeclarations

Function redeclarations are permissible in a local scope in C. We now do a great job compiling such redeclarations without compiler errors. Also, extern variable redeclarations at global scope have been hardened. ImportC has greatly improved type checking for both global and local redeclarations.

```c
/* for variables */
extern int x;
extern char x

/* for function declarations */
int foo();
double foo();
```
Like in C, this is not permissible, and D has greatly improved to ensure these cases are checked.

### C Macros

Macros defined in C programs can now be imported from D. These can be easily passed as flags or function arguments, depending on your use case. While this hasn't always functioned well in the past, especially when imported and used in D code, significant improvements have been made. Beyond that, several builtin macros have also been implemented in the compiler.

## Builtins support, Backend, and Linking Wins

### GNU GCC CRC builtins

Most of the GNU GCC Cyclic Redundancy Check (CRC) builtins have been implemented. If any C function referencing them is used in D, we provide the necessary builtin implementation.

### DMD Backend Symbol duplication

Redeclaration of global variables was initially problematic, as it often led to symbol duplication in the symbol table, particularly in DMD. This has been fixed, allowing D to link against large-scale C libraries that rely on redundant global declarations across multiple headers.

### Static linking

We previously had a difficult time creating static libraries from C modules, especially those involving forward declarations. Work has been done toward this, and we can now successfully create static libraries from C modules.

```c
static void static_fun();

void lib_fun()
{
    static_fun();
}

static void static_fun()
{
}
```
You will need to pass the `-lib` command-line option when creating a static library. `dmd -lib file.c` now supports this workflow.

## Community Acknowledgement

This work was done through the 2025 Symmetry Autumn of Code. A big thank you to the D mentors, the D community, and Symmetry Investments for sponsoring this.
