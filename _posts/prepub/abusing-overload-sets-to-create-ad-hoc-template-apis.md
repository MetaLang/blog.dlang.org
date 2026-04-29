
---
title: (Ab)using Overload Sets to Create Ad-Hoc Template APIs
author: Michael Boston

categories:
  - Templates
  - Metaprogramming
  - The Language
  - Community
  - Guest Posts
  - Tutorials
---

Overload sets are a "term of art", seemingly arising from reusing overload rules over the years. They quietly power a lot of D's generic programming—and once you understand them explicitly, a whole class of API design opens up.

```d
import std;

void bar(int)   { "int".writeln;   }
void bar(float) { "float".writeln; }
void bar(bool)  { "bool".writeln;  }

void useIt(alias F)() {
    F(1);      // prints "int"
    F(13.37);  // prints "float"  
    F(true);   // prints "bool"
}

unittest { useIt!bar; }

```

What exactly is `bar` when passed to `useIt`? Wait, does it *survive* as `useIt.F`? (yes, compiles as is)

## What Are Overload Sets?

The specification:

```
Functions declared at the same scope overload against each
other, and are called an *Overload Set*.
```

And from the alias section:

```
Aliases can also 'import' a set of overloaded functions, that can
be overloaded with functions in the current scope
```

The behavior of overload sets is scattered across the spec. A few sentences here, a few more tucked away in the template section. Template specialization lets you pattern-match against the whole set—pick the right implementation based on compile-time arguments.

Overload sets can work with several very different things, I use the following definition:

    An overload set is a collection of things that share a name and a closely related template header.

You may not know everything that can be templatized, and real-world template usage is extremely concerned about making only one declaration match at a time.

## Specialization on Integer Values

```d
alias typeAt(int I : 0) = int;
alias typeAt(int I : 1) = float;
alias typeAt(int I : 2) = string;
enum typeAtLength = Length!typeAt;

template Length(alias A, int acc=0){ // returns the pseudo-length of an overloadset
    static if( ! __traits(compiles,A!acc) ){
        enum Length=acc;
    } else {
        enum Length=Length!(A,acc+1);
    }
}

static foreach (i; 0 .. typeAtLength) {
    pragma(msg, typeAt!i.stringof);
}
// prints: int, float, string
```

By treating `value` specialization of ints as an "array", you can make an overload set that is foreachable. You can build compile-time lookup tables, generate code for each type in the set, and dispatch based on integer constants, etc.

## Real-World Pattern: Unified Vector Interface

In [Kap's joka library](https://github.com/Kapendev/joka/blob/main/source/joka/math.d "null"), `GVec2`, `GVec3`, `GVec4` are all parameterized by type, but what if I want dimension-generic code?

It's an incomplete templatization:

```d
// Separate types for each dimension
alias BVec2 = GVec2!byte;
alias IVec2 = GVec2!int;
// ... more aliases

struct GVec2(T) { T x, y; }
struct GVec3(T) { T x, y, z; }
struct GVec4(T) { T x, y, z, w; }
```

You can't write "works on any N-dimensional vector"; the dimension is stuck in the type name. To specialize on dimension, you can expand the shared template header to include an int parameter.

```d
alias GVec2(T = float) = GVec!(2, T); // (optional, allows backwards compatibility)
alias GVec3(T = float) = GVec!(3, T);
alias GVec4(T = float) = GVec!(4, T);

// struct GVec(int N, T); // implicit, no primary definition exists

struct GVec(int N : 2, T) { T x = 0; T y = 0; }
struct GVec(int N : 3, T) { T x = 0; T y = 0; T z = 0; }
struct GVec(int N : 4, T) { T x = 0; T y = 0; T z = 0; T w = 0; }
```

Now you can write functions that take `GVec!(N, T)` and work across any dimension. Pattern-matching on `N` at compile time allows you to easily access `N` in trivial meta-code:

```d
void print(int N, T)(GVec!(N, T) v) {
    import std;
    writeln("Vector of dimension ", N, " with type ", T.stringof);
    static foreach (c; "xyzw"[0 .. N]) {
        writeln(c, ": ", mixin("v." ~ c));
    }
}

unittest {
    IVec3(1, 4, 7).print;
    DVec4(2, 6, 0, 0).print;
}
```

### The Ad-hoc Template API

This is an **Ad-hoc Template API**. Note that no primary `struct GVec(int N, T)` exists in the source code. The symbol `GVec` exists only as a collection of specializations. The API is a coordinate map of successful matches. You are programming against the existence of a match in the resolution logic rather than a central definition.

    The API that can be named is not the immortal API. -monkyyy-tzu



## Swapping an Overload Set

`std.conv.to` is an overload set with the implied syntax of `.to!T`; you can let users pass their own instead for serialization.

```d
template someSerializeFunc(alias TO_ = void, Args...)(Args args) {
    static if (is(TO_ == void)) {
        import std.conv;
        alias TO = std.conv.to; // Successful partial symbol resolution
    } else {
        alias TO = TO_;
    }
    // ... use args with .TO!T for conversions
}

```

This code uses the default `std.conv.to` unless the user provides their own. So long as the user matches the ad-hoc API of `to`, they can extend it (and fix its edge cases). This flexible API, with an overloadable-overload-set, lets users fix behavior. 

## Shared Header Mechanics

```d
enum foo(int I : 0) = 0;
int foo(int I : 1)(int) => 1;
template foo(int I : 2) {
    int foo = 2;
}
struct foo(int I : 3) {
    int myint = 3;
}

```

The overload set resolution and specialization mechanisms work on all types of templates in D. The compiler only cares about something matching the template header; you can define it however you want and make ad-hoc APIs.

With `type` and `value` specialization shared across at least four declaration patterns, which of your problems could be approached by asking: "How can I define a good template header"?

## Conclusion

Overload sets aren't exotic. Combine them with template specialization and you get ad-hoc APIs that support multiple access patterns without duplicating code. Build your types to play nice with meta-programs, design your APIs to take overload sets, and let users swap in their own implementations. This works even for more complex APIs such as `std.conv.to`.

---
Based on 2 chapters from my "book" ["Black Magic in D"](https://crazymonkyyy.github.io/blackmagic-in-d/).

https://crazymonkyyy.github.io/

